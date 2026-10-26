from __future__ import annotations

import re
from dataclasses import dataclass, field

import httpx

API = "https://api.github.com"
_URL_RE = re.compile(r"^(?:https?://)?(?:www\.)?github\.com/([^/\s]+)/([^/\s#?]+)")
_SHORT_RE = re.compile(r"^([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)$")


@dataclass
class RepoInfo:
    owner: str
    name: str
    description: str = ""
    homepage: str = ""
    topics: list[str] = field(default_factory=list)
    readme: str = ""

    def as_source_text(self) -> str:
        parts = [f"GitHub 저장소: {self.owner}/{self.name}"]
        if self.description:
            parts.append(f"설명: {self.description}")
        if self.homepage:
            parts.append(f"홈페이지: {self.homepage}")
        if self.topics:
            parts.append(f"토픽: {', '.join(self.topics)}")
        if self.readme:
            parts += ["README:", self.readme]
        return "\n".join(parts)


def parse_repo(ref: str) -> tuple[str, str]:
    """'https://github.com/owner/repo', 'github.com/owner/repo/tree/main', 'owner/repo' 를 해석한다."""
    ref = ref.strip()
    m = _URL_RE.match(ref) or _SHORT_RE.match(ref)
    if not m:
        raise ValueError(f"GitHub 저장소 주소를 해석할 수 없습니다: {ref}")
    owner, repo = m.group(1), m.group(2)
    return owner, repo.removesuffix(".git")


def fetch_repo(ref: str, token: str | None = None, client: httpx.Client | None = None) -> RepoInfo:
    owner, repo = parse_repo(ref)
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    client = client or httpx.Client(timeout=20.0, follow_redirects=True)

    resp = client.get(f"{API}/repos/{owner}/{repo}", headers=headers)
    if resp.status_code == 404:
        raise RuntimeError(f"저장소 {owner}/{repo} 를 찾을 수 없습니다. 비공개 저장소라면 GitHub 토큰을 설정하세요.")
    if resp.status_code == 403:
        raise RuntimeError("GitHub API 요청 한도를 넘었거나 권한이 없습니다. GitHub 토큰을 설정하세요.")
    resp.raise_for_status()
    data = resp.json()

    info = RepoInfo(
        owner=owner,
        name=data.get("name") or repo,
        description=data.get("description") or "",
        homepage=data.get("homepage") or "",
        topics=data.get("topics") or [],
    )
    readme = client.get(f"{API}/repos/{owner}/{repo}/readme",
                        headers={**headers, "Accept": "application/vnd.github.raw+json"})
    if readme.status_code == 200:
        info.readme = readme.text
    return info


def readme_summary(readme: str, limit: int = 600) -> str:
    """README 마크다운에서 배지·이미지·코드 블록·제목 기호를 걷어내고 앞부분 문단만 남긴다."""
    text = re.sub(r"```.*?```", "", readme, flags=re.S)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    paragraphs = []
    for block in re.split(r"\n\s*\n", text):
        lines = [ln.strip() for ln in block.splitlines()]
        lines = [ln for ln in lines if ln and not ln.startswith("#") and not set(ln) <= set("-=|: ")]
        if lines:
            paragraphs.append(" ".join(lines))
    summary = ""
    for p in paragraphs:
        if summary and len(summary) + len(p) > limit:
            break
        summary = f"{summary}\n\n{p}" if summary else p
    return summary[:limit].strip()
