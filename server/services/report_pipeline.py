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
        self.cibil_score:     Optional[Dict]       = None
        self.credit_analysis: Optional[Dict]       = None

    # ── Public entry point ─────────────────────────────────────────────────

    async def run(self) -> None:
        """
        Execute all pipeline steps in order.
        Each step is isolated: a failure in one step is logged and the pipeline
        continues to the next step so the PDF is always attempted.
        """
        logger.info(
            "[Pipeline] ══ START session=%s  photos=%d  questions=%d ══",
            self.session_id,
            len(self.meta.photos),
            len(self.meta.questions),
        )
        if self.meta.basic_info:
            bi = self.meta.basic_info
            logger.info(
                "[Pipeline] Applicant: %s %s  mobile=%s  pan=%s",
                bi.first_name, bi.last_name, bi.mobile_number, bi.pan_number,
            )
        for ph in self.meta.photos:
            logger.info(
                "[Pipeline] Photo: %s  tag=%-12s  selfie=%s",
                ph.filename, ph.tag or "(none)", ph.is_selfie,
            )

        steps = [
            self._step_geo_verification,
            self._step_reverse_geocode,
            self._step_nameplate_ocr,
            self._step_pan_verification,
            self._step_image_analysis,
            self._step_income_analysis,
            self._step_cibil_score,
            self._step_credit_analysis,
            self._step_save_session_data,
            self._step_generate_pdf,
        ]

        failed = []
        for step in steps:
            name = step.__name__
            logger.info("[Pipeline] ── %s: starting ──", name)
            try:
                await step()
                logger.info("[Pipeline] ── %s: OK ──", name)
            except Exception as exc:
                failed.append(name)
                logger.exception("[Pipeline] ── %s: FAILED — %s ──", name, exc)

        if failed:
            logger.warning(
                "[Pipeline] ══ DONE (with failures) session=%s  failed_steps=%s ══",
                self.session_id, failed,
            )
        else:
            logger.info(
                "[Pipeline] ══ DONE (all steps OK) session=%s ══",
                self.session_id,
            )

    # ── Step 1: Geo verification ───────────────────────────────────────────

    async def _step_geo_verification(self) -> None:
        from services.geo_service import collect_geo_points, verify_location
        geo_points = collect_geo_points(self.meta)
        logger.info("[Pipeline] Geo: %d points collected", len(geo_points))
        for i, pt in enumerate(geo_points):
            logger.debug("[Pipeline] Geo[%d]: lat=%.5f  lon=%.5f  src=%s",
                         i, pt.get("latitude", 0), pt.get("longitude", 0), pt.get("source", "?"))
        self.geo_result = verify_location(geo_points, radius_m=settings.geo_radius_meters)
        logger.info(
            "[Pipeline] Geo: verified=%s  points=%d  pairwise_max=%.0fm",
            self.geo_result.get("verified"),
            self.geo_result.get("points_checked", 0),
            self.geo_result.get("max_pairwise_distance_m", 0),
        )
        saved = await self._save_response("geo_verification.json",
                                          json.dumps(self.geo_result, indent=2))
        logger.info("[Pipeline] Saved → %s", saved)

    # ── Step 2: Reverse geocode ────────────────────────────────────────────

    async def _step_reverse_geocode(self) -> None:
        from services.geo_service import collect_geo_points, reverse_geocode
        geo_points  = collect_geo_points(self.meta)
        first_point = next(
            (p for p in geo_points if p.get("latitude") and p.get("longitude")), None
        )
        if not first_point:
            logger.warning("[Pipeline] Reverse geocode skipped — no GPS points available")
            return
        logger.info("[Pipeline] Reverse geocode: lat=%.5f  lon=%.5f",
                    first_point["latitude"], first_point["longitude"])
        self.address = await reverse_geocode(
            first_point["latitude"],
            first_point["longitude"],
            settings.google_maps_api_key,
        )
        logger.info("[Pipeline] Address resolved: %s", self.address[:120])

        # ── City match check ──────────────────────────────────────────────
        declared_city = (
            (self.meta.basic_info.city or "").strip()
            if self.meta.basic_info else ""
        )
        if declared_city and self.address:
            addr_lower = self.address.lower()
            city_lower = declared_city.lower()
            matched = city_lower in addr_lower
            self.geo_result["city_match"] = {
                "declared_city":  declared_city,
                "google_address": self.address,
                "matched":        matched,
            }
            if matched:
                logger.info("[Pipeline] City match PASS — '%s' found in Google address", declared_city)
            else:
                logger.warning(
                    "[Pipeline] City match FAIL — declared '%s' NOT found in Google address: %s",
                    declared_city, self.address[:100],
                )
        else:
            logger.info("[Pipeline] City match skipped — no declared city or no address")

    # ── Step 3: Nameplate OCR ──────────────────────────────────────────────

    async def _step_nameplate_ocr(self) -> None:
        from services.pan_service import extract_nameplate_text
        nameplate_photo = next(
            (ph for ph in self.meta.photos
             if ph.tag == "nameplate" or "nameplate" in ph.prompt.lower()), None
        )
        if not nameplate_photo:
            logger.info("[Pipeline] Nameplate OCR skipped — no nameplate photo in session")
            return
        path = self.storage / nameplate_photo.filename
        logger.info("[Pipeline] Nameplate OCR: %s  (exists=%s  size=%s)",
                    nameplate_photo.filename, path.exists(),
                    f"{path.stat().st_size} bytes" if path.exists() else "N/A")
        self.nameplate_ocr = await extract_nameplate_text(path)
        raw = (self.nameplate_ocr or {}).get("raw_text", "")
        logger.info("[Pipeline] Nameplate text: '%s'", raw[:120])
        saved = await self._save_response("nameplate_ocr.json",
                                          json.dumps(self.nameplate_ocr, indent=2, default=str))
        logger.info("[Pipeline] Saved → %s", saved)

    # ── Step 4: PAN card verification ─────────────────────────────────────

    async def _step_pan_verification(self) -> None:
        from services.pan_service import (
            extract_pan_data, verify_pan_nsdl, match_name, face_match,
        )
        from services.name_matcher import NameMatcher
        from services.report_service import extract_customer_name

        pan_photo    = next(
            (ph for ph in self.meta.photos if "pan" in ph.prompt.lower() or ph.tag == "pan"), None
        )
        selfie_photo = next((ph for ph in self.meta.photos if ph.is_selfie), None)

        if not pan_photo:
            logger.warning("[Pipeline] PAN verification skipped — no PAN photo found in session")
            logger.info("[Pipeline] Available photo tags: %s",
                        [ph.tag for ph in self.meta.photos])
            return

        pan_path = self.storage / pan_photo.filename
        logger.info("[Pipeline] PAN photo: %s  (exists=%s  size=%s)",
                    pan_photo.filename, pan_path.exists(),
                    f"{pan_path.stat().st_size} bytes" if pan_path.exists() else "N/A")

        if not pan_path.exists():
            logger.error("[Pipeline] PAN image file missing: %s", pan_path)
            return

        # ── OCR ──────────────────────────────────────────────────────────
        logger.info("[Pipeline] PAN OCR starting...")
        pan_ocr = await extract_pan_data(pan_path)
        logger.info(
            "[Pipeline] PAN OCR result: PAN=%s  name='%s'  father='%s'  dob=%s  source=%s  error=%s",
            pan_ocr.get("pan_number", "(empty)"),
            pan_ocr.get("name", "(empty)"),
            pan_ocr.get("father_name", "(empty)"),
            pan_ocr.get("dob", "(empty)"),
            pan_ocr.get("source", "?"),
            pan_ocr.get("error", "none"),
        )

        # ── Name matching ─────────────────────────────────────────────────
        form_name      = (
            f"{self.meta.basic_info.first_name} {self.meta.basic_info.last_name}".strip()
            if self.meta.basic_info else ""
        )
        interview_name = form_name or extract_customer_name(self.meta)
        logger.info("[Pipeline] Name match: pan='%s'  form='%s'  interview='%s'",
                    pan_ocr.get("name", ""), form_name, interview_name)
        two_way   = match_name(pan_ocr.get("name", ""), interview_name)
        three_way = NameMatcher(
            form_name,
            pan_ocr.get("name", ""),
            (self.nameplate_ocr or {}).get("raw_text", ""),
        ).compare().as_dict()
        logger.info("[Pipeline] Name match result: 2-way=%s  3-way=%s",
                    two_way.get("matched"), three_way.get("status"))

        # ── NSDL ─────────────────────────────────────────────────────────
        logger.info("[Pipeline] NSDL check: PAN=%s", pan_ocr.get("pan_number", "(empty)"))
        nsdl_result = await verify_pan_nsdl(
            pan_number  = pan_ocr.get("pan_number", ""),
            name        = pan_ocr.get("name", ""),
            father_name = pan_ocr.get("father_name", ""),
            dob         = pan_ocr.get("dob", ""),
        )
        logger.info("[Pipeline] NSDL: verified=%s  status=%s",
                    nsdl_result.get("verified"), nsdl_result.get("pan_status"))

        # ── Face match ────────────────────────────────────────────────────
        face_result: Dict[str, Any] = {"error": "Selfie not available", "similarity_score": 0.0}
        if selfie_photo:
            selfie_path = self.storage / selfie_photo.filename
            logger.info("[Pipeline] Face match: selfie=%s  pan=%s",
                        selfie_photo.filename, pan_photo.filename)
            face_result = await face_match(selfie_path, pan_path)
            logger.info("[Pipeline] Face match: similarity=%.1f%%  matched=%s  error=%s",
                        face_result.get("similarity_score", 0),
                        face_result.get("matched"),
                        face_result.get("error", "none"))
        else:
            logger.warning("[Pipeline] Face match skipped — no selfie photo found")

        self.pan_verification = {
            "ocr":             pan_ocr,
            "name_match":      two_way,
            "three_way_match": three_way,
            "nsdl":            nsdl_result,
            "face_match":      face_result,
            "filename":        pan_photo.filename,
            "geo":             pan_photo.geo,
        }
        saved = await self._save_response("pan_verification.json",
                                          json.dumps(self.pan_verification, indent=2, default=str))
        logger.info("[Pipeline] PAN verification saved → %s", saved)
        logger.info(
            "[Pipeline] PAN summary: ocr_ok=%s  nsdl=%s  name_match=%s  face=%.1f%%",
            bool(pan_ocr.get("pan_number")),
            nsdl_result.get("verified"),
            two_way.get("matched"),
            face_result.get("similarity_score", 0),
        )

    # ── Step 5: Property image analysis ───────────────────────────────────

    async def _step_image_analysis(self) -> None:
        from services.openai_service import analyze_all_images

        pan_photo    = next(
            (ph for ph in self.meta.photos if "pan" in ph.prompt.lower() or ph.tag == "pan"), None
        )
        scene_photos = [ph for ph in self.meta.photos if ph is not pan_photo]

        logger.info("[Pipeline] Image analysis: %d scene photos (PAN excluded)",
                    len(scene_photos))
        for ph in scene_photos:
            fp = self.storage / ph.filename
            logger.info("[Pipeline]   ↳ %s  tag=%-12s  exists=%s  size=%s",
                        ph.filename, ph.tag or "(none)", fp.exists(),
                        f"{fp.stat().st_size} bytes" if fp.exists() else "MISSING")

        missing = [ph for ph in scene_photos if not (self.storage / ph.filename).exists()]
        if missing:
            logger.error("[Pipeline] %d photo file(s) missing on disk: %s",
                         len(missing), [ph.filename for ph in missing])

        photo_entries = [
            {
                "filename":   ph.filename,
                "prompt":     ph.prompt,
                "is_selfie":  ph.is_selfie,
                "tag":        ph.tag,
                "file_path":  self.storage / ph.filename,
                "geo":        ph.geo,
                "blur_score": ph.blur_score,
            }
            for ph in scene_photos
        ]

        logger.info("[Pipeline] Sending %d photos to GPT-4o Vision...", len(photo_entries))
        self.analysed_entries = await analyze_all_images(photo_entries)
        logger.info("[Pipeline] GPT-4o Vision analysis complete — %d results",
                    len(self.analysed_entries))

        for i, entry in enumerate(self.analysed_entries):
            analysis = entry.get("analysis", "")
            status   = "OK" if analysis and not analysis.startswith("Image") else "EMPTY/ERROR"
            logger.info("[Pipeline]   [%d] %s  tag=%-12s  chars=%d  status=%s",
                        i, entry.get("filename", "?"), entry.get("tag", "?"),
                        len(analysis), status)
            saved = await self._save_response(f"photo_{i}_{entry.get('tag','unknown')}_analysis.txt",
                                              analysis)
            logger.info("[Pipeline]   Saved → %s", saved)

        # Attach nameplate OCR to the nameplate entry
        if self.nameplate_ocr:
            for entry in self.analysed_entries:
                if entry.get("tag") == "nameplate" or "nameplate" in entry.get("prompt", "").lower():
                    entry["nameplate_ocr"] = self.nameplate_ocr
                    logger.info("[Pipeline] Nameplate OCR attached to image entry")

    # ── Step 6: Income / bank statement analysis ───────────────────────────

    async def _step_income_analysis(self) -> None:
        """
        Pull bank statement PDFs from the vault folder keyed by mobile number.
        Vault path: {FI_BANK_VAULT_ROOT}/{mobile_number}/*.pdf
        If no PDFs found in vault, falls back to any uploaded document.
        """
        from services.openai_service import analyze_bank_statement
        from pathlib import Path

        # ── 1. Try vault lookup by mobile number ──────────────────────────
        mobile = (self.meta.basic_info.mobile_number or "").strip() if self.meta.basic_info else ""
        vault_root = Path(settings.fi_bank_vault_root)
        vault_pdfs: list[Path] = []

        logger.info("[Pipeline] Bank vault root: '%s'  (exists=%s)", vault_root, vault_root.exists())
        if vault_root.exists():
            subdirs = [d.name for d in vault_root.iterdir() if d.is_dir()]
            logger.info("[Pipeline] Vault subdirs: %s", subdirs[:20])

        if mobile:
            # Try both plain number and +91 prefix
            candidates = [mobile, f"+91{mobile}", mobile.lstrip("+91")]
            candidates = list(dict.fromkeys(c for c in candidates if c))  # dedupe

            for candidate in candidates:
                vault_dir = vault_root / candidate
                logger.info("[Pipeline] Trying vault path: %s  (exists=%s)", vault_dir, vault_dir.exists())
                if vault_dir.exists():
                    vault_pdfs = sorted(vault_dir.glob("*.pdf"))
                    logger.info("[Pipeline] Vault %s — found %d PDF(s): %s",
                                vault_dir, len(vault_pdfs),
                                [p.name for p in vault_pdfs])
                    if vault_pdfs:
                        break
            if not vault_pdfs:
                logger.warning(
                    "[Pipeline] No PDF found in vault for mobile=%s  "
                    "Tried paths: %s  — check FI_BANK_VAULT_ROOT in .env",
                    mobile, [str(vault_root / c) for c in candidates],
                )
        else:
            logger.warning("[Pipeline] No mobile number in session — cannot look up vault")

        # ── 1b. Common folder fallback (college-project / demo use) ──────────
        if not vault_pdfs:
            common_dir = vault_root / "common"
            if common_dir.exists():
                vault_pdfs = sorted(common_dir.glob("*.pdf"))
                if vault_pdfs:
                    logger.info("[Pipeline] Using common vault folder: %s — found %d PDF(s): %s",
                                common_dir, len(vault_pdfs), [p.name for p in vault_pdfs])
                else:
                    logger.info("[Pipeline] Common vault folder exists but is empty: %s", common_dir)
            else:
                logger.info("[Pipeline] No common vault folder at %s", common_dir)

        # ── 2. Fall back to uploaded document (legacy path) ───────────────
        if not vault_pdfs and self.meta.documents:
            bank_doc = next(
                (d for d in self.meta.documents if d.document_type == "bank_statement"), None
            )
            if bank_doc:
                fallback = self.storage / bank_doc.filename
                if fallback.exists():
                    vault_pdfs = [fallback]
                    logger.info("[Pipeline] Using uploaded statement: %s", bank_doc.filename)

        if not vault_pdfs:
            logger.info("[Pipeline] No bank statement available — income analysis skipped")
            return

        # ── 3. Analyse first PDF (most recent alphabetically) ─────────────
        target_pdf = vault_pdfs[-1]   # last = likely most recent when sorted by name
        logger.info("[Pipeline] Bank statement: %s  (%.1f KB)",
                    target_pdf.name, target_pdf.stat().st_size / 1024)
        self.income_analysis = await analyze_bank_statement(target_pdf)
        if self.income_analysis.get("error"):
            logger.error("[Pipeline] Bank statement analysis error: %s",
                         self.income_analysis["error"])
        else:
            logger.info(
                "[Pipeline] Income: avg_income=₹%.0f  avg_expenses=₹%.0f  "
                "salary=%s  creditworthiness=%s/10",
                self.income_analysis.get("avg_monthly_income", 0),
                self.income_analysis.get("avg_monthly_expenses", 0),
                self.income_analysis.get("salary_detected"),
                self.income_analysis.get("creditworthiness_score"),
            )
        saved = await self._save_response("income_analysis.json",
                                          json.dumps(self.income_analysis, indent=2))
        logger.info("[Pipeline] Saved → %s", saved)

    # ── Step 6b: CIBIL score lookup ────────────────────────────────────────

    async def _step_cibil_score(self) -> None:
        from services.cibil_service import get_cibil_score

        pan = (self.pan_verification or {}).get("ocr", {}).get("pan_number", "")
        if not pan and self.meta.basic_info:
            pan = self.meta.basic_info.pan_number
        logger.info("[Pipeline] CIBIL lookup: PAN=%s", pan or "(empty)")

        self.cibil_score = await get_cibil_score(pan, self.income_analysis)
        logger.info("[Pipeline] CIBIL: score=%d  grade=%s",
                    self.cibil_score["score"], self.cibil_score["grade"])
        saved = await self._save_response("cibil_score.json",
                                          json.dumps(self.cibil_score, indent=2))
        logger.info("[Pipeline] Saved → %s", saved)

    # ── Step 7: Comprehensive credit analysis ──────────────────────────────

    async def _step_credit_analysis(self) -> None:
        from services.openai_service import comprehensive_credit_analysis

        logger.info(
            "[Pipeline] Credit analysis input: "
            "geo=%s  pan_verified=%s  income_ok=%s  photos=%d  interview_q=%d",
            self.geo_result.get("verified"),
            bool(self.pan_verification),
            self.income_analysis is not None and not self.income_analysis.get("error"),
            len(self.analysed_entries),
            len(self.meta.questions),
        )

        self.credit_analysis = await comprehensive_credit_analysis(
            self.meta,
            self.geo_result,
            self.address,
            self.pan_verification,
            self.nameplate_ocr,
            self.income_analysis,
            self.analysed_entries,
        )

        if self.credit_analysis.get("error"):
            logger.error("[Pipeline] Credit analysis returned error: %s",
                         self.credit_analysis["error"])
        else:
            logger.info(
                "[Pipeline] Credit analysis: score=%s  grade=%s  recommendation=%s",
                self.credit_analysis.get("overall_credit_score"),
                self.credit_analysis.get("risk_grade"),
                self.credit_analysis.get("recommendation"),
            )

        saved = await self._save_response("credit_analysis.json",
                                          json.dumps(self.credit_analysis, indent=2))
        logger.info("[Pipeline] Saved → %s", saved)

    # ── Step 8: Save session_data.json ─────────────────────────────────────

    async def _step_save_session_data(self) -> None:
        from services.storage_service import save_session_data_json

        logger.info("[Pipeline] Saving session_data.json...")
        prop_info = None
        if self.meta.property_info:
            prop_info = {
                "property_type": self.meta.property_info.property_type,
                "bedrooms":      self.meta.property_info.bedrooms,
                "hall":          self.meta.property_info.hall,
            }
        dest = await save_session_data_json(
            self.session_id,
            self.meta,
            self.geo_result,
            self.address,
            self.pan_verification,
            self.nameplate_ocr,
            self.income_analysis,
            self.credit_analysis,
            self.cibil_score,
            analysed_entries = self.analysed_entries,
            property_info    = prop_info,
        )
        logger.info("[Pipeline] session_data.json saved → %s  (%.1f KB)",
                    dest, dest.stat().st_size / 1024)

    # ── Step 9: Generate PDF ────────────────────────────────────────────────

    async def _step_generate_pdf(self) -> None:
        import asyncio
        from services.report_service import generate_credit_report

        logger.info("[Pipeline] Generating PDF report...")
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
            self.cibil_score,
        )
        logger.info("[Pipeline] ✓ PDF ready: %s  (%.1f KB)",
                    pdf_path, pdf_path.stat().st_size / 1024)

    # ── Private helpers ────────────────────────────────────────────────────

    async def _save_response(self, filename: str, content: str) -> "Path":
        from services.storage_service import save_response
        dest = await save_response(self.session_id, filename, content)
        return dest
