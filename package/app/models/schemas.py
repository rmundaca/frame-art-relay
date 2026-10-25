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
    # Firma "album:intervalo:orden" u "off" de la última rotación aplicada
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
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    sources = relationship("AlbumSource", cascade="all, delete-orphan", passive_deletes=True,
                           order_by="AlbumSource.id")
    # Las imágenes pertenecen a la fuente; las franjas se borran por ON DELETE CASCADE
    images = relationship("Image", viewonly=True, order_by="Image.key")


class AlbumSource(Base):
    __tablename__ = "album_sources"

    id = Column(Integer, primary_key=True)
    album_id = Column(Integer, ForeignKey("albums.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = Column(String, default="local", nullable=False)
    path = Column(String, nullable=False)  # carpeta del NAS o URL del álbum compartido de iCloud
    label = Column(String, nullable=True)  # nombre del álbum de iCloud
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
    key = Column(String, nullable=False)  # ruta relativa a la fuente
    size = Column(Integer, nullable=True)
    mtime = Column(Float, nullable=True)
    excluded = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class TvContent(Base):
    """Imagen subida por la app a "Mis fotos" de un TV."""
    __tablename__ = "tv_contents"
    __table_args__ = (UniqueConstraint("tv_id", "content_id"),)

    id = Column(Integer, primary_key=True)
    tv_id = Column(Integer, ForeignKey("tvs.id", ondelete="CASCADE"), nullable=False, index=True)
    image_id = Column(Integer, ForeignKey("images.id", ondelete="SET NULL"), nullable=True, index=True)
    content_id = Column(String, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class ScheduleSlot(Base):
    __tablename__ = "schedule_slots"

    id = Column(Integer, primary_key=True)
    tv_id = Column(Integer, ForeignKey("tvs.id", ondelete="CASCADE"), nullable=False, index=True)
    album_id = Column(Integer, ForeignKey("albums.id", ondelete="CASCADE"), nullable=False, index=True)
    days = Column(Integer, default=127, nullable=False)  # bit 0 = lunes ... bit 6 = domingo
    start = Column(String, nullable=False)  # "HH:MM"
    end = Column(String, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)


# Columnas añadidas después de la primera versión: tabla -> [(nombre, DDL SQLite)]
_NEW_COLUMNS = {
    "album_sources": [("label", "VARCHAR")],
}

# Sentencias idempotentes para corregir datos heredados
_DATA_FIXES = [
    # "UPDATE albums SET status = 'active' WHERE status IS NULL",
]


def init_db_migrations(engine):
    """Agrega columnas nuevas y corrige datos heredados en bases SQLite existentes."""
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
