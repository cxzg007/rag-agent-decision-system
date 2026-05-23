from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.core.security import require_api_key
from app.schemas.document import DocumentIngestResponse
from app.services.ingestion import ingestion_service

router = APIRouter()


@router.post("/upload", response_model=DocumentIngestResponse, dependencies=[Depends(require_api_key)])
async def upload_document(file: UploadFile = File(...)) -> DocumentIngestResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="filename is required")

    doc_id = uuid4().hex
    suffix = Path(file.filename).suffix.lower()
    target = Path("data/raw") / f"{doc_id}{suffix}"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(await file.read())

    result = await ingestion_service.ingest_file(
        doc_id=doc_id,
        filename=file.filename,
        path=target,
    )
    return result
