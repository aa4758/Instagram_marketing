from types import SimpleNamespace

import pytest

from instapromo.copywriter import build_user_prompt, generate_posts
from instapromo.models import PostDraft, PostPlan, Product, Slide

PRODUCT = Product(name="루틴메이트", tagline="습관 트래커", features=["체크인"])


class FakeClient:
    def __init__(self, response):
        self.kwargs = None
        self.beta = SimpleNamespace(messages=SimpleNamespace(parse=self._parse))
        self._response = response

    def _parse(self, **kwargs):
        self.kwargs = kwargs
        return self._response


def test_generate_posts_returns_parsed_posts():
    post = PostDraft(theme="t", caption="c", hashtags=[], slides=[Slide(layout="cover", headline="h")])
    client = FakeClient(SimpleNamespace(stop_reason="end_turn", parsed_output=PostPlan(posts=[post])))
    assert generate_posts(PRODUCT, model="m", count=1, client=client) == [post]
    assert client.kwargs["output_format"] is PostPlan
    assert client.kwargs["fallbacks"] == "default"


def test_generate_posts_refusal():
    client = FakeClient(SimpleNamespace(stop_reason="refusal", parsed_output=None))
    with pytest.raises(RuntimeError):
        generate_posts(PRODUCT, model="m", client=client)


def test_user_prompt_includes_page_text_and_recent_themes():
    prompt = build_user_prompt(PRODUCT, "페이지 본문", 2, ["사용 팁"])
    assert "페이지 본문" in prompt and "- 사용 팁" in prompt and "Create 2" in prompt
