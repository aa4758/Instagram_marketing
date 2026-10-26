from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from dotenv import load_dotenv


def app_dir() -> Path:
    """설정·제품 정보를 저장하는 폴더. Windows는 %APPDATA%\\InstaPromo."""
    if custom := os.environ.get("INSTAPROMO_HOME"):
        return Path(custom)
    if sys.platform == "win32" and os.environ.get("APPDATA"):
        return Path(os.environ["APPDATA"]) / "InstaPromo"
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "instapromo"


def settings_path() -> Path:
    return app_dir() / "settings.json"


@dataclass
class Settings:
    """앱 설정. settings.json 값을 읽고, 같은 이름의 환경변수(대문자)가 있으면 그 값을 우선한다."""

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-5-5"
    gemini_api_key: str = ""
    gemini_image_model: str = "gemini-2.5-flash-image"
    github_token: str = ""
    ig_user_id: str = ""
    ig_access_token: str = ""
    ig_api_version: str = "v23.0"
    s3_bucket: str = ""
    s3_endpoint_url: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_public_base_url: str = ""
    chromium_executable: str = ""
    output_dir: str = str(Path.home() / "InstaPromo")

    @classmethod
    def load(cls, path: Path | None = None, *, use_env: bool = True) -> Settings:
        """use_env=False면 settings.json만 읽는다 (GUI는 화면에서 입력한 값만 쓰도록)."""
        if use_env:
            load_dotenv()
        path = path or settings_path()
        stored = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        values = {}
        for f in fields(cls):
            env = os.environ.get(f.name.upper(), "").strip() if use_env else ""
            if env:
                values[f.name] = env
            elif isinstance(stored.get(f.name), str):
                values[f.name] = stored[f.name]
        return cls(**values)

    def save(self, path: Path | None = None) -> Path:
        path = path or settings_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    @property
    def output_path(self) -> Path:
        return Path(self.output_dir).expanduser()


class MissingSettingError(RuntimeError):
    pass


def require(value: str | None, name: str) -> str:
    if not value:
        raise MissingSettingError(f"'{name}' 설정이 비어 있습니다. 설정 화면이나 환경변수에서 입력하세요.")
    return value
