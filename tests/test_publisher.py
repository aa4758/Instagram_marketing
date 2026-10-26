import httpx
import pytest

from instapromo.publisher import InstagramError, InstagramPublisher


def make_publisher(handler):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return InstagramPublisher("123", "token", client=client, poll_interval=0)


def test_single_image_publish():
    calls = []

    def handler(request: httpx.Request):
        calls.append((request.method, request.url.path))
        if request.url.path.endswith("/123/media"):
            return httpx.Response(200, json={"id": "c1"})
        if request.url.path.endswith("/c1"):
            return httpx.Response(200, json={"status_code": "FINISHED"})
        if request.url.path.endswith("/media_publish"):
            assert b"creation_id=c1" in request.content
            return httpx.Response(200, json={"id": "m1"})
        raise AssertionError(request.url)

    assert make_publisher(handler).publish(["https://x/a.jpg"], "hi") == "m1"
    assert calls[0] == ("POST", "/v23.0/123/media")


def test_carousel_publish_creates_children_then_parent():
    created = []

    def handler(request: httpx.Request):
        if request.url.path.endswith("/123/media"):
            body = request.content.decode()
            created.append(body)
            return httpx.Response(200, json={"id": f"c{len(created)}"})
        if request.method == "GET":
            return httpx.Response(200, json={"status_code": "FINISHED"})
        return httpx.Response(200, json={"id": "m1"})

    assert make_publisher(handler).publish(["https://x/a.jpg", "https://x/b.jpg"], "cap") == "m1"
    assert all("is_carousel_item=true" in b for b in created[:2])
    assert "media_type=CAROUSEL" in created[2] and "children=c1%2Cc2" in created[2]


def test_container_error_raises():
    def handler(request: httpx.Request):
        if request.method == "POST":
            return httpx.Response(200, json={"id": "c1"})
        return httpx.Response(200, json={"status_code": "ERROR"})

    with pytest.raises(InstagramError):
        make_publisher(handler).publish(["https://x/a.jpg"], "cap")


def test_api_error_message():
    def handler(request: httpx.Request):
        return httpx.Response(400, json={"error": {"code": 190, "message": "Invalid token"}})

    with pytest.raises(InstagramError, match="190: Invalid token"):
        make_publisher(handler).publishing_quota()
