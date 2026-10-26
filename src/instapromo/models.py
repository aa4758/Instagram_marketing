from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

CAPTION_MAX_CHARS = 2200
HASHTAG_MAX = 30
CAROUSEL_MAX_SLIDES = 10


class Brand(BaseModel):
    primary_color: str = "#4F7CFF"
    secondary_color: str = "#FFD84F"
    text_color: str = "#FFFFFF"
    font: str = "Noto Sans KR"
    logo: str | None = None


class Product(BaseModel):
    """products/*.yaml 로 입력하는 홍보 대상 정보."""

    name: str
    tagline: str
    description: str = ""
    url: str | None = None
    store_links: list[str] = Field(default_factory=list)
    target: str = ""
    tone: str = "친근하고 명확한 말투"
    language: str = "ko"
    features: list[str] = Field(default_factory=list)
    banned_words: list[str] = Field(default_factory=list)
    screenshots: list[str] = Field(default_factory=list)
    brand: Brand = Field(default_factory=Brand)


# ---- Claude 구조화 출력 스키마 ----

class Slide(BaseModel):
    layout: Literal["cover", "feature", "cta"]
    headline: str = Field(description="이미지에 크게 들어갈 제목. 20자 이내")
    body: str = Field(default="", description="보조 문구. 60자 이내, 없으면 빈 문자열")
    image_prompt: str | None = Field(
        default=None,
        description="배경 이미지 생성용 영어 프롬프트. 글자/로고 없이. cta 장은 보통 null",
    )
    use_screenshot: bool = Field(
        default=False, description="제품 스크린샷을 참고 이미지로 합성할지 여부"
    )


class PostDraft(BaseModel):
    theme: str = Field(description="게시물 주제 유형 (기능 소개, 문제/해결, 사용 팁 등)")
    slides: list[Slide] = Field(description="1장이면 단일 이미지, 2장 이상이면 캐러셀")
    caption: str = Field(description="해시태그를 제외한 본문 캡션")
    hashtags: list[str] = Field(description="'#' 없이 단어만")


class PostPlan(BaseModel):
    posts: list[PostDraft]


def full_caption(post: PostDraft) -> str:
    tags = " ".join(f"#{t.lstrip('#')}" for t in post.hashtags)
    return f"{post.caption.strip()}\n\n{tags}".strip()


def validate_post(post: PostDraft, product: Product) -> list[str]:
    """게시 전 확인할 경고 목록. 빈 리스트면 문제 없음."""
    warnings: list[str] = []
    caption = full_caption(post)
    if len(caption) > CAPTION_MAX_CHARS:
        warnings.append(f"캡션이 {len(caption)}자로 {CAPTION_MAX_CHARS}자 제한을 넘습니다.")
    if len(post.hashtags) > HASHTAG_MAX:
        warnings.append(f"해시태그가 {len(post.hashtags)}개로 {HASHTAG_MAX}개 제한을 넘습니다.")
    if not 1 <= len(post.slides) <= CAROUSEL_MAX_SLIDES:
        warnings.append(f"슬라이드 수({len(post.slides)})는 1~{CAROUSEL_MAX_SLIDES}장이어야 합니다.")
    texts = [caption] + [f"{s.headline} {s.body}" for s in post.slides]
    for word in product.banned_words:
        if any(word in t for t in texts):
            warnings.append(f"금지 표현 '{word}' 이(가) 포함되어 있습니다.")
    return warnings
