"""Syncs a TV's "My Photos" with the album of the active slot."""
import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.schemas import Album, TvContent
from app.services.albums import album_images, image_file  # noqa: F401 - album_images is re-exported
from app.services.composition import effective_output, page_file, render_single, row_key

logger = logging.getLogger("sync")


@dataclass
class SyncResult:
    uploaded: int = 0
    deleted: int = 0
    pending: int = 0
    on_tv: int = 0

    @property
    def changed(self) -> bool:
        return bool(self.uploaded or self.deleted)


def reconcile(db: Session, tv_id: int, on_tv: set) -> list:
    """Forget uploads that are no longer on the TV (deleted by hand) and return the ones that remain."""
    rows = db.query(TvContent).filter(TvContent.tv_id == tv_id).all()
    alive = []
    for row in rows:
        if row.content_id in on_tv:
            alive.append(row)
        else:
            db.delete(row)
    db.commit()
    return alive


def _delete(db: Session, tv_id: int, client, rows: list) -> tuple:
    client.delete([r.content_id for r in rows])
    on_tv = {p["content_id"] for p in client.my_photos()}
    deleted = sum(1 for r in rows if r.content_id not in on_tv)
    return deleted, reconcile(db, tv_id, on_tv)


def purge_orphans(db: Session, tv_id: int, client) -> int:
    """Delete from the TV what the app uploaded for albums that no longer exist. Returns how many were deleted."""
    albums = {a for (a,) in db.query(Album.id)}
    rows = db.query(TvContent).filter(TvContent.tv_id == tv_id).all()
    orphans = [r for r in rows if r.album_id not in albums]
    if not orphans:
        return 0
    return _delete(db, tv_id, client, orphans)[0]


def sync_tv(db: Session, tv, album: Album, client) -> SyncResult:
    """Upload what is missing from the album output (in batches) and retire this album's stale content.

    Content from other albums stays on the TV, so switching back does not upload it again; it is only deleted when
    its album is deleted (purge_orphans). Older content from this same album (originals that now go in a layout,
    old page revisions, excluded photos, variants without the date or with another date) is retired only once the
    new output is fully rendered and uploaded: a failure never leaves the TV with an empty or incomplete output.
    """
    result = SyncResult()
    rows = reconcile(db, tv.id, {p["content_id"] for p in client.my_photos()})
    output = effective_output(db, album)
    if not output.current:
        # The grouping does not reflect the current photos yet: wait for the layout task
        result.pending = output.total
        result.on_tv = sum(1 for r in rows if r.album_id == album.id)
        return result

    desired = {item.key for item in output.items}
    own = [r for r in rows if r.album_id == album.id and row_key(r) not in desired]
    have = {row_key(r) for r in rows if r.album_id == album.id}
    missing = [item for item in output.items if item.key not in have]
    batch = int(settings.get("frame", {}).get("uploads_per_tick", 10))
    for item in missing[:batch]:
        try:
            if item.page:
                data = page_file(album.id, item.page.id, item.page.revision).read_bytes()
            else:
                data = render_single(image_file(db, item.image), item)
        except (ValueError, OSError) as exc:
            logger.warning("Salida %s omitida: %s", item.key, exc)
            # A layout without a file blocks retiring the old content; an unreadable original does not
            if item.page:
                result.pending += 1
            continue
        content_id = client.upload(data, album.matte)
        if item.page:
            row = TvContent(tv_id=tv.id, page_id=item.page.id, page_revision=item.page.revision,
                            content_id=content_id)
        else:
            row = TvContent(tv_id=tv.id, image_id=item.image.id, render_sig=item.key[2] or None,
                            content_id=content_id)
        row.album_id, row.size = album.id, len(data)
        db.add(row)
        db.commit()
        rows.append(row)
        result.uploaded += 1
    result.pending += max(0, len(missing) - batch)

    own = [r for r in own if r in rows]
    if own and output.complete and not result.pending:
        deleted, rows = _delete(db, tv.id, client, own)
        result.deleted += deleted
    result.on_tv = sum(1 for r in rows if r.album_id == album.id)
    return result
