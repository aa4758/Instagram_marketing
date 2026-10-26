from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path

from .images.base import ImageProvider
from .images.renderer import SlideRenderer, render_html
from .models import PostDraft, Product, full_caption, validate_post

log = logging.getLogger(__name__)

POST_FILE = "post.json"


def _slug(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "-", text).strip("-").lower()[:30] or "post"


def recent_themes(output_dir: Path, product_name: str, limit: int = 10) -> list[str]:
    """이전에 만든 게시물 주제. 같은 각도의 글이 반복되지 않게 프롬프트에 넣는다."""
    if not output_dir.exists():
        return []
    records = []
    for f in output_dir.glob(f"*/{POST_FILE}"):
        rec = json.loads(f.read_text(encoding="utf-8"))
        if rec.get("product") == product_name:
            records.append((rec.get("created_at", ""), rec["post"]["theme"]))
    return [theme for _, theme in sorted(records, reverse=True)[:limit]]


def build_post(
    post: PostDraft,
    product: Product,
    out_dir: Path,
    *,
    renderer: SlideRenderer,
    image_provider: ImageProvider | None,
) -> dict:
    """한 게시물의 슬라이드 이미지를 만들고 post.json을 기록한다."""
    out_dir.mkdir(parents=True, exist_ok=True)
    warnings = validate_post(post, product)
    slide_files: list[str] = []
    total = len(post.slides)

    for i, slide in enumerate(post.slides, start=1):
        background = None
        if image_provider and slide.image_prompt:
            refs = [Path(product.screenshots[0])] if slide.use_screenshot and product.screenshots else None
            try:
                background = image_provider.generate(slide.image_prompt, aspect_ratio="4:5", reference_images=refs)
                (out_dir / f"bg_{i:02d}.png").write_bytes(background)
            except Exception as e:  # 배경 실패 시 브랜드 그라데이션으로 대체
                log.warning("슬라이드 %d 배경 생성 실패: %s", i, e)
                warnings.append(f"슬라이드 {i} 배경 생성 실패, 기본 배경 사용: {e}")

        html = render_html(slide, product.brand, background=background, index=i, total=total)
        name = f"slide_{i:02d}.jpg"
        if renderer.render(html, out_dir / name):
            warnings.append(f"슬라이드 {i}: 문구가 영역을 넘칩니다. 문구를 줄여 주세요.")
        slide_files.append(name)

    record = {
        "product": product.name,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "status": "draft",
        "post": post.model_dump(),
        "slides": slide_files,
        "warnings": warnings,
    }
    write_record(out_dir, record)
    (out_dir / "caption.txt").write_text(full_caption(post), encoding="utf-8")
    return record


def new_post_dir(output_dir: Path, product: Product, index: int) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return output_dir / f"{stamp}-{_slug(product.name)}-{index}"


def read_record(post_dir: Path) -> dict:
    path = post_dir / POST_FILE
    if not path.exists():
        raise SystemExit(f"{path} 가 없습니다. generate로 만든 게시물 폴더를 지정하세요.")
    return json.loads(path.read_text(encoding="utf-8"))


def write_record(post_dir: Path, record: dict) -> None:
    (post_dir / POST_FILE).write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
