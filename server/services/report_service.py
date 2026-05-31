"""
Field Investigation PDF Report — Enterprise Grade, Black & White, A4.

Sections:
  1. Executive Summary
  2. Applicant Profile
  3. Field Interview (Q&A with GPS per answer)
  4. Location Report (geocoded address, spread analysis, point table)
  5. Property Documentation (photos + AI analysis + GPS)
  6. Risk Assessment (scored, visual bar, breakdown)
  7. Recommendations & Final Decision
"""

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Indian Standard Time = UTC + 5:30
_IST = timezone(timedelta(hours=5, minutes=30))


def _ist(dt_str: str, fmt: str = "%d %b %Y, %H:%M IST") -> str:
    """Convert a UTC ISO-8601 string to a human-readable IST string."""
    if not dt_str:
        return "—"
    try:
        clean = dt_str.strip().replace("Z", "+00:00")
        dt    = datetime.fromisoformat(clean)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(_IST).strftime(fmt)
    except Exception:
        return dt_str


def _now_ist(fmt: str = "%d %b %Y, %H:%M IST") -> str:
    """Current time formatted in IST."""
    return datetime.now(_IST).strftime(fmt)

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    Image as RLImage,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from config import get_storage_root, settings
from models.fi_session import SessionMetadata

logger = logging.getLogger(__name__)

# ── Palette (monochrome) ───────────────────────────────────────────────────────
BLACK   = colors.black
WHITE   = colors.white
D_GREY  = colors.HexColor("#222222")
M_GREY  = colors.HexColor("#555555")
L_GREY  = colors.HexColor("#EEEEEE")
B_GREY  = colors.HexColor("#BBBBBB")
XL_GREY = colors.HexColor("#F7F7F7")
RED     = colors.HexColor("#990000")   # used for FAIL / HIGH RISK (still printable B&W)

PAGE_W, PAGE_H = A4
MARGIN    = 1.8 * cm
CONTENT_W = PAGE_W - 2 * MARGIN

# Risk thresholds
GEO_THRESHOLD_M = 500.0
EXPECTED_PHOTOS  = 5      # selfie + 4 room shots


# ── Styles ─────────────────────────────────────────────────────────────────────

def _build_styles() -> Dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()

    def ps(name, **kw):
        return ParagraphStyle(name, parent=base["Normal"], **kw)

    return {
        # Title block
        "org_name":     ps("org",     fontSize=9,  leading=12, fontName="Helvetica-Bold",
                           textColor=M_GREY, alignment=TA_CENTER),
        "report_title": ps("rtitle",  fontSize=22, leading=26, fontName="Helvetica-Bold",
                           textColor=BLACK, alignment=TA_CENTER),
        "report_sub":   ps("rsub",    fontSize=10, leading=14, fontName="Helvetica",
                           textColor=M_GREY, alignment=TA_CENTER),
        "classify":     ps("cls",     fontSize=8,  leading=10, fontName="Helvetica-Bold",
                           textColor=WHITE, alignment=TA_CENTER),

        # Section headers
        "sec_hdr":      ps("shdr",    fontSize=11, leading=14, fontName="Helvetica-Bold",
                           textColor=WHITE),
        "sub_hdr":      ps("sshdr",   fontSize=9,  leading=12, fontName="Helvetica-Bold",
                           textColor=D_GREY),

        # Body text
        "label":        ps("lbl",     fontSize=9,  leading=13, fontName="Helvetica-Bold",
                           textColor=D_GREY),
        "value":        ps("val",     fontSize=9,  leading=13, fontName="Helvetica",
                           textColor=D_GREY),
        "small":        ps("sm",      fontSize=7.5,leading=10, fontName="Helvetica",
                           textColor=M_GREY),
        "small_bold":   ps("smb",     fontSize=7.5,leading=10, fontName="Helvetica-Bold",
                           textColor=D_GREY),
        "analysis":     ps("anal",    fontSize=8,  leading=11, fontName="Helvetica",
                           textColor=D_GREY),
        "bullet":       ps("bul",     fontSize=9,  leading=14, fontName="Helvetica",
                           textColor=D_GREY, leftIndent=10),
        "bullet_bold":  ps("bulb",    fontSize=9,  leading=14, fontName="Helvetica-Bold",
                           textColor=D_GREY, leftIndent=10),

        # Decision / risk
        "risk_score":   ps("rscore",  fontSize=36, leading=40, fontName="Helvetica-Bold",
                           textColor=BLACK, alignment=TA_CENTER),
        "risk_label":   ps("rlbl",    fontSize=13, leading=16, fontName="Helvetica-Bold",
                           textColor=BLACK, alignment=TA_CENTER),
        "risk_sub":     ps("rsub2",   fontSize=9,  leading=12, fontName="Helvetica",
                           textColor=M_GREY, alignment=TA_CENTER),
        "decision":     ps("dec",     fontSize=14, leading=18, fontName="Helvetica-Bold",
                           textColor=BLACK, alignment=TA_CENTER),

        # Captions
        "img_caption":  ps("icap",    fontSize=9,  leading=12, fontName="Helvetica-Bold",
                           textColor=D_GREY),
    }


# ── Layout primitives ──────────────────────────────────────────────────────────

def _section_header(text: str, s: Dict) -> List:
    tbl = Table([[Paragraph(f"  {text}", s["sec_hdr"])]], colWidths=[CONTENT_W])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), BLACK),
        ("TOPPADDING",    (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
    ]))
    return [Spacer(1, 10), tbl, Spacer(1, 6)]


def _sub_header(text: str, s: Dict) -> List:
    tbl = Table([[Paragraph(f"  {text}", s["sub_hdr"])]], colWidths=[CONTENT_W])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), L_GREY),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("BOX",           (0, 0), (-1, -1), 0.5, B_GREY),
    ]))
    return [Spacer(1, 6), tbl, Spacer(1, 4)]


def _kv_table(rows: List[tuple], s: Dict, label_w: float = 5.5 * cm) -> Table:
    data = [
        [Paragraph(str(k), s["label"]), Paragraph(str(v), s["value"])]
        for k, v in rows
    ]
    tbl = Table(data, colWidths=[label_w, CONTENT_W - label_w])
    tbl.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [WHITE, XL_GREY]),
        ("GRID",           (0, 0), (-1, -1), 0.4, B_GREY),
        ("TOPPADDING",     (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 4),
        ("LEFTPADDING",    (0, 0), (-1, -1), 7),
        ("VALIGN",         (0, 0), (-1, -1), "TOP"),
    ]))
    return tbl


def _status_pill(text: str, ok: bool) -> Table:
    """Inline banner: black border for OK, heavy border for FAIL."""
    border_c = BLACK if ok else RED
    tbl = Table([[Paragraph(text, ParagraphStyle(
        "pill", fontName="Helvetica-Bold", fontSize=11,
        textColor=border_c, alignment=TA_CENTER,
    ))]], colWidths=[CONTENT_W])
    tbl.setStyle(TableStyle([
        ("BOX",           (0, 0), (-1, -1), 2 if not ok else 1, border_c),
        ("BACKGROUND",    (0, 0), (-1, -1), XL_GREY),
        ("TOPPADDING",    (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
    ]))
    return tbl


def _hdr_style_cell(text: str, s: Dict) -> Paragraph:
    return Paragraph(text, ParagraphStyle(
        "th", parent=s["value"], textColor=WHITE, fontName="Helvetica-Bold"
    ))


# ── Completeness helpers ──────────────────────────────────────────────────────

def _incomplete(reason: str, s: Dict) -> Table:
    """Standardised INCOMPLETE notice for sections with missing data."""
    inc_style = ParagraphStyle(
        "inc_notice", parent=s["value"],
        fontName="Helvetica-Bold", textColor=colors.HexColor("#6A1B9A"),
    )
    tbl = Table(
        [[Paragraph(f"INCOMPLETE  —  {reason}", inc_style)]],
        colWidths=[CONTENT_W],
    )
    tbl.setStyle(TableStyle([
        ("BOX",           (0, 0), (-1, -1), 1.2, colors.HexColor("#6A1B9A")),
        ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#F3E5F5")),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
    ]))
    return tbl


# ── Geo helpers ────────────────────────────────────────────────────────────────

def _fmt_geo(geo) -> str:
    if not geo:
        return "GPS: not captured"
    ts = geo.timestamp[:19].replace("T", " ") if geo.timestamp else ""
    return f"{geo.latitude:.5f}°N  {geo.longitude:.5f}°E   [{ts}]"


# ── Customer extraction ────────────────────────────────────────────────────────

def extract_customer_name(meta: SessionMetadata) -> str:
    """Return the applicant's name as given during the interview (for PAN matching)."""
    for qa in meta.questions:
        q = qa.question.lower()
        if any(kw in q for kw in ("name", "applicant")):
            return qa.answer or ""
    return ""


def _extract_customer(meta: SessionMetadata) -> Dict[str, str]:
    keyword_map = [
        (["name", "applicant"],          "Full Name"),
        (["birth", "dob", "born"],        "Date of Birth"),
        (["pincode", "pin code"],         "Pincode"),
        (["address", "residence", "resi"],"Residential Address"),
        (["mobile", "phone", "contact"],  "Mobile / Phone"),
        (["income", "salary", "earning"], "Monthly Income"),
        (["employment", "employer", "job","company", "work"], "Employment / Employer"),
        (["loan", "purpose", "amount"],   "Loan / Purpose"),
    ]
    info: Dict[str, str] = {}
    for qa in meta.questions:
        q_lower = qa.question.lower()
        matched = next(
            (label for kws, label in keyword_map if any(kw in q_lower for kw in kws)),
            None,
        )
        key = matched or qa.question[:55]
        if key not in info:   # first match wins
            info[key] = qa.answer or "—"
    return info


# ── Risk score ─────────────────────────────────────────────────────────────────

RiskBreakdown = List[Tuple[str, int, int, str]]  # (component, earned, max, note)


def _compute_risk(
    meta: SessionMetadata,
    geo_result: Dict[str, Any],
    image_entries: List[Dict[str, Any]],
    income_analysis: Optional[Dict[str, Any]] = None,
    pan_verification: Optional[Dict[str, Any]] = None,
) -> Tuple[int, RiskBreakdown, str, str]:
    """
    Returns (score_0_100, breakdown, risk_level_label, decision_text).

    Without income analysis — 4 components, 100 pts:
      Location Integrity     30 | Interview Completeness 20
      Photo Documentation    25 | AI Image Analysis      25

    With income analysis — 8 components, 100 pts:
      Location Integrity     15 | Interview Completeness 10
      Photo Documentation    10 | AI Image Analysis       5
      Income Document         5 | Regular Income         15
      Financial Discipline   15 | AI Credit Health       25
    """
    breakdown: RiskBreakdown = []
    has_income = bool(income_analysis and not income_analysis.get("error"))
    has_pan    = bool(pan_verification and not (pan_verification.get("ocr") or {}).get("error"))

    # ── Dynamic weight allocation (always sums to 100) ──────────────────
    if has_pan and has_income:
        geo_max, qa_max, ph_max, ai_max            = 10,  8,  7,  5   # FI  : 30
        pan_max, name_max, nsdl_max                =  3, 15, 12        # PAN : 30
        doc_max, inc_max, disc_max, credit_max     =  3, 12, 12, 13   # Inc : 40
    elif has_pan:
        geo_max, qa_max, ph_max, ai_max            = 15, 12, 13,  5   # FI  : 45
        pan_max, name_max, nsdl_max                =  5, 25, 25        # PAN : 55
        doc_max, inc_max, disc_max, credit_max     =  0,  0,  0,  0
    elif has_income:
        geo_max, qa_max, ph_max, ai_max            = 15, 10, 10,  5   # FI  : 40
        pan_max, name_max, nsdl_max                =  0,  0,  0        # PAN : —
        doc_max, inc_max, disc_max, credit_max     =  5, 15, 15, 25   # Inc : 60
    else:
        geo_max, qa_max, ph_max, ai_max            = 30, 20, 25, 25   # FI  : 100
        pan_max, name_max, nsdl_max                =  0,  0,  0
        doc_max, inc_max, disc_max, credit_max     =  0,  0,  0,  0

    # ── Location Integrity ──────────────────────────────────────
    max_pw  = geo_result.get("max_pairwise_distance_m", 0.0)
    n_pts   = geo_result.get("points_checked", 0)
    if n_pts == 0:
        geo_pts, geo_note = 0, "No GPS data captured during session"
    elif max_pw <= GEO_THRESHOLD_M:
        geo_pts, geo_note = geo_max, f"All {n_pts} GPS points within {max_pw:.0f}m"
    elif max_pw <= 1000:
        geo_pts, geo_note = geo_max // 2, f"GPS spread {max_pw:.0f}m — marginally exceeds threshold"
    elif max_pw <= 2000:
        geo_pts, geo_note = geo_max // 6, f"GPS spread {max_pw:.0f}m — significantly outside threshold"
    else:
        geo_pts, geo_note = 0, f"GPS spread {max_pw:.0f}m — indicates different locations"
    breakdown.append(("Location Integrity", geo_pts, geo_max, geo_note))

    # ── Interview Completeness ──────────────────────────────────
    total_q  = len(meta.questions)
    answered = sum(
        1 for qa in meta.questions
        if qa.answer and qa.answer.strip() not in ("", "(no answer)")
    )
    if total_q == 0:
        qa_pts, qa_note = 0, "No questions on record"
    else:
        qa_pts  = int(qa_max * answered / total_q)
        qa_note = f"{answered} of {total_q} questions answered"
    breakdown.append(("Interview Completeness", qa_pts, qa_max, qa_note))

    # ── Photo Documentation ─────────────────────────────────────
    captured = len(image_entries)
    if captured == 0:
        ph_pts, ph_note = 0, "No photos captured"
    elif captured >= EXPECTED_PHOTOS:
        ph_pts, ph_note = ph_max, f"All {captured} expected photos captured"
    else:
        ph_pts  = int(ph_max * captured / EXPECTED_PHOTOS)
        ph_note = f"{captured} of {EXPECTED_PHOTOS} expected photos captured"
    breakdown.append(("Photo Documentation", ph_pts, ph_max, ph_note))

    # ── AI Image Analysis ───────────────────────────────────────
    analysed = sum(1 for e in image_entries if e.get("analysis") and "⚠" not in e.get("analysis", "⚠"))
    if captured == 0:
        ai_pts, ai_note = 0, "No photos to analyse"
    else:
        ai_pts  = int(ai_max * analysed / max(captured, 1))
        ai_note = f"{analysed} of {captured} photos AI-analysed"
    breakdown.append(("AI Image Analysis", ai_pts, ai_max, ai_note))

    # ── PAN / Identity Verification ────────────────────────────
    if has_pan and pan_max > 0:
        ocr   = pan_verification.get("ocr", {})          # type: ignore[union-attr]
        nm    = pan_verification.get("name_match", {})   # type: ignore[union-attr]
        nsdl  = pan_verification.get("nsdl", {})         # type: ignore[union-attr]

        # PAN captured and readable
        pan_num = ocr.get("pan_number", "")
        if pan_num:
            pan_pts, pan_note = pan_max, f"PAN card captured — {pan_num[:5]}*****"
        else:
            pan_pts, pan_note = pan_max // 2, "PAN card captured but PAN number not readable"
        breakdown.append(("PAN Card Captured", pan_pts, pan_max, pan_note))

        # Name match
        if name_max > 0:
            if nm.get("matched"):
                nm_pts  = name_max
                nm_note = f"Name matches interview answer (score {nm.get('match_score', 0):.0%})"
            else:
                nm_pts  = 0
                nm_note = f"Name mismatch — PAN: '{nm.get('pan_name','')}' | Interview: '{nm.get('interview_name','')}'"
            breakdown.append(("Name Match (PAN vs Interview)", nm_pts, name_max, nm_note))

        # NSDL verification
        if nsdl_max > 0:
            if nsdl.get("verified"):
                nsdl_pts  = nsdl_max
                nsdl_note = f"PAN verified by NSDL — status: {nsdl.get('pan_status','ACTIVE')}"
            else:
                nsdl_pts  = 0
                nsdl_note = f"PAN not verified — status: {nsdl.get('pan_status','UNKNOWN')}"
            breakdown.append(("NSDL PAN Verification", nsdl_pts, nsdl_max, nsdl_note))

    # ── Financial Assessment (only when income doc available) ───
    if has_income:
        ia = income_analysis  # type: ignore[assignment]

        # 5. Income document provided (5 pts)
        breakdown.append(("Income Document Provided", 5, 5, "Bank statement uploaded and analysed"))

        # 6. Regular income pattern (15 pts)
        salary   = ia.get("salary_detected", False)
        avg_inc  = float(ia.get("avg_monthly_income", 0) or 0)
        if salary and avg_inc >= 20_000:
            inc_pts, inc_note = 15, f"Regular salary detected — avg ₹{avg_inc:,.0f}/month"
        elif salary:
            inc_pts, inc_note = 10, f"Salary detected but low income — avg ₹{avg_inc:,.0f}/month"
        elif avg_inc >= 15_000:
            inc_pts, inc_note = 8,  f"Non-salary income — avg ₹{avg_inc:,.0f}/month"
        elif avg_inc > 0:
            inc_pts, inc_note = 4,  f"Irregular/low income — avg ₹{avg_inc:,.0f}/month"
        else:
            inc_pts, inc_note = 0, "No regular income detected in bank statement"
        breakdown.append(("Regular Income Pattern", inc_pts, 15, inc_note))

        # 7. Financial discipline (15 pts)
        bounces  = int(ia.get("bounce_count", 0) or 0)
        exp_rat  = float(ia.get("expense_to_income_ratio", 1.0) or 1.0)
        if bounces == 0 and exp_rat <= 0.60:
            disc_pts, disc_note = 15, f"No bounces, excellent expense ratio {exp_rat:.0%}"
        elif bounces == 0 and exp_rat <= 0.75:
            disc_pts, disc_note = 10, f"No bounces, acceptable expense ratio {exp_rat:.0%}"
        elif bounces <= 1 and exp_rat <= 0.80:
            disc_pts, disc_note = 6,  f"{bounces} bounce(s), expense ratio {exp_rat:.0%}"
        elif bounces <= 3:
            disc_pts, disc_note = 3,  f"{bounces} bounced transactions detected"
        else:
            disc_pts, disc_note = 0, f"{bounces} bounced transactions — significant concern"
        breakdown.append(("Financial Discipline", disc_pts, 15, disc_note))

        # 8. AI creditworthiness score (25 pts — maps 0-10 → 0-25)
        cw_raw  = min(10, max(0, int(ia.get("creditworthiness_score", 0) or 0)))
        cw_pts  = int(25 * cw_raw / 10)
        cw_note = f"AI creditworthiness score: {cw_raw}/10 — {ia.get('summary', '')[:120]}"
        breakdown.append(("AI Credit Health", cw_pts, 25, cw_note))

    score = sum(b[1] for b in breakdown)

    if score >= 85:
        level, decision = "LOW RISK",           "RECOMMENDED FOR FURTHER PROCESSING"
    elif score >= 70:
        level, decision = "LOW-MEDIUM RISK",    "PROCEED WITH STANDARD VERIFICATION"
    elif score >= 55:
        level, decision = "MEDIUM RISK",        "ADDITIONAL VERIFICATION REQUIRED"
    elif score >= 40:
        level, decision = "HIGH RISK",          "MANDATORY MANUAL REVIEW"
    else:
        level, decision = "CRITICAL RISK",      "ESCALATE — DO NOT PROCESS"

    return score, breakdown, level, decision


# ── Section 1a: Applicant Basic Info ─────────────────────────────────────────

def _basic_info_section(meta: SessionMetadata, s: Dict) -> List:
    bi = meta.basic_info
    if not bi:
        return [_incomplete("Application form data not submitted", s)]

    def _req(v: str, field: str) -> str:
        return v.strip() if v and v.strip() else f"INCOMPLETE — {field} not provided"

    rows = [
        ("First Name",    _req(bi.first_name, "first name")),
        ("Last Name",     _req(bi.last_name,  "last name")),
        ("Date of Birth", _req(bi.dob,        "date of birth")),
        ("Address",       _req(bi.address,    "residential address")),
        ("City",          _req(bi.city,       "city")),
        ("PAN Number",       _req(bi.pan_number,   "PAN number")),
        ("Annual Income",    _req(bi.income_range, "income range")),
        ("Loan Amount",      f"Rs {bi.loan_amount:,.0f}" if bi.loan_amount else "INCOMPLETE — not provided"),
        ("Bank",             "ABC Bank"),
        ("Product",          "Personal Loan"),
    ]
    return [_kv_table(rows, s, label_w=5.0 * cm)]


# ── Section 1: Executive Summary ──────────────────────────────────────────────

def _summary_section(
    meta: SessionMetadata,
    customer: Dict[str, str],
    geo_result: Dict[str, Any],
    entries: List[Dict[str, Any]],
    score: int,
    risk_level: str,
    s: Dict,
) -> List:
    gen_time    = _now_ist()
    photo_count = len(entries)
    analysed    = sum(1 for e in entries if e.get("analysis") and "⚠" not in e.get("analysis", "⚠"))
    geo_ok      = geo_result.get("verified", False)
    max_pw      = geo_result.get("max_pairwise_distance_m", 0.0)

    case_rows = [
        ("Report Generated",    gen_time),
        ("Case / Session ID",   meta.session_id),
        ("Field Agent Device",  meta.device_id or "—"),
        ("Investigation Start", _ist(meta.started_at)),
        ("Investigation End",   _ist(meta.ended_at)),
        ("Duration",            _duration(meta.started_at, meta.ended_at)),
    ]
    applicant_rows = [
        ("Applicant Name",      customer.get("Full Name", "—")),
        ("Date of Birth",       customer.get("Date of Birth", "—")),
        ("Residential Address", customer.get("Residential Address",
                                customer.get("Pincode", "—"))),
        ("Mobile / Phone",      customer.get("Mobile / Phone", "—")),
        ("Monthly Income",      customer.get("Monthly Income", "—")),
        ("Employment",          customer.get("Employment / Employer", "—")),
    ]
    rec_name = meta.recording_filename or "Not available"
    status_rows = [
        ("Location Verification",
         f"{'PASS' if geo_ok else 'FAIL'}  (max spread {max_pw:.0f} m)"),
        ("Questions Answered",   f"{len(meta.questions)} questions on record"),
        ("Photos Captured",      f"{photo_count} photo(s)"),
        ("Photos AI-Analysed",   f"{analysed} of {photo_count}"),
        ("Session Recording",    rec_name),
        ("Overall Risk Score",   f"{score} / 100  —  {risk_level}"),
    ]

    col_half = CONTENT_W / 2 - 0.3 * cm
    left  = _kv_table(case_rows,      s, label_w=4.5 * cm)
    right = _kv_table(applicant_rows, s, label_w=4.5 * cm)
    split = Table([[left, right]], colWidths=[col_half, col_half])
    split.setStyle(TableStyle([
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("INNERGRID",    (0, 0), (-1, -1), 0, WHITE),
    ]))

    return [
        split,
        Spacer(1, 8),
        *_sub_header("Session Status", s),
        _kv_table(status_rows, s),
    ]


def _duration(start: str, end: str) -> str:
    try:
        fmt = "%Y-%m-%dT%H:%M:%SZ"
        s = datetime.strptime(start[:19].replace(" ", "T") + "Z", fmt)
        e = datetime.strptime(end[:19].replace(" ", "T") + "Z", fmt)
        secs = int((e - s).total_seconds())
        return f"{secs // 60} min {secs % 60} sec"
    except Exception:
        return "—"


# ── Section 2: Applicant Profile ──────────────────────────────────────────────

def _profile_section(customer: Dict[str, str], meta: SessionMetadata, s: Dict) -> List:
    if not customer:
        return [Paragraph("No applicant data extracted.", s["value"])]

    rows = [(k, v) for k, v in customer.items()]
    return [_kv_table(rows, s, label_w=5.5 * cm)]


# ── Section 3: Field Interview Q&A ────────────────────────────────────────────

def _qa_section(meta: SessionMetadata, s: Dict) -> List:
    flowables: List = []
    if not meta.questions:
        return [_incomplete("No interview Q&A recorded — session may have been interrupted", s)]
    unanswered = [qa for qa in meta.questions if not (qa.answer and qa.answer.strip())]
    if unanswered:
        flowables.append(_incomplete(
            f"{len(unanswered)} of {len(meta.questions)} questions have no answer", s
        ))
        flowables.append(Spacer(1, 6))

    th = lambda t: _hdr_style_cell(t, s)
    data = [[th("#"), th("Question"), th("Answer Recorded"), th("GPS at Time of Answer")]]

    for i, qa in enumerate(meta.questions, 1):
        geo_str  = _fmt_geo(qa.geo) if qa.geo else "INCOMPLETE — GPS not captured"
        ans_text = qa.answer.strip() if qa.answer and qa.answer.strip() else "INCOMPLETE — no answer recorded"
        data.append([
            Paragraph(str(i), s["small_bold"]),
            Paragraph(qa.question, s["value"]),
            Paragraph(ans_text, s["value"]),
            Paragraph(geo_str, s["small"]),
        ])

    cw = [0.6*cm, CONTENT_W*0.32, CONTENT_W*0.34, CONTENT_W*0.28]
    tbl = Table(data, colWidths=cw)
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), BLACK),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [WHITE, XL_GREY]),
        ("GRID",          (0, 0), (-1, -1), 0.4, B_GREY),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("ALIGN",         (0, 0), (0, -1),  "CENTER"),
    ]))
    flowables.append(tbl)
    return flowables


# ── Section 4: Location Report ────────────────────────────────────────────────

def _location_section(geo_result: Dict[str, Any], address: str, s: Dict) -> List:
    max_pw   = geo_result.get("max_pairwise_distance_m", 0.0)
    c_lat    = geo_result.get("centroid_lat")
    c_lon    = geo_result.get("centroid_lon")
    details  = geo_result.get("details", [])
    passed   = max_pw <= GEO_THRESHOLD_M

    flowables: List = []

    # Determine address display
    no_gps = geo_result.get("points_checked", 0) == 0
    if no_gps:
        addr_display = "Not available — GPS was not captured during this session"
    elif address and address not in ("", "—"):
        addr_display = address
    else:
        addr_display = "Address lookup failed (check Google Maps API key)"

    centroid_str = (f"{c_lat:.5f}°N, {c_lon:.5f}°E" if c_lat else "—")
    maps_link    = (f"https://maps.google.com/?q={c_lat},{c_lon}" if c_lat else "—")
    summary_rows = [
        ("Geocoded Address",        addr_display),
        ("Session Centroid (GPS)",  centroid_str),
        ("Google Maps Link",        maps_link),
        ("Total GPS Points",        str(geo_result.get("points_checked", 0))),
        ("Max Pairwise Distance",   f"{max_pw:.1f} m"),
        ("Verification Threshold",  f"{GEO_THRESHOLD_M:.0f} m"),
        ("Location Status",         "PASS — all points within threshold" if passed
                                    else f"FAIL — spread of {max_pw:.0f}m exceeds {GEO_THRESHOLD_M:.0f}m limit"),
    ]
    flowables += [_kv_table(summary_rows, s), Spacer(1, 8)]
    flowables += [_status_pill(
        f"LOCATION VERIFICATION:  {'PASS' if passed else 'FAIL'}  "
        f"({'within' if passed else 'exceeds'} {GEO_THRESHOLD_M:.0f}m threshold)",
        ok=passed,
    ), Spacer(1, 10)]

    if not details:
        flowables.append(Paragraph("No geo points captured — location could not be verified.", s["value"]))
        return flowables

    # Per-point detail table
    th = lambda t: _hdr_style_cell(t, s)
    data = [[th("Event"), th("Latitude"), th("Longitude"), th("Captured At"), th("Dist. Centroid"), th("Status")]]
    for pt in details:
        ts   = pt.get("timestamp", "")[:19].replace("T", " ")
        dist = pt.get("distance_from_centroid_m", 0)
        ok   = pt.get("within_radius", False)
        data.append([
            Paragraph(pt.get("label", ""), s["small"]),
            Paragraph(f"{pt['latitude']:.5f}", s["small"]),
            Paragraph(f"{pt['longitude']:.5f}", s["small"]),
            Paragraph(ts, s["small"]),
            Paragraph(f"{dist:.0f} m", s["small"]),
            Paragraph("OK" if ok else "FAIL", s["small_bold"]),
        ])

    cw = [CONTENT_W*0.28, CONTENT_W*0.13, CONTENT_W*0.13,
          CONTENT_W*0.22, CONTENT_W*0.12, CONTENT_W*0.12]
    tbl = Table(data, colWidths=cw)
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), BLACK),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [WHITE, XL_GREY]),
        ("GRID",          (0, 0), (-1, -1), 0.4, B_GREY),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 5),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ]))
    flowables.append(tbl)
    return flowables


# ── Analysis text parser ──────────────────────────────────────────────────────

def _parse_analysis(text: str, s: Dict) -> List:
    """
    Convert OpenAI analysis text (markdown headings + bullets) into clean
    ReportLab flowables for the PDF report.
    """
    import re

    flowables: List = []
    BLUE_HDR  = colors.HexColor("#0D47A1")
    hdr_style = ParagraphStyle(
        "ana_hdr", parent=s["small_bold"],
        textColor=BLUE_HDR,
        spaceBefore=4, spaceAfter=1,
    )
    bul_style = ParagraphStyle(
        "ana_bul", parent=s["small"],
        leftIndent=10, spaceBefore=1,
    )
    score_style = ParagraphStyle(
        "ana_score", parent=s["small_bold"],
        textColor=D_GREY, spaceBefore=4,
        borderPad=2,
    )

    BLUE_C = colors.HexColor("#0D47A1")

    for raw_line in text.replace("\r\n", "\n").split("\n"):
        line = raw_line.strip()
        if not line:
            continue

        # **Header**: value
        m = re.match(r'^\*\*(.+?)\*\*[:\-]?\s*(.*)', line)
        if m:
            key = m.group(1).replace('*', '').strip().rstrip(':')
            val = m.group(2).strip()
            if 'score' in key.lower() or 'score' in val.lower():
                display = f"{key}: {val}" if val else key
                tbl = Table([[Paragraph(f"<b>{display}</b>",
                    ParagraphStyle("sc", parent=s["small_bold"],
                                   textColor=BLUE_C, alignment=1))]],
                    colWidths=["100%"])
                tbl.setStyle(TableStyle([
                    ("BACKGROUND",    (0,0), (-1,-1), colors.HexColor("#E8EDF8")),
                    ("TOPPADDING",    (0,0), (-1,-1), 3),
                    ("BOTTOMPADDING", (0,0), (-1,-1), 3),
                    ("LEFTPADDING",   (0,0), (-1,-1), 6),
                    ("BOX",           (0,0), (-1,-1), 0.5, BLUE_C),
                ]))
                flowables += [Spacer(1, 3), tbl]
            else:
                label = ParagraphStyle("ahl", parent=s["small_bold"],
                                       textColor=BLUE_C, spaceBefore=4)
                if val:
                    flowables.append(Paragraph(f"<b>{key}:</b>  {val}", label))
                else:
                    flowables.append(Paragraph(f"<b>{key}</b>", label))
            continue

        # Bullet: - text  or  • text
        if line.startswith(('- ', '• ', '* ')):
            body = line[2:].strip()
            colon_pos = body.find(':')
            if 0 < colon_pos < 20:
                lbl, rest = body[:colon_pos].strip(), body[colon_pos+1:].strip()
                flowables.append(Paragraph(
                    f"  •  <b>{lbl}:</b> {rest}", bul_style))
            else:
                flowables.append(Paragraph(f"  •  {body}", bul_style))
            continue

        # Plain / fallback
        clean = re.sub(r'\*+', '', line).strip()
        if clean:
            flowables.append(Paragraph(clean, s["small"]))

    return flowables or [Paragraph("No analysis available.", s["small"])]


# ── Section 5: Property Documentation ────────────────────────────────────────

def _images_section(entries: List[Dict[str, Any]], s: Dict) -> List:
    flowables: List = []
    IMG_W = 7.2 * cm
    IMG_H = 5.8 * cm
    ANA_W = CONTENT_W - IMG_W - 0.6 * cm

    for idx, entry in enumerate(entries, 1):
        file_path: Path = entry.get("file_path", Path(""))
        prompt          = entry.get("prompt", "")
        analysis        = entry.get("analysis", "No AI analysis available.")
        filename        = entry.get("filename", "")
        geo_str         = _fmt_geo(entry.get("geo")) if entry.get("geo") else "GPS not captured"
        selfie          = entry.get("is_selfie", False)
        photo_type      = "Self-Portrait (Applicant)" if selfie else "Property Photo"

        # Image cell
        if file_path.exists():
            try:
                img_cell = RLImage(str(file_path), width=IMG_W, height=IMG_H, kind="proportional")
            except Exception as exc:
                logger.warning("[Report] Cannot embed %s: %s", filename, exc)
                img_cell = Paragraph(f"[Image unavailable: {exc}]", s["small"])
        else:
            img_cell = Paragraph("[Image file not found on server]", s["small"])

        # ── Analysis: parsed bullets
        analysis_lines = _parse_analysis(analysis, s)

        # Photo + analysis side-by-side card
        img_inner = Table([[img_cell, analysis_lines]], colWidths=[IMG_W, ANA_W])
        img_inner.setStyle(TableStyle([
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
            ("TOPPADDING",    (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("BACKGROUND",    (0, 0), (0, -1),  colors.black),
            ("BACKGROUND",    (1, 0), (1, -1),  WHITE),
            ("LINEAFTER",     (0, 0), (0, -1),  0.5, B_GREY),
        ]))

        # Slim metadata strip above the photo card
        ocr_text = entry.get("nameplate_ocr", {}).get("raw_text", "") if entry.get("nameplate_ocr") else ""
        meta_parts = [
            f"Photo {idx}  |  {photo_type}",
            f"GPS: {geo_str}",
        ]
        if ocr_text:
            meta_parts.append(f"Nameplate OCR: {ocr_text[:120]}")

        meta_strip = Table(
            [[Paragraph("  " + "   │  ".join(meta_parts), s["small"])]],
            colWidths=[CONTENT_W],
        )
        meta_strip.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#E8EDF8")),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("BOX",           (0, 0), (-1, -1), 0.5, B_GREY),
        ]))

        # Prompt label
        prompt_para = Paragraph(
            f"<b>Evidence {idx}:</b>  {prompt}",
            ParagraphStyle("ep", parent=s["label"],
                           textColor=colors.HexColor("#0D47A1"), spaceBefore=8),
        )

        flowables.append(KeepTogether([
            prompt_para,
            Spacer(1, 3),
            meta_strip,
            img_inner,
            Spacer(1, 14),
        ]))

    return flowables


# ── Section 5b: PAN Card Verification ────────────────────────────────────────

def _pan_section(pan_verification: Optional[Dict[str, Any]], s: Dict) -> List:
    if not pan_verification:
        return [_incomplete("PAN card not captured — identity verification not completed", s)]

    ocr   = pan_verification.get("ocr",        {})
    nm    = pan_verification.get("name_match",  {})
    nsdl  = pan_verification.get("nsdl",        {})
    geo   = pan_verification.get("geo")

    if ocr.get("error"):
        return [Paragraph(f"PAN OCR could not be completed: {ocr['error']}", s["value"])]

    pan_raw = ocr.get("pan_number", "")
    pan_masked = (pan_raw[:5] + "****" + pan_raw[-1]) if len(pan_raw) == 10 else pan_raw or "Not detected"

    flowables: List = []

    # ── OCR results ──────────────────────────────────────────────────────────
    flowables += _sub_header("Extracted PAN Details  (via AWS Textract OCR)", s)
    ocr_rows = [
        ("PAN Number",     pan_masked),
        ("Name on PAN",    ocr.get("name", "Not detected")),
        ("Father's Name",  ocr.get("father_name", "Not detected")),
        ("Date of Birth",  ocr.get("dob", "Not detected")),
        ("GPS at Capture", _fmt_geo(geo) if geo else "Not captured"),
    ]
    flowables.append(_kv_table(ocr_rows, s))
    flowables.append(Spacer(1, 8))

    # ── 2-way name match ─────────────────────────────────────────────────────
    flowables += _sub_header("Name Verification  (PAN vs Video Interview)", s)
    matched    = nm.get("matched", False)
    score_pct  = f"{nm.get('match_score', 0):.0%}"
    match_rows = [
        ("Name on PAN",          nm.get("pan_name",       "—")),
        ("Name from Interview",   nm.get("interview_name", "—")),
        ("Match Score",           score_pct),
        ("Verification Result",   "MATCHED" if matched else "NOT MATCHED — Manual Review Required"),
    ]
    flowables.append(_kv_table(match_rows, s))
    flowables.append(Spacer(1, 8))

    # ── 3-way name match (form + PAN + nameplate) ─────────────────────────
    tw = pan_verification.get("three_way_match", {})
    if tw:
        flowables += _sub_header("3-Way Name Match  (Application Form + PAN Card + Home Nameplate)", s)
        tw_ok = tw.get("all_match", False)
        tw_rows = [
            ("Application Form Name", tw.get("form_first_name",      "—")),
            ("PAN Card Name",         tw.get("pan_first_name",        "—")),
            ("Nameplate Name",        tw.get("nameplate_first_name",  "Not detected")),
            ("Form vs PAN",           "MATCHED" if tw.get("form_vs_pan")        else "NOT MATCHED"),
            ("Form vs Nameplate",     "MATCHED" if tw.get("form_vs_nameplate")  else "NOT MATCHED / N/A"),
            ("PAN vs Nameplate",      "MATCHED" if tw.get("pan_vs_nameplate")   else "NOT MATCHED / N/A"),
            ("Overall 3-Way Result",  "ALL NAMES MATCH" if tw_ok else f"DISCREPANCY DETECTED — {tw.get('notes','')}"),
        ]
        if tw.get("missing_sources"):
            tw_rows.append(("Missing Sources", ", ".join(tw["missing_sources"])))
        flowables.append(_kv_table(tw_rows, s))
        flowables.append(Spacer(1, 8))

    # ── NSDL verification ────────────────────────────────────────────────────
    flowables += _sub_header("PAN Verification  (NSDL — Income Tax Dept., Govt. of India)", s)
    v = nsdl.get("verified", False)
    nsdl_rows = [
        ("PAN Number",          pan_masked),
        ("PAN Status",          nsdl.get("pan_status", "—")),
        ("PAN Category",        nsdl.get("pan_type",   "—")),
        ("Name as per NSDL",    nsdl.get("name_as_per_nsdl", "—")),
        ("Name Match",          "MATCHED" if nsdl.get("name_match")        else "NOT MATCHED"),
        ("Father's Name Match", "MATCHED" if nsdl.get("father_name_match") else "NOT MATCHED"),
        ("DOB Match",           "MATCHED" if nsdl.get("dob_match")         else "NOT MATCHED"),
        ("Aadhaar Seeded",      "YES"     if nsdl.get("aadhaar_seeded")    else "NOT CONFIRMED"),
        ("Verification Time",   _ist(nsdl.get("verified_at", ""))),
        ("Data Source",         nsdl.get("source", "NSDL — Income Tax Department")),
    ]
    flowables.append(_kv_table(nsdl_rows, s))
    flowables.append(Spacer(1, 8))

    # ── Face match ───────────────────────────────────────────────────────────
    fm = pan_verification.get("face_match", {})
    if fm and not fm.get("error"):
        flowables += _sub_header("Biometric Face Verification  (Selfie vs PAN Card — AWS Rekognition)", s)
        fm_rows = [
            ("Similarity Score",  f"{fm.get('similarity_score', 0):.1f}%"),
            ("Match Status",      fm.get("comparison_status", "—")),
            ("Face in Selfie",    "YES" if fm.get("face_detected_in_selfie") else "NOT DETECTED"),
            ("Result",            "FACE MATCH CONFIRMED" if fm.get("matched") else "FACE MISMATCH — REVIEW REQUIRED"),
        ]
        flowables.append(_kv_table(fm_rows, s))
        flowables.append(Spacer(1, 8))

    # ── Status banner ────────────────────────────────────────────────────────
    fm_ok      = fm.get("matched", False) if fm and not fm.get("error") else True
    overall_ok = v and matched and fm_ok
    flowables.append(_status_pill(
        f"PAN VERIFICATION STATUS:  {'VERIFIED & MATCHED' if overall_ok else 'REQUIRES REVIEW'}",
        ok=overall_ok,
    ))
    return flowables


# ── CIBIL Score section ───────────────────────────────────────────────────────

def _cibil_section(cibil: Optional[Dict[str, Any]], s: Dict) -> List:
    if not cibil:
        return [_incomplete("CIBIL score could not be retrieved — PAN number required", s)]

    score   = cibil.get("score", 0)
    grade   = cibil.get("grade", "")
    label   = cibil.get("label", "")
    color_h = cibil.get("color", "#555555")
    msg     = cibil.get("message", "")
    rec     = cibil.get("recommendation", "")

    # Score colour mapped to ReportLab
    score_color = colors.HexColor(color_h)

    # Big score display
    score_style = ParagraphStyle(
        "cibil_score", parent=s["risk_score"],
        textColor=score_color, fontSize=44, alignment=1,
    )
    label_style = ParagraphStyle(
        "cibil_lbl", parent=s["risk_label"],
        textColor=score_color, fontSize=14, alignment=1,
    )

    # Visual score bar (300–900 range)
    BAR_CELLS = 12
    filled = max(0, min(BAR_CELLS, round((score - 300) / (600 / BAR_CELLS))))
    bar_data = [[""] * BAR_CELLS]
    bar_tbl  = Table(bar_data, colWidths=[CONTENT_W / BAR_CELLS] * BAR_CELLS, rowHeights=[0.5 * cm])
    bar_cmds: list = [("GRID", (0, 0), (-1, -1), 0.3, B_GREY)]
    for i in range(BAR_CELLS):
        bg = score_color if i < filled else L_GREY
        bar_cmds.append(("BACKGROUND", (i, 0), (i, 0), bg))
    bar_tbl.setStyle(TableStyle(bar_cmds))

    score_block = Table(
        [
            [Paragraph(str(score), score_style)],
            [Paragraph(f"{label}  —  {msg}", label_style)],
            [Spacer(1, 4)],
            [bar_tbl],
            [Paragraph(f"Range: 300 (lowest) ←{'─' * 20}→ 900 (highest)", s["small"])],
        ],
        colWidths=[CONTENT_W],
    )
    score_block.setStyle(TableStyle([
        ("BOX",           (0, 0), (-1, -1), 1.5, score_color),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
    ]))

    # Detail rows
    detail_rows = [
        ("CIBIL Score",        str(score)),
        ("Credit Grade",       f"{grade}  —  {label}"),
        ("Assessment",         msg),
        ("Loan Recommendation",rec),
        ("PAN Number",         cibil.get("pan_number", "—")),
        ("Bureau",             cibil.get("bureau", "TransUnion CIBIL")),
        ("Report Date",        cibil.get("report_date", "—")),
    ]

    # Reference bands
    bands_data = [
        [Paragraph("Score Range", s["small_bold"]),
         Paragraph("Grade", s["small_bold"]),
         Paragraph("Eligibility", s["small_bold"])],
        [Paragraph("800 – 900", s["small"]), Paragraph("Excellent", s["small"]), Paragraph("Best rates", s["small"])],
        [Paragraph("750 – 799", s["small"]), Paragraph("Very Good",  s["small"]), Paragraph("Standard rates", s["small"])],
        [Paragraph("700 – 749", s["small"]), Paragraph("Good",       s["small"]), Paragraph("Eligible", s["small"])],
        [Paragraph("650 – 699", s["small"]), Paragraph("Fair",       s["small"]), Paragraph("Conditional", s["small"])],
        [Paragraph("600 – 649", s["small"]), Paragraph("Poor",       s["small"]), Paragraph("High risk", s["small"])],
        [Paragraph("300 – 599", s["small"]), Paragraph("Very Poor",  s["small"]), Paragraph("Decline", s["small"])],
    ]
    bw = CONTENT_W / 3
    bands_tbl = Table(bands_data, colWidths=[bw, bw, bw])
    bands_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), BLACK),
        ("TEXTCOLOR",     (0, 0), (-1, 0), WHITE),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [WHITE, XL_GREY]),
        ("GRID",          (0, 0), (-1, -1), 0.4, B_GREY),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        # Highlight applicant's row
        *([("BACKGROUND", (0, 1 + max(0, 5 - max(0, (score - 300) // 100))),
             (-1, 1 + max(0, 5 - max(0, (score - 300) // 100))),
             colors.HexColor("#E8F5E9"))] if score >= 700 else []),
    ]))

    return [
        score_block,
        Spacer(1, 10),
        _kv_table(detail_rows, s),
        Spacer(1, 10),
        *_sub_header("CIBIL Score Reference Table", s),
        bands_tbl,
    ]


# ── Section 5d: Income & Financial Analysis ───────────────────────────────────

def _income_section(
    income_analysis: Optional[Dict[str, Any]],
    meta: SessionMetadata,
    s: Dict,
) -> List:
    if not income_analysis:
        return [_incomplete("Bank statement not uploaded — income verification not completed", s)]

    err = income_analysis.get("error")
    if err:
        return [_incomplete(f"Bank statement analysis failed: {err}", s)]

    ia = income_analysis

    def _inr(v) -> str:
        try:
            return f"₹ {float(v):,.0f}"
        except (TypeError, ValueError):
            return "—"

    def _pct(v) -> str:
        try:
            return f"{float(v) * 100:.1f}%"
        except (TypeError, ValueError):
            return "—"

    summary_rows = [
        ("Statement Period",        f"{ia.get('months_covered', '—')} months"),
        ("Avg Monthly Income",      _inr(ia.get("avg_monthly_income"))),
        ("Avg Monthly Expenses",    _inr(ia.get("avg_monthly_expenses"))),
        ("Avg Monthly Net Savings", _inr(ia.get("avg_monthly_savings"))),
        ("Expense / Income Ratio",  _pct(ia.get("expense_to_income_ratio"))),
        ("Salary / Regular Income", "YES" if ia.get("salary_detected") else "NO"),
        ("Income Sources",          ", ".join(ia.get("income_sources", [])) or "—"),
        ("EMI / Loan Payments",     str(ia.get("emi_count", 0))),
        ("Bounced Transactions",    str(ia.get("bounce_count", 0))),
        ("Creditworthiness Score",  f"{ia.get('creditworthiness_score', '—')} / 10"),
    ]

    # Document reference
    doc_name = "—"
    if meta.documents:
        bank_doc = next((d for d in meta.documents if d.document_type == "bank_statement"), None)
        if bank_doc:
            doc_name = bank_doc.filename

    doc_rows = [("Document File", doc_name)]

    # Risk flags and positive indicators
    flags     = ia.get("risk_flags", [])
    positives = ia.get("positive_indicators", [])
    summary   = ia.get("summary", "")

    flowables: List = []
    flowables += [_kv_table(doc_rows + summary_rows, s), Spacer(1, 8)]

    # Summary paragraph
    if summary:
        flowables.append(Paragraph(f"AI Assessment: {summary}", s["value"]))
        flowables.append(Spacer(1, 8))

    # Flags + positives side by side
    col_half = CONTENT_W / 2 - 0.2 * cm

    def _bullet_list(items: List[str], icon: str, style) -> List:
        out = []
        for item in items:
            out.append(Paragraph(f"  {icon}  {item}", style))
            out.append(Spacer(1, 2))
        return out or [Paragraph("None identified.", style)]

    neg_style = ParagraphStyle("neg", parent=s["bullet"], fontName="Helvetica-Bold", textColor=D_GREY)
    left_cell  = _bullet_list(flags,     "✗", neg_style)
    right_cell = _bullet_list(positives, "✓", s["bullet"])

    flags_tbl = Table(
        [[
            [Paragraph("Risk Flags", s["sub_hdr"])] + left_cell,
            [Paragraph("Positive Indicators", s["sub_hdr"])] + right_cell,
        ]],
        colWidths=[col_half, col_half],
    )
    flags_tbl.setStyle(TableStyle([
        ("BOX",          (0, 0), (-1, -1), 0.5, B_GREY),
        ("INNERGRID",    (0, 0), (-1, -1), 0.5, B_GREY),
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",   (0, 0), (-1, -1), 6),
        ("LEFTPADDING",  (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 6),
    ]))
    flowables.append(flags_tbl)
    return flowables


# ── Section X: AI Credit Analysis ────────────────────────────────────────────

def _ai_credit_section(credit_analysis: Optional[Dict[str, Any]], s: Dict) -> List:
    if not credit_analysis or credit_analysis.get("error"):
        msg = credit_analysis.get("error", "Not performed") if credit_analysis else "Not performed"
        return [Paragraph(f"AI credit analysis not available: {msg}", s["value"])]

    ca = credit_analysis
    flowables: List = []

    # Score + grade + recommendation
    score  = ca.get("overall_credit_score", 0)
    grade  = ca.get("risk_grade", "—")
    rec    = ca.get("recommendation", "—")
    elig   = ca.get("loan_eligibility_inr", 0)

    overview_rows = [
        ("Overall Credit Score", f"{score} / 100"),
        ("Risk Grade",           grade),
        ("Recommendation",       rec),
        ("Estimated Eligibility",f"₹ {elig:,.0f}" if elig else "Subject to final review"),
    ]
    flowables.append(_kv_table(overview_rows, s))
    flowables.append(Spacer(1, 8))

    # Executive summary
    summary = ca.get("executive_summary", "")
    if summary:
        flowables.append(Paragraph(f"<b>Credit Assessment:</b>  {summary}", s["value"]))
        flowables.append(Spacer(1, 8))

    # Detailed credit narrative (new fields from enhanced prompt)
    for field_key, field_label in [
        ("creditworthiness_narrative",       "Creditworthiness Analysis"),
        ("lifestyle_vs_income_assessment",   "Lifestyle vs Declared Income"),
        ("repayment_capacity_analysis",      "Repayment Capacity"),
    ]:
        narrative = ca.get(field_key, "")
        if narrative:
            flowables += _sub_header(field_label, s)
            flowables.append(Paragraph(narrative, s["value"]))
            flowables.append(Spacer(1, 6))

    # Four assessment pillars
    pillar_keys = [
        ("Identity Assessment",  "identity_assessment"),
        ("Residence Assessment", "residence_assessment"),
        ("Income Assessment",    "income_assessment"),
        ("Location Assessment",  "location_assessment"),
    ]
    col_half = CONTENT_W / 2 - 0.2 * cm

    pillar_cells = []
    for title, key in pillar_keys:
        p = ca.get(key, {})
        p_score   = p.get("score", 0)
        p_summary = p.get("summary", "")
        p_flags   = p.get("flags", [])
        cell_paras = [
            Paragraph(f"{title}  ({p_score}/25)", s["sub_hdr"]),
            Spacer(1, 4),
            Paragraph(p_summary, s["small"]),
        ]
        for flag in p_flags:
            cell_paras.append(Paragraph(f"  ✗  {flag}", s["small"]))
        pillar_cells.append(cell_paras)

    for i in range(0, len(pillar_cells), 2):
        row = pillar_cells[i:i+2]
        while len(row) < 2:
            row.append([Paragraph("", s["small"])])
        tbl = Table([row], colWidths=[col_half, col_half])
        tbl.setStyle(TableStyle([
            ("BOX",         (0, 0), (-1, -1), 0.5, B_GREY),
            ("INNERGRID",   (0, 0), (-1, -1), 0.5, B_GREY),
            ("VALIGN",      (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING",  (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING",(0, 0),(-1,-1), 6),
        ]))
        flowables += [tbl, Spacer(1, 6)]

    # Positive / risk factors
    pos   = ca.get("positive_factors", [])
    risks = ca.get("risk_factors", [])
    cond  = ca.get("conditions", [])

    neg_style = ParagraphStyle("neg_ai", parent=s["bullet"], fontName="Helvetica-Bold")

    def _items(items, icon, style):
        out = []
        for item in items:
            out.append(Paragraph(f"  {icon}   {item}", style))
            out.append(Spacer(1, 2))
        return out or [Paragraph("None identified.", style)]

    sides = [
        _items(pos,   "✓", s["bullet"]),
        _items(risks, "✗", neg_style),
    ]
    factor_tbl = Table(
        [[
            [Paragraph("Positive Factors", s["sub_hdr"])] + sides[0],
            [Paragraph("Risk Factors",     s["sub_hdr"])] + sides[1],
        ]],
        colWidths=[col_half, col_half],
    )
    factor_tbl.setStyle(TableStyle([
        ("BOX",         (0, 0), (-1, -1), 0.5, B_GREY),
        ("INNERGRID",   (0, 0), (-1, -1), 0.5, B_GREY),
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",  (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING",(0,0),(-1,-1), 6),
    ]))
    flowables.append(factor_tbl)

    if cond:
        flowables += [Spacer(1, 8), *_sub_header("Loan Conditions", s)]
        for c in cond:
            flowables.append(Paragraph(f"  •  {c}", s["bullet"]))
    return flowables


# ── Section 6: Risk Assessment ────────────────────────────────────────────────

def _risk_section(
    score: int,
    breakdown: RiskBreakdown,
    risk_level: str,
    decision: str,
    s: Dict,
) -> List:
    CELLS = 20  # each cell = 5 points
    filled = min(CELLS, round(score / (100 / CELLS)))

    # Score bar
    bar_row = [
        Table([[""]], colWidths=[CONTENT_W / CELLS], rowHeights=[0.7 * cm])
        for _ in range(CELLS)
    ]
    bar_data = [[""]*CELLS]
    bar_cw   = [CONTENT_W / CELLS] * CELLS
    bar_tbl  = Table(bar_data, colWidths=bar_cw, rowHeights=[0.7 * cm])
    bar_cmds = [("GRID", (0,0), (-1,-1), 0.3, B_GREY)]
    for i in range(CELLS):
        bg = D_GREY if i < filled else XL_GREY
        bar_cmds.append(("BACKGROUND", (i, 0), (i, 0), bg))
    bar_tbl.setStyle(TableStyle(bar_cmds))

    # Score display + bar
    score_block = Table(
        [
            [Paragraph(str(score), s["risk_score"])],
            [Paragraph("out of 100", s["risk_sub"])],
            [Spacer(1, 4)],
            [bar_tbl],
            [Spacer(1, 4)],
            [Paragraph(risk_level, s["risk_label"])],
        ],
        colWidths=[CONTENT_W],
    )
    score_block.setStyle(TableStyle([
        ("BOX",           (0, 0), (-1, -1), 1, BLACK),
        ("BACKGROUND",    (0, 0), (-1, -1), WHITE),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))

    # Breakdown table
    th = lambda t: _hdr_style_cell(t, s)
    bd_data = [[th("Risk Component"), th("Score"), th("Max"), th("Weight %"), th("Notes")]]
    for component, earned, maximum, note in breakdown:
        weight = f"{maximum}%"
        bd_data.append([
            Paragraph(component, s["value"]),
            Paragraph(str(earned), s["small_bold"]),
            Paragraph(str(maximum), s["small"]),
            Paragraph(weight, s["small"]),
            Paragraph(note, s["small"]),
        ])
    # Totals row
    bd_data.append([
        Paragraph("TOTAL RISK SCORE", s["label"]),
        Paragraph(str(score), s["small_bold"]),
        Paragraph("100", s["small"]),
        Paragraph("100%", s["small"]),
        Paragraph(risk_level, s["small_bold"]),
    ])

    bd_cw = [CONTENT_W*0.25, CONTENT_W*0.08, CONTENT_W*0.08,
             CONTENT_W*0.10, CONTENT_W*0.49]
    bd_tbl = Table(bd_data, colWidths=bd_cw)
    last = len(bd_data) - 1
    bd_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),       BLACK),
        ("BACKGROUND",    (0, last), (-1, last),  L_GREY),
        ("ROWBACKGROUNDS",(0, 1), (-1, last-1),   [WHITE, XL_GREY]),
        ("GRID",          (0, 0), (-1, -1),       0.4, B_GREY),
        ("TOPPADDING",    (0, 0), (-1, -1),       5),
        ("BOTTOMPADDING", (0, 0), (-1, -1),       5),
        ("LEFTPADDING",   (0, 0), (-1, -1),       6),
        ("VALIGN",        (0, 0), (-1, -1),       "TOP"),
        ("FONTNAME",      (0, last), (-1, last),  "Helvetica-Bold"),
        ("LINEABOVE",     (0, last), (-1, last),  1, BLACK),
    ]))

    # Score legend
    legend = [
        ("85 – 100", "LOW RISK",       "Recommended for further processing"),
        ("70 – 84",  "LOW-MEDIUM RISK","Proceed with standard verification"),
        ("55 – 69",  "MEDIUM RISK",    "Additional verification required"),
        ("40 – 54",  "HIGH RISK",      "Mandatory manual review"),
        ("0 – 39",   "CRITICAL RISK",  "Escalate — do not process"),
    ]
    leg_data = [[th("Score Range"), th("Risk Level"), th("Recommended Action")]]
    for rng, lvl, action in legend:
        leg_data.append([
            Paragraph(rng,    s["small"]),
            Paragraph(lvl,    s["small_bold"]),
            Paragraph(action, s["small"]),
        ])
    leg_cw = [CONTENT_W*0.18, CONTENT_W*0.27, CONTENT_W*0.55]
    leg_tbl = Table(leg_data, colWidths=leg_cw)
    leg_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), BLACK),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [WHITE, XL_GREY]),
        ("GRID",          (0, 0), (-1, -1), 0.4, B_GREY),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
    ]))

    return [
        score_block,
        Spacer(1, 10),
        *_sub_header("Score Breakdown", s),
        bd_tbl,
        Spacer(1, 10),
        *_sub_header("Risk Level Reference", s),
        leg_tbl,
    ]


# ── Section 7: Recommendations & Final Decision ───────────────────────────────

def _recommendation_section(
    meta: SessionMetadata,
    geo_result: Dict[str, Any],
    entries: List[Dict[str, Any]],
    score: int,
    risk_level: str,
    decision: str,
    s: Dict,
) -> List:
    geo_ok      = geo_result.get("verified", False)
    max_pw      = geo_result.get("max_pairwise_distance_m", 0.0)
    photo_count = len(entries)
    analysed    = sum(1 for e in entries if e.get("analysis") and "⚠" not in e.get("analysis", "⚠"))
    total_q     = len(meta.questions)
    answered    = sum(1 for qa in meta.questions
                      if qa.answer and qa.answer.strip() not in ("", "(no answer)"))

    # Build structured findings
    findings: List[Tuple[bool, str]] = []   # (is_positive, text)

    # Geo
    if geo_ok:
        findings.append((True,  f"Location verified — all GPS readings within {max_pw:.0f}m of session centroid"))
    else:
        findings.append((False, f"Location NOT verified — GPS spread of {max_pw:.0f}m exceeds {GEO_THRESHOLD_M:.0f}m limit"))

    # Q&A completeness
    if answered == total_q and total_q > 0:
        findings.append((True,  f"All {total_q} interview questions answered by applicant"))
    elif answered == 0:
        findings.append((False, "No interview questions were answered"))
    else:
        findings.append((False, f"{total_q - answered} of {total_q} questions left unanswered"))

    # Photos
    if photo_count >= EXPECTED_PHOTOS:
        findings.append((True,  f"Full photo documentation — {photo_count} photos captured"))
    elif photo_count == 0:
        findings.append((False, "No property photos captured during session"))
    else:
        findings.append((False, f"Partial photo documentation — {photo_count} of {EXPECTED_PHOTOS} expected photos"))

    # AI analysis
    if photo_count > 0 and analysed == photo_count:
        findings.append((True,  f"All {photo_count} photos successfully AI-analysed"))
    elif photo_count > 0 and analysed < photo_count:
        findings.append((False, f"{analysed} of {photo_count} photos AI-analysed; {photo_count - analysed} could not be processed"))

    # Extract AI scores
    for e in entries:
        for line in e.get("analysis", "").split("\n"):
            if "assessment score" in line.lower() or "risk score" in line.lower():
                findings.append((None, line.strip().lstrip("*").strip()))  # neutral

    # Render findings
    finding_paras = []
    for positive, text in findings:
        if positive is True:
            prefix = "✓"
            style  = s["bullet"]
        elif positive is False:
            prefix = "✗"
            style  = ParagraphStyle("neg_b", parent=s["bullet"],
                                    fontName="Helvetica-Bold", textColor=D_GREY)
        else:
            prefix = "→"
            style  = s["bullet"]
        finding_paras.append(Paragraph(f"  {prefix}   {text}", style))
        finding_paras.append(Spacer(1, 3))

    findings_tbl = Table([[finding_paras]], colWidths=[CONTENT_W])
    findings_tbl.setStyle(TableStyle([
        ("BOX",           (0, 0), (-1, -1), 0.5, B_GREY),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
    ]))

    # Final decision box
    dec_bg   = L_GREY
    dec_tbl  = Table(
        [
            [Paragraph("FINAL DECISION", ParagraphStyle(
                "fd_lbl", fontName="Helvetica-Bold", fontSize=9,
                textColor=M_GREY, alignment=TA_CENTER,
            ))],
            [Paragraph(decision, s["decision"])],
            [Paragraph(f"Risk Score: {score} / 100  —  {risk_level}",
                       ParagraphStyle("fd_score", fontName="Helvetica",
                                      fontSize=10, textColor=M_GREY, alignment=TA_CENTER))],
        ],
        colWidths=[CONTENT_W],
    )
    dec_tbl.setStyle(TableStyle([
        ("BOX",           (0, 0), (-1, -1), 2, BLACK),
        ("LINEBELOW",     (0, 0), (-1, 0),  0.5, B_GREY),
        ("LINEBELOW",     (0, 1), (-1, 1),  0.5, B_GREY),
        ("BACKGROUND",    (0, 0), (-1, -1), dec_bg),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
    ]))

    # Signature block
    sig_tbl = Table(
        [[
            Table([
                [Paragraph("Field Officer Signature", s["small"])],
                [Spacer(1, 1.5*cm)],
                [HRFlowable(width="90%", thickness=0.5, color=B_GREY)],
                [Paragraph("Name / Date", s["small"])],
            ], colWidths=[CONTENT_W * 0.45]),
            Table([
                [Paragraph("Reviewed By (Credit Team)", s["small"])],
                [Spacer(1, 1.5*cm)],
                [HRFlowable(width="90%", thickness=0.5, color=B_GREY)],
                [Paragraph("Name / Date", s["small"])],
            ], colWidths=[CONTENT_W * 0.45]),
        ]],
        colWidths=[CONTENT_W * 0.5, CONTENT_W * 0.5],
    )
    sig_tbl.setStyle(TableStyle([
        ("BOX",          (0, 0), (-1, -1), 0.5, B_GREY),
        ("INNERGRID",    (0, 0), (-1, -1), 0.5, B_GREY),
        ("TOPPADDING",   (0, 0), (-1, -1), 8),
        ("LEFTPADDING",  (0, 0), (-1, -1), 10),
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
    ]))

    return [
        findings_tbl,
        Spacer(1, 12),
        dec_tbl,
        Spacer(1, 16),
        *_sub_header("Authorization Signatures", s),
        sig_tbl,
    ]


# ── Page header & footer ───────────────────────────────────────────────────────

def _make_page_template(session_id: str):
    def _draw(canvas, doc):
        canvas.saveState()
        w = PAGE_W

        # ── Header line ──
        canvas.setStrokeColor(B_GREY)
        canvas.setLineWidth(0.4)
        y_hdr = PAGE_H - MARGIN + 0.3 * cm
        canvas.line(MARGIN, y_hdr, w - MARGIN, y_hdr)
        canvas.setFont("Helvetica-Bold", 7)
        canvas.setFillColor(D_GREY)
        canvas.drawString(MARGIN, y_hdr + 2, "FIELD INVESTIGATION REPORT  —  CONFIDENTIAL")
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(M_GREY)
        canvas.drawCentredString(w / 2, y_hdr + 2, f"Case: {session_id}")
        canvas.drawRightString(w - MARGIN, y_hdr + 2, _now_ist("%d %b %Y"))

        # ── Footer line ──
        y_ftr = 0.9 * cm
        canvas.line(MARGIN, y_ftr + 8, w - MARGIN, y_ftr + 8)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(M_GREY)
        canvas.drawString(MARGIN, y_ftr, "Strictly Confidential  —  For Internal Use Only")
        canvas.drawCentredString(w / 2, y_ftr, "FI Agent  |  Automated Credit Verification System")
        canvas.drawRightString(w - MARGIN, y_ftr, f"Page  {doc.page}")

        canvas.restoreState()

    return _draw


# ── Public entry point ─────────────────────────────────────────────────────────

def generate_credit_report(
    meta: SessionMetadata,
    geo_result: Dict[str, Any],
    image_entries: List[Dict[str, Any]],
    address: str = "",
    income_analysis: Optional[Dict[str, Any]] = None,
    pan_verification: Optional[Dict[str, Any]] = None,
    nameplate_ocr: Optional[Dict[str, Any]] = None,
    credit_analysis: Optional[Dict[str, Any]] = None,
    cibil_score: Optional[Dict[str, Any]] = None,
) -> Path:
    """Build the enterprise-grade PDF and return its absolute path."""
    session_dir = get_storage_root() / meta.session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = session_dir / f"fi_report_{meta.session_id}.pdf"
    logger.info("[Report] Generating enterprise PDF: %s", pdf_path)

    draw_page = _make_page_template(meta.session_id)

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=1.8 * cm, bottomMargin=1.6 * cm,
        title=f"FI Report — {meta.session_id}",
        author="FI Agent — Automated Credit Verification",
        subject="Field Investigation Report",
        keywords="field investigation, credit verification, FI agent",
    )

    s        = _build_styles()
    customer = _extract_customer(meta)

    # If comprehensive AI credit analysis is available, use its score
    if credit_analysis and not credit_analysis.get("error"):
        ai_score = int(credit_analysis.get("overall_credit_score", 0) or 0)
        ai_grade = credit_analysis.get("risk_grade", "")
        ai_rec   = credit_analysis.get("recommendation", "")
        score    = ai_score
        # Map AI recommendation to risk level + decision text
        _rec_map = {
            "APPROVE":                    ("LOW RISK",      "APPROVED — RECOMMENDED FOR DISBURSEMENT"),
            "APPROVE_WITH_CONDITIONS":    ("LOW-MEDIUM RISK","APPROVED WITH CONDITIONS"),
            "REFER":                      ("MEDIUM RISK",   "REFER TO SENIOR CREDIT OFFICER"),
            "DECLINE":                    ("HIGH RISK",     "DECLINED — DOES NOT MEET CRITERIA"),
        }
        risk_level, decision = _rec_map.get(ai_rec, ("MEDIUM RISK", "FURTHER REVIEW REQUIRED"))
        breakdown: RiskBreakdown = [
            ("AI Credit Assessment", score, 100, credit_analysis.get("executive_summary", "")[:150]),
        ]
    else:
        score, breakdown, risk_level, decision = _compute_risk(
            meta, geo_result, image_entries, income_analysis, pan_verification
        )

    gen_ts = _now_ist()
    story: List = []

    # ── Cover title block ──────────────────────────────────────────────────
    classify_tbl = Table(
        [[Paragraph("STRICTLY CONFIDENTIAL  —  FOR AUTHORISED PERSONNEL ONLY",
                    s["classify"])]],
        colWidths=[CONTENT_W],
    )
    classify_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), D_GREY),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))

    story += [
        Spacer(1, 0.5 * cm),
        classify_tbl,
        Spacer(1, 0.4 * cm),
        Paragraph("FIELD INVESTIGATION REPORT", s["report_title"]),
        Paragraph("Automated Credit Verification  ·  Property & Applicant Due Diligence",
                  s["report_sub"]),
        Spacer(1, 4),
        HRFlowable(width="100%", thickness=2, color=BLACK, spaceAfter=4),
        HRFlowable(width="100%", thickness=0.5, color=B_GREY, spaceAfter=8),
    ]

    # ── 1. Application Details (Basic Info) ──────────────────────────────
    story += _section_header("1.  Application Details", s)
    story += _basic_info_section(meta, s)

    # ── 2. Executive Summary ───────────────────────────────────────────────
    story += _section_header("2.  Executive Summary", s)
    story += _summary_section(meta, customer, geo_result, image_entries, score, risk_level, s)

    # ── 3. Field Interview ────────────────────────────────────────────────
    story += _section_header("3.  Field Interview  (Q&A with GPS)", s)
    story += _qa_section(meta, s)

    # ── 4. Location Verification ──────────────────────────────────────────
    story += _section_header("4.  Location Verification Report", s)
    story += _location_section(geo_result, address or "—", s)

    # ── 5. Home Evidence ─────────────────────────────────────────────────
    story += _section_header("5.  Home Evidence  (Photos + AI Analysis)", s)
    if image_entries:
        story += _images_section(image_entries, s)
    else:
        story.append(_incomplete("No home photos captured — field visit documentation missing", s))

    # ── 6. PAN Card Verification ──────────────────────────────────────────
    story += _section_header("6.  PAN Card Verification  (OCR + Face Match + NSDL)", s)
    story += _pan_section(pan_verification, s)

    # ── 7. Income & Financial Analysis ───────────────────────────────────
    story += _section_header("7.  Income & Financial Analysis  (Bank Statement)", s)
    story += _income_section(income_analysis, meta, s)

    # ── 7b. CIBIL Credit Score ────────────────────────────────────────────
    story += _section_header("7b.  CIBIL Credit Score  (TransUnion CIBIL)", s)
    story += _cibil_section(cibil_score, s)

    # ── 8. AI Credit Analysis ────────────────────────────────────────────
    story += _section_header("8.  AI Credit Analysis  (GPT-4o)", s)
    story += _ai_credit_section(credit_analysis, s)

    # ── 9. Scoring & Risk Assessment ─────────────────────────────────────
    story += _section_header("9.  Scoring & Risk Assessment", s)
    story += _risk_section(score, breakdown, risk_level, decision, s)

    # ── 10. Recommendations & Final Decision ─────────────────────────────
    story += _section_header("10.  Recommendations & Final Decision", s)
    story += _recommendation_section(meta, geo_result, image_entries, score, risk_level, decision, s)

    story.append(Spacer(1, 14))

    # ── Disclaimer ────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=B_GREY))
    story.append(Spacer(1, 5))
    story.append(Paragraph(
        f"DISCLAIMER — Report generated automatically on {gen_ts} by FI Agent (Automated Credit Verification System). "
        "AI image analysis (GPT-4o) and risk scores are decision-support tools only and do not constitute a credit "
        "decision. All findings must be reviewed by a qualified credit officer before any lending action is taken. "
        "Location data is based on GPS readings captured by the field agent's mobile device and may be affected by "
        "signal conditions. This document is strictly confidential.",
        s["small"],
    ))

    doc.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
    logger.info("[Report] PDF saved: %s  (%.1f KB)", pdf_path, pdf_path.stat().st_size / 1024)
    return pdf_path
