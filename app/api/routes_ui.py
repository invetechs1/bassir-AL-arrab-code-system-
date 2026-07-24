"""Serve the Arabic RTL web interface."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.config import settings

router = APIRouter(tags=["ui"])

# Explicit allowlist — nothing else in web/ is servable.
UI_FILES = {
    "index.html": "text/html",
    "app.js": "application/javascript",
    "styles.css": "text/css",
}


@router.get("/ui")
def ui_index():
    path = settings.web_dir / "index.html"
    if not path.exists():
        raise HTTPException(status_code=404, detail="UI not installed")
    return FileResponse(path, media_type="text/html")


@router.get("/ui/{asset}")
def ui_asset(asset: str):
    media_type = UI_FILES.get(asset)
    if media_type is None:
        raise HTTPException(status_code=404, detail="asset not found")
    path = settings.web_dir / asset
    if not path.exists():
        raise HTTPException(status_code=404, detail="asset not found")
    return FileResponse(path, media_type=media_type)
