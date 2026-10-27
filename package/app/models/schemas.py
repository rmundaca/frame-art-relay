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
    composition_mode = Column(String, default="off", nullable=False)  # off | auto
    date_stamp = Column(Boolean, default=True, nullable=False)  # fecha de la toma en las fotos de iCloud
    background = Column(String, default="paper", nullable=False)  # paper | blur
    single_fit = Column(String, default="crop", nullable=False)  # crop | fit (fotos sueltas completas)
    subject_detection = Column(Boolean, default=False, nullable=False)  # recortes orientados por Gemini
    subject_error = Column(String, nullable=True)  # último error de la detección (código), None si fue bien
    # Firma de las fotos candidatas con la que se calculó la última agrupación
    composition_plan = Column(String, nullable=True)
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
    # Dimensiones tras aplicar EXIF; se borran al cambiar el archivo
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    # Fecha de la toma del EXIF ("YYYY-MM-DDTHH:MM:SS"); "" si no tiene, None si todavía no se leyó
    taken_at = Column(String, nullable=True)
    # Recuadro del sujeto según Gemini ("[x0, y0, x1, y1]" en 0-1, "" si no hay) y versión de la foto analizada
    subject_box = Column(String, nullable=True)
    subject_sig = Column(String, nullable=True)
    excluded = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class TvContent(Base):
    """Imagen subida por la app a "Mis fotos" de un TV."""
    __tablename__ = "tv_contents"
    __table_args__ = (UniqueConstraint("tv_id", "content_id"),)

    id = Column(Integer, primary_key=True)
    tv_id = Column(Integer, ForeignKey("tvs.id", ondelete="CASCADE"), nullable=False, index=True)
    image_id = Column(Integer, ForeignKey("images.id", ondelete="SET NULL"), nullable=True, index=True)
    # Composición subida en lugar de una imagen individual, con la revisión que tiene el TV
    page_id = Column(Integer, ForeignKey("composition_pages.id", ondelete="SET NULL"), nullable=True, index=True)
    page_revision = Column(Integer, nullable=True)
    # Variante de la imagen individual subida (por ejemplo, con la fecha dibujada); None es la original
    render_sig = Column(String, nullable=True)
    content_id = Column(String, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class CompositionPage(Base):
    """Página generada con varias fotos de un álbum. La identidad es la fila; cada cambio crea una revisión."""
    __tablename__ = "composition_pages"

    id = Column(Integer, primary_key=True)
    album_id = Column(Integer, ForeignKey("albums.id", ondelete="CASCADE"), nullable=False, index=True)
    template = Column(String, nullable=False)
    signature = Column(String, nullable=False)  # integrantes y versiones, plantilla y renderizador
    revision = Column(Integer, default=1, nullable=False)
    # pending | ready | error | retired (fuera de la salida; se borra cuando ningún TV la usa)
    status = Column(String, default="pending", nullable=False)
    last_error = Column(String, nullable=True)
    rendered_revision = Column(Integer, nullable=True)  # revisión cuyo JPEG existe en la caché
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
    position = Column(Integer, nullable=False)  # celda de la plantilla


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
    "albums": [("composition_mode", "VARCHAR NOT NULL DEFAULT 'off'"), ("composition_plan", "VARCHAR"),
               ("date_stamp", "BOOLEAN NOT NULL DEFAULT 1"), ("background", "VARCHAR NOT NULL DEFAULT 'paper'"),
               ("single_fit", "VARCHAR NOT NULL DEFAULT 'crop'"), ("subject_detection", "BOOLEAN NOT NULL DEFAULT 0"),
               ("subject_error", "VARCHAR")],
    "images": [("width", "INTEGER"), ("height", "INTEGER"), ("taken_at", "VARCHAR"), ("subject_box", "VARCHAR"),
               ("subject_sig", "VARCHAR")],
    "tv_contents": [("page_id", "INTEGER REFERENCES composition_pages(id) ON DELETE SET NULL"),
                    ("page_revision", "INTEGER"), ("render_sig", "VARCHAR")],
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
