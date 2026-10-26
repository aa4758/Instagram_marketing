from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

import httpx
import yaml
from bs4 import BeautifulSoup

from .github import fetch_repo
from .models import Product

log = logging.getLogger(__name__)

PAGE_TEXT_LIMIT = 20_000
README_LIMIT = 20_000


def load_product(path: str | Path) -> Product:
    path = Path(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    product = Product.model_validate(data)
    # 스크린샷·로고 경로는 YAML 파일 위치 기준으로 해석
    base = path.parent
    product.screenshots = [str((base / p).resolve()) for p in product.screenshots]
    if product.brand.logo:
        product.brand.logo = str((base / product.brand.logo).resolve())
    return product


def fetch_page_text(url: str, timeout: float = 20.0) -> str:
    """홍보 대상 페이지의 제목·설명·본문 텍스트를 추출한다."""
    resp = httpx.get(
        url,
        timeout=timeout,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 (compatible; InstaPromo/0.1)"},
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()

    parts: list[str] = []
    if soup.title and soup.title.string:
        parts.append(f"제목: {soup.title.string.strip()}")
    for name in ("description", "og:description"):
        meta = soup.find("meta", attrs={"name": name}) or soup.find("meta", attrs={"property": name})
        if meta and meta.get("content"):
            parts.append(f"설명: {meta['content'].strip()}")
    body = " ".join(soup.get_text(" ").split())
    parts.append(body)

    text = "\n".join(parts)
    if len(text) > PAGE_TEXT_LIMIT:
        log.warning("페이지 텍스트가 %d자라 앞부분 %d자만 사용합니다.", len(text), PAGE_TEXT_LIMIT)
        text = text[:PAGE_TEXT_LIMIT]
    return text


def save_product(product: Product, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = product.model_dump(mode="json")
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


def collect_source_text(
    product: Product,
    *,
    github_token: str | None = None,
    log: Callable[[str], None] = print,
) -> str | None:
    """웹페이지와 GitHub README에서 Claude에게 줄 참고 자료를 모은다. 실패한 출처는 건너뛴다."""
    sources: list[str] = []
    if product.url:
        log(f"웹페이지 읽는 중: {product.url}")
        try:
            sources.append("[웹페이지]\n" + fetch_page_text(product.url))
        except Exception as e:
            log(f"  ⚠ 웹페이지를 읽지 못했습니다: {e}")
    if product.github:
        log(f"GitHub 저장소 읽는 중: {product.github}")
        try:
            text = fetch_repo(product.github, token=github_token).as_source_text()
            if len(text) > README_LIMIT:
                log(f"  README가 길어 앞부분 {README_LIMIT}자만 사용합니다.")
                text = text[:README_LIMIT]
            sources.append("[GitHub]\n" + text)
        except Exception as e:
            log(f"  ⚠ GitHub 저장소를 읽지 못했습니다: {e}")
    return "\n\n".join(sources) or None
