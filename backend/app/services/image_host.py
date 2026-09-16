import time
import uuid
from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parents[2] / "static" / "scans"
STATIC_DIR.mkdir(parents=True, exist_ok=True)


def save_upload(content: bytes, suffix: str = ".jpg") -> Path:
    filename = f"{uuid.uuid4().hex}{suffix}"
    path = STATIC_DIR / filename
    path.write_bytes(content)
    return path


def cleanup_expired(ttl_minutes: int) -> None:
    cutoff = time.time() - ttl_minutes * 60
    for file in STATIC_DIR.glob("*"):
        if file.is_file() and file.stat().st_mtime < cutoff:
            file.unlink(missing_ok=True)
