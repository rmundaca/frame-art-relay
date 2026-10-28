from datetime import datetime

from sqlalchemy import (Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint,
                        inspect, text)
from sqlalchemy.orm import relationship

from app.core.database import Base


class Tv(Base):
    __tablename__ = "tvs"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    host = Column(String, nullable=False)
    mac = Column(String, nullable=True)
    model = Column(String, nullable=True)
    paired = Column(Boolean, default=False, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    last_state = Column(String, nullable=True)
    last_seen = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    # Signature "album:interval:order" or "off" of the last rotation applied
    applied = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    contents = relationship("TvContent", cascade="all, delete-orphan", passive_deletes=True)


class Album(Base):
    __tablename__ = "albums"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    matte = Column(String, default="none", nullable=False)
    shuffle = Column(Boolean, default=True, nullable=False)
    interval = Column(Integer, default=60, nullable=False)  # minutos
    composition_mode = Column(String, default="off", nullable=False)  # off | auto
    date_stamp = Column(Boolean, default=True, nullable=False)  # date taken on iCloud photos
    background = Column(String, default="paper", nullable=False)  # paper | blur
    single_fit = Column(String, default="crop", nullable=False)  # crop | fit (single photos shown whole)
    subject_detection = Column(Boolean, default=False, nullable=False)  # crops guided by Gemini
    subject_error = Column(String, nullable=True)  # last detection error (code), None if it succeeded
    # Signature of the candidate photos used for the last grouping
    composition_plan = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    sources = relationship("AlbumSource", cascade="all, delete-orphan", passive_deletes=True,
                           order_by="AlbumSource.id")
    # Images belong to the source; slots are deleted by ON DELETE CASCADE
    images = relationship("Image", viewonly=True, order_by="Image.key")


class AlbumSource(Base):
    __tablename__ = "album_sources"

    id = Column(Integer, primary_key=True)
    album_id = Column(Integer, ForeignKey("albums.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = Column(String, default="local", nullable=False)
    path = Column(String, nullable=False)  # NAS folder or iCloud shared album URL
    label = Column(String, nullable=True)  # iCloud album name
    recursive = Column(Boolean, default=False, nullable=False)
    last_scan = Column(DateTime, nullable=True)
    last_error = Column(String, nullable=True)

    images = relationship("Image", cascade="all, delete-orphan", passive_deletes=True)


class Image(Base):
    __tablename__ = "images"
    __table_args__ = (UniqueConstraint("source_id", "key"),)

    id = Column(Integer, primary_key=True)
    album_id = Column(Integer, ForeignKey("albums.id", ondelete="CASCADE"), nullable=False, index=True)
    source_id = Column(Integer, ForeignKey("album_sources.id", ondelete="CASCADE"), nullable=False, index=True)
    key = Column(String, nullable=False)  # path relative to the source
    size = Column(Integer, nullable=True)
    mtime = Column(Float, nullable=True)
    # Dimensions after applying EXIF; cleared when the file changes
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    # EXIF date taken ("YYYY-MM-DDTHH:MM:SS"); "" if none, None if not read yet
    taken_at = Column(String, nullable=True)
    # Subject box from Gemini ("[x0, y0, x1, y1]" in 0-1, "" if none) and version of the analysed photo
    subject_box = Column(String, nullable=True)
    subject_sig = Column(String, nullable=True)
    excluded = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class TvContent(Base):
    """Image uploaded by the app to a TV's "My Photos"."""
    __tablename__ = "tv_contents"
    __table_args__ = (UniqueConstraint("tv_id", "content_id"),)

    id = Column(Integer, primary_key=True)
    tv_id = Column(Integer, ForeignKey("tvs.id", ondelete="CASCADE"), nullable=False, index=True)
    image_id = Column(Integer, ForeignKey("images.id", ondelete="SET NULL"), nullable=True, index=True)
    # Layout uploaded instead of a single image, with the revision the TV has
    page_id = Column(Integer, ForeignKey("composition_pages.id", ondelete="SET NULL"), nullable=True, index=True)
    page_revision = Column(Integer, nullable=True)
    # Variant of the uploaded single image (e.g. with the date drawn); None is the original
    render_sig = Column(String, nullable=True)
    content_id = Column(String, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class CompositionPage(Base):
    """Page rendered from several album photos. The row is the identity; every change creates a revision."""
    __tablename__ = "composition_pages"

    id = Column(Integer, primary_key=True)
    album_id = Column(Integer, ForeignKey("albums.id", ondelete="CASCADE"), nullable=False, index=True)
    template = Column(String, nullable=False)
    signature = Column(String, nullable=False)  # members and versions, template and renderer
    revision = Column(Integer, default=1, nullable=False)
    # pending | ready | error | retired (out of the output; deleted once no TV uses it)
    status = Column(String, default="pending", nullable=False)
    last_error = Column(String, nullable=True)
    rendered_revision = Column(Integer, nullable=True)  # revision whose JPEG exists in the cache
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    members = relationship("CompositionMember", cascade="all, delete-orphan", passive_deletes=True,
                           order_by="CompositionMember.position")


class CompositionMember(Base):
    __tablename__ = "composition_members"
    __table_args__ = (UniqueConstraint("page_id", "position"),)

    id = Column(Integer, primary_key=True)
    page_id = Column(Integer, ForeignKey("composition_pages.id", ondelete="CASCADE"), nullable=False, index=True)
    image_id = Column(Integer, ForeignKey("images.id", ondelete="CASCADE"), nullable=False, index=True)
    position = Column(Integer, nullable=False)  # template cell


class ScheduleSlot(Base):
    __tablename__ = "schedule_slots"

    id = Column(Integer, primary_key=True)
    tv_id = Column(Integer, ForeignKey("tvs.id", ondelete="CASCADE"), nullable=False, index=True)
    album_id = Column(Integer, ForeignKey("albums.id", ondelete="CASCADE"), nullable=False, index=True)
    days = Column(Integer, default=127, nullable=False)  # bit 0 = lunes ... bit 6 = domingo
    start = Column(String, nullable=False)  # "HH:MM"
    end = Column(String, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)


# Columns added after the first release: table -> [(name, SQLite DDL)]
_NEW_COLUMNS = {
    "album_sources": [("label", "VARCHAR")],
    "albums": [("composition_mode", "VARCHAR NOT NULL DEFAULT 'off'"), ("composition_plan", "VARCHAR"),
               ("date_stamp", "BOOLEAN NOT NULL DEFAULT 1"), ("background", "VARCHAR NOT NULL DEFAULT 'paper'"),
               ("single_fit", "VARCHAR NOT NULL DEFAULT 'crop'"), ("subject_detection", "BOOLEAN NOT NULL DEFAULT 0"),
               ("subject_error", "VARCHAR")],
    "images": [("width", "INTEGER"), ("height", "INTEGER"), ("taken_at", "VARCHAR"), ("subject_box", "VARCHAR"),
               ("subject_sig", "VARCHAR")],
    "tv_contents": [("page_id", "INTEGER REFERENCES composition_pages(id) ON DELETE SET NULL"),
                    ("page_revision", "INTEGER"), ("render_sig", "VARCHAR")],
}

# Idempotent statements that fix legacy data
_DATA_FIXES = [
    # "UPDATE albums SET status = 'active' WHERE status IS NULL",
]


def init_db_migrations(engine):
    """Add new columns and fix legacy data in existing SQLite databases."""
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    with engine.begin() as conn:
        for table, cols in _NEW_COLUMNS.items():
            if table not in tables:
                continue
            existing = {c["name"] for c in inspector.get_columns(table)}
            for name, ddl in cols:
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
        for stmt in _DATA_FIXES:
            conn.execute(text(stmt))
