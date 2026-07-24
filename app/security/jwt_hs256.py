"""Minimal HS256 JWT implementation on the standard library.

Deliberately dependency-free: the deployment targets (Ubuntu VPS, slim
Docker images) sometimes ship broken native `cryptography` wheels, and
HS256 needs nothing beyond hmac/hashlib. Tokens are interoperable with
any standard JWT library.
"""

import base64
import hashlib
import hmac
import json
import time


class JWTError(Exception):
    pass


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def encode(payload: dict, secret: str, expires_in_seconds: int = 3600) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    body = dict(payload)
    now = int(time.time())
    body.setdefault("iat", now)
    body.setdefault("exp", now + expires_in_seconds)

    segments = [
        _b64url_encode(json.dumps(header, separators=(",", ":")).encode()),
        _b64url_encode(json.dumps(body, separators=(",", ":")).encode()),
    ]
    signing_input = ".".join(segments).encode("ascii")
    signature = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    segments.append(_b64url_encode(signature))
    return ".".join(segments)


def decode(token: str, secret: str) -> dict:
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
    except ValueError:
        raise JWTError("malformed token")

    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    expected = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    try:
        provided = _b64url_decode(signature_b64)
    except Exception:
        raise JWTError("malformed signature")
    if not hmac.compare_digest(expected, provided):
        raise JWTError("invalid signature")

    try:
        header = json.loads(_b64url_decode(header_b64))
        payload = json.loads(_b64url_decode(payload_b64))
    except Exception:
        raise JWTError("malformed payload")

    if header.get("alg") != "HS256":
        raise JWTError("unsupported algorithm")
    exp = payload.get("exp")
    if exp is not None and time.time() > float(exp):
        raise JWTError("token expired")
    return payload
