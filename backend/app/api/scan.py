import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from app.core.auth_deps import get_current_user
from app.core.rate_limit import limiter
from app.models.db import User
from app.models.schemas import ScanResponse, ScanSummary
from app.services import scan_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["scan"])

MIN_PHOTOS = 1
MAX_PHOTOS = 5
MAX_PHOTO_BYTES = 5 * 1024 * 1024
ALLOWED_PHOTO_CONTENT_TYPES = {"image/jpeg": ".jpg", "image/png": ".png"}


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
        contents.append((content, suffix))
    return contents


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
    current_user: User = Depends(get_current_user),
) -> ScanResponse:
    validated_photos = await _read_and_validate_photos(photos)
    return await scan_service.run_scan(
        photos=validated_photos,
        address=address,
        city=city,
        rent=rent,
        bhk=bhk,
        description=description,
        user_id=current_user.id,
    )


@router.get("/scan/{scan_id}", response_model=ScanResponse)
async def get_scan(scan_id: str) -> ScanResponse:
    # Intentionally not behind get_current_user — a shareable permalink by
    # design, unlike /scans below.
    scan = await scan_service.get_scan(scan_id)
    if scan is None:
        logger.info("Scan lookup miss: scan_id=%s", scan_id)
        raise HTTPException(status_code=404, detail="scan not found")
    return scan


@router.get("/scans", response_model=list[ScanSummary])
async def list_scans(current_user: User = Depends(get_current_user)) -> list[ScanSummary]:
    return await scan_service.list_recent_scans(current_user.id)
