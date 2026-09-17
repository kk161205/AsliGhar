from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.models.schemas import ScanResponse
from app.services import scan_service

router = APIRouter(prefix="/api/v1", tags=["scan"])

MIN_PHOTOS = 1
MAX_PHOTOS = 5
MAX_PHOTO_BYTES = 5 * 1024 * 1024
ALLOWED_PHOTO_CONTENT_TYPES = {"image/jpeg": ".jpg", "image/png": ".png"}


async def _read_and_validate_photos(photos: list[UploadFile]) -> list[tuple[bytes, str]]:
    if not MIN_PHOTOS <= len(photos) <= MAX_PHOTOS:
        raise HTTPException(
            status_code=422, detail=f"Submit between {MIN_PHOTOS} and {MAX_PHOTOS} photos."
        )

    contents: list[tuple[bytes, str]] = []
    for photo in photos:
        suffix = ALLOWED_PHOTO_CONTENT_TYPES.get(photo.content_type or "")
        if suffix is None:
            raise HTTPException(
                status_code=422, detail=f"Unsupported photo type: {photo.content_type}"
            )
        content = await photo.read()
        if len(content) > MAX_PHOTO_BYTES:
            raise HTTPException(status_code=422, detail=f"Photo {photo.filename} exceeds 5MB.")
        contents.append((content, suffix))
    return contents


@router.post("/scan", response_model=ScanResponse)
async def create_scan(
    photos: list[UploadFile] = File(...),
    address: str = Form(...),
    city: str = Form(...),
    rent: int = Form(...),
    bhk: str | None = Form(None),
    description: str | None = Form(None),
) -> ScanResponse:
    validated_photos = await _read_and_validate_photos(photos)
    return await scan_service.run_scan(
        photos=validated_photos,
        address=address,
        city=city,
        rent=rent,
        bhk=bhk,
        description=description,
    )


@router.get("/scan/{scan_id}", response_model=ScanResponse)
async def get_scan(scan_id: str) -> ScanResponse:
    scan = await scan_service.get_scan(scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail="scan not found")
    return scan
