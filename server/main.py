import logging
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import settings, get_storage_root
from routers.fi_session import router as fi_session_router
from routers.ws_session import router as ws_session_router
from routers.dashboard import router as dashboard_router
from routers.auditor   import router as auditor_router


# ── Logging setup ─────────────────────────────────────────────────────────────

def _setup_logging() -> None:
    fmt = "%(asctime)s [%(levelname)-8s] %(name)s — %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    for noisy in ("botocore", "boto3", "urllib3", "websockets"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


_setup_logging()
logger = logging.getLogger(__name__)


# ── FastAPI app ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="FI Agent Server",
    description="ABC Bank Field Investigation platform",
    version="2.0.0",
    # All public routes live under /fi/ so nginx can identify FI traffic
    # by a single prefix and forward with one location block.
    docs_url="/fi/docs",
    redoc_url="/fi/redoc",
    openapi_url="/fi/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Route registration ────────────────────────────────────────────────────────
#
#  Every public-facing route lives under /fi/ so nginx needs only ONE
#  location block:  location /fi/ { proxy_pass http://127.0.0.1:8000; }
#
#  /fi/api/fi-session/...  — FI session REST endpoints
#  /fi/ws/fi-session/...   — WebSocket (FI session conductor)
#  /fi/auditor/...         — Bank employee auditor portal
#  /fi/admin/...           — Internal case dashboard
#  /fi/storage/...         — Case files (photos, PDFs, recordings)
#  /fi/health              — Health check
#  /fi/                    — Customer web app (served last via StaticFiles)

app.include_router(fi_session_router, prefix="/fi")          # /fi/api/fi-session/...
app.include_router(ws_session_router, prefix="/fi")          # /fi/ws/fi-session/...
app.include_router(auditor_router,    prefix="/fi")          # /fi/auditor/...
app.include_router(dashboard_router,  prefix="/fi/admin")    # /fi/admin/ + /fi/admin/api/cases


@app.get("/fi/health", tags=["meta"])
async def health() -> dict:
    return {
        "status":          "ok",
        "storage_root":    settings.storage_root,
        "aws_region":      settings.aws_region,
        "polly_voice":     settings.polly_voice_id,
        "transcribe_lang": settings.transcribe_language_code,
    }


@app.on_event("startup")
async def startup() -> None:
    storage = get_storage_root()
    # Case files served under /fi/storage/
    app.mount("/fi/storage", StaticFiles(directory=str(storage), check_dir=False),
              name="storage")

    # Customer web app — mounted LAST so API routes always take priority
    web_dist = Path(__file__).parent.parent / "web" / "dist"
    if web_dist.exists():
        app.mount("/fi", StaticFiles(directory=str(web_dist), html=True), name="web")
        logger.info("Web dist      : %s", web_dist)
    else:
        logger.warning("Web dist not found (%s) — run:  cd web && npm run build", web_dist)

    logger.info("Storage root  : %s", storage)
    logger.info("Listening on  : %s:%s", settings.host, settings.port)
    logger.info("All routes under /fi/ — nginx: location /fi/ { proxy_pass http://127.0.0.1:8000; }")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=True)
