#!/usr/bin/env python3
"""
FI Agent – System Documentation Generator
==========================================
Generates docs/fi_agent_documentation.pdf

Run from the project root:
    python docs/generate_docs.py

Requires: reportlab   (pip install reportlab)
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.flowables import Flowable

# ── Output path ───────────────────────────────────────────────────────────────
DOCS_DIR = Path(__file__).parent
OUTPUT = DOCS_DIR / "fi_agent_documentation.pdf"

# ── Brand colours ─────────────────────────────────────────────────────────────
C_NAVY   = colors.HexColor("#1A237E")
C_RED    = colors.HexColor("#E53935")
C_STEEL  = colors.HexColor("#37474F")
C_LIGHT  = colors.HexColor("#E8EAF6")
C_LGREY  = colors.HexColor("#F5F5F5")
C_MGREY  = colors.HexColor("#9E9E9E")
C_GREEN  = colors.HexColor("#2E7D32")
C_AMBER  = colors.HexColor("#E65100")
C_TEAL   = colors.HexColor("#00695C")
C_WHITE  = colors.white

PAGE_W, PAGE_H = A4
MARGIN = 1.8 * cm


# ═══════════════════════════════════════════════════════════════════════════════
#  Sequence-diagram Flowable
# ═══════════════════════════════════════════════════════════════════════════════

class SeqDiagram(Flowable):
    """
    Lightweight sequence-diagram renderer using raw canvas calls.

    participants – list of str (actor labels, left → right)
    messages     – list of dict:
        { frm, to, label }              → solid arrow
        { frm, to, label, ret:True }    → dashed return arrow
        { frm, frm, label, note:True }  → yellow note box on participant frm
        { frm, to, label, grp:True }    → group/activation bar background
    """
    BOX_W  = 105
    BOX_H  = 22
    GAP    = 28
    ROW_H  = 30
    PAD_X  = 6

    def __init__(self, participants, messages, scale=1.0):
        super().__init__()
        self.parts   = participants
        self.msgs    = messages
        self._scale  = scale
        n = len(participants)
        self._nat_w = self.PAD_X * 2 + n * self.BOX_W + (n - 1) * self.GAP
        self._nat_h = self.BOX_H + len(messages) * self.ROW_H + self.BOX_H + 8

    def _cx(self, idx):
        return self.PAD_X + idx * (self.BOX_W + self.GAP) + self.BOX_W / 2

    def wrap(self, aW, aH):
        s = min(self._scale, aW / self._nat_w)
        self._draw_scale = s
        return aW, self._nat_h * s

    def _box(self, c, x, y, w, h, fill_c, stroke_c, text, font="Helvetica-Bold", fsize=7.5):
        c.setFillColor(fill_c)
        c.setStrokeColor(stroke_c)
        c.setLineWidth(0.6)
        c.roundRect(x, y, w, h, 3, fill=1, stroke=1)
        c.setFillColor(C_WHITE)
        c.setFont(font, fsize)
        c.drawCentredString(x + w / 2, y + h / 2 - fsize / 2 + 1, text)

    def draw(self):
        c   = self.canv
        s   = self._draw_scale
        th  = self._nat_h
        n   = len(self.parts)

        c.saveState()
        c.scale(s, s)

        # Lifelines
        c.setStrokeColor(colors.HexColor("#B0BEC5"))
        c.setDash(3, 3)
        c.setLineWidth(0.7)
        for i in range(n):
            cx = self._cx(i)
            c.line(cx, th - self.BOX_H, cx, self.BOX_H)
        c.setDash()

        # Top participant boxes
        for i, name in enumerate(self.parts):
            x = self.PAD_X + i * (self.BOX_W + self.GAP)
            self._box(c, x, th - self.BOX_H, self.BOX_W, self.BOX_H,
                      C_NAVY, C_NAVY, name)

        # Messages
        for idx, msg in enumerate(self.msgs):
            row_y = th - self.BOX_H - (idx + 1) * self.ROW_H + self.ROW_H // 2
            frm, to = msg["frm"], msg.get("to", msg["frm"])
            label = msg.get("label", "")
            is_ret  = msg.get("ret",  False)
            is_note = msg.get("note", False)

            if is_note:
                nw = self.BOX_W - 10
                nx = self._cx(frm) - nw / 2
                c.setFillColor(colors.HexColor("#FFFDE7"))
                c.setStrokeColor(colors.HexColor("#F9A825"))
                c.setLineWidth(0.5)
                c.roundRect(nx, row_y - 9, nw, 18, 2, fill=1, stroke=1)
                c.setFillColor(C_STEEL)
                c.setFont("Helvetica-Oblique", 7)
                c.drawCentredString(self._cx(frm), row_y - 2, label[:36])
                continue

            fx, tx = self._cx(frm), self._cx(to)
            if is_ret:
                c.setStrokeColor(colors.HexColor("#78909C"))
                c.setDash(4, 3)
                arr_clr = colors.HexColor("#78909C")
            else:
                c.setStrokeColor(C_NAVY)
                c.setDash()
                arr_clr = C_NAVY

            c.setLineWidth(1.0)
            c.line(fx, row_y, tx, row_y)
            c.setDash()

            # Arrowhead
            d = 1 if tx >= fx else -1
            c.setFillColor(arr_clr)
            p = c.beginPath()
            p.moveTo(tx, row_y)
            p.lineTo(tx - d * 9, row_y + 4)
            p.lineTo(tx - d * 9, row_y - 4)
            p.close()
            c.drawPath(p, fill=1, stroke=0)

            # Label above arrow
            mid_x = (fx + tx) / 2
            c.setFillColor(C_STEEL if is_ret else C_NAVY)
            c.setFont("Helvetica" if is_ret else "Helvetica-Bold", 7)
            c.drawCentredString(mid_x, row_y + 4, label[:46])

        # Bottom participant boxes (mirror)
        for i, name in enumerate(self.parts):
            x = self.PAD_X + i * (self.BOX_W + self.GAP)
            self._box(c, x, 0, self.BOX_W, self.BOX_H, C_NAVY, C_NAVY, name)

        c.restoreState()


# ═══════════════════════════════════════════════════════════════════════════════
#  Style sheet
# ═══════════════════════════════════════════════════════════════════════════════

def _styles():
    def ps(name, **kw):
        return ParagraphStyle(name, parent=getSampleStyleSheet()["Normal"], **kw)

    return {
        "title":     ps("dt", fontSize=28, leading=34, textColor=C_NAVY,
                        alignment=TA_CENTER, fontName="Helvetica-Bold"),
        "subtitle":  ps("ds", fontSize=14, leading=18, textColor=C_STEEL,
                        alignment=TA_CENTER),
        "meta":      ps("dm", fontSize=10, leading=14, textColor=C_MGREY,
                        alignment=TA_CENTER),
        "ch":        ps("ch", fontSize=16, leading=20, textColor=C_WHITE,
                        fontName="Helvetica-Bold"),
        "h2":        ps("h2", fontSize=12, leading=16, textColor=C_NAVY,
                        fontName="Helvetica-Bold", spaceBefore=10, spaceAfter=4),
        "h3":        ps("h3", fontSize=10, leading=14, textColor=C_STEEL,
                        fontName="Helvetica-Bold", spaceBefore=6, spaceAfter=2),
        "body":      ps("bd", fontSize=9,  leading=13, textColor=C_STEEL,
                        alignment=TA_JUSTIFY),
        "body_l":    ps("bl", fontSize=9,  leading=13, textColor=C_STEEL),
        "bold":      ps("bb", fontSize=9,  leading=13, textColor=C_STEEL,
                        fontName="Helvetica-Bold"),
        "code":      ps("cd", fontSize=8,  leading=11, textColor=colors.HexColor("#263238"),
                        fontName="Courier", backColor=colors.HexColor("#ECEFF1"),
                        leftIndent=6, rightIndent=6, spaceBefore=2, spaceAfter=2),
        "small":     ps("sm", fontSize=7.5, leading=10, textColor=C_MGREY),
        "footer":    ps("ft", fontSize=7.5, leading=10, textColor=C_MGREY,
                        alignment=TA_CENTER),
        "toc_h":     ps("th", fontSize=10, leading=15, textColor=C_NAVY,
                        fontName="Helvetica-Bold"),
        "toc":       ps("tc", fontSize=9,  leading=14, textColor=C_STEEL,
                        leftIndent=12),
        "bullet":    ps("bu", fontSize=9,  leading=13, textColor=C_STEEL,
                        leftIndent=14, firstLineIndent=-10),
    }


# ── Common builders ───────────────────────────────────────────────────────────

def chapter(text, s):
    tbl = Table([[Paragraph(f"  {text}", s["ch"])]], colWidths=[PAGE_W - 2 * MARGIN])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), C_NAVY),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return [tbl, Spacer(1, 6)]


def h2(text, s):  return [Paragraph(text, s["h2"])]
def h3(text, s):  return [Paragraph(text, s["h3"])]
def body(text, s): return [Paragraph(text, s["body"])]
def sp(n=6):      return [Spacer(1, n)]
def hr():         return [HRFlowable(width="100%", thickness=0.5, color=C_MGREY, spaceAfter=4)]


def kv_table(rows, s, col1=5*cm):
    data = [[Paragraph(k, s["bold"]), Paragraph(str(v), s["body_l"])] for k, v in rows]
    w2 = PAGE_W - 2 * MARGIN - col1
    tbl = Table(data, colWidths=[col1, w2])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (0, -1), C_LIGHT),
        ("ROWBACKGROUNDS",(0, 0), (-1, -1), [C_WHITE, C_LGREY]),
        ("GRID",          (0, 0), (-1, -1), 0.3, colors.HexColor("#BDBDBD")),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING",   (0, 0), (-1, -1), 5),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ]))
    return [tbl]


def col_table(headers, rows, s, col_widths=None):
    all_rows = [[Paragraph(h, s["bold"]) for h in headers]]
    for r in rows:
        all_rows.append([Paragraph(str(c), s["body_l"]) for c in r])
    tbl = Table(all_rows, colWidths=col_widths)
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), C_STEEL),
        ("TEXTCOLOR",     (0, 0), (-1, 0), C_WHITE),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [C_WHITE, C_LGREY]),
        ("GRID",          (0, 0), (-1, -1), 0.3, colors.HexColor("#BDBDBD")),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 8),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING",   (0, 0), (-1, -1), 4),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ]))
    return [tbl]


def bullets(items, s):
    return [Paragraph(f"• {i}", s["bullet"]) for i in items]


def code_block(text, s):
    lines = text.strip().split("\n")
    return [Paragraph(line.replace(" ", "&nbsp;") or "&nbsp;", s["code"]) for line in lines]


def caption(text, s):
    return [Paragraph(f"<i>{text}</i>", s["small"]), Spacer(1, 6)]


# ── Page footer ───────────────────────────────────────────────────────────────

def _footer(canvas, doc):
    canvas.saveState()
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(C_MGREY)
    canvas.drawString(MARGIN, 0.9 * cm, "FI Agent — System Documentation — Confidential")
    canvas.drawRightString(PAGE_W - MARGIN, 0.9 * cm, f"Page {doc.page}  |  {ts}")
    canvas.restoreState()


# ═══════════════════════════════════════════════════════════════════════════════
#  COVER PAGE
# ═══════════════════════════════════════════════════════════════════════════════

def cover(s):
    gen = datetime.now(timezone.utc).strftime("%B %Y")
    return [
        Spacer(1, 3 * cm),
        Paragraph("FI Agent", s["title"]),
        Spacer(1, 0.4 * cm),
        HRFlowable(width="60%", thickness=3, color=C_RED, spaceAfter=12),
        Paragraph("Field Investigation Credit Verification System", s["subtitle"]),
        Spacer(1, 0.6 * cm),
        Paragraph("Technical Architecture &amp; System Documentation", s["meta"]),
        Spacer(1, 0.3 * cm),
        Paragraph(f"Version 2.0  ·  {gen}", s["meta"]),
        Spacer(1, 2.5 * cm),
        # Feature summary box
        _cover_feature_box(s),
        Spacer(1, 2.5 * cm),
        Paragraph("CONFIDENTIAL — FOR INTERNAL USE ONLY", s["small"]),
        PageBreak(),
    ]


def _cover_feature_box(s):
    rows = [
        ["📱 Android App",   "Camera, Microphone, GPS, WebSocket client"],
        ["🖥  FastAPI Server","WebSocket conductor, REST upload, PDF reports"],
        ["🎙  AWS Polly",     "Neural Text-to-Speech (Indian English — Kajal)"],
        ["🔤 AWS Transcribe", "Real-time STT streaming (en-IN)"],
        ["🤖 OpenAI GPT-4o", "Property image analysis for credit assessment"],
        ["📄 ReportLab PDF", "Auto-generated credit verification reports"],
    ]
    data = [[Paragraph(k, s["bold"]), Paragraph(v, s["body_l"])] for k, v in rows]
    tbl = Table(data, colWidths=[4.5 * cm, PAGE_W - 2 * MARGIN - 4.5 * cm])
    tbl.setStyle(TableStyle([
        ("BOX",           (0, 0), (-1, -1), 1.0, C_NAVY),
        ("LINEBELOW",     (0, 0), (-1, -2), 0.3, colors.HexColor("#BDBDBD")),
        ("ROWBACKGROUNDS",(0, 0), (-1, -1), [C_LIGHT, C_WHITE]),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
    ]))
    return tbl


# ═══════════════════════════════════════════════════════════════════════════════
#  TABLE OF CONTENTS
# ═══════════════════════════════════════════════════════════════════════════════

def toc(s):
    f = []
    f += chapter("Table of Contents", s)
    toc_entries = [
        ("1.", "System Overview", [
            "1.1  Purpose", "1.2  High-Level Architecture", "1.3  Key Components",
        ]),
        ("2.", "Android Application", [
            "2.1  Package Structure & Layers", "2.2  Permissions",
            "2.3  Session Flow", "2.4  Local Storage", "2.5  FiConfig Reference",
        ]),
        ("3.", "Server Application", [
            "3.1  Directory Structure", "3.2  API Endpoints",
            "3.3  Service Layer", "3.4  Server Storage",
        ]),
        ("4.", "WebSocket Communication Protocol", [
            "4.1  Connection & Handshake", "4.2  Message Reference Table",
            "4.3  Audio Streaming Format",
        ]),
        ("5.", "End-to-End Sequence Diagrams", [
            "5.1  Full Session Flow", "5.2  Q&A with AWS TTS + STT",
            "5.3  Photo Capture & Upload", "5.4  Post-Session Report Pipeline",
        ]),
        ("6.", "AWS Services Integration", [
            "6.1  AWS Polly (TTS)", "6.2  AWS Transcribe Streaming (STT)",
            "6.3  Required IAM Permissions",
        ]),
        ("7.", "Storage Architecture", [
            "7.1  Android Local Storage", "7.2  Server Session Storage",
            "7.3  Reports Directory", "7.4  File Naming Conventions",
        ]),
        ("8.", "Report Generation Pipeline", [
            "8.1  Geo-Verification Logic", "8.2  OpenAI Image Analysis",
            "8.3  PDF Report Structure",
        ]),
        ("9.", "Configuration Reference", [
            "9.1  Server .env Variables", "9.2  Android FiConfig",
        ]),
        ("10.", "Deployment Guide", [
            "10.1  Server Setup", "10.2  Android Build", "10.3  Testing Checklist",
        ]),
    ]
    for num, title, subs in toc_entries:
        f.append(Paragraph(f"{num}  {title}", s["toc_h"]))
        for sub in subs:
            f.append(Paragraph(sub, s["toc"]))
        f.append(Spacer(1, 4))
    f.append(PageBreak())
    return f


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 1 — SYSTEM OVERVIEW
# ═══════════════════════════════════════════════════════════════════════════════

def sec1(s):
    f = []
    f += chapter("1.  System Overview", s)

    f += h2("1.1  Purpose", s)
    f += body(
        "FI Agent is a <b>Field Investigation Credit Verification</b> system for small-loan "
        "disbursement teams. A field officer visits the applicant's residence, launches the "
        "Android app, and conducts a server-orchestrated interview: structured questions are "
        "spoken aloud (AWS Polly), the applicant's answers are recorded and transcribed in "
        "real time (AWS Transcribe), and property photographs are captured. At session end the "
        "server automatically runs geo-verification, property analysis (OpenAI GPT-4o), and "
        "produces a formatted PDF credit report — all without manual data entry.", s
    )
    f += sp()

    f += h2("1.2  High-Level Architecture", s)
    arch_rows = [
        ["Layer", "Component", "Technology", "Role"],
        ["Client",  "Android App",      "Kotlin / CameraX / OkHttp WS",    "UI, camera, mic, GPS, WS client"],
        ["Comms",   "WebSocket",         "FastAPI / OkHttp3",               "Bidirectional real-time session"],
        ["Server",  "Session Conductor", "Python asyncio",                  "Orchestrates entire FI flow"],
        ["AI/TTS",  "AWS Polly",         "boto3 Neural en-IN (Kajal)",      "Text → MP3 audio"],
        ["AI/STT",  "AWS Transcribe",    "amazon-transcribe SDK streaming", "PCM audio → live transcript"],
        ["AI/Vision","OpenAI GPT-4o",    "openai Python SDK",               "Property image analysis"],
        ["Storage", "Session Files",     "Filesystem  D:\\fig\\",           "Photos, recording, metadata JSON"],
        ["Output",  "PDF Report",        "ReportLab",                       "server/reports/ credit report"],
    ]
    cw = [2.2*cm, 3.5*cm, 5*cm, PAGE_W - 2*MARGIN - 2.2*cm - 3.5*cm - 5*cm]
    f += col_table(arch_rows[0], arch_rows[1:], s, col_widths=cw)
    f += sp(10)

    f += h2("1.3  Key Capabilities", s)
    f += bullets([
        "Server-driven protocol — Android is a thin terminal; all session logic lives on the server",
        "Real-time Indian-English voice questions via AWS Polly (Neural Kajal voice)",
        "Live STT transcript displayed on screen as the applicant speaks (AWS Transcribe en-IN)",
        "GPS captured at every Q&A and photo event, verified against configurable 500 m radius",
        "Session audio recorded in full (foreground service) for audit trail",
        "OpenAI GPT-4o analyses each property photo: condition, credit indicators, score 1–10",
        "Auto-generated A4 PDF report with embedded photo thumbnails and geo-verification table",
        "All questions and photo prompts configurable via environment variables — no code change",
    ], s)
    f.append(PageBreak())
    return f


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 2 — ANDROID APPLICATION
# ═══════════════════════════════════════════════════════════════════════════════

def sec2(s):
    f = []
    f += chapter("2.  Android Application", s)

    f += h2("2.1  Package Structure & Layers", s)
    f += body("The app follows a strict layered architecture. Each layer has a single "
              "responsibility and depends only on the layer below it.", s)
    f += sp(4)

    pkg_rows = [
        ["Package",                  "Layer",    "Key Classes"],
        ["com.ficx.app",             "Root",     "MainActivity — Start FI button, permission gating"],
        ["com.ficx.app.config",      "Config",   "FiConfig — all tunable parameters"],
        ["com.ficx.app.domain.model","Domain",   "FiSession, SessionStep, QuestionAnswer, PhotoCapture, GeoPoint"],
        ["com.ficx.app.domain.usecase","Domain", "BuildSessionStepsUseCase — builds ordered step list"],
        ["com.ficx.app.data.model",  "Data",     "DTO classes (Gson-serialisable) for REST upload"],
        ["com.ficx.app.data.network","Data",     "FiApiService (Retrofit), FiApiClient (OkHttp)"],
        ["com.ficx.app.data.repository","Data",  "FiSessionRepository — multipart upload"],
        ["com.ficx.app.service",     "Service",  "WebSocketManager, AudioRecorder, AudioPlayer,\n"
                                                  "LocationHelper, SessionRecordingService, FiLog"],
        ["com.ficx.app.ui.viewmodel","UI",       "FiSessionViewModel — WS message handler, state machine"],
        ["com.ficx.app.ui",          "UI",       "FiSessionActivity — camera, layout, lifecycle"],
    ]
    cw = [5*cm, 2.5*cm, PAGE_W - 2*MARGIN - 7.5*cm]
    f += col_table(pkg_rows[0], pkg_rows[1:], s, col_widths=cw)
    f += sp(8)

    f += h2("2.2  Permissions", s)
    perm_rows = [
        ["Permission",                      "Used for"],
        ["CAMERA",                          "CameraX preview, photo capture (front + back)"],
        ["RECORD_AUDIO",                    "AudioRecord PCM stream → server STT + session recording"],
        ["ACCESS_FINE_LOCATION",            "FusedLocationProvider — lat/long per Q&A and photo"],
        ["INTERNET",                        "WebSocket + REST upload to server"],
        ["READ_MEDIA_IMAGES / READ_EXTERNAL_STORAGE", "Access saved session files (API-version gated)"],
        ["FOREGROUND_SERVICE (camera|microphone)", "SessionRecordingService — keeps recording across lifecycle"],
        ["WAKE_LOCK",                       "Prevent screen-off during session"],
    ]
    cw2 = [6.5*cm, PAGE_W - 2*MARGIN - 6.5*cm]
    f += col_table(perm_rows[0], perm_rows[1:], s, col_widths=cw2)
    f += sp(8)

    f += h2("2.3  Session Flow (Android side)", s)
    f += bullets([
        "1. User taps Start FI → EasyPermissions requests all required permissions",
        "2. FiSessionActivity starts: front camera binds, SessionRecordingService starts foreground service",
        "3. FiSessionViewModel connects WebSocket to  ws://<server>/ws/fi-session/<sessionId>",
        "4. Sends {type:\"ready\", session_id, device_id, started_at} handshake",
        "5. Handles incoming server messages and updates UiState flow (observed by Activity)",
        "6. On tts_audio  → AudioPlayer decodes base64 MP3, plays via MediaPlayer, sends tts_done",
        "7. On start_listening → AudioRecorder sends 100 ms PCM chunks as binary WS frames",
        "8. On capture_photo → CameraX takePicture(), base64 JPEG sent as {type:\"photo\"} JSON",
        "9. On session_done → stop recording service, toast message, Activity finishes after 3 s",
    ], s)
    f += sp(8)

    f += h2("2.4  Local Storage (Android)", s)
    f += kv_table([
        ("Session files",      "getFilesDir()/fi_sessions/<session_id>/"),
        ("Photos",             "photo_<yyyyMMdd_HHmmss_SSS>.jpg"),
        ("Session recording",  "recording_<session_id>_<timestamp>.aac"),
        ("TTS temp files",     "getCacheDir()/tts_<timestamp>.mp3  (deleted after playback)"),
    ], s)
    f += sp(8)

    f += h2("2.5  FiConfig Reference  (android/.../config/FiConfig.kt)", s)
    cfg_rows = [
        ["Field",               "Default",     "Purpose"],
        ["serverUrl",           "http://192.168.1.100:8000", "FastAPI server base URL"],
        ["questions",           "3 defaults",  "Spoken Q&A questions (configurable list)"],
        ["selfPhotoPrompt",     "See code",    "Text spoken before the selfie countdown"],
        ["photoPrompts",        "4 rooms",     "Text + countdown for each room photo"],
        ["countdownSeconds",    "10",          "Countdown timer before each photo"],
        ["sttTimeoutMs",        "10 000",      "Max recording duration per question (ms)"],
        ["uploadTimeoutSec",    "120",         "HTTP upload timeout for REST batch upload"],
    ]
    cw3 = [3.5*cm, 3.5*cm, PAGE_W - 2*MARGIN - 7*cm]
    f += col_table(cfg_rows[0], cfg_rows[1:], s, col_widths=cw3)
    f.append(PageBreak())
    return f


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 3 — SERVER APPLICATION
# ═══════════════════════════════════════════════════════════════════════════════

def sec3(s):
    f = []
    f += chapter("3.  Server Application", s)

    f += h2("3.1  Directory Structure", s)
    f += code_block("""
server/
├── main.py                   FastAPI app, logging setup, router registration
├── config.py                 Pydantic-settings; all env-var config + property helpers
├── requirements.txt          Python dependencies
├── .env                      (not committed) secrets and overrides
├── models/
│   └── fi_session.py         Pydantic models: SessionMetadata, PhotoMeta, GeoPoint …
├── routers/
│   ├── fi_session.py         POST /api/fi-session/upload  (REST batch upload)
│   └── ws_session.py         WS  /ws/fi-session/{session_id}
└── services/
    ├── aws_service.py        PollyService + TranscribeService + singletons
    ├── geo_service.py        Haversine, centroid, radius verification
    ├── openai_service.py     GPT-4o batch image analysis
    ├── report_service.py     ReportLab A4 PDF generation
    ├── session_conductor.py  WebSocket orchestration + background report trigger
    └── storage_service.py    Async file I/O into D:\\fig\\<session_id>\\

docs/
├── generate_docs.py          This script
└── fi_agent_documentation.pdf

reports/
└── <session_id>/
    └── fi_report_<id>_<ts>.pdf
""", s)
    f += sp(6)

    f += h2("3.2  API Endpoints", s)
    ep_rows = [
        ["Method / Protocol", "Path",                            "Purpose"],
        ["WebSocket",         "/ws/fi-session/{session_id}",     "Real-time FI session — server-driven conductor"],
        ["POST (multipart)",  "/api/fi-session/upload",          "Legacy/batch upload after offline session"],
        ["GET",               "/api/fi-session/{id}/files",      "List files stored for a session"],
        ["GET",               "/health",                         "Server status + active config summary"],
    ]
    cw = [3*cm, 5.5*cm, PAGE_W - 2*MARGIN - 8.5*cm]
    f += col_table(ep_rows[0], ep_rows[1:], s, col_widths=cw)
    f += sp(8)

    f += h2("3.3  Service Layer Responsibilities", s)
    svc_rows = [
        ["Service",              "Responsibility"],
        ["session_conductor",    "WebSocket message loop; calls all other services in sequence; "
                                 "triggers report generation as background asyncio task"],
        ["aws_service",          "PollyService: boto3 synthesize_speech → base64 MP3. "
                                 "TranscribeService: async streaming PCM queue → final transcript"],
        ["geo_service",          "Collects GeoPoints from SessionMetadata; Haversine centroid check; "
                                 "returns per-point distance table and verified boolean"],
        ["openai_service",       "Encodes each photo as base64; sends to GPT-4o with credit-officer "
                                 "system prompt; runs all images concurrently with asyncio.gather"],
        ["report_service",       "ReportLab A4 PDF: cover, Q&A table, geo table, photo+analysis panels, "
                                 "credit summary; saved to server/reports/<session_id>/"],
        ["storage_service",      "Async aiofiles writes to D:\\fig\\<session_id>\\; "
                                 "creates directories on first use"],
    ]
    cw2 = [3.5*cm, PAGE_W - 2*MARGIN - 3.5*cm]
    f += col_table(svc_rows[0], svc_rows[1:], s, col_widths=cw2)
    f += sp(8)

    f += h2("3.4  Server Storage Layout", s)
    f += kv_table([
        ("Session root",   "D:\\fig\\  (FI_STORAGE_ROOT env var)"),
        ("Session folder", "D:\\fig\\<session_id>\\"),
        ("Photos",         "D:\\fig\\<session_id>\\photo_<yyyyMMdd_HHmmss_SSS>.jpg"),
        ("Recording",      "D:\\fig\\<session_id>\\recording_<session_id>_<ts>.aac"),
        ("Metadata",       "D:\\fig\\<session_id>\\metadata.json"),
        ("Reports root",   "server/reports\\  (relative to server working dir)"),
        ("Report PDF",     "server/reports\\<session_id>\\fi_report_<id>_<ts>.pdf"),
    ], s)
    f.append(PageBreak())
    return f


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 4 — WEBSOCKET PROTOCOL
# ═══════════════════════════════════════════════════════════════════════════════

def sec4(s):
    f = []
    f += chapter("4.  WebSocket Communication Protocol", s)

    f += h2("4.1  Connection & Handshake", s)
    f += kv_table([
        ("URL",          "ws://<host>:<port>/ws/fi-session/<session_id>"),
        ("Transport",    "OkHttp3 WebSocket (Android)  ↔  FastAPI WebSocket (server)"),
        ("Text frames",  "UTF-8 JSON — all control messages"),
        ("Binary frames","Raw PCM audio chunks from Android during listening phases"),
        ("Handshake",    "Android sends {type:\"ready\"} after connection opens; "
                         "server begins session after receiving it"),
    ], s)
    f += sp(8)

    f += h2("4.2  Message Reference Table", s)
    f += body("Direction: S→A = Server to Android,  A→S = Android to Server,  BIN = binary frame.", s)
    f += sp(4)

    msg_rows = [
        ["Type",           "Dir", "Key Fields",                     "Description"],
        ["ready",          "A→S", "session_id, device_id, started_at", "Handshake — starts the session"],
        ["question",       "S→A", "index, text",                    "Display question text on screen"],
        ["tts_audio",      "S→A", "format='mp3', data=<b64>",       "Polly MP3 to play on device"],
        ["tts_done",       "A→S", "—",                              "Playback complete; server may proceed"],
        ["start_listening","S→A", "question_index, timeout_ms",     "Android starts AudioRecord and streams PCM"],
        ["<PCM chunks>",   "A→S", "binary frames",                  "Raw 16 kHz / 16-bit / mono PCM"],
        ["audio_end",      "A→S", "—",                              "Recording stopped; Transcribe stream closed"],
        ["transcript",     "S→A", "question_index, text, is_final", "Partial (live) or final answer text"],
        ["announce_photo", "S→A", "prompt, is_selfie",              "Show prompt; play TTS"],
        ["countdown",      "S→A", "value (10 … 1)",                 "Countdown tick — shown as large number"],
        ["capture_photo",  "S→A", "prompt, is_selfie, photo_index", "CameraX takePicture() triggered"],
        ["photo",          "A→S", "filename, data=<b64 JPEG>, prompt, photo_index, geo={lat,lon,ts}", "Captured photo + GPS"],
        ["photo_ack",      "S→A", "photo_index",                    "Server saved photo successfully"],
        ["session_done",   "S→A", "session_id, message",            "All steps complete; report generating"],
        ["error",          "S→A", "message",                        "Fatal error — session terminated"],
    ]
    cw = [2.5*cm, 1.3*cm, 4.5*cm, PAGE_W - 2*MARGIN - 8.3*cm]
    f += col_table(msg_rows[0], msg_rows[1:], s, col_widths=cw)
    f += sp(8)

    f += h2("4.3  Audio Streaming Format", s)
    f += kv_table([
        ("Encoding",      "PCM signed 16-bit little-endian"),
        ("Sample rate",   "16 000 Hz"),
        ("Channels",      "Mono (1 channel)"),
        ("Chunk size",    "~3 200 bytes per frame  (100 ms of audio)"),
        ("Frame type",    "WebSocket binary frame"),
        ("End signal",    "JSON text frame  {type: 'audio_end'}"),
        ("AWS requirement","Transcribe streaming expects exactly this format for en-IN"),
    ], s)
    f.append(PageBreak())
    return f


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 5 — SEQUENCE DIAGRAMS
# ═══════════════════════════════════════════════════════════════════════════════

def sec5(s):
    f = []
    f += chapter("5.  End-to-End Sequence Diagrams", s)

    # ── 5.1 Full Session Flow ─────────────────────────────────────────────────
    f += h2("5.1  Complete FI Session Flow", s)
    parts_full = ["Android", "Server", "AWS Polly", "AWS Transcribe", "OpenAI / PDF"]
    msgs_full  = [
        {"frm":0,"to":1,"label":"WS connect + {ready}"},
        {"frm":1,"to":1,"label":"Handshake OK — begin Q&A", "note":True},
        # Q1
        {"frm":1,"to":2,"label":"synthesize_speech( Q1 )"},
        {"frm":2,"to":1,"label":"← MP3 audio bytes", "ret":True},
        {"frm":1,"to":0,"label":"{question} + {tts_audio}"},
        {"frm":0,"to":0,"label":"plays audio, records answer","note":True},
        {"frm":0,"to":1,"label":"{tts_done}"},
        {"frm":1,"to":0,"label":"{start_listening}"},
        {"frm":0,"to":1,"label":"[binary PCM chunks…]"},
        {"frm":1,"to":3,"label":"stream PCM → Transcribe"},
        {"frm":3,"to":1,"label":"← partial transcript", "ret":True},
        {"frm":1,"to":0,"label":"{transcript is_final:false}"},
        {"frm":3,"to":1,"label":"← FINAL transcript", "ret":True},
        {"frm":0,"to":1,"label":"{audio_end}"},
        {"frm":1,"to":0,"label":"{transcript is_final:true}"},
        {"frm":1,"to":1,"label":"[repeat for Q2, Q3 …]", "note":True},
        # Photo
        {"frm":1,"to":0,"label":"{announce_photo} + {tts_audio}"},
        {"frm":1,"to":0,"label":"{countdown: 10 … 1}"},
        {"frm":1,"to":0,"label":"{capture_photo}"},
        {"frm":0,"to":0,"label":"CameraX takePicture()","note":True},
        {"frm":0,"to":1,"label":"{photo: base64 JPEG + GPS}"},
        {"frm":1,"to":1,"label":"save to D:\\fig\\<id>\\","note":True},
        {"frm":1,"to":0,"label":"{photo_ack}"},
        {"frm":1,"to":1,"label":"[repeat for each room photo]","note":True},
        # Done
        {"frm":1,"to":0,"label":"{session_done}"},
        {"frm":1,"to":4,"label":"analyze_all_images() [async]"},
        {"frm":4,"to":1,"label":"← JSON analyses", "ret":True},
        {"frm":1,"to":4,"label":"generate_credit_report()"},
        {"frm":4,"to":1,"label":"← PDF saved", "ret":True},
    ]
    f.append(SeqDiagram(parts_full, msgs_full, scale=0.88))
    f += caption("Figure 5.1 — Complete WebSocket session with Q&A, photos, and background report generation", s)
    f.append(PageBreak())

    # ── 5.2 TTS + STT Detail ─────────────────────────────────────────────────
    f += h2("5.2  Q&A Detail — AWS Polly TTS + AWS Transcribe STT", s)
    parts_qa = ["Android", "Server / Conductor", "AWS Polly", "AWS Transcribe"]
    msgs_qa  = [
        {"frm":1,"to":2,"label":"boto3 synthesize_speech(text, Kajal, en-IN, mp3)"},
        {"frm":2,"to":1,"label":"← AudioStream (MP3 bytes)", "ret":True},
        {"frm":1,"to":1,"label":"base64-encode MP3","note":True},
        {"frm":1,"to":0,"label":"{question, index, text}"},
        {"frm":1,"to":0,"label":"{tts_audio, format:'mp3', data:'<b64>'}"},
        {"frm":0,"to":0,"label":"AudioPlayer decodes → temp .mp3 → MediaPlayer.start()","note":True},
        {"frm":0,"to":0,"label":"MediaPlayer.onCompletion fires","note":True},
        {"frm":0,"to":1,"label":"{tts_done}"},
        {"frm":1,"to":0,"label":"{start_listening, question_index, timeout_ms:12000}"},
        {"frm":0,"to":0,"label":"AudioRecorder starts (16kHz PCM mono)","note":True},
        {"frm":0,"to":1,"label":"[binary frame: 3200 B / 100 ms chunk]"},
        {"frm":1,"to":3,"label":"stream.input_stream.send_audio_event(chunk)"},
        {"frm":3,"to":1,"label":"← TranscriptEvent (is_partial=True)", "ret":True},
        {"frm":1,"to":0,"label":"{transcript, is_final:false, text:'Jo…'}"},
        {"frm":0,"to":1,"label":"[more PCM chunks…]"},
        {"frm":0,"to":1,"label":"{audio_end}  (after timeout)"},
        {"frm":1,"to":3,"label":"stream.input_stream.end_stream()"},
        {"frm":3,"to":1,"label":"← TranscriptEvent (is_partial=False, final)", "ret":True},
        {"frm":1,"to":0,"label":"{transcript, is_final:true, text:'John Smith'}"},
    ]
    f.append(SeqDiagram(parts_qa, msgs_qa, scale=0.92))
    f += caption("Figure 5.2 — Single question: Polly TTS playback followed by Transcribe STT", s)
    f.append(PageBreak())

    # ── 5.3 Photo Capture ────────────────────────────────────────────────────
    f += h2("5.3  Photo Capture & Upload", s)
    parts_ph = ["Android", "Server / Conductor", "CameraX", "Storage"]
    msgs_ph  = [
        {"frm":1,"to":0,"label":"{announce_photo, prompt, is_selfie}"},
        {"frm":1,"to":0,"label":"{tts_audio}  (prompt spoken aloud)"},
        {"frm":0,"to":1,"label":"{tts_done}"},
        {"frm":1,"to":0,"label":"{countdown, value:10}"},
        {"frm":1,"to":0,"label":"{countdown, value:9}"},
        {"frm":0,"to":0,"label":"... (1 s per tick displayed on screen)","note":True},
        {"frm":1,"to":0,"label":"{countdown, value:1}"},
        {"frm":1,"to":0,"label":"{capture_photo, is_selfie, photo_index}"},
        {"frm":0,"to":2,"label":"switch lens (front↔back if needed)"},
        {"frm":0,"to":2,"label":"imageCapture.takePicture(outputFileOptions)"},
        {"frm":2,"to":0,"label":"← onImageSaved(file)", "ret":True},
        {"frm":0,"to":0,"label":"GPS captured via FusedLocationProvider","note":True},
        {"frm":0,"to":0,"label":"Base64-encode JPEG file","note":True},
        {"frm":0,"to":1,"label":"{photo, filename, data:<b64>, geo:{lat,lon,ts}}"},
        {"frm":1,"to":3,"label":"base64.b64decode → save_file(session_id, filename)"},
        {"frm":3,"to":1,"label":"← file saved", "ret":True},
        {"frm":1,"to":0,"label":"{photo_ack, photo_index}"},
    ]
    f.append(SeqDiagram(parts_ph, msgs_ph, scale=0.92))
    f += caption("Figure 5.3 — Photo capture: countdown → CameraX → GPS tagging → server save", s)
    f.append(PageBreak())

    # ── 5.4 Report Pipeline ───────────────────────────────────────────────────
    f += h2("5.4  Post-Session Report Generation Pipeline", s)
    parts_rp = ["Conductor", "Geo Service", "OpenAI GPT-4o", "ReportLab", "reports/"]
    msgs_rp  = [
        {"frm":0,"to":0,"label":"session_done sent to Android; WS closes","note":True},
        {"frm":0,"to":0,"label":"asyncio.create_task(_generate_report(…))","note":True},
        {"frm":0,"to":1,"label":"collect_geo_points(session_meta)"},
        {"frm":1,"to":1,"label":"haversine centroid; check each point","note":True},
        {"frm":1,"to":0,"label":"← geo_result {verified, max_dist, details}", "ret":True},
        {"frm":0,"to":2,"label":"analyze_all_images([photo_entries]) [concurrent]"},
        {"frm":2,"to":2,"label":"GPT-4o vision: scene, condition, credit score","note":True},
        {"frm":2,"to":0,"label":"← [{analysis, score} × N images]", "ret":True},
        {"frm":0,"to":3,"label":"generate_credit_report(meta, geo, analyses)"},
        {"frm":3,"to":3,"label":"build cover, Q&A table, geo table, photo panels","note":True},
        {"frm":3,"to":3,"label":"embed photo thumbnails, add recommendation","note":True},
        {"frm":3,"to":4,"label":"doc.build() → fi_report_<id>_<ts>.pdf"},
        {"frm":4,"to":0,"label":"← pdf_path", "ret":True},
        {"frm":0,"to":0,"label":"logger.info('PDF ready: …')","note":True},
    ]
    f.append(SeqDiagram(parts_rp, msgs_rp, scale=0.95))
    f += caption("Figure 5.4 — Background report pipeline: geo verification, GPT-4o analysis, PDF build", s)
    f.append(PageBreak())
    return f


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 6 — AWS SERVICES
# ═══════════════════════════════════════════════════════════════════════════════

def sec6(s):
    f = []
    f += chapter("6.  AWS Services Integration", s)

    f += h2("6.1  AWS Polly — Text-to-Speech", s)
    f += kv_table([
        ("Voice ID",      "Kajal (Neural, Female, Indian English)"),
        ("Language Code", "en-IN"),
        ("Engine",        "neural"),
        ("Output Format", "mp3"),
        ("Invocation",    "boto3 client: polly.synthesize_speech(…)"),
        ("Called by",     "PollyService.synthesize() → async_synthesize() in services/aws_service.py"),
        ("Fallback",      "If Polly fails, question is sent as text only; TTS skipped gracefully"),
    ], s)
    f += sp(8)

    f += h2("6.2  AWS Transcribe Streaming — Speech-to-Text", s)
    f += kv_table([
        ("Language Code",  "en-IN (Indian English)"),
        ("Media Encoding", "pcm"),
        ("Sample Rate",    "16 000 Hz"),
        ("SDK Package",    "amazon-transcribe  (pip install amazon-transcribe)"),
        ("Invocation",     "client.start_stream_transcription(…) then send_audio_event per chunk"),
        ("Called by",      "TranscribeService.transcribe_stream() in services/aws_service.py"),
        ("Partial results","Sent to Android in real time as {type:'transcript', is_final:false}"),
        ("Final result",   "Assembled from all non-partial TranscriptEvent segments"),
    ], s)
    f += sp(8)

    f += h2("6.3  Required IAM Permissions", s)
    f += body("Create an IAM user or role with the following minimum policy:", s)
    f += sp(4)
    f += code_block("""{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "polly:SynthesizeSpeech",
        "transcribe:StartStreamTranscription"
      ],
      "Resource": "*"
    }
  ]
}""", s)
    f += sp(4)
    f += body("Credentials are provided via environment variables "
              "FI_AWS_ACCESS_KEY_ID and FI_AWS_SECRET_ACCESS_KEY, or via "
              "an EC2 instance role / ECS task role (recommended for production).", s)
    f.append(PageBreak())
    return f


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 7 — STORAGE ARCHITECTURE
# ═══════════════════════════════════════════════════════════════════════════════

def sec7(s):
    f = []
    f += chapter("7.  Storage Architecture", s)

    f += h2("7.1  Android Local Storage", s)
    f += code_block("""
/data/data/com.ficx.app/files/           ← getFilesDir()
└── fi_sessions/
    └── session_<epoch_ms>/
        ├── photo_20260503_102345_001.jpg  ← front camera (selfie)
        ├── photo_20260503_102410_002.jpg  ← hall
        ├── photo_20260503_102445_003.jpg  ← kitchen
        ├── photo_20260503_102520_004.jpg  ← bedroom
        ├── photo_20260503_102555_005.jpg  ← outside
        └── recording_session_<id>_<ts>.aac  ← full session audio

/data/data/com.ficx.app/cache/           ← getCacheDir()
└── tts_<timestamp>.mp3                  ← temporary, deleted after playback
""", s)
    f += sp(8)

    f += h2("7.2  Server Session Storage", s)
    f += code_block("""
D:\\fig\\                                  ← FI_STORAGE_ROOT (configurable)
└── session_<epoch_ms>\\
    ├── photo_20260503_102345_001.jpg     ← received via WebSocket binary
    ├── photo_20260503_102410_002.jpg
    ├── photo_20260503_102445_003.jpg
    ├── photo_20260503_102520_004.jpg
    ├── photo_20260503_102555_005.jpg
    ├── recording_session_<id>_<ts>.aac  ← uploaded via REST (optional)
    └── metadata.json                    ← session Q&A, photo meta, timestamps
""", s)
    f += sp(4)
    f += body("metadata.json schema:", s)
    f += code_block("""{
  "session_id": "session_1746291234567",
  "device_id":  "a1b2c3d4e5f6",
  "started_at": "2026-05-03T10:20:00Z",
  "ended_at":   "2026-05-03T10:28:45Z",
  "questions": [
    { "question": "What is your name?",
      "answer":   "Ramesh Kumar",
      "geo":      { "latitude": 19.0760, "longitude": 72.8777, "timestamp": "…" } }
  ],
  "photos": [
    { "prompt": "I am taking your photo now…",
      "filename": "photo_20260503_102345_001.jpg",
      "geo": { "latitude": 19.0761, "longitude": 72.8778, "timestamp": "…" } }
  ],
  "recording_filename": null
}""", s)
    f += sp(8)

    f += h2("7.3  Reports Directory", s)
    f += code_block("""
server/                                  ← working directory when uvicorn runs
└── reports/                             ← created automatically on first use
    └── session_<epoch_ms>/
        └── fi_report_session_<id>_20260503_102900.pdf
""", s)
    f += sp(8)

    f += h2("7.4  File Naming Conventions", s)
    fn_rows = [
        ["File",              "Pattern",                        "Notes"],
        ["Photo (Android)",   "photo_<yyyyMMdd_HHmmss_SSS>.jpg","SimpleDateFormat timestamp"],
        ["Photo (Server)",    "Same as received from Android",  "Preserved as-is"],
        ["Session recording", "recording_<session_id>_<yyyyMMdd_HHmmss>.aac", "AAC 128 kbps, 44.1 kHz"],
        ["Session metadata",  "metadata.json",                  "One per session folder"],
        ["Credit report PDF", "fi_report_<session_id>_<yyyyMMdd_HHmmss>.pdf", "UTC timestamp"],
    ]
    cw = [3.5*cm, 5.5*cm, PAGE_W - 2*MARGIN - 9*cm]
    f += col_table(fn_rows[0], fn_rows[1:], s, col_widths=cw)
    f.append(PageBreak())
    return f


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 8 — REPORT GENERATION PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════

def sec8(s):
    f = []
    f += chapter("8.  Report Generation Pipeline", s)

    f += h2("8.1  Geo-Verification Logic", s)
    f += body(
        "After the session ends the server collects every GPS coordinate captured during the "
        "session — one per Q&A answer and one per photo. All points must lie within the "
        "configured radius (default 500 m) of the geographic centroid to be considered "
        "co-located.", s
    )
    f += sp(4)
    f += code_block("""Algorithm (services/geo_service.py)
─────────────────────────────────────
1. collect_geo_points(meta)
   Yields all GeoPoint objects from meta.questions[].geo
                     and from meta.photos[].geo

2. centroid = mean(latitudes), mean(longitudes)

3. For each point P:
   d = haversine(centroid, P)           # in metres
   if d > geo_radius_meters → OUTLIER

4. verified = (outliers == [])

Haversine formula:
  R = 6 371 000 m
  Δφ = lat2 - lat1  (radians)
  Δλ = lon2 - lon1  (radians)
  a = sin²(Δφ/2) + cos(φ1)·cos(φ2)·sin²(Δλ/2)
  d = R · 2 · atan2(√a, √(1−a))""", s)
    f += sp(8)

    f += h2("8.2  OpenAI Image Analysis", s)
    f += kv_table([
        ("Model",       "gpt-4o (configurable via FI_OPENAI_MODEL)"),
        ("Detail level","low  (faster, lower cost; sufficient for property assessment)"),
        ("Concurrency", "asyncio.gather — all photos analysed in parallel"),
        ("System prompt","Experienced FI officer conducting home-visit credit verification"),
        ("User prompt", "Structured template requesting: Scene Type, Condition, Key Observations, "
                        "Credit Indicators (positive / concerns), Assessment Score 1–10"),
        ("Max tokens",  "450 per image"),
        ("Fallback",    "Analysis text set to '⚠ Analysis skipped' if key not configured or API fails"),
    ], s)
    f += sp(8)

    f += h2("8.3  PDF Report Structure  (services/report_service.py)", s)
    rpt_rows = [
        ["Section",         "Content"],
        ["Cover header",    "FI Agent logo area, session ID, device ID, start/end times, report date"],
        ["1. Customer Details", "Q&A answers displayed as key-value pairs; keywords matched to "
                                "Full Name, DOB, Address"],
        ["2. Location Verification", "Status badge (VERIFIED / FAILED), centroid co-ordinates, "
                                     "per-point table with distance and colour-coded pass/fail"],
        ["3. Image Analysis", "One panel per photo: thumbnail (6.5 cm wide) beside GPT-4o analysis text; "
                              "condition, observations, credit indicators, score"],
        ["4. Credit Assessment", "Summary table: customer info, geo status, photo count, AI model used, "
                                 "Recommendation (RECOMMEND / FURTHER VERIFICATION REQUIRED)"],
        ["Footer",          "Page number, generated timestamp, confidentiality notice"],
    ]
    cw2 = [4*cm, PAGE_W - 2*MARGIN - 4*cm]
    f += col_table(rpt_rows[0], rpt_rows[1:], s, col_widths=cw2)
    f.append(PageBreak())
    return f


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 9 — CONFIGURATION REFERENCE
# ═══════════════════════════════════════════════════════════════════════════════

def sec9(s):
    f = []
    f += chapter("9.  Configuration Reference", s)

    f += h2("9.1  Server — .env Variables", s)
    f += body("All variables are prefixed FI_ and read by pydantic-settings at startup.", s)
    f += sp(4)
    env_rows = [
        ["Variable",                  "Default",          "Purpose"],
        ["FI_STORAGE_ROOT",           "D:\\\\fig",         "Root folder for session files"],
        ["FI_HOST",                   "0.0.0.0",          "Uvicorn bind host"],
        ["FI_PORT",                   "8000",             "Uvicorn bind port"],
        ["FI_AWS_REGION",             "us-east-1",        "AWS region for Polly + Transcribe"],
        ["FI_AWS_ACCESS_KEY_ID",      "(empty)",          "AWS credentials (or use instance role)"],
        ["FI_AWS_SECRET_ACCESS_KEY",  "(empty)",          "AWS credentials"],
        ["FI_POLLY_VOICE_ID",         "Kajal",            "Polly voice (Kajal = Neural en-IN)"],
        ["FI_TRANSCRIBE_LANGUAGE_CODE","en-IN",           "Transcribe language code"],
        ["FI_OPENAI_API_KEY",         "(empty)",          "OpenAI API key for image analysis"],
        ["FI_OPENAI_MODEL",           "gpt-4o",           "OpenAI model (gpt-4o or gpt-4o-mini)"],
        ["FI_GEO_RADIUS_METERS",      "500",              "Max distance from centroid for geo-verify"],
        ["FI_COUNTDOWN_SECONDS",      "10",               "Seconds of countdown before each photo"],
        ["FI_LISTEN_TIMEOUT_MS",      "12000",            "Max STT recording duration per question"],
        ["FI_SELF_PHOTO_PROMPT",      "See config.py",    "TTS text before selfie countdown"],
        ["FI_FI_QUESTIONS_JSON",      "3 defaults",       "JSON array of question strings"],
        ["FI_FI_PHOTO_PROMPTS_JSON",  "4 room defaults",  "JSON array of photo prompt strings"],
    ]
    cw = [5*cm, 3*cm, PAGE_W - 2*MARGIN - 8*cm]
    f += col_table(env_rows[0], env_rows[1:], s, col_widths=cw)
    f += sp(4)
    f += body("Example .env file:", s)
    f += code_block("""FI_STORAGE_ROOT=D:\\fig
FI_AWS_REGION=ap-south-1
FI_AWS_ACCESS_KEY_ID=AKIA...
FI_AWS_SECRET_ACCESS_KEY=wJalrX...
FI_OPENAI_API_KEY=sk-proj-...
FI_GEO_RADIUS_METERS=300
FI_POLLY_VOICE_ID=Kajal
FI_TRANSCRIBE_LANGUAGE_CODE=en-IN
FI_FI_QUESTIONS_JSON=["What is your name?","What is your date of birth?","What is your address?"]""", s)
    f += sp(8)

    f += h2("9.2  Android — FiConfig  (config/FiConfig.kt)", s)
    f += body("Edit FiConfig.kt to change Android-side settings. "
              "The server URL must point to the machine running the FastAPI server.", s)
    f += sp(4)
    f += code_block("""data class FiConfig(
    val serverUrl          : String = "http://192.168.1.100:8000",
    val questions          : List<String> = listOf(…),  // overridden by server
    val selfPhotoPrompt    : String = "…",              // for local reference
    val photoPrompts       : List<String> = listOf(…),  // for local reference
    val countdownSeconds   : Int    = 10,
    val sttTimeoutMs       : Long   = 10_000L,
    val uploadTimeoutSec   : Long   = 120L
)""", s)
    f += sp(4)
    f += body("Note: questions and photo prompts are actually driven by the server. "
              "The FiConfig values are used only if the app falls back to offline (REST) mode.", s)
    f.append(PageBreak())
    return f


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 10 — DEPLOYMENT GUIDE
# ═══════════════════════════════════════════════════════════════════════════════

def sec10(s):
    f = []
    f += chapter("10.  Deployment Guide", s)

    f += h2("10.1  Server Setup", s)
    f += code_block("""# 1. Create and activate virtualenv
python -m venv .venv
.venv\\Scripts\\activate          # Windows
source .venv/bin/activate          # Linux / macOS

# 2. Install dependencies
cd server
pip install -r requirements.txt

# 3. Configure environment
copy .env.example .env             # then edit .env with keys

# 4. Ensure storage root exists  (or set FI_STORAGE_ROOT)
mkdir D:\\fig

# 5. Start server
python main.py
#   or for production:
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4""", s)
    f += sp(4)

    f += h2("10.2  Android Build", s)
    f += bullets([
        "Open android/ in Android Studio (Hedgehog 2023.1.1 or later)",
        "Update serverUrl in FiConfig.kt to the server's LAN IP address",
        "Build → Generate Signed APK  (or Run on connected device in debug)",
        "Minimum SDK: API 26 (Android 8.0); Target SDK: 34",
        "Ensure the Android device and server are on the same LAN / VPN",
        "Grant all permissions when prompted on first launch",
    ], s)
    f += sp(8)

    f += h2("10.3  Testing Checklist", s)
    test_rows = [
        ["#",  "Test",                                   "Expected Result"],
        ["1",  "GET /health",                            "200 OK with config summary"],
        ["2",  "WS connect to /ws/fi-session/test123",   "Connection accepted; server waits for {ready}"],
        ["3",  "Send {ready}",                           "Server sends {question, tts_audio} for Q1"],
        ["4",  "Send {tts_done}",                        "Server sends {start_listening}"],
        ["5",  "Stream 5 s of PCM then {audio_end}",     "Server sends {transcript, is_final:true}"],
        ["6",  "Complete all questions",                 "Server advances to photo phase"],
        ["7",  "Send {photo} with base64 JPEG + GPS",    "Server saves file; sends {photo_ack}"],
        ["8",  "Send all photos then session completes", "Server sends {session_done}"],
        ["9",  "Wait 30–60 s after session",             "PDF appears in server/reports/<id>/"],
        ["10", "Open PDF",                               "Customer details, geo table, image analysis visible"],
        ["11", "Geo outlier test (fake GPS far away)",   "Geo section shows FAILED with outlier name"],
        ["12", "Polly disabled (wrong key)",             "Session continues; audio not played"],
        ["13", "OpenAI disabled (empty key)",            "Report generated with '⚠ Analysis skipped' text"],
    ]
    cw = [0.8*cm, 6*cm, PAGE_W - 2*MARGIN - 6.8*cm]
    f += col_table(test_rows[0], test_rows[1:], s, col_widths=cw)
    f += sp(10)
    f += hr()
    f += sp(4)
    f += body(
        "For issues or contributions, review the log output at INFO level. "
        "All server log lines are prefixed with the originating component in brackets: "
        "[Polly], [Transcribe], [Conductor], [Geo], [OpenAI], [Report]. "
        "Android logs are prefixed FiAgent/<component> and visible in Android Studio Logcat.", s
    )
    return f


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Building documentation -> {OUTPUT}")

    doc = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=1.5 * cm, bottomMargin=2 * cm,
        title="FI Agent System Documentation",
        author="FI Agent Team",
        subject="Technical Architecture & Flow",
    )

    s = _styles()
    story = []
    story += cover(s)
    story += toc(s)
    story += sec1(s)
    story += sec2(s)
    story += sec3(s)
    story += sec4(s)
    story += sec5(s)
    story += sec6(s)
    story += sec7(s)
    story += sec8(s)
    story += sec9(s)
    story += sec10(s)

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    size_kb = OUTPUT.stat().st_size / 1024
    print(f"Done. {OUTPUT}  ({size_kb:.0f} KB)")


if __name__ == "__main__":
    main()
