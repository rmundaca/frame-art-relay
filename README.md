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

## Empaquetar e instalar

```powershell
build.bat -m "Qué cambió"      # dist\frame-art_<versión>_any.apk
```

ADM → App Central → Administración → Instalación manual → subir el `.apk` (requiere Entware instalado).
