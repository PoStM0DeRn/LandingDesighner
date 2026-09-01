import logging
import logging.handlers
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.api.routes import auth, generate, landings, models, skills
from app.config import settings

# --- logging: console + rotating file --------------------------------------
_logs_dir = Path(settings.storage_dir) / "logs"
_logs_dir.mkdir(parents=True, exist_ok=True)
_file_handler = logging.handlers.RotatingFileHandler(
    _logs_dir / "backend.log", maxBytes=1_000_000, backupCount=5, encoding="utf-8"
)
_file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(), _file_handler],
)

logger = logging.getLogger(__name__)

app = FastAPI(title="Landing Generator API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(landings.router)
app.include_router(generate.router)
app.include_router(models.router)
app.include_router(skills.router)


@app.get("/api/health")
def health():
    """Diagnostics: ComfyUI reachable, npm available, storage writable."""
    from app.engine.tailwind_builder import is_npm_available
    from app.mcp.comfyui_api import ComfyUIClient

    storage_ok = True
    try:
        probe = settings.landings_dir / ".probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except Exception:
        storage_ok = False

    return {
        "status": "ok",
        "comfyui": ComfyUIClient().is_available_sync(),
        "npm": is_npm_available(),
        "storage_ok": storage_ok,
        "version": app.version,
    }


# --- frontend (single origin in production) ---------------------------------
# Registered LAST so it never shadows API routes or /docs.
_dist = Path(settings.frontend_dist_dir)
if settings.serve_frontend and _dist.exists():

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        candidate = None
        if full_path:
            resolved = (_dist / full_path).resolve()
            try:
                resolved.relative_to(_dist.resolve())
            except ValueError:
                resolved = None  # path traversal attempt
            if resolved is not None and resolved.is_file():
                candidate = resolved
        if candidate is not None:
            return FileResponse(candidate)
        return FileResponse(_dist / "index.html", media_type="text/html")

    logger.info("Serving frontend from %s", _dist)


# --- startup tasks -----------------------------------------------------------

@app.on_event("startup")
def recover_orphaned_generations() -> None:
    try:
        from app.core.watchdog import mark_orphaned_generations
        fixed = mark_orphaned_generations()
        if fixed:
            logger.warning("Watchdog recovered %d orphaned generations", fixed)
    except Exception as e:
        logger.warning("Watchdog skipped: %s", e)


@app.on_event("startup")
def prewarm_tailwind() -> None:
    def _run() -> None:
        try:
            from app.engine.tailwind_builder import prewarm
            prewarm()
        except Exception as e:
            logger.warning("Tailwind prewarm skipped: %s", e)

    threading.Thread(target=_run, daemon=True).start()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.api_host, port=settings.api_port, reload=True)
