import os
import time

from app.services import image_host


def test_cleanup_expired_never_deletes_gitkeep(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(image_host, "STATIC_DIR", tmp_path)
    gitkeep = tmp_path / ".gitkeep"
    gitkeep.write_text("")
    old_time = time.time() - 3600
    os.utime(gitkeep, (old_time, old_time))

    image_host.cleanup_expired(ttl_minutes=1)

    assert gitkeep.exists()


def test_cleanup_expired_deletes_old_uploads(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(image_host, "STATIC_DIR", tmp_path)
    stale = tmp_path / "stale.jpg"
    stale.write_bytes(b"data")
    old_time = time.time() - 3600
    os.utime(stale, (old_time, old_time))

    image_host.cleanup_expired(ttl_minutes=1)

    assert not stale.exists()
