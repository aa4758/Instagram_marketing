from __future__ import annotations

from pathlib import Path

from google import genai
from google.genai import types
from PIL import Image

STYLE_SUFFIX = (
    " Instagram feed background, clean composition with empty space for overlaid text,"
    " no text, no letters, no words, no logos, no watermarks."
)


class GeminiImageProvider:
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash-image", client: genai.Client | None = None):
        self.model = model
        self.client = client or genai.Client(api_key=api_key)

    def generate(
        self,
        prompt: str,
        *,
        aspect_ratio: str = "4:5",
        reference_images: list[Path] | None = None,
    ) -> bytes:
        contents: list = [prompt + STYLE_SUFFIX]
        for path in reference_images or []:
            contents.append(Image.open(path))
        if reference_images:
            contents[0] += " Place the provided app screenshot naturally on a smartphone screen in the scene."

        response = self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(aspect_ratio=aspect_ratio),
            ),
        )
        for candidate in response.candidates or []:
            for part in candidate.content.parts or []:
                if part.inline_data and part.inline_data.data:
                    return part.inline_data.data
        raise RuntimeError("Gemini 응답에 이미지가 없습니다. 프롬프트가 정책에 걸렸을 수 있습니다.")
