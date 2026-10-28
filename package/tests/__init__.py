import os
import tempfile

# Isolated database for the whole suite (before importing app.*)
os.environ.setdefault("APP_DATA_DIR", tempfile.mkdtemp(prefix="app-tests-"))
