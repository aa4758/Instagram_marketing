from __future__ import annotations

import logging
from pathlib import Path

import httpx
import yaml
from bs4 import BeautifulSoup

from .models import Product

log = logging.getLogger(__name__)

PAGE_TEXT_LIMIT = 20_000


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
