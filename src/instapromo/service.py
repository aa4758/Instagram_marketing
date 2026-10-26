"""CLI와 GUI가 함께 쓰는 작업 단위 (생성 → 승인 → 게시)."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from .config import Settings, require
from .models import Product

Log = Callable[[str], None]


def generate(product: Product, settings: Settings, *, count: int = 1, use_images: bool = True,
             fetch_sources: bool = True, log: Log = print) -> list[Path]:
    from .copywriter import generate_posts
    from .images.renderer import SlideRenderer
    from .pipeline import build_post, new_post_dir, recent_themes
    from .product import collect_source_text

    source_text = collect_source_text(product, github_token=settings.github_token, log=log) if fetch_sources else None

    log(f"Claude로 게시물 {count}개 기획 중...")
    posts = generate_posts(
        product,
        model=settings.anthropic_model,
        api_key=require(settings.anthropic_api_key, "Claude API 키"),
        count=count,
        source_text=source_text,
        recent_themes=recent_themes(settings.output_path, product.name),
    )

    image_provider = None
    if use_images:
        from .images.gemini import GeminiImageProvider
        image_provider = GeminiImageProvider(require(settings.gemini_api_key, "Gemini API 키"),
                                             model=settings.gemini_image_model)

    dirs: list[Path] = []
    with SlideRenderer(settings.chromium_executable or None) as renderer:
        for n, post in enumerate(posts, start=1):
            out_dir = new_post_dir(settings.output_path, product, n)
            log(f"[{n}/{len(posts)}] {post.theme} - 슬라이드 {len(post.slides)}장 만드는 중...")
            record = build_post(post, product, out_dir, renderer=renderer, image_provider=image_provider)
            log(f"  → {out_dir}")
            for w in record["warnings"]:
                log(f"  ⚠ {w}")
            dirs.append(out_dir)
    return dirs


def list_posts(settings: Settings) -> list[tuple[Path, dict]]:
    """출력 폴더의 게시물을 최신순으로 반환한다."""
    from .pipeline import POST_FILE, read_record

    root = settings.output_path
    if not root.exists():
        return []
    dirs = sorted((f.parent for f in root.glob(f"*/{POST_FILE}")), reverse=True)
    return [(d, read_record(d)) for d in dirs]


def approve(post_dir: Path, caption: str | None = None) -> None:
    from .pipeline import read_record, write_record

    record = read_record(post_dir)
    if record["status"] == "published":
        raise RuntimeError("이미 게시된 게시물입니다.")
    caption_file = post_dir / "caption.txt"
    if caption is not None:
        caption_file.write_text(caption.strip(), encoding="utf-8")
    record["final_caption"] = caption_file.read_text(encoding="utf-8").strip()
    record["status"] = "approved"
    write_record(post_dir, record)


def _publisher(settings: Settings):
    from .publisher import InstagramPublisher

    return InstagramPublisher(require(settings.ig_user_id, "Instagram 사용자 ID"),
                              require(settings.ig_access_token, "Instagram 액세스 토큰"),
                              settings.ig_api_version)


def publish(post_dir: Path, settings: Settings, *, dry_run: bool = False, log: Log = print) -> str | None:
    from .pipeline import read_record, write_record
    from .storage import S3Storage

    record = read_record(post_dir)
    if record["status"] == "published":
        raise RuntimeError(f"이미 게시됨: {record.get('permalink')}")
    if record["status"] != "approved":
        raise RuntimeError("승인되지 않은 게시물입니다. 먼저 승인하세요.")
    caption = record["final_caption"]
    files = [post_dir / name for name in record["slides"]]

    if dry_run:
        log("[dry-run] 업로드할 파일:\n" + "\n".join(f"  {f}" for f in files))
        log("[dry-run] 캡션:\n" + caption)
        return None

    publisher = _publisher(settings)
    quota = publisher.publishing_quota()
    total = quota.get("config", {}).get("quota_total")
    if total is not None and quota.get("quota_usage", 0) >= total:
        raise RuntimeError(f"24시간 게시 한도({total})에 도달했습니다. 나중에 다시 시도하세요.")

    storage = S3Storage(
        bucket=require(settings.s3_bucket, "S3 버킷"),
        public_base_url=require(settings.s3_public_base_url, "S3 공개 URL"),
        endpoint_url=settings.s3_endpoint_url or None,
        access_key_id=settings.s3_access_key_id or None,
        secret_access_key=settings.s3_secret_access_key or None,
    )
    urls = [storage.upload(f, f"instapromo/{post_dir.name}/{f.name}") for f in files]
    log(f"이미지 {len(urls)}장 업로드 완료, Instagram 게시 중...")

    media_id = publisher.publish(urls, caption)
    record.update(status="published", ig_media_id=media_id,
                  permalink=publisher.permalink(media_id),
                  published_at=datetime.now().isoformat(timespec="seconds"))
    write_record(post_dir, record)
    link = record["permalink"] or media_id
    log(f"게시 완료: {link}")
    return link


def quota(settings: Settings) -> tuple[int | None, int | None]:
    q = _publisher(settings).publishing_quota()
    return q.get("quota_usage"), q.get("config", {}).get("quota_total")


def refresh_token(settings: Settings, *, save: bool = True) -> int:
    """토큰을 갱신하고 남은 유효 일수를 반환한다. save=True면 settings.json에 저장."""
    data = _publisher(settings).refresh_token()
    settings.ig_access_token = data["access_token"]
    if save:
        settings.save()
    return int(data.get("expires_in", 0)) // 86400
