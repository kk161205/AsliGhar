from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.services import evidence, image_host, scan_service


@pytest.fixture(autouse=True)
def _clean_fetch_record():
    image_host._fetched_at.clear()
    yield
    image_host._fetched_at.clear()


def test_a_successful_download_is_recorded_and_a_miss_is_not(tmp_path: Path) -> None:
    (tmp_path / "seen.jpg").write_bytes(b"jpeg-bytes")
    app = FastAPI()
    app.mount("/static/scans", image_host.TrackingStaticFiles(directory=tmp_path))
    client = TestClient(app)

    assert client.get("/static/scans/seen.jpg").status_code == 200
    assert client.get("/static/scans/missing.jpg").status_code == 404

    assert image_host.was_fetched("seen.jpg")
    assert not image_host.was_fetched("missing.jpg")


def test_a_photo_nobody_downloaded_has_its_lens_result_discarded() -> None:
    image_host.mark_fetched("fetched.jpg")
    empty_result = {"exact_matches": []}

    checked = scan_service._discard_unretrieved(
        [empty_result, empty_result], [Path("fetched.jpg"), Path("never_fetched.jpg")]
    )

    assert checked[0] is empty_result
    assert isinstance(checked[1], image_host.PhotoNotRetrieved)


def test_a_failed_lens_call_is_left_as_the_failure_it_already_is() -> None:
    error = TimeoutError("t")
    assert scan_service._discard_unretrieved([error], [Path("x.jpg")]) == [error]


def test_no_photo_being_downloaded_makes_the_image_check_unavailable_not_clean() -> None:
    lens_results = scan_service._discard_unretrieved(
        [{"exact_matches": []}], [Path("never_fetched.jpg")]
    )
    signal, matches = evidence.extract_image_reuse(
        lens_results, submitted_price=15000, submitted_city="Bengaluru"
    )
    assert signal.status == "unavailable"
    assert "weren't found" not in signal.finding
    assert matches == []


def test_expired_fetch_records_are_pruned() -> None:
    image_host._fetched_at["old.jpg"] = 0.0
    image_host.mark_fetched("new.jpg")
    image_host.cleanup_expired(ttl_minutes=15)
    assert not image_host.was_fetched("old.jpg")
    assert image_host.was_fetched("new.jpg")
