import json
import aiofiles
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import get_storage_root
from models.fi_session import SessionMetadata


def _session_folder(session_id: str) -> Path:
    root = get_storage_root()
    folder = root / session_id
    folder.mkdir(parents=True, exist_ok=True)
    return folder


async def save_file(session_id: str, filename: str, data: bytes) -> Path:
    folder = _session_folder(session_id)
    dest = folder / filename
    async with aiofiles.open(dest, "wb") as f:
        await f.write(data)
    return dest


async def save_metadata(session_id: str, meta: SessionMetadata) -> Path:
    folder = _session_folder(session_id)
    dest = folder / "metadata.json"
    async with aiofiles.open(dest, "w", encoding="utf-8") as f:
        await f.write(meta.model_dump_json(indent=2))
    return dest


async def save_response(case_id: str, filename: str, content: str) -> Path:
    """Save a text response (AI analysis, geo JSON, etc.) under {case_id}/responses/."""
    folder = _session_folder(case_id) / "responses"
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / filename
    async with aiofiles.open(dest, "w", encoding="utf-8") as f:
        await f.write(content)
    return dest


def list_session_files(session_id: str) -> List[str]:
    folder = _session_folder(session_id)
    return [f.name for f in folder.iterdir() if f.is_file()]


async def save_session_data_json(
    session_id:       str,
    meta:             SessionMetadata,
    geo_result:       Dict[str, Any],
    address:          str,
    pan_verification: Optional[Dict[str, Any]],
    nameplate_ocr:    Optional[Dict[str, Any]],
    income_analysis:  Optional[Dict[str, Any]],
    credit_analysis:  Optional[Dict[str, Any]] = None,
    cibil_score:      Optional[Dict[str, Any]] = None,
) -> Path:
    """
    Write a comprehensive, denormalised session_data.json that is the single
    source of truth for all captured information.  This file is stored at:
      {storage_root}/{session_id}/session_data.json
    """
    bi = meta.basic_info

    def _geo(g) -> Optional[Dict]:
        if not g:
            return None
        return {"latitude": g.latitude, "longitude": g.longitude, "timestamp": g.timestamp}

    photos_data = []
    for ph in meta.photos:
        entry: Dict[str, Any] = {
            "filename":   ph.filename,
            "tag":        ph.tag or "",
            "prompt":     ph.prompt,
            "is_selfie":  ph.is_selfie,
            "geo":        _geo(ph.geo),
            "blur_score": ph.blur_score,
            "ocr_text":   ph.ocr_text,
        }
        # Attach face match if this is the selfie
        if ph.is_selfie and pan_verification and "face_match" in pan_verification:
            entry["face_match"] = pan_verification["face_match"]
        # Attach nameplate OCR
        if (ph.tag == "nameplate" or "nameplate" in ph.prompt.lower()) and nameplate_ocr:
            entry["nameplate_ocr"] = nameplate_ocr
        photos_data.append(entry)

    doc = {
        "case_id":      session_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "bank":         "ABC Bank",
        "product":      "Personal Loan",

        "basic_info": {
            "first_name":   bi.first_name   if bi else "",
            "last_name":    bi.last_name    if bi else "",
            "full_name":    f"{bi.first_name} {bi.last_name}".strip() if bi else "",
            "dob":          bi.dob          if bi else "",
            "address":      bi.address      if bi else "",
            "city":         bi.city         if bi else "",
            "pan_number":    bi.pan_number    if bi else "",
            "mobile_number": bi.mobile_number if bi else "",
            "income_range":  bi.income_range  if bi else "",
        },

        "session": {
            "started_at":  meta.started_at,
            "ended_at":    meta.ended_at,
            "device_id":   meta.device_id or "",
            "recording":   meta.recording_filename or "",
            "device_info": {
                "browser":      meta.device_info.browser      if meta.device_info else "",
                "os":           meta.device_info.os           if meta.device_info else "",
                "device_type":  meta.device_info.device_type  if meta.device_info else "",
                "screen_size":  meta.device_info.screen_size  if meta.device_info else "",
                "language":     meta.device_info.language     if meta.device_info else "",
                "user_agent":   meta.device_info.user_agent   if meta.device_info else "",
            },
        },

        "interview": [
            {
                "question": qa.question,
                "answer":   qa.answer,
                "geo":      _geo(qa.geo),
            }
            for qa in meta.questions
        ],

        "photos": photos_data,

        "pan_verification": pan_verification or {},

        "income_document": {
            "documents": [
                {"type": d.document_type, "filename": d.filename, "uploaded_at": d.uploaded_at}
                for d in meta.documents
            ],
            "analysis": income_analysis or {},
        },

        "location": {
            "address":             address,
            "centroid_lat":        geo_result.get("centroid_lat"),
            "centroid_lon":        geo_result.get("centroid_lon"),
            "max_pairwise_m":      geo_result.get("max_pairwise_distance_m"),
            "points_checked":      geo_result.get("points_checked"),
            "status":              "PASS" if geo_result.get("verified") else "FAIL",
            "details":             geo_result.get("details", []),
        },

        "credit_analysis": credit_analysis or {},
        "cibil_score":     cibil_score     or {},
    }

    folder = _session_folder(session_id)
    dest   = folder / "session_data.json"
    async with aiofiles.open(dest, "w", encoding="utf-8") as f:
        await f.write(json.dumps(doc, indent=2, default=str))
    return dest
