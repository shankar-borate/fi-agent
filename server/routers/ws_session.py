import asyncio
import base64
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from services.session_conductor import conduct_fi_session

logger = logging.getLogger(__name__)
router = APIRouter(tags=["ws-session"])

# 500 ms of 16 kHz / 16-bit mono PCM
_SARVAM_CHUNK_BYTES = 16_000 * 2 // 2


@router.websocket("/ws/fi-session/{session_id}")
async def fi_session_websocket(websocket: WebSocket, session_id: str) -> None:
    """WebSocket endpoint — server drives the full FI session."""
    await websocket.accept()
    logger.info("[WS] Client connected: %s  session=%s", websocket.client, session_id)
    try:
        await conduct_fi_session(websocket, session_id)
    except WebSocketDisconnect as exc:
        logger.info("[WS] Client disconnected: session=%s code=%s", session_id, exc.code)
    except Exception as exc:
        logger.exception("[WS] Unhandled exception in session %s: %s", session_id, exc)
    finally:
        logger.info("[WS] Session handler exiting: %s", session_id)


@router.websocket("/ws/sarvam-stt")
async def sarvam_stt_proxy(websocket: WebSocket) -> None:
    """
    Proxy WebSocket — browser streams raw 16 kHz PCM binary frames here;
    this endpoint forwards them to Sarvam AI (adding the auth header the
    browser cannot set) and relays transcript segments back:
      Server → Browser:  {"type": "transcript", "text": "..."}
    Browser ends the stream with:
      Browser → Server:  {"type": "flush"}
    """
    import websockets as _ws
    from config import settings

    await websocket.accept()
    logger.info("[SarvamProxy] Browser connected")

    if not settings.sarvam_api_key:
        await websocket.send_text(json.dumps({"type": "error", "message": "Sarvam API key not configured"}))
        await websocket.close()
        return

    sarvam_url = (
        f"wss://api.sarvam.ai/speech-to-text/ws"
        f"?language-code={settings.transcribe_language_code}"
        f"&model=saaras:v3&sample_rate=16000&input_audio_codec=pcm_s16le"
    )

    try:
        async with _ws.legacy.client.connect(
            sarvam_url,
            extra_headers={"Api-Subscription-Key": settings.sarvam_api_key},
        ) as sarvam_ws:
            logger.info("[SarvamProxy] Connected to Sarvam — lang=%s", settings.transcribe_language_code)

            buffer = bytearray()

            async def _browser_to_sarvam() -> None:
                while True:
                    try:
                        data = await asyncio.wait_for(websocket.receive(), timeout=30.0)
                    except asyncio.TimeoutError:
                        logger.warning("[SarvamProxy] Browser receive timeout")
                        break
                    except WebSocketDisconnect:
                        break

                    if "bytes" in data:
                        buffer.extend(data["bytes"])
                        if len(buffer) >= _SARVAM_CHUNK_BYTES:
                            await sarvam_ws.send(json.dumps({
                                "audio": {
                                    "data": base64.b64encode(bytes(buffer)).decode(),
                                    "sample_rate": "16000",
                                    "encoding": "pcm_s16le",
                                }
                            }))
                            buffer.clear()

                    elif "text" in data:
                        msg = json.loads(data["text"])
                        if msg.get("type") == "flush":
                            # Flush remaining buffer then signal end to Sarvam
                            if buffer:
                                await sarvam_ws.send(json.dumps({
                                    "audio": {
                                        "data": base64.b64encode(bytes(buffer)).decode(),
                                        "sample_rate": "16000",
                                        "encoding": "pcm_s16le",
                                    }
                                }))
                                buffer.clear()
                            await sarvam_ws.send(json.dumps({"type": "flush"}))
                            logger.info("[SarvamProxy] Flush sent to Sarvam")
                            break

            async def _sarvam_to_browser() -> None:
                async for message in sarvam_ws:
                    try:
                        data = json.loads(message)
                        if data.get("type") == "data":
                            text = (data.get("data") or {}).get("transcript", "").strip()
                            if text:
                                logger.info("[SarvamProxy] Transcript: %s", text)
                                await websocket.send_text(json.dumps({"type": "transcript", "text": text}))
                    except Exception as exc:
                        logger.warning("[SarvamProxy] Parse error: %s", exc)

            await asyncio.gather(_browser_to_sarvam(), _sarvam_to_browser())

    except Exception as exc:
        logger.error("[SarvamProxy] Error: %s", exc)
        try:
            await websocket.send_text(json.dumps({"type": "error", "message": str(exc)}))
        except Exception:
            pass
    finally:
        logger.info("[SarvamProxy] Connection closed")
