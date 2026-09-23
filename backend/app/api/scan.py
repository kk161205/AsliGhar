import logging
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from app.core.auth_deps import get_current_user
from app.core.rate_limit import limiter
from app.models.db import User
from app.models.schemas import PrecheckRequest, ScanResponse, ScanSummary
from app.services import input_gate, insights, scan_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["scan"])

MIN_PHOTOS = 1
MAX_PHOTOS = 5
MAX_PHOTO_BYTES = 5 * 1024 * 1024
MAX_LISTING_URL_CHARS = 500
ALLOWED_PHOTO_CONTENT_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
# The client-declared content-type is just a header — cheap to fake or get
# wrong. A magic-number check on the actual bytes is the minimum bar before
# trusting an upload enough to write it to disk and serve it back publicly.
_MAGIC_SIGNATURES: dict[str, tuple[bytes, ...]] = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
}


def _matches_declared_type(content: bytes, content_type: str) -> bool:
    if content_type == "image/webp":
        return content[:4] == b"RIFF" and content[8:12] == b"WEBP"
    return any(content.startswith(sig) for sig in _MAGIC_SIGNATURES.get(content_type, ()))


async def _read_and_validate_photos(photos: list[UploadFile]) -> list[tuple[bytes, str]]:
    if not MIN_PHOTOS <= len(photos) <= MAX_PHOTOS:
        logger.warning("Scan rejected: %s photos submitted, need %s-%s", len(photos), MIN_PHOTOS, MAX_PHOTOS)
        raise HTTPException(
            status_code=422, detail=f"Submit between {MIN_PHOTOS} and {MAX_PHOTOS} photos."
        )

    contents: list[tuple[bytes, str]] = []
    for photo in photos:
        suffix = ALLOWED_PHOTO_CONTENT_TYPES.get(photo.content_type or "")
        if suffix is None:
            logger.warning("Scan rejected: unsupported photo type=%s", photo.content_type)
            raise HTTPException(
                status_code=422, detail=f"Unsupported photo type: {photo.content_type}"
            )
        content = await photo.read()
        if len(content) > MAX_PHOTO_BYTES:
            logger.warning("Scan rejected: photo %s exceeds %s bytes", photo.filename, MAX_PHOTO_BYTES)
            raise HTTPException(status_code=422, detail=f"Photo {photo.filename} exceeds 5MB.")
        if not _matches_declared_type(content, photo.content_type or ""):
            logger.warning(
                "Scan rejected: photo %s's content doesn't match declared type=%s",
                photo.filename,
                photo.content_type,
            )
            raise HTTPException(status_code=422, detail=f"{photo.filename} isn't a valid image file.")
        contents.append((content, suffix))
    return contents


@router.post(
    "/scan/precheck",
    response_model=input_gate.GateResult,
    dependencies=[Depends(get_current_user)],
)
async def precheck_scan(body: PrecheckRequest) -> input_gate.GateResult:
    """Free, instant check of the inputs, so a typo is caught before a scan is paid for."""
    return input_gate.evaluate(body.rent)


def _clean_listing_url(url: str | None) -> str | None:
    """The pasted listing link, if it is an http(s) URL. It is only ever used as a search query."""
    url = (url or "").strip()
    if not url:
        return None
    parsed = urlparse(url)
    if len(url) > MAX_LISTING_URL_CHARS or parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise HTTPException(status_code=422, detail="Enter the listing link as a full web address (https://…).")
    return url


def _clean_phone(phone: str | None) -> str | None:
    if not (phone or "").strip():
        return None
    normalized = insights.normalize_phone(phone)
    if normalized is None:
        raise HTTPException(status_code=422, detail="Enter a 10-digit Indian mobile number.")
    return normalized


def _override_reason_for(rent: int, override_reason: str | None) -> str | None:
    """Apply the input gate: refuse, demand a reason, or let the scan through.

    The reason is only recorded when the gate actually asked for one, and it
    never reaches scoring.
    """
    gate = input_gate.evaluate(rent)
    if gate.status == "rejected":
        logger.warning("Scan rejected: rent=%s is not a possible monthly rent", rent)
        raise HTTPException(status_code=422, detail=gate.issues[0].message)
    if gate.status == "ok":
        return None
    reason = (override_reason or "").strip()
    if len(reason) < input_gate.MIN_OVERRIDE_REASON_CHARS:
        logger.warning("Scan rejected: unusual rent=%s submitted without a stated reason", rent)
        raise HTTPException(
            status_code=422,
            detail=(
                f"{gate.issues[0].message} To scan it anyway, say why "
                f"(at least {input_gate.MIN_OVERRIDE_REASON_CHARS} characters)."
            ),
        )
    logger.info("Unusual rent=%s accepted with a stated reason", rent)
    return reason


@router.post("/scan", response_model=ScanResponse)
@limiter.limit("10/hour")
async def create_scan(
    request: Request,
    photos: list[UploadFile] = File(...),
    address: str = Form(...),
    city: str = Form(...),
    rent: int = Form(...),
    bhk: str | None = Form(None),
    description: str | None = Form(None),
    override_reason: str | None = Form(None, max_length=input_gate.MAX_OVERRIDE_REASON_CHARS),
    listing_url: str | None = Form(None),
    phone: str | None = Form(None),
    current_user: User = Depends(get_current_user),
) -> ScanResponse:
    # Before any photo is read or search paid for.
    reason = _override_reason_for(rent, override_reason)
    link = _clean_listing_url(listing_url)
    contact = _clean_phone(phone)
    validated_photos = await _read_and_validate_photos(photos)
    return await scan_service.run_scan(
        photos=validated_photos,
        address=address,
        city=city,
        rent=rent,
        bhk=bhk,
        description=description,
        user_id=current_user.id,
        override_reason=reason,
        listing_url=link,
        phone=contact,
    )


@router.get("/scan/{scan_id}", response_model=ScanResponse)
async def get_scan(scan_id: str) -> ScanResponse:
    # Intentionally not behind get_current_user — a shareable permalink by
    # design, unlike /scans below.
    scan = await scan_service.get_scan(scan_id)
    if scan is None:
        logger.info("Scan lookup miss: scan_id=%s", scan_id)
        raise HTTPException(status_code=404, detail="Scan not found.")
    return scan


@router.get("/scans", response_model=list[ScanSummary])
async def list_scans(current_user: User = Depends(get_current_user)) -> list[ScanSummary]:
    return await scan_service.list_recent_scans(current_user.id)


@router.delete("/scans/{scan_id}", status_code=204)
async def delete_scan(scan_id: str, current_user: User = Depends(get_current_user)) -> None:
    deleted = await scan_service.delete_scan(scan_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Scan not found.")
