"""
NameMatcher — OOP service for cross-source name verification.

Compares first names across three data sources captured during a Field
Investigation:
  1. Application form   — applicant's self-declared name
  2. PAN card OCR       — name as printed on the PAN card (AWS Textract)
  3. Home nameplate OCR — name / text extracted from the door/gate nameplate

Only the first name is used for the primary match (sufficient for FI
verification; last-name mis-spellings are common on nameplates).

Usage:
    matcher = NameMatcher(form_name, pan_name, nameplate_text)
    result  = matcher.compare()   # → NameMatchResult
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Value objects ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class NameMatchResult:
    all_match:       bool
    form_first:      str
    pan_first:       str
    nameplate_first: str
    form_vs_pan:     bool
    form_vs_nameplate: bool
    pan_vs_nameplate:  bool
    missing_sources: List[str]
    notes:           str

    def as_dict(self) -> Dict:
        return {
            "all_match":          self.all_match,
            "form_first_name":    self.form_first,
            "pan_first_name":     self.pan_first,
            "nameplate_first_name": self.nameplate_first,
            "form_vs_pan":        self.form_vs_pan,
            "form_vs_nameplate":  self.form_vs_nameplate,
            "pan_vs_nameplate":   self.pan_vs_nameplate,
            "missing_sources":    self.missing_sources,
            "notes":              self.notes,
        }

    @property
    def status(self) -> str:
        if self.missing_sources:
            available = 3 - len(self.missing_sources)
            if available < 2:
                return "INSUFFICIENT_DATA"
        return "MATCHED" if self.all_match else "MISMATCH"


# ── NameMatcher class ─────────────────────────────────────────────────────────

class NameMatcher:
    """
    Compares first names from the application form, PAN card OCR, and
    home nameplate OCR to detect identity inconsistencies.
    """

    def __init__(
        self,
        form_full_name:    str,
        pan_full_name:     str,
        nameplate_raw_text: str,
    ) -> None:
        self._form      = form_full_name.strip()
        self._pan       = pan_full_name.strip()
        self._nameplate = nameplate_raw_text.strip()

    # ── Public interface ──────────────────────────────────────────────────────

    def compare(self) -> NameMatchResult:
        form_first      = self._extract_first(self._form)
        pan_first       = self._extract_first(self._pan)
        nameplate_first = self._find_first_in_text(self._nameplate, form_first or pan_first)

        missing: List[str] = []
        if not form_first:      missing.append("application form")
        if not pan_first:       missing.append("PAN card")
        if not nameplate_first: missing.append("nameplate")

        fvp  = self._names_match(form_first, pan_first)
        fvn  = self._names_match(form_first, nameplate_first)
        pvn  = self._names_match(pan_first,  nameplate_first)

        # All-match: every available pair must agree
        available_pairs = [
            (fvp,  bool(form_first and pan_first)),
            (fvn,  bool(form_first and nameplate_first)),
            (pvn,  bool(pan_first  and nameplate_first)),
        ]
        checked = [(r, active) for r, active in available_pairs if active]
        all_match = all(r for r, _ in checked) if checked else False

        notes = self._build_notes(form_first, pan_first, nameplate_first, fvp, fvn, pvn, missing)

        result = NameMatchResult(
            all_match         = all_match,
            form_first        = form_first,
            pan_first         = pan_first,
            nameplate_first   = nameplate_first,
            form_vs_pan       = fvp,
            form_vs_nameplate = fvn,
            pan_vs_nameplate  = pvn,
            missing_sources   = missing,
            notes             = notes,
        )
        logger.info("[NameMatcher] form=%s pan=%s nameplate=%s status=%s",
                    form_first, pan_first, nameplate_first, result.status)
        return result

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _normalize(name: str) -> str:
        """Uppercase, strip punctuation and extra whitespace."""
        return re.sub(r'[^A-Z]', '', name.upper()).strip()

    @staticmethod
    def _extract_first(full_name: str) -> str:
        """Return the first word of a full name, normalised."""
        if not full_name:
            return ""
        first = full_name.strip().split()[0] if full_name.strip() else ""
        return NameMatcher._normalize(first)

    @staticmethod
    def _find_first_in_text(text: str, reference_first: str) -> str:
        """
        Try to find a likely person's first name in raw nameplate text.

        Strategy:
          1. Look for any word that exactly matches the reference first name.
          2. Fall back to the longest all-alpha word (≥4 chars) as a heuristic.
        """
        if not text:
            return ""
        words = [w.strip().upper() for w in re.split(r'[\s|,\-]+', text) if w.strip()]
        alpha_words = [re.sub(r'[^A-Z]', '', w) for w in words if len(w) >= 3]

        ref = NameMatcher._normalize(reference_first)
        if ref:
            for w in alpha_words:
                if w == ref:
                    return w

        # Heuristic: longest plausible first name (exclude common noise words)
        _NOISE = {"AND", "FAMILY", "HOME", "NIWAS", "VILLA", "HOUSE",
                  "FLAT", "ROAD", "STREET", "PLOT", "BUILDING"}
        candidates = [w for w in alpha_words if len(w) >= 4 and w not in _NOISE]
        if candidates:
            return max(candidates, key=len)
        return ""

    @staticmethod
    def _names_match(a: str, b: str) -> bool:
        """Exact match after normalisation; returns False if either is empty."""
        return bool(a and b and NameMatcher._normalize(a) == NameMatcher._normalize(b))

    @staticmethod
    def _build_notes(
        form: str, pan: str, nameplate: str,
        fvp: bool, fvn: bool, pvn: bool,
        missing: List[str],
    ) -> str:
        parts = []
        if form and pan:
            parts.append(f"Form vs PAN: {'MATCH' if fvp else 'MISMATCH'} ({form} / {pan})")
        if form and nameplate:
            parts.append(f"Form vs Nameplate: {'MATCH' if fvn else 'MISMATCH'} ({form} / {nameplate})")
        if pan and nameplate:
            parts.append(f"PAN vs Nameplate: {'MATCH' if pvn else 'MISMATCH'} ({pan} / {nameplate})")
        if missing:
            parts.append(f"Missing sources: {', '.join(missing)}")
        return "  |  ".join(parts) if parts else "Insufficient data for comparison"
