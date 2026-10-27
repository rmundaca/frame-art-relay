# Asustor App Template

Esqueleto funcional para apps web autohospedadas en un NAS **Asustor AS-202TE** (ADM 3.5.x, i686 32-bit, 1 GB RAM): FastAPI + SQLite + SPA vanilla estilo iOS, empaquetada como `.apk` de App Central.

La especificación completa (reglas de plataforma, convenciones, sistema visual, despliegue) está en [ASUSTOR_AS202TE_APP_TEMPLATE.md](ASUSTOR_AS202TE_APP_TEMPLATE.md).

## Crear un proyecto nuevo

1. Copia esta carpeta completa (sin `.git/`, `dist/` ni `package/data/`) con el nombre del proyecto.
2. Reemplaza los marcadores de la **sección 0** de la plantilla: `mi-app`, `Mi App`, `MiApp`, `8090`, `ma_` y los datos de autoría.
3. Sustituye `assets/icon-source.png` (1024×1024) y ejecuta `python tools/make_icons.py` (requiere `pip install Pillow`).
4. Reemplaza el ejemplo `items` (modelo, router, pantallas) por el dominio de la app.
5. Recorre el checklist de la **sección 12**.

## Desarrollo local (Windows, Python 3.11)

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\pip install -r package\requirements.txt
cd package
..\.venv\Scripts\python -m uvicorn app.main:app --reload --port 8092
..\.venv\Scripts\python -m unittest discover -s tests -t .
```

## Álbumes compartidos de iCloud

Se admiten enlaces públicos `https://photos.icloud.com/shared/album/...` (CloudKit)
y `https://www.icloud.com/sharedalbum/#...` (Shared Streams), sin iniciar sesión.
En las opciones de compartir del álbum, permite **Cualquier persona con el enlace**
o activa **Sitio web público**. Los álbumes privados o con enlaces caducados no se pueden leer.
Las fotos se descargan como JPEG a la caché del directorio de datos, hasta el límite
`icloud.max_photos`; los vídeos se omiten. Los enlaces de descarga temporales se
renuevan en cada reescaneo. Ambas integraciones usan servicios internos de Apple
que pueden cambiar.

Con **Fecha en las fotos de iCloud** (activada por defecto en cada álbum), cada foto de iCloud
que llega al TV lleva abajo a la derecha la fecha en que se tomó (`YYYY-MM-DD`, del EXIF
`DateTimeOriginal`). En las composiciones va en cada foto. Las fotos sin fecha y las de carpetas
del NAS se envían sin marca. La fuente es Inter (licencia OFL, `app/assets/fonts/`).

## Composiciones automáticas

Con **Composición automática** activada en un álbum, la app agrupa dos o tres fotos en una
imagen de 3840x2160 (dos o tres verticales, dos panorámicas apiladas, una vertical con una o dos
horizontales) y envía al TV esa imagen en lugar de las fotos sueltas. Para aprovechar el lienzo,
cada foto se recorta al centro como mucho un 15 % por eje; nunca se deforma. Las fotos sin una
combinación adecuada se envían solas. Los originales y sus exclusiones no cambian; las imágenes
generadas van a `data/cache/compositions/`. Borrar una composición desde la galería del TV
excluye sus fotos del álbum.

Cada álbum tiene además dos ajustes de presentación:
- **Fotos sueltas:** *Recortar a pantalla completa* (como siempre) o *Mostrar completas*. Con la
  segunda, las verticales y panorámicas que van solas se muestran enteras (con el mismo recorte
  limitado) sobre el fondo. Las horizontales que casi llenan la pantalla (4:3, 3:2, 16:9) se
  siguen recortando.
- **Fondo:** *Papel* (gris cálido) o *Desenfocado*, hecho con las propias fotos.
- **Detectar el sujeto con Gemini** (opcional, desactivado por defecto): antes de recortar, la
  app pregunta a Gemini dónde están las personas o animales de cada foto y orienta el recorte
  para conservarlos. Envía a Google una copia de 768 px como máximo, sin EXIF ni ubicación; cada
  foto se consulta una sola vez. La clave, el modelo (`gemini-flash-latest` por defecto) y un
  tope diario de consultas se configuran en **Ajustes** y se guardan en `data/gemini.json`. Si
  Gemini falla, se recorta al centro y se reintenta más tarde.

## Rotación

Cada álbum tiene un intervalo. De 10 minutos en adelante (10 min, 30 min, 1 h, 6 h, 12 h, 1 día y
3 días) usa el slideshow nativo del TV. Con **1, 2, 3 o 5 minutos**, que el TV no admite, la app
desactiva el slideshow y cambia ella la imagen. Solo lo hace con la pantalla encendida, y solo con
las fotos del álbum. Cualquier conexión al canal de arte enciende la pantalla aunque el sensor de
movimiento la haya apagado, así que, si el TV no responde (pantalla apagada o TV apagado), la app
no lo toca hasta que vuelve a encenderse.

## Empaquetar e instalar

```powershell
build.bat -m "Qué cambió"      # dist\frame-art_<versión>_any.apk
```

ADM → App Central → Administración → Instalación manual → subir el `.apk` (requiere Entware instalado).
