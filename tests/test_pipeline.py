import json
import os
from pathlib import Path

import pytest

from instapromo.images.renderer import SlideRenderer
from instapromo.models import PostDraft, Product, Slide
from instapromo.pipeline import build_post, recent_themes

CHROMIUM = os.environ.get("CHROMIUM_EXECUTABLE") or (
    "/opt/pw-browsers/chromium" if Path("/opt/pw-browsers/chromium").exists() else None
)


class FakeProvider:
    def __init__(self):
        self.prompts = []

    def generate(self, prompt, *, aspect_ratio="4:5", reference_images=None):
        self.prompts.append(prompt)
        from io import BytesIO

        from PIL import Image
        buf = BytesIO()
        Image.new("RGB", (40, 50), "orange").save(buf, "PNG")
        return buf.getvalue()


@pytest.fixture(scope="module")
def renderer():
    try:
        with SlideRenderer(CHROMIUM) as r:
            yield r
    except Exception as e:
        pytest.skip(f"Chromium을 실행할 수 없습니다: {e}")


def test_build_post_renders_slides(tmp_path, renderer):
    product = Product(name="앱", tagline="소개")
    post = PostDraft(theme="기능 소개", caption="본문", hashtags=["태그"], slides=[
        Slide(layout="cover", headline="제목", image_prompt="a desk"),
        Slide(layout="cta", headline="시작하기"),
    ])
    provider = FakeProvider()
    record = build_post(post, product, tmp_path / "p1", renderer=renderer, image_provider=provider)

    assert provider.prompts == ["a desk"]  # cta는 image_prompt가 없어 생성 안 함
    assert record["slides"] == ["slide_01.jpg", "slide_02.jpg"]
    assert (tmp_path / "p1" / "slide_01.jpg").read_bytes()[:3] == b"\xff\xd8\xff"
    assert (tmp_path / "p1" / "caption.txt").read_text(encoding="utf-8") == "본문\n\n#태그"
    assert json.loads((tmp_path / "p1" / "post.json").read_text(encoding="utf-8"))["status"] == "draft"
    assert recent_themes(tmp_path, "앱") == ["기능 소개"]
    assert recent_themes(tmp_path, "다른앱") == []
