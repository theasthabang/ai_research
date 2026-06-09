"""app/routers/ingest.py — POST /ingest endpoint."""
import os, re, shutil, traceback, logging
from fastapi import APIRouter, File, HTTPException, UploadFile
from app.ingest import ingest_pdf, UPLOAD_DIR

router = APIRouter()
log    = logging.getLogger("ai-research-helper.ingest-router")


def _safe_remove(path):
    try:
        if os.path.exists(path): os.remove(path)
    except Exception: pass


@router.post("/ingest", status_code=201)
async def ingest_document(file: UploadFile = File(...)):
    if not file or not file.filename:
        raise HTTPException(400, "No file uploaded.")
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are supported.")

    safe_name = re.sub(r"[^A-Za-z0-9._\- ()]+", "_",
                       os.path.basename(file.filename)).strip()
    if not safe_name.lower().endswith(".pdf"):
        safe_name += ".pdf"

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(UPLOAD_DIR, safe_name)

    try:
        with open(file_path, "wb") as buf:
            shutil.copyfileobj(file.file, buf)
    except Exception as exc:
        raise HTTPException(500, f"Could not save file: {exc}")
    finally:
        try: file.file.close()
        except Exception: pass

    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        raise HTTPException(400, "Uploaded file is empty.")

    try:
        chunks = ingest_pdf(file_path)
        if chunks == 0:
            _safe_remove(file_path)
            raise HTTPException(422, "No extractable text found.")
        return {"status": "success", "chunks_added": chunks}
    except HTTPException:
        raise
    except Exception as exc:
        log.error("Ingestion error:\n%s", traceback.format_exc())
        _safe_remove(file_path)
        raise HTTPException(500, f"{type(exc).__name__}: {exc}")