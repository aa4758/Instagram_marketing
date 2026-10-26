from instapromo.models import PostDraft, Product, Slide, full_caption, validate_post


def make_post(**kw) -> PostDraft:
    data = dict(theme="기능 소개", caption="본문", hashtags=["습관", "#루틴"],
                slides=[Slide(layout="cover", headline="제목")])
    data.update(kw)
    return PostDraft(**data)


def test_full_caption_normalizes_hashtags():
    assert full_caption(make_post()) == "본문\n\n#습관 #루틴"


def test_validate_post_ok():
    assert validate_post(make_post(), Product(name="앱", tagline="소개")) == []


def test_validate_post_flags_limits_and_banned_words():
    product = Product(name="앱", tagline="소개", banned_words=["최고"])
    post = make_post(caption="업계 최고" + "가" * 2200, hashtags=[f"t{i}" for i in range(31)],
                     slides=[Slide(layout="feature", headline="h")] * 11)
    warnings = validate_post(post, product)
    assert len(warnings) == 4
    assert any("최고" in w for w in warnings)
