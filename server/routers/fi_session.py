import asyncio
import json
import logging

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import List, Optional

from models.fi_session import SessionMetadata, SessionUploadResponse, PhotoUploadResponse, DocumentMeta
from services.storage_service import save_file, save_metadata, list_session_files

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/fi-session", tags=["fi-session"])


@router.post("/upload", response_model=SessionUploadResponse)
async def upload_session(
    metadata_json: str = Form(...),
    photos: List[UploadFile] = File(default=[]),
    recording: Optional[UploadFile] = File(default=None),
):
    try:
        meta_dict = json.loads(metadata_json)
        meta = SessionMetadata(**meta_dict)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid metadata: {e}")

    session_id = meta.session_id
    saved: list[str] = []

    # Save photos
    for photo in photos:
        if photo.filename:
            data = await photo.read()
            await save_file(session_id, photo.filename, data)
            saved.append(photo.filename)
            logger.info("[Upload] Photo saved: %s (%d bytes)", photo.filename, len(data))

    # Save recording
    if recording and recording.filename:
        data = await recording.read()
        await save_file(session_id, recording.filename, data)
        saved.append(recording.filename)
        logger.info("[Upload] Recording saved: %s (%d bytes)", recording.filename, len(data))

    # Save metadata JSON
    dest = await save_metadata(session_id, meta)
    saved.append(dest.name)
    logger.info("[Upload] Metadata saved for session %s — %d files total", session_id, len(saved))

    from config import get_storage_root
    folder = str(get_storage_root() / session_id)

    # Kick off report generation in the background so the response is returned immediately
    from services.session_conductor import generate_report_for_session
    asyncio.create_task(generate_report_for_session(session_id, meta))
    logger.info("[Upload] Report generation queued for %s", session_id)

    return SessionUploadResponse(
        session_id=session_id,
        status="success",
        session_folder=folder,
        files_saved=saved,
        message=f"Session {session_id} stored ({len(saved)} files). Report generation started.",
    )


@router.post("/{case_id}/photo", response_model=PhotoUploadResponse)
async def upload_photo(
    case_id:   str,
    photo:     UploadFile = File(...),
    meta_json: str        = Form(...),
):
    """Save a single photo immediately after the field officer taps Save."""
    filename = photo.filename or f"photo_{case_id}.jpg"
    data = await photo.read()
    await save_file(case_id, filename, data)

    # Persist photo metadata alongside the image
    try:
        meta_dict = json.loads(meta_json)
    except Exception:
        meta_dict = {}
    meta_file = filename.rsplit(".", 1)[0] + "_meta.json"
    await save_file(case_id, meta_file, json.dumps(meta_dict, indent=2).encode())

    logger.info("[Photo] Saved %s (%d bytes) for case %s", filename, len(data), case_id)
    return PhotoUploadResponse(status="success", filename=filename)


@router.post("/{case_id}/submit", response_model=SessionUploadResponse)
async def submit_session(
    case_id:       str,
    metadata_json: str                   = Form(...),
    recording:     Optional[UploadFile]  = File(default=None),
):
    """Finalise a session: save recording + metadata and trigger report generation."""
    try:
        meta_dict = json.loads(metadata_json)
        meta = SessionMetadata(**meta_dict)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid metadata: {e}")

    saved: list[str] = []

    if recording and recording.filename:
        data = await recording.read()
        await save_file(case_id, recording.filename, data)
        saved.append(recording.filename)
        logger.info("[Submit] Recording saved: %s (%d bytes)", recording.filename, len(data))

    dest = await save_metadata(case_id, meta)
    saved.append(dest.name)
    logger.info("[Submit] Metadata saved for case %s", case_id)

    from config import get_storage_root
    folder = str(get_storage_root() / case_id)

    from services.session_conductor import generate_report_for_session
    asyncio.create_task(generate_report_for_session(case_id, meta))
    logger.info("[Submit] Report generation queued for %s", case_id)

    return SessionUploadResponse(
        session_id=case_id,
        status="success",
        session_folder=folder,
        files_saved=saved,
        message=f"Session {case_id} submitted ({len(saved)} files). Report generation started.",
    )


@router.post("/{case_id}/document")
async def upload_document(
    case_id:       str,
    document:      UploadFile = File(...),
    document_type: str        = Form("bank_statement"),
):
    """Receive an income document (PDF) uploaded by the field officer during the session."""
    raw_name = document.filename or f"document_{case_id}.pdf"
    # Force a safe filename: strip path separators
    safe_name = raw_name.replace("/", "_").replace("\\", "_")
    data = await document.read()
    await save_file(case_id, safe_name, data)
    logger.info("[Document] Saved %s (%d bytes) for case %s  type=%s",
                safe_name, len(data), case_id, document_type)
    return {"status": "success", "filename": safe_name, "document_type": document_type}


@router.get("/config")
async def get_client_config():
    """Return client-side config flags."""
    from config import settings
    return {
        "transcribe_engine":  settings.transcribe_engine,
        "upload_recording":   settings.fi_upload_recording,
    }


@router.get("/{session_id}/files")
async def list_files(session_id: str):
    files = list_session_files(session_id)
    return {"session_id": session_id, "files": files}
