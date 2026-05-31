"""
ReportPipeline — orchestrates all post-submission analysis steps.

Design principles
─────────────────
• Single Responsibility: each private method owns exactly one analysis step.
• Open/Closed: new steps are added as new methods; existing steps are not modified.
• Dependency Inversion: all external services are injected via the constructor
  (or resolved lazily on first use) so the pipeline is testable without real AWS/OpenAI.

Pipeline steps (in order):
  1.  Geo verification (haversine centroid + spread)
  2.  Reverse geocode (Google Maps)
  3.  Nameplate OCR (AWS Textract)
  4.  PAN verification (Textract OCR + NSDL mock + Rekognition face match)
  5.  Property image analysis (OpenAI GPT-4o Vision)
  6.  Bank statement income analysis (pdfplumber + GPT-4)
  7.  Comprehensive credit analysis (single GPT-4o call with all data)
  8.  Save session_data.json (denormalised single source of truth)
  9.  Generate PDF report (ReportLab)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import get_storage_root, settings
from models.fi_session import SessionMetadata

logger = logging.getLogger(__name__)


class ReportPipeline:
    """
    Executes all post-submission analysis steps for one FI session.
    Instantiate once per session, then call ``await pipeline.run()``.
    """

    def __init__(self, session_id: str, meta: SessionMetadata) -> None:
        self.session_id    = session_id
        self.meta          = meta
        self.storage       = get_storage_root() / session_id

        # Results — populated as each step runs
        self.geo_result:      Dict[str, Any]       = {}
        self.address:         str                  = ""
        self.nameplate_ocr:   Optional[Dict]       = None
        self.pan_verification: Optional[Dict]      = None
        self.analysed_entries: List[Dict[str, Any]] = []
        self.income_analysis: Optional[Dict]       = None
        self.credit_analysis: Optional[Dict]       = None

    # ── Public entry point ─────────────────────────────────────────────────

    async def run(self) -> None:
        """Execute all pipeline steps in order, swallowing per-step failures."""
        logger.info("[Pipeline] Starting for session %s", self.session_id)
        try:
            await self._step_geo_verification()
            await self._step_reverse_geocode()
            await self._step_nameplate_ocr()
            await self._step_pan_verification()
            await self._step_image_analysis()
            await self._step_income_analysis()
            await self._step_credit_analysis()
            await self._step_save_session_data()
            await self._step_generate_pdf()
        except Exception as exc:
            logger.exception("[Pipeline] Unhandled failure for %s: %s", self.session_id, exc)
        else:
            logger.info("[Pipeline] Completed for session %s", self.session_id)

    # ── Step 1: Geo verification ───────────────────────────────────────────

    async def _step_geo_verification(self) -> None:
        from services.geo_service import collect_geo_points, verify_location
        geo_points = collect_geo_points(self.meta)
        self.geo_result = verify_location(geo_points, radius_m=settings.geo_radius_meters)
        logger.info(
            "[Pipeline] Geo: verified=%s  pairwise_max=%.0fm",
            self.geo_result.get("verified"),
            self.geo_result.get("max_pairwise_distance_m", 0),
        )
        await self._save_response("geo_verification.json",
                                  json.dumps(self.geo_result, indent=2))

    # ── Step 2: Reverse geocode ────────────────────────────────────────────

    async def _step_reverse_geocode(self) -> None:
        from services.geo_service import collect_geo_points, reverse_geocode
        geo_points  = collect_geo_points(self.meta)
        first_point = next(
            (p for p in geo_points if p.get("latitude") and p.get("longitude")), None
        )
        if first_point:
            self.address = await reverse_geocode(
                first_point["latitude"],
                first_point["longitude"],
                settings.google_maps_api_key,
            )
            logger.info("[Pipeline] Address: %s", self.address[:80])

    # ── Step 3: Nameplate OCR ──────────────────────────────────────────────

    async def _step_nameplate_ocr(self) -> None:
        from services.pan_service import extract_nameplate_text
        nameplate_photo = next(
            (ph for ph in self.meta.photos
             if ph.tag == "nameplate" or "nameplate" in ph.prompt.lower()), None
        )
        if nameplate_photo:
            path = self.storage / nameplate_photo.filename
            self.nameplate_ocr = await extract_nameplate_text(path)
            await self._save_response("nameplate_ocr.json",
                                      json.dumps(self.nameplate_ocr, indent=2, default=str))
            logger.info("[Pipeline] Nameplate: %s",
                        (self.nameplate_ocr or {}).get("raw_text", "")[:60])

    # ── Step 4: PAN card verification ─────────────────────────────────────

    async def _step_pan_verification(self) -> None:
        from services.pan_service import (
            extract_pan_data, verify_pan_nsdl, match_name, face_match,
        )
        from services.name_matcher import NameMatcher
        from services.report_service import extract_customer_name

        pan_photo    = next(
            (ph for ph in self.meta.photos if "pan" in ph.prompt.lower()), None
        )
        selfie_photo = next((ph for ph in self.meta.photos if ph.is_selfie), None)

        if not pan_photo:
            return

        pan_path = self.storage / pan_photo.filename
        pan_ocr  = await extract_pan_data(pan_path)

        form_name      = (
            f"{self.meta.basic_info.first_name} {self.meta.basic_info.last_name}".strip()
            if self.meta.basic_info else ""
        )
        interview_name = form_name or extract_customer_name(self.meta)
        two_way        = match_name(pan_ocr.get("name", ""), interview_name)
        three_way      = NameMatcher(
            form_name,
            pan_ocr.get("name", ""),
            (self.nameplate_ocr or {}).get("raw_text", ""),
        ).compare().as_dict()

        nsdl_result  = await verify_pan_nsdl(
            pan_number  = pan_ocr.get("pan_number", ""),
            name        = pan_ocr.get("name", ""),
            father_name = pan_ocr.get("father_name", ""),
            dob         = pan_ocr.get("dob", ""),
        )

        face_result: Dict[str, Any] = {"error": "Selfie not available", "similarity_score": 0.0}
        if selfie_photo:
            selfie_path = self.storage / selfie_photo.filename
            face_result = await face_match(selfie_path, pan_path)

        self.pan_verification = {
            "ocr":             pan_ocr,
            "name_match":      two_way,
            "three_way_match": three_way,
            "nsdl":            nsdl_result,
            "face_match":      face_result,
            "filename":        pan_photo.filename,
            "geo":             pan_photo.geo,
        }
        await self._save_response("pan_verification.json",
                                  json.dumps(self.pan_verification, indent=2, default=str))
        logger.info(
            "[Pipeline] PAN: verified=%s  name_match=%s  face=%.1f%%",
            nsdl_result.get("verified"),
            two_way.get("matched"),
            face_result.get("similarity_score", 0),
        )

    # ── Step 5: Property image analysis ───────────────────────────────────

    async def _step_image_analysis(self) -> None:
        from services.openai_service import analyze_all_images

        pan_photo    = next(
            (ph for ph in self.meta.photos if "pan" in ph.prompt.lower()), None
        )
        scene_photos = [ph for ph in self.meta.photos if ph is not pan_photo]

        photo_entries = [
            {
                "filename":  ph.filename,
                "prompt":    ph.prompt,
                "is_selfie": ph.is_selfie,
                "tag":       ph.tag,
                "file_path": self.storage / ph.filename,
                "geo":       ph.geo,
                "blur_score": ph.blur_score,
            }
            for ph in scene_photos
        ]

        self.analysed_entries = await analyze_all_images(photo_entries)

        for i, entry in enumerate(self.analysed_entries):
            await self._save_response(f"photo_{i}_analysis.txt",
                                      entry.get("analysis", ""))

        # Attach nameplate OCR to the nameplate entry
        if self.nameplate_ocr:
            for entry in self.analysed_entries:
                if entry.get("tag") == "nameplate" or "nameplate" in entry.get("prompt", "").lower():
                    entry["nameplate_ocr"] = self.nameplate_ocr

    # ── Step 6: Income / bank statement analysis ───────────────────────────

    async def _step_income_analysis(self) -> None:
        from services.openai_service import analyze_bank_statement

        if not self.meta.documents:
            return

        bank_doc = next(
            (d for d in self.meta.documents if d.document_type == "bank_statement"), None
        )
        if not bank_doc:
            return

        doc_path = self.storage / bank_doc.filename
        if not doc_path.exists():
            logger.warning("[Pipeline] Bank statement not found: %s", doc_path)
            return

        self.income_analysis = await analyze_bank_statement(doc_path)
        await self._save_response("income_analysis.json",
                                  json.dumps(self.income_analysis, indent=2))
        logger.info("[Pipeline] Income analysis: creditworthiness=%s",
                    (self.income_analysis or {}).get("creditworthiness_score"))

    # ── Step 7: Comprehensive credit analysis ──────────────────────────────

    async def _step_credit_analysis(self) -> None:
        from services.openai_service import comprehensive_credit_analysis

        try:
            self.credit_analysis = await comprehensive_credit_analysis(
                self.meta,
                self.geo_result,
                self.address,
                self.pan_verification,
                self.nameplate_ocr,
                self.income_analysis,
                self.analysed_entries,
            )
            await self._save_response("credit_analysis.json",
                                      json.dumps(self.credit_analysis, indent=2))
        except Exception as exc:
            logger.error("[Pipeline] Credit analysis failed: %s", exc)

    # ── Step 8: Save session_data.json ─────────────────────────────────────

    async def _step_save_session_data(self) -> None:
        from services.storage_service import save_session_data_json

        await save_session_data_json(
            self.session_id,
            self.meta,
            self.geo_result,
            self.address,
            self.pan_verification,
            self.nameplate_ocr,
            self.income_analysis,
        )

    # ── Step 9: Generate PDF ────────────────────────────────────────────────

    async def _step_generate_pdf(self) -> None:
        import asyncio
        from services.report_service import generate_credit_report

        pdf_path = await asyncio.to_thread(
            generate_credit_report,
            self.meta,
            self.geo_result,
            self.analysed_entries,
            self.address,
            self.income_analysis,
            self.pan_verification,
            self.nameplate_ocr,
            self.credit_analysis,
        )
        logger.info("[Pipeline] PDF ready: %s  (%.1f KB)",
                    pdf_path, pdf_path.stat().st_size / 1024)

    # ── Private helpers ────────────────────────────────────────────────────

    async def _save_response(self, filename: str, content: str) -> None:
        from services.storage_service import save_response
        await save_response(self.session_id, filename, content)
