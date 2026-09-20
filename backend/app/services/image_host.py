import time
import uuid
from pathlib import Path

from starlette.staticfiles import StaticFiles

STATIC_DIR = Path(__file__).resolve().parents[2] / "static" / "scans"
STATIC_DIR.mkdir(parents=True, exist_ok=True)

# Which uploaded photos an outside client has actually downloaded, and when.
# Lens answers "Success, zero matches" whether or not it could fetch the image
# (confirmed: identical responses for an unreachable localhost photo and a
# reachable one), so the response can't say if the photo was even seen — our
# own access record is the only ground truth. In-memory and per-process, which
# is fine: a scan starts and finishes inside one process.
_fetched_at: dict[str, float] = {}


class PhotoNotRetrieved(Exception):
    """The image search never requested this photo, so its "no matches" means nothing."""


def mark_fetched(filename: str) -> None:
    _fetched_at[filename] = time.time()


def was_fetched(filename: str) -> bool:
    return filename in _fetched_at


class TrackingStaticFiles(StaticFiles):
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            mark_fetched(Path(path).name)
        return response


def save_upload(content: bytes, suffix: str = ".jpg") -> Path:
    filename = f"{uuid.uuid4().hex}{suffix}"
    path = STATIC_DIR / filename
    path.write_bytes(content)
    return path


def cleanup_expired(ttl_minutes: int) -> None:
    cutoff = time.time() - ttl_minutes * 60
    for name in [name for name, fetched_at in _fetched_at.items() if fetched_at < cutoff]:
        del _fetched_at[name]
    for file in STATIC_DIR.glob("*"):
        if file.name == ".gitkeep":
            continue
        if file.is_file() and file.stat().st_mtime < cutoff:
            file.unlink(missing_ok=True)
