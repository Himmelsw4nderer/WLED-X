import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
from wled_x.db import init_db
from wled_x.effects.engine import start_render_loop, stop_render_loop

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
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

    return app


app = create_app()


def run() -> None:
    uvicorn.run("wled_x.main:app", host=settings.host, port=settings.port, reload=True)


if __name__ == "__main__":
    run()
