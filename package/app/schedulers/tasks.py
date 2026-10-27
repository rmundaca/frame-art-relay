import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.database import SessionLocal
from app.models.schemas import Album, AlbumSource, Tv
from app.services import composition, rotation, supervisor
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


def rotate_all():
    """Rotación por la app (intervalos menores de 10 min); cada TV decide si le toca cambiar de imagen."""
    db = SessionLocal()
    try:
        for tv in db.query(Tv).filter(Tv.enabled.is_(True)).all():
            try:
                rotation.tick(db, tv)
            except Exception:  # noqa: BLE001 - un TV no debe frenar a los demás
                logger.exception("Rotación TV %s", tv.id)
    finally:
        db.close()


def refresh_sources():
    db = SessionLocal()
    try:
        rescan_all(db)
    except Exception:  # noqa: BLE001
        logger.exception("Reescaneo de fuentes")
    finally:
        db.close()
    compose_all()


def compose_album(album_id: int):
    """Agrupa, genera y limpia las composiciones de un álbum, fuera de las peticiones HTTP."""
    db = SessionLocal()
    try:
        composition.process_album(db, album_id)
    except Exception:  # noqa: BLE001
        logger.exception("Composiciones del álbum %s", album_id)
    finally:
        db.close()


def compose_all():
    """También recupera las páginas que quedaron pendientes tras un reinicio y limpia revisiones viejas."""
    db = SessionLocal()
    try:
        ids = [album_id for (album_id,) in db.query(Album.id).order_by(Album.id)]
    finally:
        db.close()
    for album_id in ids:
        compose_album(album_id)


def refresh_source(source_id: int):
    """Reescaneo de una fuente en segundo plano (las de iCloud descargan fotos y tardan)."""
    db = SessionLocal()
    try:
        source = db.get(AlbumSource, source_id)
        album_id = source.album_id if source else None
        if source:
            rescan_source(db, source)
    except Exception:  # noqa: BLE001
        logger.exception("Reescaneo de la fuente %s", source_id)
        album_id = None
    finally:
        db.close()
    if album_id:
        compose_album(album_id)


def run_now(func, *args):
    """Ejecuta un trabajo en segundo plano lo antes posible (sin bloquear la petición HTTP)."""
    scheduler.add_job(func, args=args, id=f"{func.__name__}-{'-'.join(map(str, args))}",
                      replace_existing=True, max_instances=1, coalesce=True)


def start_scheduler():
    scheduler.add_job(supervise_all, "interval", minutes=1, id="supervise", replace_existing=True,
                      next_run_time=datetime.now() + timedelta(seconds=20), max_instances=1, coalesce=True)
    scheduler.add_job(refresh_sources, "interval", hours=6, id="refresh", replace_existing=True,
                      next_run_time=datetime.now() + timedelta(minutes=2), max_instances=1, coalesce=True)
    scheduler.add_job(compose_all, "interval", minutes=10, id="compose", replace_existing=True,
                      next_run_time=datetime.now() + timedelta(seconds=30), max_instances=1, coalesce=True)
    scheduler.add_job(rotate_all, "interval", seconds=30, id="rotate", replace_existing=True,
                      next_run_time=datetime.now() + timedelta(seconds=45), max_instances=1, coalesce=True)
    scheduler.start()
    logger.info("APScheduler iniciado.")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
