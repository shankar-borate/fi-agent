from pydantic import BaseModel
from typing import Any, Dict, List, Optional
from datetime import datetime


class GeoPoint(BaseModel):
    latitude: float
    longitude: float
    timestamp: str


class DeviceInfo(BaseModel):
    user_agent:  str = ""
    browser:     str = ""
    os:          str = ""
    device_type: str = ""
    screen_size: str = ""
    language:    str = ""


class BasicInfo(BaseModel):
    first_name:    str   = ""
    last_name:     str   = ""
    dob:           str   = ""   # ISO date string
    address:       str   = ""
    city:          str   = ""
    pan_number:    str   = ""
    mobile_number: str   = ""
    income_range:  str   = ""   # e.g. "5-20L"
    loan_amount:   float = 0.0  # in INR


class QuestionAnswer(BaseModel):
    question: str
    answer:   str
    geo:      Optional[GeoPoint] = None


class PhotoMeta(BaseModel):
    prompt:     str
    filename:   str
    is_selfie:  bool           = False
    tag:        str            = ""     # "selfie","kitchen","bedroom1","nameplate","pan",…
    geo:        Optional[GeoPoint]  = None
    blur_score: Optional[float]     = None
    ocr_text:   Optional[str]       = None   # raw OCR text for nameplate / signage


class DocumentMeta(BaseModel):
    document_type: str          # e.g. "bank_statement"
    filename:      str
    uploaded_at:   Optional[str] = None


class SessionMetadata(BaseModel):
    session_id:         str
    device_id:          Optional[str]        = None
    started_at:         str
    ended_at:           str
    basic_info:         Optional[BasicInfo]  = None
    device_info:        Optional[DeviceInfo] = None
    questions:          List[QuestionAnswer] = []
    photos:             List[PhotoMeta]      = []
    documents:          List[DocumentMeta]   = []
    recording_filename: Optional[str]    = None


class PhotoUploadResponse(BaseModel):
    status: str
    filename: str


class SessionUploadResponse(BaseModel):
    session_id: str
    status: str
    session_folder: str
    files_saved: List[str]
    message: str
