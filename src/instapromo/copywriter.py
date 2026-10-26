from __future__ import annotations

import anthropic

from .models import PostDraft, PostPlan, Product

SYSTEM_PROMPT = """\
You are a senior social media marketer who writes Instagram feed posts that promote apps and websites.

Write every caption, headline and body in the product's language. Image prompts are always in English.

Rules:
- Only state facts found in the product information. Never invent numbers, prices, awards, user counts or features.
- Never use the product's banned words.
- Each post: a hook in the first caption line, a short body, then a call to action such as "프로필 링크에서 확인하세요".
- Hashtags: 8-15 relevant tags, mixing broad and niche ones, without the '#' symbol.
- Slides: the first slide uses layout "cover" (the hook), middle slides use "feature", the last slide of a carousel uses "cta".
  A single-image post has one "cover" slide. Use 1 to 6 slides.
- Headlines are at most 20 characters and bodies at most 60 characters, because they are printed on the image.
- image_prompt describes only a background photo or illustration for that slide in the brand's mood.
  It must ask for no text, no letters, no logos and no real people's faces. Use null for "cta" slides.
- Set use_screenshot to true only on "feature" slides that show the product's screen, and only if screenshots are available.
- Vary the theme across posts (feature intro, problem/solution, usage tip, before/after, use case) and do not repeat angles.
"""


def build_user_prompt(product: Product, page_text: str | None, count: int, recent_themes: list[str]) -> str:
    lines = [
        f"Create {count} Instagram feed post(s) for this product.",
        "",
        "<product>",
        product.model_dump_json(indent=2, exclude={"brand"}),
        "</product>",
        f"Screenshots available: {'yes' if product.screenshots else 'no'}",
    ]
    if page_text:
        lines += ["", "<website_text>", page_text, "</website_text>"]
    if recent_themes:
        lines += ["", "Recently published themes to avoid repeating:", *[f"- {t}" for t in recent_themes]]
    return "\n".join(lines)


def generate_posts(
    product: Product,
    *,
    model: str,
    count: int = 1,
    page_text: str | None = None,
    recent_themes: list[str] | None = None,
    client: anthropic.Anthropic | None = None,
) -> list[PostDraft]:
    client = client or anthropic.Anthropic()
    response = client.beta.messages.parse(
        model=model,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": build_user_prompt(product, page_text, count, recent_themes or []),
        }],
        output_format=PostPlan,
        output_config={"effort": "medium"},
        # 정책상 거절되면 서버가 다른 모델로 자동 재시도
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("Claude가 요청을 거절했습니다. 제품 설명을 확인해 주세요.")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("응답이 길이 제한에 걸려 잘렸습니다. --count 를 줄여 다시 시도하세요.")
    plan = response.parsed_output
    if plan is None:
        raise RuntimeError("구조화된 응답을 해석하지 못했습니다.")
    return plan.posts
