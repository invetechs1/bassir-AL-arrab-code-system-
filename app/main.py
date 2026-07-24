"""FastAPI application factory for Alarrab CodeVision AI."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse

from app.api import (
    routes_advisory, routes_assess, routes_auth, routes_rules,
    routes_system, routes_ui,
)
from app.config import settings
from app.db.base import init_db
from app.security.headers import apply_security_headers
from app.security.rate_limit import RateLimiter
from app.version import APP_NAME, __version__

rate_limiter = RateLimiter(settings.rate_limit_per_minute)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.ensure_dirs()
    init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=APP_NAME,
        version=__version__,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url=None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", "X-API-Key"],
    )

    @app.middleware("http")
    async def security_middleware(request: Request, call_next):
        client_key = request.headers.get("x-api-key") or (
            request.client.host if request.client else "unknown"
        )
        if not rate_limiter.allow(client_key):
            response = JSONResponse(
                status_code=429,
                content={"detail": "rate limit exceeded, retry later"},
            )
        else:
            response = await call_next(request)
        apply_security_headers(response.headers)
        return response

    app.include_router(routes_system.router)
    app.include_router(routes_auth.router)
    app.include_router(routes_assess.router)
    app.include_router(routes_advisory.router)
    app.include_router(routes_rules.router)
    app.include_router(routes_ui.router)

    @app.get("/", include_in_schema=False)
    def root():
        return RedirectResponse(url="/ui")

    return app


app = create_app()
