import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api import albums, schedule, settings as settings_api, tvs
from app.core.config import settings
from app.core.database import Base, engine
from app.models.schemas import init_db_migrations
from app.schedulers.tasks import start_scheduler, stop_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

Base.metadata.create_all(bind=engine)
init_db_migrations(engine)

app = FastAPI(title="Frame Art", version=__version__)
app.add_middleware(GZipMiddleware, minimum_size=1000)

for module in (albums, tvs, schedule, settings_api):
    app.include_router(module.router)

STATIC_DIR = Path(__file__).resolve().parent / "static"


class RevalidatedStaticFiles(StaticFiles):
    """Obliga al navegador a revalidar (304 si no cambió): tras actualizar el paquete no quedan JS/CSS viejos."""

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache"
        return response


app.mount("/static", RevalidatedStaticFiles(directory=str(STATIC_DIR)), name="static")


@app.on_event("startup")
def on_startup():
    start_scheduler()


@app.on_event("shutdown")
def on_shutdown():
    stop_scheduler()


@app.get("/api/health")
def health():
    return {"status": "ok", "version": __version__}


@app.get("/")
def serve_index():
    return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-cache"})


if __name__ == "__main__":
    import uvicorn
    cfg = settings.get("app", {})
    uvicorn.run("app.main:app", host=cfg.get("host", "0.0.0.0"), port=cfg.get("port", 8092), workers=1)
