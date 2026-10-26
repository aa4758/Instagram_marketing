from __future__ import annotations

from pathlib import Path
from typing import Protocol


class ImageProvider(Protocol):
    """배경 이미지 생성기. Gemini 외 다른 서비스도 이 인터페이스로 교체한다."""

    def generate(
        self,
        prompt: str,
        *,
        aspect_ratio: str = "4:5",
        reference_images: list[Path] | None = None,
    ) -> bytes:
        """이미지 바이트(PNG/JPEG)를 반환한다."""
        ...
