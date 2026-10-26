import json

from instapromo import service
from instapromo.config import Settings


def test_settings_roundtrip_and_env_override(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    Settings(anthropic_api_key="from-file", ig_user_id="42").save(path)
    monkeypatch.setenv("IG_USER_ID", "from-env")

    assert Settings.load(path).ig_user_id == "from-env"
    assert Settings.load(path, use_env=False).ig_user_id == "42"
    assert Settings.load(path, use_env=False).anthropic_api_key == "from-file"


def test_approve_writes_caption_and_status(tmp_path):
    post_dir = tmp_path / "p"
    post_dir.mkdir()
    (post_dir / "post.json").write_text(json.dumps({"status": "draft", "slides": []}), encoding="utf-8")
    (post_dir / "caption.txt").write_text("원래 캡션", encoding="utf-8")

    service.approve(post_dir, "고친 캡션\n")
    record = json.loads((post_dir / "post.json").read_text(encoding="utf-8"))
    assert record["status"] == "approved" and record["final_caption"] == "고친 캡션"
    assert (post_dir / "caption.txt").read_text(encoding="utf-8") == "고친 캡션"
