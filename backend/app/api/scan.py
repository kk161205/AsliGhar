from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.models.schemas import ScanResponse

router = APIRouter(prefix="/api/v1", tags=["scan"])


@router.post("/scan", response_model=ScanResponse)
async def create_scan(
    photos: list[UploadFile] = File(...),
    address: str = Form(...),
    city: str = Form(...),
    rent: int = Form(...),
    bhk: str | None = Form(None),
    description: str | None = Form(None),
) -> ScanResponse:
    raise HTTPException(status_code=501, detail="scan pipeline not yet implemented")


@router.get("/scan/{scan_id}", response_model=ScanResponse)
async def get_scan(scan_id: str) -> ScanResponse:
    raise HTTPException(status_code=404, detail="scan not found")
