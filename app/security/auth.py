"""Authentication principals: JWT bearer tokens and static API keys.

API keys are configured via the API_KEYS env var as comma-separated
"key:tenant_id:role" entries — never hardcoded. When AUTH_REQUIRED is
false (local demo mode only) unauthenticated requests are mapped to a
demo viewer/engineer principal in the "demo" tenant.
"""

import hashlib
import hmac
import os
from dataclasses import dataclass, field

from app.config import settings
from app.security import jwt_hs256
from app.security.rbac import has_permission


class AuthError(Exception):
    def __init__(self, message: str, status_code: int = 401):
        super().__init__(message)
        self.status_code = status_code


@dataclass
class Principal:
    subject: str
    tenant_id: str
    roles: tuple = ("viewer",)
    auth_method: str = "none"
    claims: dict = field(default_factory=dict)

    def can(self, permission: str) -> bool:
        return has_permission(self.roles, permission)


DEMO_PRINCIPAL = Principal(
    subject="demo-user",
    tenant_id="demo",
    roles=("engineer",),
    auth_method="demo-mode",
)


def hash_password(password: str, salt: bytes = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return f"pbkdf2_sha256$200000${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt_hex, digest_hex = stored.split("$")
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations)
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def create_access_token(subject: str, tenant_id: str, roles) -> str:
    return jwt_hs256.encode(
        {"sub": subject, "tenant_id": tenant_id, "roles": list(roles)},
        settings.secret_key,
        expires_in_seconds=settings.jwt_expires_minutes * 60,
    )


def _principal_from_token(token: str) -> Principal:
    try:
        claims = jwt_hs256.decode(token, settings.secret_key)
    except jwt_hs256.JWTError as exc:
        raise AuthError(f"invalid token: {exc}")
    return Principal(
        subject=str(claims.get("sub", "")),
        tenant_id=str(claims.get("tenant_id", "")),
        roles=tuple(claims.get("roles", ["viewer"])),
        auth_method="jwt",
        claims=claims,
    )


def _principal_from_api_key(key: str) -> Principal:
    for entry in settings.api_keys:
        parts = entry.split(":")
        if len(parts) != 3:
            continue
        configured_key, tenant_id, role = parts
        if hmac.compare_digest(configured_key, key):
            return Principal(
                subject=f"api-key:{tenant_id}",
                tenant_id=tenant_id,
                roles=(role,),
                auth_method="api-key",
            )
    raise AuthError("invalid API key")


def authenticate(authorization_header: str = None, api_key_header: str = None) -> Principal:
    if authorization_header:
        scheme, _, token = authorization_header.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise AuthError("expected 'Authorization: Bearer <token>'")
        return _principal_from_token(token.strip())
    if api_key_header:
        return _principal_from_api_key(api_key_header.strip())
    if not settings.auth_required:
        return DEMO_PRINCIPAL
    raise AuthError("authentication required")
