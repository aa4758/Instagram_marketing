from __future__ import annotations

import argparse
import logging
from pathlib import Path

from . import service
from .config import MissingSettingError, Settings, settings_path
from .models import PostDraft, full_caption


def cmd_generate(args: argparse.Namespace, settings: Settings) -> None:
    from .product import load_product

    product = load_product(args.product)
    if args.github:
        product.github = args.github
    service.generate(product, settings, count=args.count, use_images=not args.no_images,
                     fetch_sources=not args.no_fetch)
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
    # caption.txt 를 직접 고쳤다면 그 내용을 최종 캡션으로 사용
    service.approve(Path(args.post_dir))
    print(f"승인됨: {args.post_dir}")


def cmd_publish(args: argparse.Namespace, settings: Settings) -> None:
    service.publish(Path(args.post_dir), settings, dry_run=args.dry_run)


def cmd_quota(args: argparse.Namespace, settings: Settings) -> None:
    used, total = service.quota(settings)
    print(f"최근 24시간 게시 수: {used} / {total}")


def cmd_refresh_token(args: argparse.Namespace, settings: Settings) -> None:
    days = service.refresh_token(settings)
    print(f"토큰을 갱신해 {settings_path()} 에 저장했습니다 (약 {days}일 유효).")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="instapromo", description="Instagram 홍보 피드 자동화")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("generate", help="제품 설명으로 게시물(캡션+이미지) 생성")
    p.add_argument("--product", required=True, help="제품 YAML 파일 경로")
    p.add_argument("--github", help="설명을 가져올 GitHub 저장소 (YAML의 github 값보다 우선)")
    p.add_argument("--count", type=int, default=1, help="생성할 게시물 수")
    p.add_argument("--no-images", action="store_true", help="AI 배경 없이 브랜드 그라데이션만 사용")
    p.add_argument("--no-fetch", action="store_true", help="웹페이지·GitHub 내용을 읽지 않음")
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
    try:
        args.func(args, Settings.load())
    except (MissingSettingError, RuntimeError) as e:
        raise SystemExit(f"오류: {e}") from e


if __name__ == "__main__":
    main()
