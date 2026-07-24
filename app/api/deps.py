"""FastAPI dependencies: authentication and permission enforcement."""

from fastapi import Depends, Header, HTTPException

from app.security.auth import AuthError, Principal, authenticate


def get_principal(
    authorization: str = Header(default=None),
    x_api_key: str = Header(default=None),
) -> Principal:
    try:
        return authenticate(authorization, x_api_key)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


def require(permission: str):
    def dependency(principal: Principal = Depends(get_principal)) -> Principal:
        if not principal.can(permission):
            raise HTTPException(
                status_code=403,
                detail=f"permission '{permission}' required (roles: {list(principal.roles)})",
            )
        return principal

    return dependency
