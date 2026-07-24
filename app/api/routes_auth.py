"""Token issuance for database users."""

from fastapi import APIRouter, HTTPException

from app.api.schemas import TokenRequest
from app.audit import log_action
from app.config import settings
from app.db.base import SessionLocal
from app.db.models import User
from app.security.auth import create_access_token, verify_password

router = APIRouter(prefix="/v1/auth", tags=["auth"])


@router.post("/token")
def issue_token(body: TokenRequest):
    if settings.is_production and not settings.secret_key_is_secure:
        raise HTTPException(status_code=503, detail="server SECRET_KEY not configured securely")

    session = SessionLocal()
    try:
        user = session.query(User).filter_by(email=body.email, is_active=True).first()
    finally:
        session.close()

    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid credentials")

    token = create_access_token(user.email, user.tenant_id, [user.role])
    log_action(user.tenant_id, user.email, "auth.token_issued")
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": settings.jwt_expires_minutes * 60,
        "role": user.role,
        "tenant_id": user.tenant_id,
    }
