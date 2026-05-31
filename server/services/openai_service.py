"""
OpenAI GPT-4o Vision service + bank statement income analysis.

Sends each captured FI photo to GPT-4o with a credit-officer system prompt
and returns a structured written analysis per image.

Also provides analyze_bank_statement() which extracts text from a PDF bank
statement via pdfplumber and sends it to GPT-4 for structured income / expense
analysis used in the credit score.
"""

import asyncio
import base64
import functools
import json as _json
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TypeVar

_T = TypeVar("_T")


def _async_retry(max_attempts: int = 3, delay_s: float = 2.0):
    """
    Decorator that retries an async function on transient OpenAI / network errors.
    Backs off exponentially: delay, delay*2, delay*4 …
    """
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: Exception = RuntimeError("No attempts made")
            for attempt in range(1, max_attempts + 1):
                try:
                    return await fn(*args, **kwargs)
                except Exception as exc:
                    last_exc = exc
                    if attempt < max_attempts:
                        wait = delay_s * (2 ** (attempt - 1))
                        logger.warning(
                            "[OpenAI] Attempt %d/%d failed: %s — retrying in %.0fs",
                            attempt, max_attempts, exc, wait,
                        )
                        await asyncio.sleep(wait)
                    else:
                        logger.error(
                            "[OpenAI] All %d attempts failed: %s", max_attempts, exc
                        )
            raise last_exc
        return wrapper
    return decorator

from openai import AsyncOpenAI

from config import settings

logger = logging.getLogger(__name__)

# ── Prompts ───────────────────────────────────────────────────────────────────

_SYSTEM = (
    "You are an experienced Field Investigation (FI) officer working for a "
    "microfinance / NBFC credit team in India. You assist loan officers by "
    "analysing property and residential images captured during home visits. "
    "Your assessments are objective, professional, and support the credit "
    "underwriting decision. Keep responses concise and factual."
)

_USER_TEMPLATE = """\
I am a Credit Officer conducting a Field Investigation (FI) for a small loan application.

**Image context**: {prompt}

Analyse this image and return a structured assessment using exactly the following headings:

**Scene / Property Type**: (one line — e.g. "Residential living room", "Exterior of house", "Applicant identity photo")

**Condition**: Excellent | Good | Average | Poor | Not Assessable

**Key Observations**:
- <observation 1>
- <observation 2>
- <observation 3 if applicable>

**Credit Indicators**:
- Positive: <any indicator supporting creditworthiness, or "None identified">
- Concerns: <any red flag or area needing clarification, or "None identified">

**Assessment Score**: <1–10>  (10 = strongest positive indicator for creditworthiness)

Keep the total response under 220 words. Be factual; do not speculate beyond what is visible.
"""


# ── Single-image analysis ─────────────────────────────────────────────────────

async def analyze_image(image_path: Path, prompt: str) -> str:
    """
    Sends one image to GPT-4o Vision and returns the analysis string.
    Returns a placeholder string if the key is not configured or the file is missing.
    Pre-conditions are checked before the retry wrapper to avoid wasting retries.
    """
    if not settings.openai_api_key:
        logger.warning("[OpenAI] API key not set — skipping image analysis")
        return "Image analysis skipped (API key not configured)."

    if not image_path.exists():
        logger.warning("[OpenAI] Image file missing: %s", image_path)
        return f"Image file not found: {image_path.name}"

    return await _analyze_image_with_retry(image_path, prompt)


@_async_retry(max_attempts=3, delay_s=2.0)
async def _analyze_image_with_retry(image_path: Path, prompt: str) -> str:
    suffix = image_path.suffix.lower().lstrip(".")
    mime   = "image/jpeg" if suffix in ("jpg", "jpeg") else f"image/{suffix}"
    logger.info("[OpenAI] Analysing %s (%.1f KB)", image_path.name, image_path.stat().st_size / 1024)
    b64    = base64.b64encode(image_path.read_bytes()).decode()
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    resp   = await client.chat.completions.create(
        model=settings.openai_model,
        max_tokens=450,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {
                "role": "user",
                "content": [
                    {"type": "image_url",
                     "image_url": {"url": f"data:{mime};base64,{b64}", "detail": "low"}},
                    {"type": "text",
                     "text": _USER_TEMPLATE.format(prompt=prompt)},
                ],
            },
        ],
    )
    analysis = (resp.choices[0].message.content or "").strip()
    logger.info("[OpenAI] Done: %s — %d chars", image_path.name, len(analysis))
    return analysis


# ── Bank statement income analysis ───────────────────────────────────────────

_INCOME_SYSTEM = (
    "You are a senior credit analyst at an Indian NBFC / microfinance institution. "
    "You analyse bank statements to assess the applicant's income stability, spending "
    "discipline, and creditworthiness. Be objective, precise, and conservative."
)

_INCOME_PROMPT = """\
Analyse the following bank statement text and return ONLY a valid JSON object with these keys:

{{
  "months_covered": <integer — number of months in the statement>,
  "avg_monthly_income": <number — average monthly credit / income in INR>,
  "avg_monthly_expenses": <number — average monthly debit / expenses in INR>,
  "avg_monthly_savings": <number — average net savings per month in INR>,
  "expense_to_income_ratio": <float 0.0–1.0 — expenses divided by income>,
  "salary_detected": <true | false — whether regular salary credits are visible>,
  "income_sources": [<list of identified income source strings>],
  "emi_count": <integer — number of regular EMI / loan-repayment debits found>,
  "bounce_count": <integer — number of dishonoured / returned transactions>,
  "creditworthiness_score": <integer 0–10 — overall credit health, 10 = excellent>,
  "risk_flags": [<list of concern strings>],
  "positive_indicators": [<list of positive financial indicator strings>],
  "summary": "<2–3 sentence plain-English summary of financial health>"
}}

Return ONLY the JSON object. Do not include any other text.

Bank statement text (up to {chars} characters):
{text}
"""


@_async_retry(max_attempts=2, delay_s=3.0)
async def analyze_bank_statement(pdf_path: Path) -> Dict[str, Any]:
    """
    Extract text from a PDF bank statement and analyse it with GPT-4.
    Returns a dict of financial metrics; on error returns a dict with 'error' key.
    """
    if not settings.openai_api_key:
        logger.warning("[OpenAI] API key not set — skipping bank statement analysis")
        return {"error": "OpenAI API key not configured", "creditworthiness_score": 0}

    # Extract text with pdfplumber
    text = ""
    try:
        import pdfplumber
        with pdfplumber.open(str(pdf_path)) as pdf:
            pages = pdf.pages[:24]        # cap at 24 pages
            for page in pages:
                t = page.extract_text()
                if t:
                    text += t + "\n"
        logger.info("[OpenAI] Extracted %d chars from %s (%d pages)",
                    len(text), pdf_path.name, len(pages))
    except ImportError:
        logger.error("[OpenAI] pdfplumber not installed — run: pip install pdfplumber")
        return {"error": "pdfplumber not installed", "creditworthiness_score": 0}
    except Exception as exc:
        logger.error("[OpenAI] PDF extraction failed for %s: %s", pdf_path.name, exc)
        return {"error": f"PDF read failed: {exc}", "creditworthiness_score": 0}

    if not text.strip():
        logger.warning("[OpenAI] No text extracted from %s", pdf_path.name)
        return {"error": "No readable text in PDF (scanned image?)", "creditworthiness_score": 0}

    # Limit text sent to GPT to ~12 000 chars (~3 k tokens)
    MAX_CHARS = 12_000
    snippet   = text[:MAX_CHARS]

    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        resp = await client.chat.completions.create(
            model=settings.openai_model,
            temperature=0.1,
            max_tokens=800,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _INCOME_SYSTEM},
                {"role": "user",   "content": _INCOME_PROMPT.format(
                    chars=len(snippet), text=snippet,
                )},
            ],
        )
        raw = resp.choices[0].message.content or "{}"
        result: Dict[str, Any] = _json.loads(raw)
        logger.info("[OpenAI] Bank statement analysis done — creditworthiness=%s",
                    result.get("creditworthiness_score"))
        return result
    except Exception as exc:
        logger.error("[OpenAI] Bank statement analysis failed: %s", exc)
        return {"error": str(exc), "creditworthiness_score": 0}


# ── Comprehensive credit analysis ────────────────────────────────────────────

_CREDIT_SYSTEM = (
    "You are a senior credit underwriter at ABC Bank (India). "
    "You review Field Investigation reports for personal loan applications and produce "
    "a thorough, objective credit assessment. Be concise, structured, and professional. "
    "Use INR (₹) for monetary values."
)

_CREDIT_PROMPT = """\
Review the following Field Investigation data for a personal loan application at ABC Bank
and return ONLY a valid JSON object with your complete credit assessment.

APPLICANT:
{basic_info}

INTERVIEW Q&A:
{qa_text}

HOME EVIDENCE PHOTOS:
{photo_summary}

PAN CARD VERIFICATION:
{pan_summary}

NAMEPLATE OCR:
{nameplate_text}

INCOME / BANK STATEMENT ANALYSIS:
{income_summary}

LOCATION DATA:
{location_summary}

Return this exact JSON structure (no other text):
{{
  "overall_credit_score": <integer 0-100>,
  "risk_grade":           "<AAA|AA|A|BBB|BB|B|CCC|D>",
  "recommendation":       "<APPROVE|APPROVE_WITH_CONDITIONS|REFER|DECLINE>",
  "loan_eligibility_inr": <estimated max loan amount as integer>,

  "identity_assessment": {{
    "score": <0-25>,
    "summary": "<2 sentences>",
    "flags": [<list of concerns>]
  }},

  "residence_assessment": {{
    "score": <0-25>,
    "summary": "<2 sentences>",
    "flags": [<list of concerns>]
  }},

  "income_assessment": {{
    "score": <0-25>,
    "summary": "<2 sentences>",
    "flags": [<list of concerns>]
  }},

  "location_assessment": {{
    "score": <0-25>,
    "summary": "<2 sentences>",
    "flags": [<list of concerns>]
  }},

  "positive_factors":  [<list of strengths observed>],
  "risk_factors":      [<list of risks or concerns>],
  "conditions":        [<list of any loan conditions if APPROVE_WITH_CONDITIONS>],
  "executive_summary": "<3-4 sentence overall assessment for the credit committee>"
}}
"""


@_async_retry(max_attempts=2, delay_s=3.0)
async def comprehensive_credit_analysis(
    meta,
    geo_result:       Dict[str, Any],
    address:          str,
    pan_verification: Optional[Dict[str, Any]],
    nameplate_ocr:    Optional[Dict[str, Any]],
    income_analysis:  Optional[Dict[str, Any]],
    image_analyses:   List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Single consolidated OpenAI call that analyses all FI data together and
    returns a structured credit assessment JSON.
    """
    if not settings.openai_api_key:
        logger.warning("[OpenAI] API key not set — skipping credit analysis")
        return {"error": "OpenAI API key not configured"}

    # Build context strings
    bi = meta.basic_info
    basic_str = (
        f"Name: {bi.first_name} {bi.last_name} | DOB: {bi.dob} | "
        f"City: {bi.city} | Income Range: {bi.income_range} | PAN: {bi.pan_number}"
    ) if bi else "Not provided"

    qa_lines = "\n".join(
        f"  Q: {qa.question}\n  A: {qa.answer or '(no answer)'}"
        for qa in meta.questions
    ) or "None"

    photo_lines = "\n".join(
        f"  [{e.get('tag', e.get('prompt','')[:30])}] {e.get('analysis','No analysis')[:300]}"
        for e in image_analyses
    ) or "No photos analysed"

    # PAN
    if pan_verification:
        ocr  = pan_verification.get("ocr", {})
        nm   = pan_verification.get("name_match", {})
        nsdl = pan_verification.get("nsdl", {})
        fm   = pan_verification.get("face_match", {})
        pan_str = (
            f"PAN: {ocr.get('pan_number','?')} | Name: {ocr.get('name','?')} | "
            f"Father: {ocr.get('father_name','?')} | DOB: {ocr.get('dob','?')} | "
            f"Name match: {'YES' if nm.get('matched') else 'NO'} | "
            f"NSDL: {nsdl.get('pan_status','?')} | "
            f"Face match: {fm.get('similarity_score',0):.0f}% ({fm.get('comparison_status','?')})"
        )
    else:
        pan_str = "PAN card not captured"

    nameplate_str = nameplate_ocr.get("raw_text", "Not available") if nameplate_ocr else "Not captured"

    if income_analysis and not income_analysis.get("error"):
        ia = income_analysis
        income_str = (
            f"Months covered: {ia.get('months_covered','?')} | "
            f"Avg income: ₹{ia.get('avg_monthly_income',0):,.0f}/mo | "
            f"Avg expenses: ₹{ia.get('avg_monthly_expenses',0):,.0f}/mo | "
            f"Expense ratio: {ia.get('expense_to_income_ratio',0)*100:.0f}% | "
            f"Salary: {'YES' if ia.get('salary_detected') else 'NO'} | "
            f"Bounces: {ia.get('bounce_count',0)} | "
            f"AI creditworthiness: {ia.get('creditworthiness_score',0)}/10\n"
            f"Summary: {ia.get('summary','')}"
        )
    else:
        income_str = "Bank statement not uploaded"

    loc_str = (
        f"Address: {address} | "
        f"GPS spread: {geo_result.get('max_pairwise_distance_m',0):.0f}m | "
        f"Status: {'PASS' if geo_result.get('verified') else 'FAIL'}"
    )

    prompt = _CREDIT_PROMPT.format(
        basic_info=basic_str, qa_text=qa_lines, photo_summary=photo_lines,
        pan_summary=pan_str, nameplate_text=nameplate_str,
        income_summary=income_str, location_summary=loc_str,
    )

    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        resp   = await client.chat.completions.create(
            model=settings.openai_model,
            temperature=0.1,
            max_tokens=1200,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _CREDIT_SYSTEM},
                {"role": "user",   "content": prompt},
            ],
        )
        result = _json.loads(resp.choices[0].message.content or "{}")
        logger.info("[OpenAI] Credit analysis done — score=%s grade=%s rec=%s",
                    result.get("overall_credit_score"),
                    result.get("risk_grade"),
                    result.get("recommendation"))
        return result
    except Exception as exc:
        logger.error("[OpenAI] Credit analysis failed: %s", exc)
        return {"error": str(exc)}


# ── Batch analysis ────────────────────────────────────────────────────────────

async def analyze_all_images(
    photo_entries: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Analyse all photos concurrently.

    photo_entries — list of dicts with keys: filename, prompt, file_path (Path)
    Returns the same list with an 'analysis' key added to each entry.
    """
    logger.info("[OpenAI] Starting batch analysis of %d images", len(photo_entries))

    async def _analyse_one(entry: Dict[str, Any]) -> Dict[str, Any]:
        analysis = await analyze_image(entry["file_path"], entry["prompt"])
        return {**entry, "analysis": analysis}

    results = await asyncio.gather(*[_analyse_one(e) for e in photo_entries])
    logger.info("[OpenAI] Batch analysis complete")
    return list(results)
