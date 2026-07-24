"""Environment-driven settings. No secrets are hardcoded here.

Every value can be overridden via environment variables (see .env.example).
The insecure development SECRET_KEY default is refused when ENV=production
by the production-readiness checks and by token issuance.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DEV_SECRET_PLACEHOLDER = "dev-insecure-secret-change-me"


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "") or default)
    except ValueError:
        return default


def _list(name: str, default: str) -> list:
    raw = os.environ.get(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


class Settings:
    def __init__(self) -> None:
        self.env = os.environ.get("ENV", "development").strip().lower()
        self.debug = _bool("DEBUG", self.env != "production")

        self.secret_key = os.environ.get("SECRET_KEY", DEV_SECRET_PLACEHOLDER)
        self.jwt_expires_minutes = _int("JWT_EXPIRES_MINUTES", 60)
        self.auth_required = _bool("AUTH_REQUIRED", self.env == "production")
        # Comma-separated "key:tenant_id:role" entries, e.g. "abc123:demo:engineer"
        self.api_keys = _list("API_KEYS", "")

        self.database_url = os.environ.get(
            "DATABASE_URL", f"sqlite:///{BASE_DIR / 'alarrab.db'}"
        )

        self.cors_origins = _list("CORS_ORIGINS", "http://localhost:8000")
        self.rate_limit_per_minute = _int("RATE_LIMIT_PER_MINUTE", 120)
        self.enable_hsts = _bool("ENABLE_HSTS", self.env == "production")

        self.max_upload_mb = _int("MAX_UPLOAD_MB", 10)
        self.allowed_upload_extensions = _list(
            "ALLOWED_UPLOAD_EXTENSIONS", ".pdf,.png,.jpg,.jpeg,.ifc,.dxf,.json"
        )

        self.storage_dir = Path(os.environ.get("STORAGE_DIR", BASE_DIR / "storage"))
        self.uploads_dir = self.storage_dir / "uploads"
        self.reports_dir = self.storage_dir / "reports"

        self.data_dir = Path(os.environ.get("DATA_DIR", BASE_DIR / "data"))
        self.web_dir = Path(os.environ.get("WEB_DIR", BASE_DIR / "web"))

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def secret_key_is_secure(self) -> bool:
        return self.secret_key != DEV_SECRET_PLACEHOLDER and len(self.secret_key) >= 32

    def ensure_dirs(self) -> None:
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
