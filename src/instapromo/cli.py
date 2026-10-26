from __future__ import annotations

import argparse
import logging
from datetime import datetime
from pathlib import Path

from .config import Settings, require
from .models import PostDraft, full_caption


def cmd_generate(args: argparse.Namespace, settings: Settings) -> None:
    from .copywriter import generate_posts
    from .images.renderer import SlideRenderer
    from .pipeline import build_post, new_post_dir, recent_themes
    from .product import fetch_page_text, load_product

    product = load_product(args.product)
    page_text = None
    if product.url and not args.no_fetch:
        print(f"페이지 읽는 중: {product.url}")
        try:
            page_text = fetch_page_text(product.url)
        except Exception as e:
            print(f"  ⚠ 페이지를 읽지 못해 YAML 정보만 사용합니다: {e}")

    print(f"Claude로 게시물 {args.count}개 기획 중...")
    posts = generate_posts(
        product,
        model=settings.anthropic_model,
        count=args.count,
        page_text=page_text,
        recent_themes=recent_themes(settings.output_dir, product.name),
    )

    image_provider = None
    if not args.no_images:
        from .images.gemini import GeminiImageProvider
        image_provider = GeminiImageProvider(require(settings.gemini_api_key, "GEMINI_API_KEY"),
                                             model=settings.gemini_image_model)

    with SlideRenderer(settings.chromium_executable) as renderer:
        for n, post in enumerate(posts, start=1):
            out_dir = new_post_dir(settings.output_dir, product, n)
            print(f"[{n}/{len(posts)}] {post.theme} - 슬라이드 {len(post.slides)}장 생성 중...")
            record = build_post(post, product, out_dir, renderer=renderer, image_provider=image_provider)
            print(f"  → {out_dir}")
            for w in record["warnings"]:
                print(f"  ⚠ {w}")
    print("\n검토 후 `instapromo approve <폴더>` 로 승인하고 `instapromo publish <폴더>` 로 올리세요.")


def cmd_show(args: argparse.Namespace, settings: Settings) -> None:
    from .pipeline import read_record

    record = read_record(Path(args.post_dir))
    post = PostDraft.model_validate(record["post"])
    print(f"상태: {record['status']}   주제: {post.theme}")
    for name, s in zip(record["slides"], post.slides):
        print(f"  {name} [{s.layout}] {s.headline} / {s.body}")
    print("\n" + full_caption(post))
    for w in record.get("warnings", []):
        print(f"⚠ {w}")


def cmd_approve(args: argparse.Namespace, settings: Settings) -> None:
    from .pipeline import read_record, write_record

    post_dir = Path(args.post_dir)
    record = read_record(post_dir)
    if record["status"] == "published":
        raise SystemExit("이미 게시된 게시물입니다.")
    # caption.txt 를 직접 고쳤다면 그 내용을 최종 캡션으로 사용
    record["final_caption"] = (post_dir / "caption.txt").read_text(encoding="utf-8").strip()
    record["status"] = "approved"
    write_record(post_dir, record)
    print(f"승인됨: {post_dir}")


def _publisher(settings: Settings):
    from .publisher import InstagramPublisher

    return InstagramPublisher(require(settings.ig_user_id, "IG_USER_ID"),
                              require(settings.ig_access_token, "IG_ACCESS_TOKEN"),
                              settings.ig_api_version)


def cmd_publish(args: argparse.Namespace, settings: Settings) -> None:
    from .pipeline import read_record, write_record
    from .storage import S3Storage

    post_dir = Path(args.post_dir)
    record = read_record(post_dir)
    if record["status"] == "published":
        raise SystemExit(f"이미 게시됨: {record.get('permalink')}")
    if record["status"] != "approved":
        raise SystemExit("승인되지 않은 게시물입니다. 먼저 `instapromo approve` 를 실행하세요.")
    caption = record["final_caption"]
    files = [post_dir / name for name in record["slides"]]

    if args.dry_run:
        print("[dry-run] 업로드할 파일:", *[f"  {f}" for f in files], sep="\n")
        print("[dry-run] 캡션:\n" + caption)
        return

    publisher = _publisher(settings)
    quota = publisher.publishing_quota()
    total = quota.get("config", {}).get("quota_total")
    if total is not None and quota.get("quota_usage", 0) >= total:
        raise SystemExit(f"24시간 게시 한도({total})에 도달했습니다. 나중에 다시 시도하세요.")

    storage = S3Storage(
        bucket=require(settings.s3_bucket, "S3_BUCKET"),
        public_base_url=require(settings.s3_public_base_url, "S3_PUBLIC_BASE_URL"),
        endpoint_url=settings.s3_endpoint_url,
        access_key_id=settings.s3_access_key_id,
        secret_access_key=settings.s3_secret_access_key,
    )
    urls = [storage.upload(f, f"instapromo/{post_dir.name}/{f.name}") for f in files]
    print(f"이미지 {len(urls)}장 업로드 완료, Instagram 게시 중...")

    media_id = publisher.publish(urls, caption)
    record.update(status="published", ig_media_id=media_id,
                  permalink=publisher.permalink(media_id),
                  published_at=datetime.now().isoformat(timespec="seconds"))
    write_record(post_dir, record)
    print(f"게시 완료: {record['permalink'] or media_id}")


def cmd_quota(args: argparse.Namespace, settings: Settings) -> None:
    quota = _publisher(settings).publishing_quota()
    print(f"최근 24시간 게시 수: {quota.get('quota_usage')} / {quota.get('config', {}).get('quota_total')}")


def cmd_refresh_token(args: argparse.Namespace, settings: Settings) -> None:
    data = _publisher(settings).refresh_token()
    days = int(data.get("expires_in", 0)) // 86400
    print(f"새 토큰 (약 {days}일 유효). .env 의 IG_ACCESS_TOKEN 을 교체하세요:\n{data['access_token']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="instapromo", description="Instagram 홍보 피드 자동화")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("generate", help="제품 설명으로 게시물(캡션+이미지) 생성")
    p.add_argument("--product", required=True, help="제품 YAML 파일 경로")
    p.add_argument("--count", type=int, default=1, help="생성할 게시물 수")
    p.add_argument("--no-images", action="store_true", help="AI 배경 없이 브랜드 그라데이션만 사용")
    p.add_argument("--no-fetch", action="store_true", help="제품 URL 페이지를 읽지 않음")
    p.set_defaults(func=cmd_generate)

    for name, func, help_ in [("show", cmd_show, "게시물 내용 보기"),
                              ("approve", cmd_approve, "게시물 승인 (caption.txt 수정 내용 반영)")]:
        p = sub.add_parser(name, help=help_)
        p.add_argument("post_dir")
        p.set_defaults(func=func)

    p = sub.add_parser("publish", help="승인된 게시물을 Instagram에 업로드")
    p.add_argument("post_dir")
    p.add_argument("--dry-run", action="store_true", help="실제 업로드 없이 확인만")
    p.set_defaults(func=cmd_publish)

    sub.add_parser("quota", help="24시간 게시 한도 확인").set_defaults(func=cmd_quota)
    sub.add_parser("refresh-token", help="장기 액세스 토큰 갱신").set_defaults(func=cmd_refresh_token)
    return parser


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    args = build_parser().parse_args(argv)
    args.func(args, Settings.from_env())


if __name__ == "__main__":
    main()
