"""Core configuration and environment variable loader."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "dashboard.db"


def load_env(env_path: Path = BASE_DIR / ".env"):
    """Lightweight zero-dependency .env parser."""
    if not env_path.exists():
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val


load_env()


class Config:
    PORT = int(os.getenv("PORT", "8000"))
    CWA_API_KEY = os.getenv("CWA_API_KEY", "").strip()
    GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").strip()
    LLM_API_KEY = os.getenv("LLM_API_KEY", "").strip()
    LLM_MODEL = os.getenv("LLM_MODEL", "gemini-2.5-flash").strip()

    DEFAULT_COUNTY = os.getenv("DEFAULT_COUNTY", "新竹縣").strip()
    DEFAULT_TOWN = os.getenv("DEFAULT_TOWN", "竹東鎮").strip()
    DEFAULT_LAT = float(os.getenv("DEFAULT_LAT", "24.7376"))
    DEFAULT_LNG = float(os.getenv("DEFAULT_LNG", "121.0887"))
    DEFAULT_RADIUS_METERS = int(os.getenv("DEFAULT_RADIUS_METERS", "2500"))

    @classmethod
    def has_valid_key(cls, key_val: str) -> bool:
        return bool(key_val) and not key_val.startswith("your_")
