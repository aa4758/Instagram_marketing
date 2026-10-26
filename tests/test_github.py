import httpx
import pytest

from instapromo.github import fetch_repo, parse_repo, readme_summary


@pytest.mark.parametrize("ref", [
    "https://github.com/owner/repo",
    "https://github.com/owner/repo.git",
    "github.com/owner/repo/tree/main/docs",
    "owner/repo",
])
def test_parse_repo(ref):
    assert parse_repo(ref) == ("owner", "repo")


def test_parse_repo_invalid():
    with pytest.raises(ValueError):
        parse_repo("https://example.com/x")


def test_fetch_repo_reads_metadata_and_readme():
    def handler(request: httpx.Request):
        assert request.headers["Authorization"] == "Bearer tok"
        if request.url.path == "/repos/owner/repo":
            return httpx.Response(200, json={"name": "repo", "description": "습관 앱",
                                             "homepage": "https://app.example", "topics": ["habit"]})
        if request.url.path == "/repos/owner/repo/readme":
            return httpx.Response(200, text="# Repo\n\n매일 3분 체크인")
        return httpx.Response(404)

    info = fetch_repo("owner/repo", token="tok", client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert (info.description, info.homepage, info.topics) == ("습관 앱", "https://app.example", ["habit"])
    text = info.as_source_text()
    assert "매일 3분 체크인" in text and "습관 앱" in text


def test_fetch_repo_not_found():
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(404)))
    with pytest.raises(RuntimeError, match="찾을 수 없습니다"):
        fetch_repo("owner/repo", client=client)


def test_readme_summary_strips_markdown_noise():
    readme = """# 루틴메이트

[![build](https://x/badge.svg)](https://x)
<p align="center"><img src="logo.png"></p>

작심삼일을 끝내는 [습관 트래커](https://app.example)입니다.

```bash
npm install
```

| a | b |
|---|---|
"""
    summary = readme_summary(readme)
    assert summary.startswith("작심삼일을 끝내는 습관 트래커입니다.")
    assert "npm" not in summary and "badge" not in summary and "#" not in summary
