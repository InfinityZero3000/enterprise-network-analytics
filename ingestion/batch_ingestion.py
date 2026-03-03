"""
Batch Ingestion — tải dữ liệu hàng loạt lên MinIO (S3-compatible)
"""
from pathlib import Path
import boto3
from botocore.client import Config
from loguru import logger
from config.settings import settings


def _s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.minio_endpoint,
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        config=Config(signature_version="s3v4"),
    )


class BatchIngestion:
    RAW_BUCKET = "ena-raw"
    PROCESSED_BUCKET = "ena-processed"

    def __init__(self):
        self.s3 = _s3_client()
        self._ensure_buckets()

    def _ensure_buckets(self):
        existing = {b["Name"] for b in self.s3.list_buckets().get("Buckets", [])}
        for bucket in [self.RAW_BUCKET, self.PROCESSED_BUCKET]:
            if bucket not in existing:
                self.s3.create_bucket(Bucket=bucket)
                logger.info(f"Created bucket: {bucket}")

    def upload_file(self, local_path: str, s3_key: str, bucket: str | None = None) -> bool:
        bucket = bucket or self.RAW_BUCKET
        path = Path(local_path)
        if not path.exists():
            logger.error(f"File not found: {local_path}")
            return False
        try:
            self.s3.upload_file(str(path), bucket, s3_key)
            logger.info(f"Uploaded {local_path} → s3://{bucket}/{s3_key}")
            return True
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            return False

    def upload_directory(self, local_dir: str, prefix: str = "", bucket: str | None = None) -> int:
        bucket = bucket or self.RAW_BUCKET
        base = Path(local_dir)
        count = 0
        for file in base.rglob("*"):
            if file.is_file():
                rel = str(file.relative_to(base))
                key = f"{prefix}/{rel}" if prefix else rel
                if self.upload_file(str(file), key, bucket):
                    count += 1
        logger.info(f"Uploaded {count} files from {local_dir} to s3://{bucket}/{prefix}")
        return count

    def list_objects(self, prefix: str = "", bucket: str | None = None) -> list[dict]:
        bucket = bucket or self.RAW_BUCKET
        resp = self.s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
        return [
            {"key": obj["Key"], "size": obj["Size"], "last_modified": obj["LastModified"]}
            for obj in resp.get("Contents", [])
        ]

    def download_file(self, s3_key: str, local_path: str, bucket: str | None = None) -> bool:
        bucket = bucket or self.RAW_BUCKET
        try:
            Path(local_path).parent.mkdir(parents=True, exist_ok=True)
            self.s3.download_file(bucket, s3_key, local_path)
            logger.info(f"Downloaded s3://{bucket}/{s3_key} → {local_path}")
            return True
        except Exception as e:
            logger.error(f"Download failed: {e}")
            return False
