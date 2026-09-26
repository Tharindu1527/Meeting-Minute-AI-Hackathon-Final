# server/main.py
"""
FastAPI backend for the React frontend.

Run in development:   uvicorn server.main:app --reload --port 8000
In production the built frontend (frontend/dist) is served from the same
server, so the whole app is one process on one port.
"""
import logging
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.pipeline import InputError
from database.mongodb import DatabaseError
from server.auth import require_auth
from server.routes import action_items, assistant, fact_check, meetings, status
from utils.config import is_debug

FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"


def create_app():
    logging.basicConfig(level=logging.DEBUG if is_debug() else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    app = FastAPI(title="Meeting Minutes AI", version="3.0")

    @app.exception_handler(DatabaseError)
    def database_error(_request: Request, exc: DatabaseError):
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.exception_handler(InputError)
    def input_error(_request: Request, exc: InputError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    # Status and sign-in are public; everything else needs a token when APP_PASSWORD is set
    app.include_router(status.router, prefix="/api")
    for module in (meetings, action_items, assistant, fact_check):
        app.include_router(module.router, prefix="/api", dependencies=[Depends(require_auth)])

    if FRONTEND_DIST.is_dir():
        _serve_frontend(app)
    return app


def _serve_frontend(app):
    """Serve the built React app, falling back to index.html for client-side routes"""
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")
    index = FRONTEND_DIST / "index.html"

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            return JSONResponse(status_code=404, content={"detail": "Not found"})
        candidate = (FRONTEND_DIST / path).resolve()
        if path and candidate.is_file() and FRONTEND_DIST.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index)


app = create_app()
