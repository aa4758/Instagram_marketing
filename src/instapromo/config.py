from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    anthropic_model: str
    gemini_api_key: str | None
    gemini_image_model: str
    ig_user_id: str | None
    ig_access_token: str | None
    ig_api_version: str
    s3_bucket: str | None
    s3_endpoint_url: str | None
    s3_access_key_id: str | None
    s3_secret_access_key: str | None
    s3_public_base_url: str | None
    chromium_executable: str | None
    output_dir: Path

    @classmethod
    def from_env(cls) -> Settings:
        load_dotenv()

        def get(name: str, default: str | None = None) -> str | None:
            value = os.environ.get(name, "").strip()
            return value or default

        return cls(
            anthropic_model=get("ANTHROPIC_MODEL", "claude-opus-5-5"),
            gemini_api_key=get("GEMINI_API_KEY"),
            gemini_image_model=get("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image"),
            ig_user_id=get("IG_USER_ID"),
            ig_access_token=get("IG_ACCESS_TOKEN"),
            ig_api_version=get("IG_API_VERSION", "v23.0"),
            s3_bucket=get("S3_BUCKET"),
            s3_endpoint_url=get("S3_ENDPOINT_URL"),
            s3_access_key_id=get("S3_ACCESS_KEY_ID"),
            s3_secret_access_key=get("S3_SECRET_ACCESS_KEY"),
            s3_public_base_url=get("S3_PUBLIC_BASE_URL"),
            chromium_executable=get("CHROMIUM_EXECUTABLE"),
            output_dir=Path(get("OUTPUT_DIR", "output")),
        )


def require(value: str | None, name: str) -> str:
    if not value:
        raise SystemExit(f"환경변수 {name} 가 설정되지 않았습니다. .env 파일을 확인하세요.")
    return value
