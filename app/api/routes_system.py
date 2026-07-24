"""System endpoints: health, version, production readiness."""

from fastapi import APIRouter, Depends

from app.api.deps import require
from app.api.readiness import production_readiness
from app.config import settings
from app.version import API_VERSION, APP_NAME, APP_VENDOR, __version__

router = APIRouter(prefix="/v1", tags=["system"])


@router.get("/health")
def health():
    return {"status": "ok", "service": APP_NAME, "environment": settings.env}


@router.get("/version")
def version():
    return {
        "name": APP_NAME,
        "vendor": APP_VENDOR,
        "version": __version__,
        "api_version": API_VERSION,
    }


@router.get("/production/readiness")
def readiness(principal=Depends(require("system:read"))):
    return production_readiness()
