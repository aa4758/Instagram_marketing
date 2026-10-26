from __future__ import annotations

import time

import httpx

GRAPH_HOST = "https://graph.instagram.com"


class InstagramError(RuntimeError):
    pass


class InstagramPublisher:
    """Instagram 로그인 방식 Graph API로 피드 게시물을 올린다."""

    def __init__(self, ig_user_id: str, access_token: str, api_version: str = "v23.0",
                 client: httpx.Client | None = None, poll_interval: float = 3.0, poll_timeout: float = 120.0):
        self.ig_user_id = ig_user_id
        self.access_token = access_token
        self.base = f"{GRAPH_HOST}/{api_version}"
        self.client = client or httpx.Client(timeout=30.0)
        self.poll_interval = poll_interval
        self.poll_timeout = poll_timeout

    def _request(self, method: str, path: str, **params) -> dict:
        params["access_token"] = self.access_token
        if method == "GET":
            resp = self.client.get(f"{self.base}/{path}", params=params)
        else:
            resp = self.client.post(f"{self.base}/{path}", data=params)
        data = resp.json()
        if resp.status_code >= 400 or "error" in data:
            err = data.get("error", {})
            raise InstagramError(f"{err.get('code')}: {err.get('message', resp.text)}")
        return data

    def publishing_quota(self) -> dict:
        """24시간 기준 게시 한도 사용량 {'quota_usage': n, 'config': {'quota_total': m, ...}}."""
        data = self._request("GET", f"{self.ig_user_id}/content_publishing_limit", fields="quota_usage,config")
        return data["data"][0] if data.get("data") else {}

    def _wait_until_ready(self, container_id: str) -> None:
        deadline = time.monotonic() + self.poll_timeout
        while True:
            status = self._request("GET", container_id, fields="status_code").get("status_code")
            if status in ("FINISHED", "PUBLISHED"):
                return
            if status in ("ERROR", "EXPIRED"):
                raise InstagramError(f"컨테이너 {container_id} 처리 실패: {status}")
            if time.monotonic() > deadline:
                raise InstagramError(f"컨테이너 {container_id} 처리 대기 시간 초과 (상태: {status})")
            time.sleep(self.poll_interval)

    def publish(self, image_urls: list[str], caption: str) -> str:
        """이미지 1장이면 단일 게시물, 2장 이상이면 캐러셀로 올리고 media id를 반환한다."""
        if not image_urls:
            raise ValueError("이미지가 없습니다.")
        if len(image_urls) == 1:
            container = self._request("POST", f"{self.ig_user_id}/media",
                                      image_url=image_urls[0], caption=caption)["id"]
        else:
            children = []
            for url in image_urls:
                child = self._request("POST", f"{self.ig_user_id}/media",
                                      image_url=url, is_carousel_item="true")["id"]
                self._wait_until_ready(child)
                children.append(child)
            container = self._request("POST", f"{self.ig_user_id}/media", media_type="CAROUSEL",
                                      children=",".join(children), caption=caption)["id"]
        self._wait_until_ready(container)
        return self._request("POST", f"{self.ig_user_id}/media_publish", creation_id=container)["id"]

    def permalink(self, media_id: str) -> str | None:
        return self._request("GET", media_id, fields="permalink").get("permalink")

    def refresh_token(self) -> dict:
        """장기 토큰 갱신. {'access_token', 'expires_in'} 반환 (발급 24시간 후부터 가능)."""
        resp = self.client.get(f"{GRAPH_HOST}/refresh_access_token",
                               params={"grant_type": "ig_refresh_token", "access_token": self.access_token})
        data = resp.json()
        if resp.status_code >= 400 or "error" in data:
            raise InstagramError(str(data.get("error", data)))
        return data
