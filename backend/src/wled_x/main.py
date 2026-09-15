import logging
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select
from starlette.exceptions import HTTPException as StarletteHTTPException

from wled_x.api import (
    nodes_registry,
    routes_audio,
    routes_color_schemes,
    routes_devices,
    routes_discovery,
    routes_effects,
    routes_fixtures,
    routes_playlists,
    routes_preview,
    routes_scenes,
    ws,
)
from wled_x.config import settings
from wled_x.db import engine, init_db
from wled_x.effects.engine import start_render_loop, stop_render_loop
from wled_x.examples import seed_example_effects
from wled_x.models.effect import Effect

logging.basicConfig(level=logging.INFO)


def _resolve_frontend_dist() -> Path | None:
    """Where to find a built frontend (`npm run build`'s `dist/`), if any --
    see `Settings.frontend_dist`. Checked for an `index.html` rather than just
    existing, so an empty/half-built directory doesn't get mounted."""
    default_dir = Path(__file__).parent / "static"
    candidate = Path(settings.frontend_dist) if settings.frontend_dist else default_dir
    return candidate if (candidate / "index.html").is_file() else None


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    with Session(engine) as session:
        # Only on a genuinely empty DB (first-ever launch) -- once seeded,
        # deleting one of these is a deliberate choice, not something to
        # silently undo on the next restart.
        if session.exec(select(Effect)).first() is None:
            seed_example_effects(session)
    if settings.render_enabled:
        start_render_loop()
    yield
    if settings.render_enabled:
        await stop_render_loop()


def create_app() -> FastAPI:
    app = FastAPI(title="WLED-X", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(routes_audio.router)
    app.include_router(routes_devices.router)
    app.include_router(routes_discovery.router)
    app.include_router(routes_fixtures.router)
    app.include_router(routes_effects.router)
    app.include_router(routes_preview.router)
    app.include_router(routes_scenes.router)
    app.include_router(routes_color_schemes.router)
    app.include_router(routes_playlists.router)
    app.include_router(routes_playlists.phrase_router)
    app.include_router(nodes_registry.router)
    app.include_router(ws.router)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    # A packaged build (see packaging/appimage) drops a built frontend next to
    # this package; plain `uv run wled-x` dev usage has none, so this is a
    # no-op there and Vite's own dev server keeps serving :5173 as before.
    frontend_dist = _resolve_frontend_dist()
    if frontend_dist is not None:
        app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")

        @app.exception_handler(StarletteHTTPException)
        async def spa_fallback(request: Request, exc: StarletteHTTPException):
            # react-router paths (e.g. /devices) aren't real files under
            # frontend_dist, so the static mount above 404s on them -- hand
            # those back index.html so client-side routing can take over.
            # Actual API 404s (e.g. a deleted effect's id) fall through to
            # the normal JSON error response.
            if exc.status_code == 404 and not request.url.path.startswith(("/api", "/ws")):
                return FileResponse(frontend_dist / "index.html")
            return await http_exception_handler(request, exc)

    return app


app = create_app()


def run() -> None:
    uvicorn.run(
        "wled_x.main:app", host=settings.host, port=settings.port, reload=settings.reload
    )


if __name__ == "__main__":
    run()
