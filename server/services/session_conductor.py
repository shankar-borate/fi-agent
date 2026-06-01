"""
Server-side session conductor.

Drives the entire FI session over a WebSocket connection:
  1. Q&A: TTS (Polly) → play on Android → listen (Transcribe) → transcript
  2. Photos: announce → TTS → countdown → capture → wait for photo_taken ack
  3. Send session_done

Photos and recording are NOT transmitted during the WebSocket session.
Android stores them locally and uploads everything via POST /api/fi-session/upload
after the officer taps Submit. The REST upload handler then triggers report generation.

WebSocket message protocol
──────────────────────────
Server → Android (JSON text frames):
  {type:"question",          index:N, text:"..."}
  {type:"tts_audio",         format:"mp3", data:"<b64>"}
  {type:"start_listening",   question_index:N, timeout_ms:N}
  {type:"transcript",        question_index:N, text:"...", is_final:bool}
  {type:"announce_photo",    prompt:"...", is_selfie:bool}
  {type:"countdown",         value:N}
  {type:"capture_photo",     prompt:"...", is_selfie:bool, photo_index:N}
  {type:"photo_ack",         photo_index:N}
  {type:"session_done",      session_id:"...", message:"..."}
  {type:"error",             message:"..."}

Android → Server:
  {type:"ready",       session_id:"...", device_id:"...", started_at:"..."}
  {type:"tts_done"}
  {type:"audio_end"}
  {type:"photo_taken", photo_index:N, filename:"..."}
  Binary frames  → raw PCM 16 kHz / 16-bit / mono
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect

from config import settings, get_storage_root
from models.fi_session import (
    GeoPoint as GeoPointModel,
    PhotoMeta,
    QuestionAnswer,
    SessionMetadata,
)
from services.aws_service import get_active_transcribe

logger = logging.getLogger(__name__)

_ISO = "%Y-%m-%dT%H:%M:%SZ"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime(_ISO)


# ── Low-level helpers ─────────────────────────────────────────────────────────

async def _send(ws: WebSocket, payload: dict) -> None:
    text = json.dumps(payload)
    logger.debug("[WS→Android] %s", text[:140])
    await ws.send_text(text)


async def _recv_json(ws: WebSocket, timeout: float = 60.0) -> Optional[dict]:
    """Receive next TEXT frame and parse JSON. Returns None on timeout/disconnect."""
    try:
        raw = await asyncio.wait_for(ws.receive_text(), timeout=timeout)
        logger.debug("[Android→WS] %s", raw[:140])
        return json.loads(raw)
    except asyncio.TimeoutError:
        logger.warning("[Conductor] Receive timeout after %.0fs", timeout)
        return None
    except WebSocketDisconnect:
        logger.info("[Conductor] Client disconnected")
        return None


# ── TTS helper ────────────────────────────────────────────────────────────────

async def _wait_tts_done(ws: WebSocket) -> None:
    """Wait for Android to finish speaking the last message via device TTS."""
    msg = await _recv_json(ws, timeout=30.0)
    if not msg or msg.get("type") != "tts_done":
        logger.warning("[Conductor] Expected tts_done, got: %s", msg)


# ── STT helper ────────────────────────────────────────────────────────────────

async def _listen(ws: WebSocket, question_index: int) -> str:
    """
    Tell client to start recording and return the transcript.

    Two paths:
      - PCM path (Android): receives binary PCM frames + audio_end → server STT
      - Browser-direct path (Sarvam): receives transcript_result JSON → skip STT
    """
    audio_queue: asyncio.Queue[Optional[bytes]] = asyncio.Queue()
    browser_transcript: Optional[str] = None

    await _send(ws, {
        "type": "start_listening",
        "question_index": question_index,
        "timeout_ms": settings.fi_listen_timeout_ms,
    })

    async def on_partial(text: str) -> None:
        try:
            await _send(ws, {
                "type": "transcript",
                "question_index": question_index,
                "text": text,
                "is_final": False,
            })
        except Exception:
            pass

    async def _collect_audio() -> None:
        nonlocal browser_transcript
        total = 0
        while True:
            try:
                data = await asyncio.wait_for(ws.receive(), timeout=20.0)
            except asyncio.TimeoutError:
                logger.warning("[Conductor] Audio receive timeout — ending stream")
                break
            except WebSocketDisconnect:
                logger.info("[Conductor] Disconnected during audio receive")
                break

            if "bytes" in data:
                chunk: bytes = data["bytes"]
                total += len(chunk)
                await audio_queue.put(chunk)
            elif "text" in data:
                msg = json.loads(data["text"])
                msg_type = msg.get("type")
                if msg_type == "audio_end":
                    logger.info("[Conductor] audio_end — %d bytes total", total)
                    break
                elif msg_type == "transcript_result":
                    # Browser handled STT directly (Sarvam proxy path)
                    browser_transcript = msg.get("text", "").strip()
                    logger.info("[Conductor] Browser transcript: '%s'", browser_transcript)
                    break
        await audio_queue.put(None)

    collect_task = asyncio.create_task(_collect_audio())
    transcript_task = asyncio.create_task(
        get_active_transcribe().transcribe_stream(audio_queue, on_partial=on_partial)
    )

    await collect_task
    server_transcript = await transcript_task

    # Browser-direct transcript takes priority (server STT will return "" for empty queue)
    answer = (browser_transcript or server_transcript or "(no answer)").strip() or "(no answer)"
    logger.info("[Conductor] Final answer Q%d: '%s'", question_index + 1, answer)
    return answer


# ── Photo helper ──────────────────────────────────────────────────────────────

async def _photo_phase(
    ws: WebSocket,
    prompt: str,
    is_selfie: bool,
    photo_index: int,
) -> None:
    """
    Announce → TTS → countdown → capture_photo → wait for photo_taken ack.
    Photos are stored locally on Android; no binary data crosses the WebSocket.
    """
    logger.info("[Conductor] Photo phase: selfie=%s index=%d", is_selfie, photo_index)

    # Synthesize with Polly so the same female voice is used for all prompts
    audio_b64 = ""
    try:
        from services.aws_service import get_polly
        audio_b64 = await get_polly().async_synthesize(prompt)
    except Exception as exc:
        logger.warning("[Conductor] Polly failed for photo prompt: %s", exc)

    await _send(ws, {"type": "announce_photo", "prompt": prompt,
                     "is_selfie": is_selfie, "audio": audio_b64})
    await _wait_tts_done(ws)

    # Countdown
    for i in range(settings.fi_countdown_seconds, 0, -1):
        await _send(ws, {"type": "countdown", "value": i})
        await asyncio.sleep(1.0)

    # Tell Android to capture
    await _send(ws, {
        "type": "capture_photo",
        "prompt": prompt,
        "is_selfie": is_selfie,
        "photo_index": photo_index,
    })

    # Wait for lightweight ack (no photo data — just confirmation)
    ack = await _recv_json(ws, timeout=30.0)
    if not ack or ack.get("type") != "photo_taken":
        logger.warning("[Conductor] Expected photo_taken, got: %s", ack)
    else:
        logger.info(
            "[Conductor] photo_taken ack: index=%d filename=%s",
            ack.get("photo_index"), ack.get("filename"),
        )

    await _send(ws, {"type": "photo_ack", "photo_index": photo_index})


# ── PAN photo phase (with inline OCR validation + retry) ─────────────────────

async def _pan_photo_phase(ws: WebSocket, session_id: str) -> Optional[dict]:
    """
    Capture the PAN card with up to fi_pan_max_attempts retries.
    Runs AWS Textract inline after each capture; retries if required fields
    (pan_number, name) are missing.  Returns {filename, ocr} or None.
    """
    from services.pan_service import extract_pan_data_sync
    from config import get_storage_root

    storage = get_storage_root() / session_id
    prompt  = settings.fi_pan_photo_prompt
    # PAN is the last photo after selfie + room photos
    photo_index = len(settings.fi_photo_prompts) + 1

    for attempt in range(1, settings.fi_pan_max_attempts + 1):
        await _send(ws, {"type": "announce_photo", "prompt": prompt, "is_selfie": False})
        await _wait_tts_done(ws)

        for i in range(settings.fi_countdown_seconds, 0, -1):
            await _send(ws, {"type": "countdown", "value": i})
            await asyncio.sleep(1.0)

        await _send(ws, {
            "type":        "capture_photo",
            "prompt":      prompt,
            "is_selfie":   False,
            "photo_index": photo_index,
        })

        ack = await _recv_json(ws, timeout=60.0)
        if not ack or ack.get("type") != "photo_taken":
            # Photo was NOT captured — only case where we retry
            logger.warning("[Conductor] PAN: photo not captured (attempt %d/%d): %s",
                           attempt, settings.fi_pan_max_attempts, ack)
            if attempt < settings.fi_pan_max_attempts:
                retry_msg = (
                    f"Photo not captured (attempt {attempt}/{settings.fi_pan_max_attempts}). "
                    "Please show your PAN card again."
                )
                await _send(ws, {"type": "pan_retry", "attempt": attempt, "message": retry_msg})
                continue
            # All attempts exhausted with no capture
            await _send(ws, {"type": "error", "message": "PAN card could not be captured after multiple attempts."})
            return None

        filename = ack.get("filename", "")
        await _send(ws, {"type": "photo_ack", "photo_index": photo_index})

        if not filename:
            logger.warning("[Conductor] PAN: empty filename in photo_taken ack")
            if attempt < settings.fi_pan_max_attempts:
                continue
            return None

        # ── Photo captured successfully → run OCR and return regardless of result ──
        pan_path = storage / filename
        if not pan_path.exists():
            await asyncio.sleep(0.5)   # brief wait for upload flush

        ocr: dict = {}
        if pan_path.exists():
            ocr = await asyncio.to_thread(extract_pan_data_sync, pan_path)
        logger.info("[Conductor] PAN captured (attempt %d): pan=%s name=%s",
                    attempt, ocr.get("pan_number", "?"), ocr.get("name", "?"))
        return {"filename": filename, "ocr": ocr}


# ── Bank statement consent helper ─────────────────────────────────────────────

async def _request_consent_phase(ws: WebSocket) -> None:
    """
    Request applicant's consent to retrieve bank statement from their bank.
    Bank statements are pulled server-side from the vault folder after submit —
    no file upload from the user is needed.
    Waits up to 60 s for consent_given or consent_declined.
    """
    await _send(ws, {
        "type":    "request_consent",
        "purpose": "bank_statement",
        "message": (
            "To complete your loan application, ABC Bank needs to retrieve "
            "your last 12 months' bank statement directly from your bank. "
            "Your data is secure and used only for this loan assessment."
        ),
    })
    logger.info("[Conductor] Waiting for bank statement consent")
    msg = await _recv_json(ws, timeout=60.0)
    if msg and msg.get("type") == "consent_given":
        logger.info("[Conductor] Consent given — bank statement will be retrieved after submit")
    else:
        logger.info("[Conductor] Consent declined or timed out — income analysis will be skipped")


# ── Main conductor ────────────────────────────────────────────────────────────

async def conduct_fi_session(ws: WebSocket, session_id: str) -> None:
    logger.info("[Conductor] ── Session start: %s ──", session_id)

    # Handshake
    ready_msg = await _recv_json(ws, timeout=30.0)
    if not ready_msg or ready_msg.get("type") != "ready":
        logger.error("[Conductor] Handshake failed: %s", ready_msg)
        await _send(ws, {"type": "error", "message": "Handshake failed"})
        return

    device_id   = ready_msg.get("device_id", "unknown")
    basic_info  = ready_msg.get("basic_info", {})
    device_info = ready_msg.get("device_info", {})
    logger.info(
        "[Conductor] Handshake OK — device=%s  applicant=%s %s  client=%s %s",
        device_id,
        basic_info.get("first_name", "?"), basic_info.get("last_name", ""),
        device_info.get("device_type", "?"), device_info.get("os", ""),
    )

    try:
        from services.aws_service import get_polly

        # ── Q&A phase ────────────────────────────────────────────────────────
        for i, question in enumerate(settings.fi_questions):
            logger.info("[Conductor] Q%d/%d: %s", i + 1, len(settings.fi_questions), question)
            confirmed_answer: Optional[str] = None
            while confirmed_answer is None:
                # Synthesize with Polly so voice is consistent on every repeat
                audio_b64 = ""
                try:
                    audio_b64 = await get_polly().async_synthesize(question)
                except Exception as polly_exc:
                    logger.warning("[Conductor] Polly synthesis failed for Q%d: %s", i + 1, polly_exc)

                await _send(ws, {"type": "question", "index": i, "text": question, "audio": audio_b64})
                await _wait_tts_done(ws)
                answer_text = await _listen(ws, i)
                if not answer_text.strip() or answer_text.strip() == "(no answer)":
                    logger.info("[Conductor] No answer for Q%d — repeating question", i + 1)
                    continue

                # Send transcript to client for confirmation
                await _send(ws, {
                    "type": "transcript",
                    "question_index": i,
                    "text": answer_text,
                    "is_final": True,
                })

                # Wait for client confirm or retry (up to 12 s; timeout = auto-confirm)
                confirm_msg = await _recv_json(ws, timeout=12.0)
                if confirm_msg is None or confirm_msg.get("type") == "answer_confirm":
                    logger.info("[Conductor] Answer confirmed Q%d: '%s'", i + 1, answer_text)
                    confirmed_answer = answer_text
                elif confirm_msg.get("type") == "answer_retry":
                    logger.info("[Conductor] Client requested re-record for Q%d", i + 1)
                    # loop continues — question will be re-sent
                else:
                    # Unexpected message; treat as confirm to avoid stalling
                    logger.warning("[Conductor] Unexpected msg during confirm: %s", confirm_msg)
                    confirmed_answer = answer_text

        # ── Self photo ────────────────────────────────────────────────────────
        await _photo_phase(ws, settings.fi_self_photo_prompt, is_selfie=True, photo_index=0)

        # ── Room photos ───────────────────────────────────────────────────────
        for idx, prompt in enumerate(settings.fi_photo_prompts):
            await _photo_phase(ws, prompt, is_selfie=False, photo_index=idx + 1)

        # ── PAN card photo (with inline OCR retry) ───────────────────────────
        await _pan_photo_phase(ws, session_id)

        # ── Bank statement consent ────────────────────────────────────────────
        await _request_consent_phase(ws)

        # Tell Android the interview is complete — officer will tap Submit
        await _send(ws, {
            "type": "session_done",
            "session_id": session_id,
            "message": (
                f"Session {session_id} complete. "
                "Please review and tap Submit to upload."
            ),
        })
        logger.info("[Conductor] ── Session done: %s — awaiting Submit ──", session_id)

    except WebSocketDisconnect:
        logger.warning("[Conductor] Client disconnected mid-session: %s", session_id)
    except Exception as exc:
        logger.exception("[Conductor] Unhandled error in session %s: %s", session_id, exc)
        try:
            await _send(ws, {"type": "error", "message": str(exc)})
        except Exception:
            pass


# ── Background report generation (called by REST upload handler) ──────────────

async def generate_report_for_session(session_id: str, meta: SessionMetadata) -> None:
    """
    Delegates all post-submission analysis to ReportPipeline.
    Called as an asyncio background task after the REST upload completes.
    """
    logger.info("[Report] Starting post-upload report for %s", session_id)
    try:
        from services.report_pipeline import ReportPipeline
        await ReportPipeline(session_id, meta).run()
        return
        # ── Legacy code below is unreachable but kept for reference ──────────
        import json as _json
        from services.geo_service import collect_geo_points, verify_location, reverse_geocode
        from services.openai_service import (analyze_all_images, analyze_bank_statement,
                                              comprehensive_credit_analysis)
        from services.pan_service import (extract_pan_data, verify_pan_nsdl, match_name,
                                           face_match, extract_nameplate_text)
        from services.name_matcher import NameMatcher
        from services.report_service import generate_credit_report, extract_customer_name
        from services.storage_service import save_response, save_session_data_json

        # 1. Geo verification
        geo_points = collect_geo_points(meta)
        geo_result = verify_location(geo_points, radius_m=settings.geo_radius_meters)
        logger.info(
            "[Report] Geo: verified=%s  points=%d  pairwise_max=%.0fm",
            geo_result.get("verified"), geo_result.get("points_checked"),
            geo_result.get("max_pairwise_distance_m", 0),
        )
        await save_response(session_id, "geo_verification.json",
                            _json.dumps(geo_result, indent=2))

        # 1b. Reverse geocode — pick first available point for address lookup
        address = "No location data captured"
        first_point = next(
            (p for p in geo_points if p.get("latitude") and p.get("longitude")), None
        )
        if first_point:
            address = await reverse_geocode(
                first_point["latitude"], first_point["longitude"],
                settings.google_maps_api_key,
            )

        # 2. Build photo entries — separate PAN card from property photos
        storage = get_storage_root() / session_id
        pan_photo   = next(
            (ph for ph in meta.photos if "pan" in ph.prompt.lower()), None
        )
        scene_photos = [ph for ph in meta.photos if ph is not pan_photo]

        photo_entries = [
            {
                "filename":  ph.filename,
                "prompt":    ph.prompt,
                "is_selfie": ph.is_selfie,
                "file_path": storage / ph.filename,
                "geo":       ph.geo,
            }
            for ph in scene_photos
        ]

        # 2b. Nameplate OCR (identify nameplate photo by tag/prompt)
        nameplate_photo = next(
            (ph for ph in meta.photos
             if ph.tag == "nameplate" or "nameplate" in ph.prompt.lower()), None
        )
        nameplate_ocr: Optional[dict] = None
        if nameplate_photo:
            nameplate_ocr = await extract_nameplate_text(storage / nameplate_photo.filename)
            await save_response(session_id, "nameplate_ocr.json",
                                _json.dumps(nameplate_ocr, indent=2, default=str))
            logger.info("[Report] Nameplate OCR: %s", nameplate_ocr.get("raw_text", "")[:80])

        # 2c. PAN card OCR + NSDL + face match
        pan_verification: Optional[dict] = None
        selfie_photo = next((ph for ph in meta.photos if ph.is_selfie), None)

        if pan_photo:
            pan_path = storage / pan_photo.filename
            logger.info("[Report] Running PAN OCR on: %s", pan_photo.filename)
            pan_ocr = await extract_pan_data(pan_path)

            # Prefer form-supplied name for matching; fall back to Q&A answer
            form_name = ""
            if meta.basic_info:
                form_name = f"{meta.basic_info.first_name} {meta.basic_info.last_name}".strip()
            interview_name = form_name or extract_customer_name(meta)
            name_match     = match_name(pan_ocr.get("name", ""), interview_name)

            nsdl_result = await verify_pan_nsdl(
                pan_number  = pan_ocr.get("pan_number", ""),
                name        = pan_ocr.get("name", ""),
                father_name = pan_ocr.get("father_name", ""),
                dob         = pan_ocr.get("dob", ""),
            )

            # Face match: selfie vs PAN
            face_result: dict = {"error": "Selfie not available", "similarity_score": 0.0}
            if selfie_photo:
                face_result = await face_match(
                    storage / selfie_photo.filename, pan_path
                )

            # 3-way name match: form + PAN + nameplate
            form_name       = f"{meta.basic_info.first_name} {meta.basic_info.last_name}".strip() if meta.basic_info else ""
            nm_text         = (nameplate_ocr or {}).get("raw_text", "")
            three_way       = NameMatcher(form_name, pan_ocr.get("name", ""), nm_text).compare()
            three_way_dict  = three_way.as_dict()

            pan_verification = {
                "ocr":             pan_ocr,
                "name_match":      name_match,
                "three_way_match": three_way_dict,
                "nsdl":            nsdl_result,
                "face_match":      face_result,
                "filename":        pan_photo.filename,
                "geo":             pan_photo.geo,
            }
            await save_response(session_id, "pan_verification.json",
                                _json.dumps(pan_verification, indent=2, default=str))
            logger.info(
                "[Report] PAN: verified=%s  2-way=%s  3-way=%s  face=%.1f%%",
                nsdl_result.get("verified"), name_match.get("matched"),
                three_way.status, face_result.get("similarity_score", 0),
            )

        # 3. OpenAI image analysis on scene photos (concurrent)
        analysed_entries = await analyze_all_images(photo_entries)

        # 4. Persist each analysis to responses/
        for i, entry in enumerate(analysed_entries):
            analysis_text = entry.get("analysis", "")
            await save_response(session_id, f"photo_{i}_analysis.txt", analysis_text)
            logger.debug("[Report] Saved analysis for photo %d", i)

        # 5. Income document analysis
        income_analysis: Optional[dict] = None
        if meta.documents:
            bank_doc = next(
                (d for d in meta.documents if d.document_type == "bank_statement"), None
            )
            if bank_doc:
                doc_path = get_storage_root() / session_id / bank_doc.filename
                if doc_path.exists():
                    logger.info("[Report] Analysing bank statement: %s", doc_path.name)
                    income_analysis = await analyze_bank_statement(doc_path)
                    await save_response(
                        session_id, "income_analysis.json",
                        _json.dumps(income_analysis, indent=2),
                    )
                else:
                    logger.warning("[Report] Bank statement file not found: %s", doc_path)

        # 5b. Comprehensive OpenAI credit analysis (single consolidated call)
        credit_analysis: Optional[dict] = None
        try:
            credit_analysis = await comprehensive_credit_analysis(
                meta, geo_result, address,
                pan_verification, nameplate_ocr, income_analysis, analysed_entries,
            )
            await save_response(session_id, "credit_analysis.json",
                                _json.dumps(credit_analysis, indent=2))
        except Exception as exc:
            logger.error("[Report] Credit analysis failed: %s", exc)

        # 6. Comprehensive session_data.json (single source of truth)
        await save_session_data_json(
            session_id, meta, geo_result, address,
            pan_verification, nameplate_ocr, income_analysis,
        )

        # 7. Generate PDF (CPU-bound, run in thread pool)
        pdf_path = await asyncio.to_thread(
            generate_credit_report,
            meta, geo_result, analysed_entries, address,
            income_analysis, pan_verification, nameplate_ocr, credit_analysis,
        )
        logger.info("[Report] PDF ready: %s", pdf_path)

    except Exception as exc:
        logger.exception("[Report] Failed to generate report for %s: %s", session_id, exc)
