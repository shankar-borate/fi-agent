"""
Mock CIBIL Credit Score Service.

In production this would call the TransUnion CIBIL API using the applicant's
PAN number and date of birth.  For this student project, the score is computed
deterministically from the income-analysis data so the same applicant always
gets the same score within a session.

Score ranges (RBI / CIBIL standard):
  750 – 900  : Excellent  — low risk, easy approval
  700 – 749  : Good       — eligible, standard terms
  650 – 699  : Fair       — conditional approval, higher rate
  600 – 649  : Poor       — manual review required
  300 – 599  : Very Poor  — high risk, likely decline
"""

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# ── Score band definitions ────────────────────────────────────────────────────

_BANDS = [
    (800, 900, "EXCELLENT",  "Excellent",  "#1B5E20", "Strong credit profile — lowest risk category"),
    (750, 799, "VERY_GOOD",  "Very Good",  "#2E7D32", "Very good credit — eligible for best interest rates"),
    (700, 749, "GOOD",       "Good",       "#558B2F", "Good credit — eligible for standard personal loan"),
    (650, 699, "FAIR",       "Fair",       "#F57F17", "Fair credit — conditional approval, may need guarantor"),
    (600, 649, "POOR",       "Poor",       "#E65100", "Below average — high-risk borrower, manual review needed"),
    (300, 599, "VERY_POOR",  "Very Poor",  "#C62828", "Very poor credit — not recommended for approval"),
]


def _band(score: int) -> Dict[str, str]:
    for lo, hi, grade, label, color, msg in _BANDS:
        if lo <= score <= hi:
            return {"grade": grade, "label": label, "color": color, "message": msg}
    return {"grade": "UNKNOWN", "label": "Unknown", "color": "#555", "message": "Unable to determine"}


# ── Mock score computation ────────────────────────────────────────────────────

def _compute_score(pan_number: str, income_analysis: Optional[Dict[str, Any]]) -> int:
    """
    Deterministically compute a mock CIBIL score.

    Base: 650 (average Indian borrower)
    Adjustments driven by income-analysis metrics so the score is plausible
    for this applicant's financial profile.
    A small PAN-hash nudge (±25) ensures different applicants get different scores.
    """
    base = 650

    if income_analysis and not income_analysis.get("error"):
        ia = income_analysis

        # Creditworthiness score from bank statement (0-10 → ±60)
        cw = int(ia.get("creditworthiness_score") or 5)
        base += (cw - 5) * 12          # +60 for 10, -60 for 0

        # Regular salary = +35 (stability indicator)
        if ia.get("salary_detected"):
            base += 35

        # No bounced transactions = +40
        bounces = int(ia.get("bounce_count") or 0)
        if bounces == 0:
            base += 40
        elif bounces <= 2:
            base -= bounces * 15
        else:
            base -= bounces * 25

        # Expense-to-income ratio
        exp_ratio = float(ia.get("expense_to_income_ratio") or 0.6)
        if exp_ratio < 0.40:
            base += 40      # very disciplined
        elif exp_ratio < 0.55:
            base += 20
        elif exp_ratio < 0.70:
            base += 0
        elif exp_ratio < 0.80:
            base -= 20
        else:
            base -= 40      # over-spending

        # Existing EMI burden
        emi_count = int(ia.get("existing_emi_count") or ia.get("emi_count") or 0)
        base -= emi_count * 10

    # PAN-hash nudge ±25 for uniqueness (reproducible per applicant)
    if pan_number:
        h = int(hashlib.md5(pan_number.upper().encode()).hexdigest(), 16)
        base += (h % 51) - 25   # -25 to +25

    return max(300, min(900, round(base / 5) * 5))   # round to nearest 5


# ── Public entry point ────────────────────────────────────────────────────────

async def get_cibil_score(
    pan_number:      str,
    income_analysis: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Return a mock CIBIL credit score for the applicant.
    Called after income analysis so the score reflects the financial profile.
    """
    score = _compute_score(pan_number, income_analysis)
    band  = _band(score)

    result = {
        "score":            score,
        "grade":            band["grade"],
        "label":            band["label"],
        "color":            band["color"],
        "message":          band["message"],
        "pan_number":       pan_number,
        "bureau":           "TransUnion CIBIL",
        "report_date":      datetime.now(timezone.utc).strftime("%d %b %Y"),
        "loan_eligible":    score >= 650,
        "recommendation": (
            "Approved — excellent credit profile"      if score >= 800 else
            "Approved — good credit profile"           if score >= 750 else
            "Approved — standard terms apply"          if score >= 700 else
            "Conditional approval — verify income"     if score >= 650 else
            "Refer to credit committee"                if score >= 600 else
            "Decline — insufficient credit history"
        ),
    }

    logger.info("[CIBIL] PAN=%s  score=%d  grade=%s", pan_number, score, band["grade"])
    return result
