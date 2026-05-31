"""
AWS Polly (TTS) and AWS Transcribe Streaming (STT) wrappers.

Polly  → synthesize_speech with Kajal (en-IN neural voice) → base64 MP3
Transcribe → start_stream_transcription with en-IN → final text
"""

import asyncio
import base64
import logging
import os
from typing import Awaitable, Callable, Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from config import settings

logger = logging.getLogger(__name__)

# Inject credentials into environment so both boto3 and amazon-transcribe
# (which uses awscrt underneath) pick them up consistently.
if settings.aws_access_key_id:
    os.environ["AWS_ACCESS_KEY_ID"]     = settings.aws_access_key_id
    os.environ["AWS_SECRET_ACCESS_KEY"] = settings.aws_secret_access_key
os.environ["AWS_DEFAULT_REGION"] = settings.aws_region


# ── AWS Polly TTS ─────────────────────────────────────────────────────────────

class PollyService:
    """Thread-safe Polly wrapper. Call synthesize() from a thread pool."""

    def __init__(self):
        kwargs: dict = {"region_name": settings.aws_region}
        if settings.aws_access_key_id:
            kwargs["aws_access_key_id"] = settings.aws_access_key_id
            kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
        self._client = boto3.client("polly", **kwargs)

    def synthesize(self, text: str) -> str:
        """Returns base64-encoded MP3 string. Raises on error."""
        logger.info("[Polly] Synthesizing: %.80s", text)
        try:
            resp = self._client.synthesize_speech(
                Text=text,
                OutputFormat="mp3",
                VoiceId=settings.polly_voice_id,
                LanguageCode="en-IN",
                Engine="neural",
            )
            audio_bytes: bytes = resp["AudioStream"].read()
            encoded = base64.b64encode(audio_bytes).decode("utf-8")
            logger.info("[Polly] Done — %d bytes encoded", len(audio_bytes))
            return encoded
        except (BotoCoreError, ClientError) as exc:
            logger.error("[Polly] Failed: %s", exc)
            raise

    async def async_synthesize(self, text: str) -> str:
        """Run synthesize() on the default executor so the event loop is not blocked."""
        return await asyncio.to_thread(self.synthesize, text)


# ── AWS Transcribe Streaming STT ──────────────────────────────────────────────

OnPartialCb = Callable[[str], Awaitable[None]]


class TranscribeService:
    """
    Streaming transcription via amazon-transcribe SDK.

    audio_queue  : asyncio.Queue[bytes | None]
                   Feed 16 kHz / 16-bit / mono PCM chunks.
                   Put None to signal end-of-stream.
    on_partial   : async callback called with each partial transcript string.
    Returns      : final assembled transcript string.
    """

    async def transcribe_stream(
        self,
        audio_queue: "asyncio.Queue[Optional[bytes]]",
        on_partial: Optional[OnPartialCb] = None,
    ) -> str:
        try:
            from amazon_transcribe.client import TranscribeStreamingClient
            from amazon_transcribe.handlers import TranscriptResultStreamHandler
            from amazon_transcribe.model import TranscriptEvent
        except ImportError:
            logger.error("[Transcribe] 'amazon-transcribe' package not installed")
            return ""

        client = TranscribeStreamingClient(region=settings.aws_region)
        logger.info(
            "[Transcribe] Opening stream — lang=%s", settings.transcribe_language_code
        )

        stream = await client.start_stream_transcription(
            language_code=settings.transcribe_language_code,
            media_sample_rate_hz=16000,
            media_encoding="pcm",
        )

        final_parts: list[str] = []

        class Handler(TranscriptResultStreamHandler):
            async def handle_transcript_event(_, event: TranscriptEvent):  # noqa: N805
                for result in event.transcript.results:
                    if not result.alternatives:
                        continue
                    text = result.alternatives[0].transcript
                    if result.is_partial:
                        logger.debug("[Transcribe] Partial: %s", text)
                        if on_partial:
                            await on_partial(text)
                    else:
                        logger.info("[Transcribe] Final segment: %s", text)
                        final_parts.append(text)

        async def _feed_audio() -> None:
            total = 0
            while True:
                chunk = await audio_queue.get()
                if chunk is None:
                    logger.info("[Transcribe] Audio end — total %d bytes sent", total)
                    break
                total += len(chunk)
                await stream.input_stream.send_audio_event(audio_chunk=chunk)
            await stream.input_stream.end_stream()

        handler = Handler(stream.output_stream)
        await asyncio.gather(_feed_audio(), handler.handle_events())

        result = " ".join(final_parts).strip()
        logger.info("[Transcribe] Full transcript: '%s'", result)
        return result


# ── Sarvam Streaming STT ──────────────────────────────────────────────────────

class SarvamTranscribeService:
    """
    Streaming transcription via Sarvam AI WebSocket API (saaras:v3).

    audio_queue  : asyncio.Queue[bytes | None]
                   Feed 16 kHz / 16-bit / mono PCM chunks.
                   Put None to signal end-of-stream.
    on_partial   : async callback called with each transcript segment.
    Returns      : final assembled transcript string.
    """

    async def transcribe_stream(
        self,
        audio_queue: "asyncio.Queue[Optional[bytes]]",
        on_partial: Optional[OnPartialCb] = None,
    ) -> str:
        import base64
        import json as _json
        import websockets

        lang = settings.transcribe_language_code
        ws_url = (
            f"wss://api.sarvam.ai/speech-to-text/ws"
            f"?language-code={lang}"
            f"&model=saaras:v3"
            f"&sample_rate=16000"
            f"&input_audio_codec=pcm_s16le"
        )
        logger.info("[Sarvam] Opening stream — lang=%s", lang)

        final_parts: list[str] = []
        # 500 ms worth of 16 kHz / 16-bit mono PCM
        CHUNK_BYTES = 16000 * 2 // 2

        try:
            async with websockets.legacy.client.connect(
                ws_url,
                extra_headers={"Api-Subscription-Key": settings.sarvam_api_key},
            ) as ws:

                async def _feed_audio() -> None:
                    buffer = bytearray()
                    total = 0
                    while True:
                        chunk = await audio_queue.get()
                        if chunk is None:
                            if buffer:
                                await ws.send(_json.dumps({
                                    "audio": {
                                        "data": base64.b64encode(bytes(buffer)).decode(),
                                        "sample_rate": "16000",
                                        "encoding": "pcm_s16le",
                                    }
                                }))
                            await ws.send(_json.dumps({"type": "flush"}))
                            logger.info("[Sarvam] Audio end — %d bytes sent", total)
                            break
                        buffer.extend(chunk)
                        total += len(chunk)
                        if len(buffer) >= CHUNK_BYTES:
                            await ws.send(_json.dumps({
                                "audio": {
                                    "data": base64.b64encode(bytes(buffer)).decode(),
                                    "sample_rate": "16000",
                                    "encoding": "pcm_s16le",
                                }
                            }))
                            buffer.clear()

                async def _recv_transcripts() -> None:
                    async for message in ws:
                        try:
                            data = _json.loads(message)
                            if data.get("type") == "data":
                                text = (data.get("data") or {}).get("transcript", "").strip()
                                if text:
                                    logger.info("[Sarvam] Segment: %s", text)
                                    final_parts.append(text)
                                    if on_partial:
                                        await on_partial(text)
                        except Exception as exc:
                            logger.warning("[Sarvam] Parse error: %s", exc)

                await asyncio.gather(_feed_audio(), _recv_transcripts())

        except Exception as exc:
            logger.error("[Sarvam] Stream error: %s", exc)
            return ""

        result = " ".join(final_parts).strip()
        logger.info("[Sarvam] Full transcript: '%s'", result)
        return result


# ── Singletons ────────────────────────────────────────────────────────────────

_polly: Optional[PollyService] = None
_transcribe: Optional[TranscribeService] = None
_sarvam_transcribe: Optional[SarvamTranscribeService] = None


def get_polly() -> PollyService:
    global _polly
    if _polly is None:
        _polly = PollyService()
    return _polly


def get_transcribe() -> TranscribeService:
    global _transcribe
    if _transcribe is None:
        _transcribe = TranscribeService()
    return _transcribe


def get_sarvam_transcribe() -> SarvamTranscribeService:
    global _sarvam_transcribe
    if _sarvam_transcribe is None:
        _sarvam_transcribe = SarvamTranscribeService()
    return _sarvam_transcribe


def get_active_transcribe():
    """Return the transcription service selected by FI_TRANSCRIBE_ENGINE."""
    if settings.transcribe_engine.lower() == "sarvam":
        logger.info("[Transcribe] Engine: Sarvam AI")
        return get_sarvam_transcribe()
    logger.info("[Transcribe] Engine: AWS Transcribe")
    return get_transcribe()
