import re
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.router import api_router
from app.core.config import settings
from app.core.logging import log_request
from app.db.session import engine

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)
    origins = settings.cors_origin_list()
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["DELETE", "GET", "PATCH", "POST", "PUT", "OPTIONS"],
            allow_headers=["Content-Type", "X-CSRF-Token", "X-Request-ID", "X-User-Public-ID"],
            expose_headers=["X-Request-ID"],
        )

    @app.middleware("http")
    async def request_observability(request: Request, call_next):
        request_id = _request_id(request.headers.get("X-Request-ID"))
        request.state.request_id = request_id
        started_at = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:  # noqa: BLE001 - HTTP boundary must convert unknown faults safely.
            duration_ms = (time.perf_counter() - started_at) * 1_000
            log_request(
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                status_code=500,
                duration_ms=duration_ms,
                failed=True,
            )
            return JSONResponse(
                status_code=500,
                content={"detail": "internal-server-error", "request_id": request_id},
                headers={"X-Request-ID": request_id},
            )
        response.headers["X-Request-ID"] = request_id
        log_request(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=(time.perf_counter() - started_at) * 1_000,
        )
        return response

    app.include_router(api_router, prefix="/api/v1")

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready", tags=["health"])
    def ready() -> JSONResponse:
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except SQLAlchemyError:
            return JSONResponse(status_code=503, content={"status": "unavailable"})
        return JSONResponse(content={"status": "ready"})

    return app


def _request_id(candidate: str | None) -> str:
    """Accept a bounded trace identifier or generate an unguessable replacement."""
    if candidate and REQUEST_ID_PATTERN.fullmatch(candidate):
        return candidate
    return str(uuid.uuid4())


app = create_app()
