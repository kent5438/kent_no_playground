"""Core configuration and environment variable loader."""
import os
import socket
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "dashboard.db"


def load_env(env_path: Path = PROJECT_ROOT / ".env"):
    """Lightweight zero-dependency .env parser."""
    for candidate in (env_path, BASE_DIR / ".env"):
        if not candidate.exists():
            continue
        with open(candidate, "r", encoding="utf-8") as f:
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


def get_lan_ips() -> list:
    """Detect local area network (LAN) IPv4 addresses for cross-device / mobile access."""
    ips = []
    # Method 1: UDP socket routing table lookup (no actual traffic sent)
    for target in (("8.8.8.8", 80), ("10.255.255.255", 1)):
        s = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.2)
            s.connect(target)
            ip = s.getsockname()[0]
            if ip and not ip.startswith("127.") and ip != "0.0.0.0" and ip not in ips:
                ips.append(ip)
        except Exception:
            pass
        finally:
            if s:
                try:
                    s.close()
                except Exception:
                    pass

    # Method 2: Hostname resolution fallback
    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if ip and not ip.startswith("127.") and ip != "0.0.0.0" and ip not in ips:
                ips.append(ip)
    except Exception:
        pass

    # Method 3: Parse /sbin/ifconfig output (works on macOS/Linux even without socket routing)
    if not ips:
        import re
        import subprocess
        for cmd in (["/sbin/ifconfig"], ["ifconfig"]):
            try:
                out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True, timeout=1.5)
                for found_ip in re.findall(r"inet\s+(\d+\.\d+\.\d+\.\d+)", out):
                    if not found_ip.startswith("127.") and found_ip != "0.0.0.0" and found_ip not in ips:
                        ips.append(found_ip)
                if ips:
                    break
            except Exception:
                pass

    return ips


class Config:
    # 一律將 Host 綁定為 0.0.0.0（取代預設的 localhost），確保手機與同區網裝置可直接連線
    HOST = "0.0.0.0"
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
