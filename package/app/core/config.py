import os
from pathlib import Path

import yaml

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # package/
CONFIG_PATH = BASE_DIR / "config" / "config.yaml"  # local override, not packaged
DEFAULT_CONFIG_PATH = BASE_DIR / "config" / "config.default.yaml"


def _read_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_config() -> dict:
    config = _read_yaml(DEFAULT_CONFIG_PATH)
    for key, value in _read_yaml(CONFIG_PATH).items():
        if isinstance(value, dict):
            config.setdefault(key, {}).update(value)
        else:
            config[key] = value

    # APP_DATA_DIR isolates the data (tests, alternative installs)
    data_dir = Path(os.getenv("APP_DATA_DIR") or (BASE_DIR / "data")).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    config["data_dir"] = str(data_dir)
    config.setdefault("database", {})["url"] = f"sqlite:///{data_dir / 'app.db'}"
    return config


settings = load_config()
