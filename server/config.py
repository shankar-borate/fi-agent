import json
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Storage
    storage_root: str = "D:\\fig"
    host: str = "0.0.0.0"
    port: int = 8000
    max_upload_size_mb: int = 500

    # AWS
    aws_region: str = "us-east-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    polly_voice_id: str = "Kajal"
    transcribe_language_code: str = "en-IN"

    # Transcription engine — "aws" or "sarvam"
    transcribe_engine: str = "aws"
    sarvam_api_key: str = ""

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    # Google Maps — reverse geocoding for Location Report
    google_maps_api_key: str = ""

    # Credit thresholds (configurable)
    fi_cibil_threshold:      int   = 800   # score >= this is shown as "Good" in green
    fi_face_match_threshold: float = 30.0  # Rekognition similarity % to call it a match

    # Bank statement vault — PDFs stored as {vault_root}/{mobile_number}/*.pdf
    # The pipeline reads these automatically after submit (no user upload needed).
    fi_bank_vault_root: str = "D:\\bank-vault"

    # Geo verification — all captured points must lie within this radius
    # of the session centroid to be considered at the same location.
    geo_radius_meters: float = 500.0

    # Session behaviour
    fi_countdown_seconds: int = 5
    fi_listen_timeout_ms: int = 12000
    fi_pan_max_attempts:  int = 3      # OCR retry limit for PAN card

    fi_self_photo_prompt: str = (
        "Please look straight at the camera. I will take your photo now."
    )
    fi_pan_photo_prompt: str = (
        "Please hold your PAN card flat in front of the back camera. "
        "Ensure the PAN number, your name, father's name, and date of birth are all clearly visible."
    )

    # Blur rejection threshold — Laplacian score below this triggers a retake
    fi_blur_threshold: float = 40.0

    fi_questions_json: str = json.dumps([
        "Please confirm your full name.",
        "What is your residential PIN code?",
        "What is the name of your city?",
    ])
    fi_photo_prompts_json: str = json.dumps([
        "Please show your home nameplate or door nameplate clearly so the name and address text is readable.",
        "Please show your kitchen.",
        "Please show Bedroom 1.",
        "Please show Bedroom 2.",
        "Please show the hall or living room.",
        "Please show the front outside view of your home.",
        "Please show another outside view of your home.",
    ])

    @property
    def fi_questions(self) -> List[str]:
        return json.loads(self.fi_questions_json)

    @property
    def fi_photo_prompts(self) -> List[str]:
        return json.loads(self.fi_photo_prompts_json)

    class Config:
        env_file    = ".env"
        env_prefix  = "FI_"

    def __post_init_validate__(self) -> None:
        """Called after construction to assert invariants."""
        assert self.fi_countdown_seconds >= 1, "FI_COUNTDOWN_SECONDS must be >= 1"
        assert self.fi_pan_max_attempts  >= 1, "FI_PAN_MAX_ATTEMPTS must be >= 1"
        assert self.geo_radius_meters    >  0, "FI_GEO_RADIUS_METERS must be positive"
        assert self.fi_blur_threshold    >= 0, "FI_BLUR_THRESHOLD must be non-negative"


settings = Settings()


def get_storage_root() -> Path:
    root = Path(settings.storage_root)
    root.mkdir(parents=True, exist_ok=True)
    return root


def get_reports_dir() -> Path:
    """Reports are stored under <project>/reports/ — created on first use."""
    d = Path("reports")
    d.mkdir(parents=True, exist_ok=True)
    return d
