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
                except (AuthenticationError, PermissionDeniedError) as exc:
                    # Wrong API key or access denied — retrying won't help
                    logger.error("[OpenAI] Non-retryable error: %s", exc)
                    raise
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

import httpx
from openai import AsyncOpenAI, AuthenticationError, PermissionDeniedError

from config import settings

logger = logging.getLogger(__name__)

# ── Singleton client ──────────────────────────────────────────────────────────
# Created once and reused for the process lifetime.
# Passing an explicit http_client prevents the OpenAI SDK from calling
# httpx.AsyncClient(proxies=…), which was removed in httpx 0.28 and causes
# "__init__() got an unexpected keyword argument 'proxies'" on newer installs.

_client: Optional[AsyncOpenAI] = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            http_client=httpx.AsyncClient(timeout=httpx.Timeout(60.0)),
        )
    return _client

# ── Prompts ───────────────────────────────────────────────────────────────────

_SYSTEM = (
    "You are a senior Field Investigation (FI) officer and credit underwriter at ABC Bank, India. "
    "You analyse home-visit images to assess personal loan applications. "
    "Your observations must directly support or challenge the credit decision. "
    "Be concise, factual, and specific. Never speculate beyond what is visible."
)

# Tag-specific prompts — each tells GPT exactly what to look for and why
_TAG_PROMPTS: Dict[str, str] = {

    "selfie": """\
ABC Bank — Identity Verification
INTENT: Confirm the applicant's identity, appearance, and that a real person is present.

Analyse this portrait image and respond using EXACTLY these headings:

**Identity Assessment**: Is a clear human face visible? Lighting adequate for facial recognition?

**Liveness Indicators**: Any signs of a spoofed or printed photo? (flat image, reflections, background anomalies)

**Presentation**: Professional / Casual / Unkempt — does appearance align with stated income level?

**Risk Flags**: Anything that raises identity doubt. Write "None" if clear.

**Identity Score**: <1–10>  (10 = clear, genuine identity; 1 = serious doubt)

Limit to 150 words. Be factual.""",

    "nameplate": """\
ABC Bank — Address & Identity Verification
INTENT: Verify the applicant's residential address, confirm they live there, and extract any visible names or addresses from the nameplate/signage.

Analyse this door/gate nameplate image and respond using EXACTLY these headings:

**Nameplate Text**: Transcribe ALL visible text exactly as shown (name, flat/house number, street, etc.).

**Address Match**: Does the visible address or name match what the applicant declared? Note any discrepancy.

**Property Ownership Signals**: Does the nameplate suggest owner-occupancy or rental? (e.g. single family name vs. multiple names, condition)

**Locality Quality**: Based on visible surroundings — High-end / Middle-class / Working-class / Slum

**Risk Flags**: Any mismatch, illegibility, or suspicious detail. Write "None" if clear.

**Verification Score**: <1–10>  (10 = name/address clearly confirmed; 1 = unreadable or mismatched)

Limit to 180 words.""",

    "kitchen": """\
ABC Bank — Lifestyle & Income Level Assessment
INTENT: Kitchen photos reveal household income level, spending habits, and lifestyle quality — key indicators of financial stability and repayment capacity.

Analyse this kitchen image and respond using EXACTLY these headings:

**Kitchen Type**: Modular / Semi-modular / Basic / Makeshift

**Appliances Visible**: List major appliances (refrigerator, microwave, RO water purifier, dishwasher, etc.) — these indicate disposable income.

**Income Level Indicator**: Affluent | Upper-Middle | Middle | Lower-Middle | Poor
(Base on counter materials, cabinetry quality, appliances, cleanliness, space utilisation)

**Spending Behaviour**: Signs of organised, planned household (indicates financial discipline) vs. disorganised (financial stress indicator)

**Credit-Relevant Observations**:
- <observation linking kitchen quality to income/lifestyle>
- <any premium vs. budget indicators>

**Risk Flags**: Extreme poverty, signs of financial distress. Write "None" if not applicable.

**Lifestyle Score**: <1–10>  (10 = affluent lifestyle clearly supporting loan repayment capacity)

Limit to 200 words.""",

    "bedroom1": """\
ABC Bank — Lifestyle & Living Standard Assessment
INTENT: Bedroom quality directly reflects the applicant's income level, spending patterns, and household stability — used to cross-check declared income.

Analyse this bedroom image and respond using EXACTLY these headings:

**Room Quality**: Premium / Standard / Basic / Minimal

**Furnishing Level**: List visible furniture and fittings (bed type, AC, wardrobe, TV, etc.) as income indicators.

**Income Cross-check**: Affluent | Upper-Middle | Middle | Lower-Middle | Poor
(Compare visible assets against declared income range)

**Household Stability**: Is the bedroom well-maintained, indicating a stable household? Or cluttered/distressed?

**Credit-Relevant Observations**:
- <specific asset that supports or contradicts declared income>
- <household stability indicators>

**Risk Flags**: Mismatch with declared income, signs of financial distress. Write "None" if clear.

**Lifestyle Score**: <1–10>  (10 = furnishings clearly consistent with declared income and loan request)

Limit to 200 words.""",

    "bedroom2": """\
ABC Bank — Lifestyle & Living Standard Assessment (Bedroom 2)
INTENT: Second bedroom confirms family size, household income level, and whether the property supports the lifestyle claimed in the application.

Analyse this second bedroom image and respond using EXACTLY these headings:

**Room Purpose**: Master bedroom / Children's room / Guest room / Home office / Storage

**Furnishing & Asset Level**: List visible items. Note premium vs. budget indicators.

**Family Size Indicator**: Does this room suggest single occupant, nuclear family, or joint family? (affects loan repayment capacity)

**Income Level Cross-check**: Affluent | Upper-Middle | Middle | Lower-Middle | Poor

**Credit-Relevant Observations**:
- <observation supporting or questioning income claims>
- <asset level consistency with loan amount>

**Risk Flags**: Any inconsistency with application data. Write "None" if clear.

**Lifestyle Score**: <1–10>

Limit to 180 words.""",

    "hall": """\
ABC Bank — Lifestyle, Spending & Asset Assessment
INTENT: The hall/living room is the primary lifestyle indicator — furniture, electronics, and decor directly reflect spending capacity and disposable income. Used to assess whether the applicant's lifestyle is consistent with their declared income and loan request.

Analyse this hall/living room image and respond using EXACTLY these headings:

**Living Room Quality**: Premium / Standard / Basic / Minimal

**Key Assets Visible**: List all major items (sofa set, TV size/brand, AC, home theatre, art, etc.) — each signals spending capacity.

**Lifestyle Assessment**: Affluent | Upper-Middle | Middle | Lower-Middle | Poor
(Your most important assessment — be specific about what drives this rating)

**Spending Pattern**: Planned & aspirational (premium brands, organised) vs. Functional (budget items) vs. Financially stressed (minimal or poor condition)

**Income Consistency Check**: Does the visible lifestyle match the declared income range and requested loan amount? Note any over/under-claiming.

**Risk Flags**: Lifestyle significantly above or below declared income (both are red flags). Write "None" if consistent.

**Asset Score**: <1–10>  (10 = clear evidence of stable middle/upper-middle income lifestyle)

Limit to 220 words. This is your most important lifestyle assessment.""",

    "outside": """\
ABC Bank — Property Value & Locality Assessment
INTENT: Exterior and locality photos are used to assess property value, neighbourhood quality, and whether the locality supports the credit profile. High-value locality = better collateral assurance and lower credit risk.

Analyse this exterior/locality image and respond using EXACTLY these headings:

**Property Type**: Independent house / Apartment building / Row house / Urban tenement / Rural property

**Construction Quality**: Premium (RCC, modern finish) / Standard (plastered, maintained) / Basic (brick, minor repairs needed) / Poor (dilapidated)

**Locality Grade**: High-end residential / Upper-middle residential / Middle-class colony / Working-class area / Slum / Industrial/commercial
(This directly affects property value and credit risk)

**Neighbourhood Indicators**: Roads, nearby infrastructure, commercial activity visible — these indicate locality development level and property appreciation potential.

**Property Value Estimate**: High / Medium / Low — based on visible construction and locality.

**Credit Risk Implications**: How does this locality/property value affect the loan risk? Does it support the loan amount applied for?

**Risk Flags**: Locality or property conditions that increase credit risk. Write "None" if strong locality.

**Property Score**: <1–10>  (10 = prime locality with high property value, lowest credit risk)

Limit to 220 words.""",

    "pan": """\
ABC Bank — PAN Card Identity Verification
INTENT: PAN card is the primary identity document for loan verification — used to confirm applicant identity, check NSDL records, and verify name consistency.

Analyse this PAN card image and respond using EXACTLY these headings:

**Card Authenticity**: Does the card appear genuine? (hologram, print quality, layout consistent with official PAN cards)

**Visible Data**: List all readable fields — Name, Father's Name, Date of Birth, PAN Number.

**OCR Quality**: Are all fields clearly readable? Note any partially visible or obscured text.

**Identity Consistency**: Does the name/DOB visible match what you'd expect for the applicant's stated profile?

**Risk Flags**: Tampered card, poor readability, inconsistencies. Write "None" if clear.

**Verification Score**: <1–10>  (10 = all fields clearly visible and card appears genuine)

Limit to 150 words.""",
}

# Fallback generic template for untagged photos
_USER_TEMPLATE = """\
ABC Bank — Personal Loan Field Investigation
Image context: {prompt}

Analyse this image for credit assessment and respond using EXACTLY these headings:

**Scene / Property Type**: One line description.

**Living Standard**: Affluent | Upper-Middle | Middle | Lower-Middle | Poor

**Credit-Relevant Observations**:
- <observation 1>
- <observation 2>
- <observation 3 if applicable>

**Risk Flags**: Any concerns. Write "None" if clear.

**Verification Score**: <1–10>

Limit to 180 words. Be factual and credit-specific.
"""


def _build_user_prompt(tag: str, prompt: str) -> str:
    """Return the tag-specific prompt, falling back to the generic template."""
    tag_key = tag.lower() if tag else ""
    # Map similar tags to canonical keys
    _tag_map = {
        "bedroom": "bedroom1", "bed1": "bedroom1", "bed2": "bedroom2",
        "living": "hall", "living_room": "hall",
        "exterior": "outside", "front": "outside", "outside1": "outside", "outside2": "outside",
        "door": "nameplate", "signage": "nameplate",
        "self": "selfie", "portrait": "selfie",
    }
    canonical = _tag_map.get(tag_key, tag_key)
    if canonical in _TAG_PROMPTS:
        return _TAG_PROMPTS[canonical]
    return _USER_TEMPLATE.format(prompt=prompt)


# ── Single-image analysis ─────────────────────────────────────────────────────

async def analyze_image(image_path: Path, prompt: str, tag: str = "") -> str:
    """
    Sends one image to GPT-4o Vision with a tag-specific prompt and returns the analysis.
    tag: photo type (selfie, kitchen, bedroom1, hall, outside, nameplate, pan, …)
    """
    if not settings.openai_api_key:
        logger.warning("[OpenAI] API key not set — skipping image analysis")
        return "Image analysis skipped (API key not configured)."

    if not image_path.exists():
        logger.warning("[OpenAI] Image file missing: %s", image_path)
        return f"Image file not found: {image_path.name}"

    return await _analyze_image_with_retry(image_path, prompt, tag)


@_async_retry(max_attempts=3, delay_s=2.0)
async def _analyze_image_with_retry(image_path: Path, prompt: str, tag: str = "") -> str:
    suffix     = image_path.suffix.lower().lstrip(".")
    mime       = "image/jpeg" if suffix in ("jpg", "jpeg") else f"image/{suffix}"
    user_text  = _build_user_prompt(tag, prompt)
    logger.info("[OpenAI] Analysing %s  tag=%s (%.1f KB)", image_path.name, tag or "generic",
                image_path.stat().st_size / 1024)
    b64    = base64.b64encode(image_path.read_bytes()).decode()
    client = _get_client()
    resp   = await client.chat.completions.create(
        model=settings.openai_model,
        max_tokens=500,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {
                "role": "user",
                "content": [
                    {"type": "image_url",
                     "image_url": {"url": f"data:{mime};base64,{b64}", "detail": "auto"}},
                    {"type": "text",
                     "text": user_text},
                ],
            },
        ],
    )
    analysis = (resp.choices[0].message.content or "").strip()
    logger.info("[OpenAI] Done: %s — %d chars", image_path.name, len(analysis))
    return analysis


# ── Bank statement income analysis ───────────────────────────────────────────

_INCOME_SYSTEM = (
    "You are a senior credit underwriter at ABC Bank, India, specialising in personal loan assessment. "
    "You analyse bank statements to determine whether an applicant has stable income and sufficient "
    "repayment capacity for the requested loan. Apply conservative Indian banking standards: "
    "EMI should not exceed 40-50% of net monthly income. Flag any signs of financial stress clearly."
)

_INCOME_PROMPT = """\
ABC Bank — Personal Loan Credit Assessment
Analyse the following bank statement for loan eligibility and repayment capacity.

Return ONLY a valid JSON object with these exact keys (no other text):

{{
  "months_covered":           <integer — number of months covered by this statement>,
  "avg_monthly_income":       <number — average monthly credits/income in INR>,
  "avg_monthly_expenses":     <number — average monthly debits/expenses in INR>,
  "avg_monthly_savings":      <number — average net savings per month in INR>,
  "expense_to_income_ratio":  <float 0.0–1.0 — total expenses divided by total income>,
  "salary_detected":          <true | false — is there a regular fixed salary credit?>,
  "income_sources":           [<identified income sources e.g. "Salary - Employer Name", "Business receipts">],
  "existing_emi_count":       <integer — number of existing loan EMI debits found>,
  "existing_emi_total":       <number — estimated total existing EMI burden per month in INR>,
  "bounce_count":             <integer — dishonoured / returned / insufficient-fund transactions>,
  "large_irregular_debits":   [<any unusually large one-time withdrawals with approximate amount>],
  "creditworthiness_score":   <integer 0–10 — repayment capacity score; 10 = excellent, 0 = high risk>,
  "risk_flags":               [<specific concerns that could affect loan repayment>],
  "positive_indicators":      [<specific strengths supporting loan approval>],
  "summary":                  "<2–3 sentences: income stability, repayment capacity, and recommendation>"
}}

Bank statement text ({chars} characters):
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
        logger.warning("[OpenAI] No text extracted from %s — likely a scanned PDF", pdf_path.name)
        return {"error": "No readable text in PDF (scanned image?)", "creditworthiness_score": 0}

    # Limit text sent to GPT to ~12 000 chars (~3 k tokens)
    MAX_CHARS = 12_000
    snippet   = text[:MAX_CHARS]
    logger.info("[OpenAI] Bank statement: sending %d chars to GPT-4o (truncated=%s)",
                len(snippet), len(text) > MAX_CHARS)

    try:
        client = _get_client()
        logger.info("[OpenAI] Bank statement: calling chat.completions.create (model=%s)...",
                    settings.openai_model)
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
    "You are the Head of Credit Underwriting at ABC Bank, India, reviewing a personal loan application. "
    "You have received a complete Field Investigation (FI) report including home-visit photos, "
    "identity verification, income documentation, and GPS-verified location data. "
    "Your task is to produce a final credit decision that is thorough, objective, and defensible. "
    "Apply RBI personal loan guidelines and standard Indian banking credit norms. "
    "Use INR (Rs) for all monetary values. Be concise and specific — avoid vague language."
)

_CREDIT_PROMPT = """\
ABC BANK — PERSONAL LOAN CREDIT ASSESSMENT
Field Investigation Report Review

Evaluate all the evidence below and return ONLY a valid JSON credit assessment.

━━━ APPLICANT PROFILE ━━━
{basic_info}

━━━ LOAN REQUEST ━━━
Amount Requested: {loan_amount_str}
Assessment requirement: Verify if income, property, and identity evidence support
repayment of this amount. Estimated EMI at 12% p.a. / 5 years — check against income.
Flag if monthly EMI would exceed 40% of net monthly income.

━━━ INTERVIEW RESPONSES ━━━
{qa_text}

━━━ HOME EVIDENCE (Photo Analysis) ━━━
{photo_summary}

━━━ IDENTITY VERIFICATION ━━━
PAN Card: {pan_summary}
Home Nameplate OCR: {nameplate_text}

━━━ INCOME EVIDENCE (Bank Statement) ━━━
{income_summary}

━━━ LOCATION VERIFICATION ━━━
{location_summary}

━━━ CREDIT ASSESSMENT CRITERIA ━━━
1. IDENTITY: PAN verified, name matches interview, face matches selfie
2. RESIDENCE: Home photos show genuine occupation, nameplate confirms address
3. INCOME: Salary/income sufficient for EMI, no excessive existing liabilities
4. LOCATION: All GPS readings within 500m (genuine on-site visit)
5. AFFORDABILITY: Max 40% of net income for total EMI burden including this loan
6. LIFESTYLE CONSISTENCY: Property condition consistent with stated income level

Return this exact JSON structure (no other text):
{{
  "overall_credit_score":    <integer 0-100>,
  "risk_grade":              "<AAA|AA|A|BBB|BB|B|CCC|D>",
  "recommendation":          "<APPROVE|APPROVE_WITH_CONDITIONS|REFER|DECLINE>",
  "requested_amount_inr":    <requested loan amount as integer>,
  "loan_eligibility_inr":    <max supportable loan amount as integer>,
  "affordability_status":    "<AFFORDABLE|BORDERLINE|UNAFFORDABLE>",
  "estimated_monthly_emi":   <integer — EMI for requested amount at 12% over 5 yrs>,
  "emi_to_income_ratio":     <float 0.0-1.0 — estimated EMI divided by monthly income>,

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
    "summary": "<2 sentences — explicitly mention if income supports the loan amount>",
    "flags": [<list of concerns>]
  }},

  "location_assessment": {{
    "score": <0-25>,
    "summary": "<2 sentences>",
    "flags": [<list of concerns>]
  }},

  "positive_factors":  [<minimum 3 specific strengths with evidence>],
  "risk_factors":      [<minimum 3 specific risks with evidence — always include if requested > eligibility>],
  "conditions":        [<specific conditions; include reduced amount if unaffordable>],

  "creditworthiness_narrative": "<4-6 sentences of detailed credit intelligence: explain HOW the evidence supports or challenges the application, reference specific photos/income data/location, give your professional underwriter's view on credit character, capacity, and collateral>",

  "lifestyle_vs_income_assessment": "<2-3 sentences: Do the home photos confirm the declared income? Is the applicant living above or below their means? Are they financially disciplined?>",

  "repayment_capacity_analysis": "<2-3 sentences: Based on income data and EMI calculation, can this applicant realistically repay the loan? What is the safety margin?>",

  "executive_summary": "<4-5 sentences covering the complete credit picture: identity, residence, income, lifestyle, location — and your final professional recommendation with reasoning>"
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
    loan_amt   = bi.loan_amount if bi else 0
    loan_str   = (
        f"Rs {loan_amt:,.0f}"
        + (f"  ({loan_amt/100000:.1f} Lakh)" if loan_amt >= 100_000 else "")
    ) if loan_amt else "Not specified"
    basic_str = (
        f"Name: {bi.first_name} {bi.last_name} | DOB: {bi.dob} | "
        f"City: {bi.city} | Income Range: {bi.income_range} | PAN: {bi.pan_number} | "
        f"Loan Requested: {loan_str}"
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
        basic_info=basic_str,   loan_amount_str=loan_str,
        qa_text=qa_lines,       photo_summary=photo_lines,
        pan_summary=pan_str,    nameplate_text=nameplate_str,
        income_summary=income_str, location_summary=loc_str,
    )
    logger.info(
        "[OpenAI] Credit analysis: applicant=%s  photos=%d  qa=%d  "
        "pan_ok=%s  income_ok=%s  prompt_len=%d",
        basic_str[:50], len(image_analyses), len(meta.questions) if meta else 0,
        bool(pan_verification), bool(income_analysis and not income_analysis.get("error")),
        len(prompt),
    )

    try:
        client = _get_client()
        logger.info("[OpenAI] Credit analysis: calling chat.completions.create (model=%s)...",
                    settings.openai_model)
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
        raw    = resp.choices[0].message.content or "{}"
        logger.info("[OpenAI] Credit analysis response: %d chars", len(raw))
        result = _json.loads(raw)
        logger.info("[OpenAI] Credit analysis done — score=%s  grade=%s  recommendation=%s",
                    result.get("overall_credit_score"),
                    result.get("risk_grade"),
                    result.get("recommendation"))
        return result
    except Exception as exc:
        logger.error("[OpenAI] Credit analysis FAILED: %s", exc, exc_info=True)
        return {"error": str(exc)}


# ── PAN card structured OCR ───────────────────────────────────────────────────

async def extract_pan_fields_gpt4o(image_path: Path) -> Dict[str, Any]:
    """
    Use GPT-4o Vision to extract structured fields from a PAN card image.
    Returns {"pan_number", "name", "father_name", "dob"} — empty string if not readable.
    Falls back gracefully: caller should check for "error" key.
    """
    if not settings.openai_api_key:
        return {"error": "OpenAI key not set"}
    if not image_path.exists():
        return {"error": f"File not found: {image_path.name}"}

    suffix = image_path.suffix.lower().lstrip(".")
    mime   = "image/jpeg" if suffix in ("jpg", "jpeg") else f"image/{suffix}"
    b64    = base64.b64encode(image_path.read_bytes()).decode()

    prompt = (
        "This is an Indian PAN card photograph. "
        "Extract the printed text and return ONLY a JSON object — no markdown, no explanation:\n"
        '{"pan_number":"","name":"","father_name":"","dob":""}\n'
        "Rules: pan_number = exactly 10 chars, format AAAAA9999A. "
        "dob = DD/MM/YYYY. Use empty string for any field that is not clearly visible."
    )

    try:
        resp = await _get_client().chat.completions.create(
            model=settings.openai_model,
            max_tokens=150,
            response_format={"type": "json_object"},
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url",
                     "image_url": {"url": f"data:{mime};base64,{b64}", "detail": "high"}},
                    {"type": "text", "text": prompt},
                ],
            }],
        )
        raw    = (resp.choices[0].message.content or "{}").strip()
        result = _json.loads(raw)
        logger.info(
            "[OpenAI] PAN OCR — PAN=%s  name=%s  dob=%s",
            result.get("pan_number"), result.get("name"), result.get("dob"),
        )
        return result
    except Exception as exc:
        logger.error("[OpenAI] PAN OCR failed: %s", exc)
        return {"error": str(exc)}


# ── Batch analysis ────────────────────────────────────────────────────────────

async def analyze_all_images(
    photo_entries: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Analyse all photos with bounded concurrency to avoid rate-limit errors.

    photo_entries — list of dicts with keys: filename, prompt, file_path (Path)
    Returns the same list with an 'analysis' key added to each entry.
    """
    logger.info("[OpenAI] Starting batch analysis of %d images", len(photo_entries))
    sem = asyncio.Semaphore(3)   # max 3 concurrent Vision calls

    async def _analyse_one(entry: Dict[str, Any]) -> Dict[str, Any]:
        async with sem:
            analysis = await analyze_image(
                entry["file_path"], entry.get("prompt", ""),
                tag=entry.get("tag", ""),
            )
        return {**entry, "analysis": analysis}

    results = await asyncio.gather(*[_analyse_one(e) for e in photo_entries])
    logger.info("[OpenAI] Batch analysis complete")
    return list(results)
