import os
import tempfile

# Base de datos aislada para toda la suite (antes de importar app.*)
os.environ.setdefault("APP_DATA_DIR", tempfile.mkdtemp(prefix="app-tests-"))
