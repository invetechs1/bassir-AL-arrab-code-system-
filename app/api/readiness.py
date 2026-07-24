"""Production readiness self-checks (GET /v1/production/readiness)."""

from app.config import settings
from app.governance.catalog import validate_catalog


def production_readiness() -> dict:
    checks = []

    def check(name: str, ok: bool, detail: str, blocking: bool = True):
        checks.append({"check": name, "ok": bool(ok), "detail": detail, "blocking": blocking})

    check("secret_key_secure", settings.secret_key_is_secure,
          "SECRET_KEY must be a unique random value of 32+ characters (not the dev default)")
    check("auth_required", settings.auth_required,
          "AUTH_REQUIRED must be true in production (demo mode disabled)")
    check("debug_disabled", not settings.debug, "DEBUG must be false in production")
    check("cors_restricted", "*" not in settings.cors_origins,
          f"CORS origins must be explicit (current: {settings.cors_origins})")
    check("rate_limit_enabled", settings.rate_limit_per_minute > 0,
          f"rate limit: {settings.rate_limit_per_minute}/min")
    check("postgres_database", settings.database_url.startswith("postgresql"),
          "production should use PostgreSQL (DATABASE_URL), SQLite is for local demo",
          blocking=settings.is_production)
    check("hsts_enabled", settings.enable_hsts,
          "ENABLE_HSTS should be true behind HTTPS", blocking=False)
    catalog_problems = validate_catalog()
    check("regulatory_catalog_valid", not catalog_problems,
          "catalog problems: " + "; ".join(catalog_problems) if catalog_problems else "catalog well-formed")
    check("upload_limits_configured", settings.max_upload_mb <= 50,
          f"MAX_UPLOAD_MB={settings.max_upload_mb}", blocking=False)

    blockers = [c for c in checks if not c["ok"] and c["blocking"]]
    warnings = [c for c in checks if not c["ok"] and not c["blocking"]]

    return {
        "environment": settings.env,
        "ready_for_production": not blockers,
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
    }
