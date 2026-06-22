import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from ocr_processor import OcrProcessor

_processor: OcrProcessor | None = None

_OCR_API_KEY = os.getenv("OCR_SERVICE_API_KEY", "")
_MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _processor
    _processor = OcrProcessor()
    yield


app = FastAPI(lifespan=lifespan)


def _check_auth(authorization: str | None) -> None:
    """Validate Bearer token when OCR_SERVICE_API_KEY is configured."""
    if not _OCR_API_KEY:
        return  # Auth disabled (dev / unset)
    expected = f"Bearer {_OCR_API_KEY}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.post("/ocr/process")
async def process_image(
    file: UploadFile = File(...),
    belge_tipi: str = Form(default="yakit_fisi"),
    authorization: str | None = Header(default=None),
) -> dict:
    _check_auth(authorization)
    image_bytes = await file.read()
    if len(image_bytes) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Upload exceeds 20 MB limit")
    assert _processor is not None
    return await _processor.process(image_bytes, belge_tipi)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model_loaded": _processor is not None}
