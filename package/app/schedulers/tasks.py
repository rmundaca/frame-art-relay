import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.database import SessionLocal
from app.models.schemas import AlbumSource, Tv
from app.services import supervisor
from app.services.albums import rescan_all, rescan_source

logger = logging.getLogger("scheduler")
scheduler = BackgroundScheduler()


def supervise_tv(tv_id: int):
    db = SessionLocal()
    try:
        tv = db.get(Tv, tv_id)
        if tv and tv.enabled:
            supervisor.tick(db, tv)
    except Exception:  # noqa: BLE001
        logger.exception("Supervisor TV %s", tv_id)
    finally:
        db.close()


def supervise_all():
    db = SessionLocal()
    try:
        ids = [tv_id for (tv_id,) in db.query(Tv.id).filter(Tv.enabled.is_(True))]
    finally:
        db.close()
    for tv_id in ids:
        supervise_tv(tv_id)


def refresh_sources():
    db = SessionLocal()
    try:
        rescan_all(db)
    except Exception:  # noqa: BLE001
        logger.exception("Reescaneo de fuentes")
    finally:
        db.close()


def refresh_source(source_id: int):
    """Reescaneo de una fuente en segundo plano (las de iCloud descargan fotos y tardan)."""
    db = SessionLocal()
    try:
        source = db.get(AlbumSource, source_id)
        if source:
            rescan_source(db, source)
    except Exception:  # noqa: BLE001
        logger.exception("Reescaneo de la fuente %s", source_id)
    finally:
        db.close()


def run_now(func, *args):
    """Ejecuta un trabajo en segundo plano lo antes posible (sin bloquear la petición HTTP)."""
    scheduler.add_job(func, args=args, id=f"{func.__name__}-{'-'.join(map(str, args))}",
                      replace_existing=True, max_instances=1, coalesce=True)


def start_scheduler():
    scheduler.add_job(supervise_all, "interval", minutes=1, id="supervise", replace_existing=True,
                      next_run_time=datetime.now() + timedelta(seconds=20), max_instances=1, coalesce=True)
    scheduler.add_job(refresh_sources, "interval", hours=6, id="refresh", replace_existing=True,
                      next_run_time=datetime.now() + timedelta(minutes=2), max_instances=1, coalesce=True)
    scheduler.start()
    logger.info("APScheduler iniciado.")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
