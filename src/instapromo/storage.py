from __future__ import annotations

from pathlib import Path


class S3Storage:
    """S3 호환 스토리지(Cloudflare R2 등)에 올리고 공개 URL을 돌려준다.

    Instagram API는 이미지를 직접 받지 않고 공개 URL에서 내려받기 때문에 필요하다.
    """

    def __init__(self, *, bucket: str, public_base_url: str, endpoint_url: str | None,
                 access_key_id: str | None, secret_access_key: str | None):
        try:
            import boto3
        except ImportError as e:  # pragma: no cover
            raise SystemExit("S3 업로드에는 boto3가 필요합니다: pip install 'instapromo[s3]'") from e
        self.bucket = bucket
        self.public_base_url = public_base_url.rstrip("/")
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
        )

    def upload(self, path: Path, key: str) -> str:
        self.client.upload_file(str(path), self.bucket, key, ExtraArgs={"ContentType": "image/jpeg"})
        return f"{self.public_base_url}/{key}"
