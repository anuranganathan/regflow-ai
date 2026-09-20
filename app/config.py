"""Application settings, read from environment variables (and a local .env file).

Secrets are never hard-coded. AWS credentials are deliberately NOT read here:
boto3 finds them itself (env vars -> ~/.aws/credentials -> IAM role).
"""
import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

from app.errors import ConfigError

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
logger = logging.getLogger("regflow.config")


@dataclass(frozen=True)
class Settings:
    storage_mode: str          # "local" or "s3"
    aws_region: str
    s3_bucket_name: str
    gemini_api_key: str
    gemini_model: str
    local_upload_dir: Path     # used when STORAGE_MODE=local
    results_dir: Path          # processing results are kept as JSON files here
    max_upload_mb: int

    @property
    def gemini_enabled(self) -> bool:
        return bool(self.gemini_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings(
        storage_mode=os.getenv("STORAGE_MODE", "local").strip().lower(),
        aws_region=os.getenv("AWS_REGION", "ap-south-1"),
        s3_bucket_name=os.getenv("S3_BUCKET_NAME", ""),
        # GEMINI_API_KEY is preferred; GOOGLE_API_KEY is accepted for older .env files
        gemini_api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", ""),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest"),
        local_upload_dir=BASE_DIR / os.getenv("LOCAL_UPLOAD_DIR", "uploads"),
        results_dir=BASE_DIR / os.getenv("RESULTS_DIR", "results"),
        max_upload_mb=int(os.getenv("MAX_UPLOAD_MB", "10")),
    )


def validate_settings(settings: Settings) -> None:
    """Fail fast at startup if the configuration cannot work."""
    if settings.storage_mode not in ("local", "s3"):
        raise ConfigError(f"STORAGE_MODE must be 'local' or 's3', got '{settings.storage_mode}'.")
    if settings.storage_mode == "s3" and not settings.s3_bucket_name:
        raise ConfigError("STORAGE_MODE=s3 requires the S3_BUCKET_NAME environment variable.")
    if not settings.gemini_enabled:
        logger.warning(
            "GEMINI_API_KEY is not set. Documents will be checked with Python rules only "
            "and every result will be flagged for human review."
        )
