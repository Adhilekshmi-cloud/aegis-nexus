import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"

if ENV_FILE.exists():
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


class Settings:
    app_name = os.getenv("APP_NAME", "Aegis Knowledge Ingestion")
    api_prefix = os.getenv("API_PREFIX", "/api")
    dataset_path = os.getenv("DATASET_PATH", str(PROJECT_ROOT / "aegis-dataset"))
    database_url = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{(PROJECT_ROOT / 'data' / 'aegis_kb.db').as_posix()}",
    )


settings = Settings()
