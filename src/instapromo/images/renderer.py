from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape
from playwright.sync_api import sync_playwright

from ..models import Brand, Slide

WIDTH, HEIGHT = 1080, 1350  # 4:5 피드 권장 규격

_env = Environment(loader=PackageLoader("instapromo", "templates"), autoescape=select_autoescape())


def _data_uri(data: bytes | None = None, path: str | Path | None = None) -> str | None:
    if path:
        mime = mimetypes.guess_type(str(path))[0] or "image/png"
        data = Path(path).read_bytes()
    elif data:
        mime = "image/jpeg" if data[:3] == b"\xff\xd8\xff" else "image/png"
    else:
        return None
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def render_html(slide: Slide, brand: Brand, *, background: bytes | None, index: int, total: int) -> str:
    return _env.get_template("slide.html").render(
        slide=slide,
        brand=brand,
        background=_data_uri(data=background),
        logo=_data_uri(path=brand.logo) if brand.logo else None,
        index=index,
        total=total,
        width=WIDTH,
        height=HEIGHT,
    )


class SlideRenderer:
    """HTML 템플릿을 Chromium으로 캡처해 JPEG로 저장한다."""

    def __init__(self, chromium_executable: str | None = None):
        self.chromium_executable = chromium_executable
        self._pw = None
        self._browser = None

    def __enter__(self) -> SlideRenderer:
        self._pw = sync_playwright().start()
        kwargs = {"executable_path": self.chromium_executable} if self.chromium_executable else {}
        self._browser = self._pw.chromium.launch(**kwargs)
        return self

    def __exit__(self, *exc) -> None:
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()

    def render(self, html: str, out_path: Path) -> bool:
        """out_path 에 JPEG를 저장하고, 문구가 영역을 넘치면 True를 반환한다."""
        page = self._browser.new_page(viewport={"width": WIDTH, "height": HEIGHT})
        try:
            page.set_content(html, wait_until="networkidle")
            page.evaluate("document.fonts.ready")
            # 한글 글꼴은 줄 높이보다 글자 영역이 커서 몇 px 넘치는 건 정상. 반 줄 이상 넘치면 잘린 것으로 본다.
            overflow = page.evaluate(
                """[...document.querySelectorAll('.fit')].some(e =>
                    e.scrollHeight - e.clientHeight > parseFloat(getComputedStyle(e).lineHeight) / 2)"""
            )
            page.screenshot(path=str(out_path), type="jpeg", quality=92)
        finally:
            page.close()
        return bool(overflow)
