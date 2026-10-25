"""Cliente de Samsung The Frame (API de arte 0.97, modelo 2019) sobre samsungtvws.

Particularidades verificadas en la fase 0 (ver PLAN.md):
- El canal de arte no siempre envía ms.channel.ready: no se espera.
- El TV ignora en silencio peticiones desconocidas y sus ping impiden que salte el timeout del socket:
  cada operación lleva un vigilante que cierra el socket al vencer el plazo.
- El TV atiende un solo canal de arte: las operaciones de un mismo TV se serializan con un RLock.
"""
import logging
import socket
import threading
from contextlib import contextmanager
from pathlib import Path

import requests
import urllib3
from samsungtvws import SamsungTVWS, exceptions
from samsungtvws.art import SamsungTVArt
from samsungtvws.connection import SamsungTVWSConnection

from app.core.config import settings

logger = logging.getLogger("tv")
# Certificado autofirmado del TV en el puerto 8002
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

MY_PHOTOS = "MY-C0002"
CLIENT_NAME = "FrameArt"
MATTES = ["none"] + [f"{style}_{color}" for style in ("modern", "shadowbox") for color in (
    "black", "neutral", "antique", "warm", "polar", "sand", "seafoam", "sage", "burgandy", "navy")]
# Intervalos de rotación (minutos) que acepta el modelo 2019
INTERVALS = [10, 30, 60, 360, 720, 1440, 4320]

_locks = {}
_locks_guard = threading.Lock()


class TvError(Exception):
    """Error con código estable para la API (tv_unavailable, tv_busy, tv_not_paired, tv_timeout)."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _lock_for(host: str) -> threading.RLock:
    with _locks_guard:
        return _locks.setdefault(host, threading.RLock())


class _FrameArt(SamsungTVArt):
    def open(self):
        return SamsungTVWSConnection.open(self)

    def get_api_version(self):
        # El firmware 2019 no responde a "api_version" (la petición nueva que la librería prueba primero)
        data = self._request_json("get_api_version")
        return data.get("version", data) if isinstance(data, dict) else data


class TvClient:
    def __init__(self, host: str, token_file: Path):
        cfg = settings.get("frame", {})
        self.host = host
        self.token_file = Path(token_file)
        self.timeout = float(cfg.get("request_timeout", 15))
        self.upload_timeout = float(cfg.get("upload_timeout", 120))

    # ------------------------------------------------------------ helpers

    @contextmanager
    def session(self, wait: float = 60):
        """Reserva el TV para una secuencia de operaciones."""
        lock = _lock_for(self.host)
        if not lock.acquire(timeout=wait):
            raise TvError("tv_busy")
        try:
            yield self
        finally:
            lock.release()

    @property
    def paired(self) -> bool:
        return self.token_file.exists() and bool(self.token_file.read_text().strip())

    @contextmanager
    def _art(self, deadline: float = None):
        if not self.paired:
            raise TvError("tv_not_paired")
        deadline = deadline or self.timeout
        with self.session():
            art = _FrameArt(host=self.host, port=8002, token_file=str(self.token_file),
                            timeout=deadline, name=CLIENT_NAME)
            fired = threading.Event()

            def kill():
                fired.set()
                conn = art.connection
                if conn is not None and getattr(conn, "sock", None) is not None:
                    try:
                        conn.sock.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass

            timer = threading.Timer(deadline, kill)
            timer.daemon = True
            timer.start()
            try:
                yield art
            except TvError:
                raise
            except Exception as exc:
                if fired.is_set():
                    raise TvError("tv_timeout") from None
                logger.info("TV %s: %s: %s", self.host, type(exc).__name__, exc)
                raise TvError("tv_unavailable") from None
            finally:
                timer.cancel()
                try:
                    art.close()
                except Exception:  # noqa: BLE001
                    pass

    # --------------------------------------------------------------- REST

    def rest_info(self) -> dict:
        resp = requests.get(f"http://{self.host}:8001/api/v2/", timeout=3)
        resp.raise_for_status()
        return resp.json().get("device", {})

    def state(self) -> str:
        """offline | standby | art | tv (en uso o arrancando) | on (sin emparejar)."""
        try:
            power = self.rest_info().get("PowerState", "on")
        except (requests.RequestException, ValueError):
            return "offline"
        if power != "on":
            return "standby"
        if not self.paired:
            return "on"
        try:
            with self._art(deadline=8) as art:
                return "art" if art.get_artmode() == "on" else "tv"
        except TvError as exc:
            if exc.code == "tv_busy":
                raise
            return "tv"

    # ---------------------------------------------------------- operaciones

    def pair(self) -> bool:
        """Abre el canal de control remoto: el TV (en modo TV) pide permiso y entrega el token."""
        self.token_file.parent.mkdir(parents=True, exist_ok=True)
        with self.session():
            remote = SamsungTVWS(host=self.host, port=8002, token_file=str(self.token_file),
                                 timeout=30, name=CLIENT_NAME)
            try:
                remote.open()
            except Exception as exc:  # noqa: BLE001
                logger.info("Emparejamiento con %s falló: %s", self.host, exc)
                return False
            finally:
                try:
                    remote.close()
                except Exception:  # noqa: BLE001
                    pass
        return self.paired

    def my_photos(self) -> list:
        with self._art() as art:
            return [p for p in art.available(MY_PHOTOS) if p.get("content_id")]

    def upload(self, data: bytes, matte: str) -> str:
        with self._art(deadline=self.upload_timeout) as art:
            return art.upload(data, matte=matte, portrait_matte=matte, file_type="jpg")

    def delete(self, content_ids: list) -> None:
        if content_ids:
            with self._art() as art:
                art.delete_list(content_ids)

    def thumbnail(self, content_id: str) -> bytes:
        with self._art(deadline=self.upload_timeout) as art:
            data = art.get_thumbnail(content_id)
        if not data:
            raise TvError("tv_unavailable")
        return bytes(data)

    def set_rotation(self, minutes: int, shuffle: bool) -> None:
        with self._art() as art:
            try:
                art.set_auto_rotation_status(duration=minutes, type=shuffle, category_id=MY_PHOTOS)
            except exceptions.ResponseError:
                # Firmwares más nuevos solo conocen el nombre actual del comando
                art.set_slideshow_status(duration=minutes, type=shuffle, category_id=MY_PHOTOS)

    def wake(self, mac: str) -> None:
        raw = bytes.fromhex(mac.replace(":", "").replace("-", ""))
        packet = b"\xff" * 6 + raw * 16
        targets = {"255.255.255.255", self.host.rsplit(".", 1)[0] + ".255", self.host}
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            for addr in targets:
                try:
                    sock.sendto(packet, (addr, 9))
                except OSError:
                    pass


def token_path(tv_id: int) -> Path:
    return Path(settings["data_dir"]) / "tokens" / f"tv-{tv_id}.txt"


def client_for(tv) -> TvClient:
    return TvClient(tv.host, token_path(tv.id))
