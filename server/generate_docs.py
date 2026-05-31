"""
Generates two architecture / design documents as professional PDFs:
  1. docs/customer_flow.pdf   — Customer journey, system architecture, data capture
  2. docs/auditor_portal.pdf  — Auditor portal, case review workflow, report structure

Run:  python generate_docs.py
"""

import os
from pathlib import Path
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Polygon
from reportlab.graphics import renderPDF
from reportlab.platypus import Flowable

# ── Palette ───────────────────────────────────────────────────────────────────
BLUE    = colors.HexColor("#0D47A1")
L_BLUE  = colors.HexColor("#1565C0")
GOLD    = colors.HexColor("#F9A825")
WHITE   = colors.white
BLACK   = colors.black
L_GREY  = colors.HexColor("#F0F4FF")
M_GREY  = colors.HexColor("#555555")
B_GREY  = colors.HexColor("#CCCCCC")
GREEN   = colors.HexColor("#2E7D32")
RED     = colors.HexColor("#C62828")

PAGE_W, PAGE_H = A4
MARGIN    = 1.8 * cm
CONTENT_W = PAGE_W - 2 * MARGIN


# ── Style helpers ─────────────────────────────────────────────────────────────

def _styles():
    base = getSampleStyleSheet()
    def ps(name, **kw):
        return ParagraphStyle(name, parent=base["Normal"], **kw)
    return {
        "doc_title":  ps("dt",  fontSize=26, fontName="Helvetica-Bold",
                          textColor=WHITE, alignment=TA_CENTER, leading=32),
        "doc_sub":    ps("ds",  fontSize=13, fontName="Helvetica",
                          textColor=colors.HexColor("#BBDEFB"), alignment=TA_CENTER),
        "sec_hdr":    ps("sh",  fontSize=13, fontName="Helvetica-Bold",
                          textColor=WHITE),
        "h2":         ps("h2",  fontSize=12, fontName="Helvetica-Bold",
                          textColor=BLUE, spaceBefore=6),
        "body":       ps("bd",  fontSize=10, fontName="Helvetica",
                          textColor=colors.HexColor("#222222"), leading=15),
        "bullet":     ps("bl",  fontSize=10, fontName="Helvetica",
                          textColor=colors.HexColor("#222222"), leftIndent=12, leading=14),
        "small":      ps("sm",  fontSize=8,  fontName="Helvetica",
                          textColor=M_GREY),
        "code":       ps("co",  fontSize=8,  fontName="Courier",
                          textColor=colors.HexColor("#222222"), leading=12,
                          backColor=L_GREY, leftIndent=8),
        "label":      ps("lb",  fontSize=9,  fontName="Helvetica-Bold",
                          textColor=BLUE),
    }


def _sec_header(text, s):
    tbl = Table([[Paragraph(f"  {text}", s["sec_hdr"])]], colWidths=[CONTENT_W])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), BLUE),
        ("TOPPADDING",    (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return [Spacer(1, 10), tbl, Spacer(1, 6)]


def _kv(rows, s, lw=5.0*cm):
    data = [[Paragraph(str(k), s["label"]), Paragraph(str(v), s["body"])]
            for k, v in rows]
    tbl = Table(data, colWidths=[lw, CONTENT_W - lw])
    tbl.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [WHITE, L_GREY]),
        ("GRID",           (0, 0), (-1, -1), 0.4, B_GREY),
        ("TOPPADDING",     (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 4),
        ("LEFTPADDING",    (0, 0), (-1, -1), 7),
        ("VALIGN",         (0, 0), (-1, -1), "TOP"),
    ]))
    return tbl


def _box(title, items, s, bullet_char="•"):
    paras = [Paragraph(f"  {bullet_char}  {item}", s["bullet"]) for item in items]
    inner = Table([[paras]], colWidths=[CONTENT_W])
    inner.setStyle(TableStyle([
        ("BOX",           (0, 0), (-1, -1), 0.5, B_GREY),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
    ]))
    return [Paragraph(title, s["h2"]), Spacer(1, 4), inner, Spacer(1, 8)]


# ── Flow diagram helper ───────────────────────────────────────────────────────

class FlowDiagram(Flowable):
    """Renders a horizontal or vertical step flow diagram using ReportLab shapes."""

    def __init__(self, steps, width=None, orientation="horizontal"):
        super().__init__()
        self._steps = steps
        self._w = width or CONTENT_W
        self._orientation = orientation
        BOX_H = 40
        ARROW = 20
        if orientation == "horizontal":
            n = len(steps)
            box_w = (self._w - ARROW * (n - 1)) / n
            self._bw, self._bh = box_w, BOX_H
            self.width  = self._w
            self.height = BOX_H + 30
        else:
            self._bw, self._bh = self._w * 0.6, 36
            self.width  = self._w
            self.height = len(steps) * (36 + 24) + 10

    def draw(self):
        steps = self._steps
        n     = len(steps)
        c     = self.canv

        if self._orientation == "horizontal":
            ARROW_W = 20
            bw      = (self._w - ARROW_W * (n - 1)) / n
            bh      = self._bh
            y_top   = self.height - 10

            for idx, (label, colour) in enumerate(steps):
                x = idx * (bw + ARROW_W)
                # Box
                c.setFillColor(colour)
                c.setStrokeColor(WHITE)
                c.roundRect(x, y_top - bh, bw, bh, 4, fill=1, stroke=0)
                # Label
                c.setFillColor(WHITE)
                c.setFont("Helvetica-Bold", 8)
                c.drawCentredString(x + bw / 2, y_top - bh / 2 - 4, label)
                # Arrow
                if idx < n - 1:
                    ax = x + bw + 2
                    ay = y_top - bh / 2
                    c.setFillColor(colors.HexColor("#555555"))
                    c.setStrokeColor(colors.HexColor("#555555"))
                    c.setLineWidth(1.5)
                    c.line(ax, ay, ax + ARROW_W - 8, ay)
                    # Arrowhead
                    c.setFillColor(colors.HexColor("#555555"))
                    pts = [ax + ARROW_W - 8, ay + 4,
                           ax + ARROW_W - 8, ay - 4,
                           ax + ARROW_W - 1, ay]
                    p = c.beginPath()
                    p.moveTo(pts[0], pts[1])
                    p.lineTo(pts[2], pts[3])
                    p.lineTo(pts[4], pts[5])
                    p.close()
                    c.drawPath(p, fill=1, stroke=0)
        else:
            bw = self._bw
            bh = self._bh
            x0 = (self._w - bw) / 2
            for idx, (label, colour) in enumerate(steps):
                y = self.height - 10 - idx * (bh + 24)
                c.setFillColor(colour)
                c.roundRect(x0, y - bh, bw, bh, 4, fill=1, stroke=0)
                c.setFillColor(WHITE)
                c.setFont("Helvetica-Bold", 9)
                c.drawCentredString(x0 + bw / 2, y - bh / 2 - 4, label)
                if idx < len(steps) - 1:
                    ax = x0 + bw / 2
                    ay = y - bh - 2
                    c.setStrokeColor(M_GREY)
                    c.setFillColor(M_GREY)
                    c.setLineWidth(1.5)
                    c.line(ax, ay, ax, ay - 14)
                    pts = [ax - 5, ay - 14, ax + 5, ay - 14, ax, ay - 22]
                    p = c.beginPath()
                    p.moveTo(pts[0], pts[1])
                    p.lineTo(pts[2], pts[3])
                    p.lineTo(pts[4], pts[5])
                    p.close()
                    c.drawPath(p, fill=1, stroke=0)


# ── Page template ─────────────────────────────────────────────────────────────

def _make_page(title, doc_type, gen_ts):
    def _draw(canvas, doc):
        w = PAGE_W
        # Header stripe
        canvas.setFillColor(BLUE)
        canvas.rect(0, PAGE_H - 30, w, 30, fill=1, stroke=0)
        canvas.setFillColor(WHITE)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(MARGIN, PAGE_H - 20, f"ABC Bank FI Agent  —  {title}")
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(w - MARGIN, PAGE_H - 20, f"CONFIDENTIAL  |  {doc_type}")
        # Footer
        canvas.setFillColor(M_GREY)
        canvas.setFont("Helvetica", 7.5)
        canvas.drawString(MARGIN, 0.7*cm, f"Generated: {gen_ts}  |  For internal use only")
        canvas.drawRightString(w - MARGIN, 0.7*cm, f"Page {doc.page}")
        canvas.setStrokeColor(B_GREY)
        canvas.setLineWidth(0.4)
        canvas.line(MARGIN, 1.0*cm, w - MARGIN, 1.0*cm)
    return _draw


# ══════════════════════════════════════════════════════════════════════════════
#  DOCUMENT 1: CUSTOMER FLOW
# ══════════════════════════════════════════════════════════════════════════════

def build_customer_doc(out_path: Path) -> None:
    s       = _styles()
    gen_ts  = datetime.now().strftime("%d %b %Y %H:%M")
    draw_pg = _make_page("Customer Flow & Architecture", "Customer Journey", gen_ts)

    doc = SimpleDocTemplate(
        str(out_path), pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=2.2*cm, bottomMargin=1.6*cm,
        title="ABC Bank FI Agent — Customer Flow",
        author="ABC Bank Technology",
    )

    story = []

    # ── Cover ─────────────────────────────────────────────────────────────
    cover = Table(
        [[Paragraph("ABC BANK", s["doc_sub"])],
         [Paragraph("FI Agent — Personal Loan", s["doc_title"])],
         [Spacer(1, 6)],
         [Paragraph("Customer Journey · System Architecture · Data Capture Guide", s["doc_sub"])],
         [Spacer(1, 4)],
         [Paragraph(f"Prepared: {gen_ts}", ParagraphStyle('c', parent=s["doc_sub"], fontSize=10))]],
        colWidths=[CONTENT_W],
    )
    cover.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), BLUE),
        ("TOPPADDING",    (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
    ]))
    story += [Spacer(1, 0.4*cm), cover, Spacer(1, 14)]
    story += [HRFlowable(width="100%", thickness=2, color=GOLD), Spacer(1, 10)]

    # ── 1. Purpose ────────────────────────────────────────────────────────
    story += _sec_header("1.  Purpose & Scope", s)
    story.append(_kv([
        ("System",    "ABC Bank Field Investigation (FI) Agent — Personal Loan origination"),
        ("Purpose",   "Automate identity verification, property documentation, and income assessment "
                      "for personal loan applications via a mobile-friendly web interface"),
        ("Audience",  "Customer (loan applicant), Field Investigation Officer, Technology Team"),
        ("Version",   "2.0  |  " + gen_ts),
    ], s))

    # ── 2. High-level architecture ────────────────────────────────────────
    story += _sec_header("2.  System Architecture", s)
    story.append(Paragraph("Components", s["h2"]))
    comp_rows = [
        ("Web Frontend",   "Vite + TypeScript SPA served at /fi/ — handles camera, audio, geolocation, "
                           "photo capture, blur detection, bank statement upload, and session recording"),
        ("WebSocket Server", "FastAPI + Python — drives the entire FI session in real-time; "
                             "sends questions, TTS audio, photo prompts; receives answers and photo ACKs"),
        ("REST API",       "FastAPI — receives photos (immediate), bank statement PDF, and final submit "
                           "(metadata + WebM recording); triggers background report generation"),
        ("AWS Polly",      "Neural TTS (Kajal en-IN voice) — converts each question to MP3 audio "
                           "played on the applicant's device"),
        ("AWS Transcribe", "Streaming speech-to-text — applicant's spoken answers transcribed in "
                           "real-time over the WebSocket stream"),
        ("AWS Textract",   "OCR engine — extracts text from PAN card photo and home nameplate"),
        ("AWS Rekognition","Face match — compares selfie photo with PAN card face to verify identity"),
        ("OpenAI GPT-4o",  "Analyses property images and bank statement; produces "
                           "structured credit assessment"),
        ("Google Maps API","Reverse geocodes the session centroid to a human-readable address"),
        ("ReportLab",      "Generates the 10-section PDF credit report server-side"),
        ("Storage (disk)", "Case folder per session: photos, recording, metadata, analysis JSON, PDF"),
    ]
    story.append(_kv(comp_rows, s, lw=4.5*cm))

    # Architecture flow diagram
    story += [Spacer(1, 10), Paragraph("Request Flow (simplified)", s["h2"]), Spacer(1, 4)]
    arch_steps = [
        ("Browser\n(Customer)", BLUE),
        ("WebSocket\nServer", L_BLUE),
        ("AWS\nPolly/Transcribe", colors.HexColor("#1B5E20")),
        ("Storage\n(Disk)", colors.HexColor("#4A148C")),
        ("Report\nPipeline", colors.HexColor("#E65100")),
    ]
    story.append(FlowDiagram(arch_steps, width=CONTENT_W, orientation="horizontal"))

    # ── 3. Customer journey ───────────────────────────────────────────────
    story += _sec_header("3.  Customer Journey", s)
    story += [Spacer(1, 4)]
    journey_steps = [
        ("1 · Marketing",    BLUE),
        ("2 · Application",  L_BLUE),
        ("3 · Review",       colors.HexColor("#1B5E20")),
        ("4 · FI Session",   colors.HexColor("#4A148C")),
        ("5 · Submit",       GOLD),
        ("6 · Thank You",    GREEN),
    ]
    story.append(FlowDiagram(journey_steps, width=CONTENT_W, orientation="horizontal"))
    story.append(Spacer(1, 12))

    journey_detail = [
        ("Step 1 — Marketing Page",
         "/fi/  →  ABC Bank landing page with loan benefits, interest rates, and 'Apply Now' CTA"),
        ("Step 2 — Application Form",
         "Customer enters: First Name, Last Name, Date of Birth, Address, City, PAN Number, "
         "Mobile Number, Annual Income Range"),
        ("Step 3 — Review",
         "All form data shown in a summary table; customer confirms before starting the FI process"),
        ("Step 4 — FI Session",
         "Automated session: 3 verbal Q&A → selfie → 7 home photos (nameplate first) → PAN card → "
         "bank statement upload  |  Session recorded throughout as WebM video+audio"),
        ("Step 5 — Submit",
         "'Submit FI Report' button uploads session recording + metadata; background report generation starts"),
        ("Step 6 — Thank You",
         "Full-screen confirmation: case reference number + registered mobile number displayed; "
         "customer informed that ABC Bank will contact them on their mobile"),
    ]
    story.append(_kv(journey_detail, s, lw=5.5*cm))

    # ── 4. FI session detail ──────────────────────────────────────────────
    story += _sec_header("4.  FI Session — Detailed Flow", s)
    fi_steps = [
        ("Selfie",    BLUE),
        ("Nameplate", L_BLUE),
        ("Kitchen",   colors.HexColor("#1B5E20")),
        ("Bedrooms",  colors.HexColor("#1B5E20")),
        ("Hall",      colors.HexColor("#1B5E20")),
        ("Outside",   colors.HexColor("#1B5E20")),
        ("PAN Card",  colors.HexColor("#4A148C")),
        ("Bank Stmt", GOLD),
    ]
    story.append(Paragraph("Photo & Document Capture Sequence", s["h2"]))
    story.append(Spacer(1, 4))
    story.append(FlowDiagram(fi_steps, width=CONTENT_W, orientation="horizontal"))
    story.append(Spacer(1, 12))

    story += _box("Q&A Phase (3 questions, spoken & transcribed)", [
        "Q1: Please confirm your full name",
        "Q2: What is your residential PIN code?",
        "Q3: What is the name of your city?",
        "GPS coordinates captured at start of each answer",
        "Answer shown on screen for confirmation; Re-record option available",
        "Server retries if answer is empty or inaudible",
    ], s)

    story += _box("Photo Phase — per-photo flow", [
        "Server sends 'capture_photo' → countdown timer (5 sec configurable)",
        "Photo captured automatically from camera",
        "Blur detection (Laplacian variance): score < 40 → auto-retake (up to 2 times)",
        "Review screen: Save (5-second auto-save) or Discard (retake)",
        "Photo uploaded immediately to server via REST; GPS + blur score recorded",
        "PAN card: up to 3 OCR retries if text not readable",
    ], s)

    story += _box("Bank Statement Upload", [
        "Server requests PDF upload after all photos",
        "Customer taps 'Upload PDF' → OS file picker",
        "PDF uploaded via REST; server saves to session folder",
        "Skip option available (income section shown as INCOMPLETE in report)",
    ], s)

    # ── 5. Data captured ─────────────────────────────────────────────────
    story += _sec_header("5.  Data Captured Per Session", s)
    data_rows = [
        ("Application Form",      "First/Last Name, DOB, Address, City, PAN, Mobile, Income Range"),
        ("Q&A Answers",           "Text transcript + GPS coordinates (lat/lon/timestamp) per answer"),
        ("Photos (up to 9)",      "JPEG files + GPS + blur score + OCR text (nameplate/PAN)"),
        ("PAN Verification",      "Textract OCR (PAN no., name, father, DOB) + NSDL result + "
                                  "Rekognition face-match score vs selfie"),
        ("3-Way Name Match",      "Application form name  ↔  PAN OCR name  ↔  Nameplate OCR text"),
        ("Bank Statement",        "PDF file + GPT-4 income analysis JSON"),
        ("GPS Trail",             "All lat/lon readings — geo-verified (max spread ≤ 500m = PASS)"),
        ("Session Recording",     "WebM video+audio of the entire session (browser captureStream)"),
        ("Metadata JSON",         "session_data.json — denormalised single source of truth"),
    ]
    story.append(_kv(data_rows, s, lw=4.8*cm))

    # ── 6. WebSocket protocol ─────────────────────────────────────────────
    story += _sec_header("6.  WebSocket Message Protocol", s)
    story.append(Paragraph("Server → Client", s["h2"]))
    ws_s2c = [
        ("{type:'question', index, text}",         "Ask next interview question (TTS MP3 embedded)"),
        ("{type:'start_listening', timeout_ms}",   "Begin STT recording"),
        ("{type:'transcript', text, is_final}",    "Partial or final transcript"),
        ("{type:'announce_photo', prompt}",        "Announce upcoming photo"),
        ("{type:'countdown', value}",              "Tick-by-tick countdown (5…1)"),
        ("{type:'capture_photo', index}",          "Trigger camera capture"),
        ("{type:'pan_retry', attempt, message}",   "PAN OCR failed — retake requested"),
        ("{type:'request_document', prompt}",      "Request bank statement upload"),
        ("{type:'session_done', message}",         "All steps complete — show Submit button"),
    ]
    story.append(_kv(ws_s2c, s, lw=7.0*cm))
    story.append(Spacer(1, 8))
    story.append(Paragraph("Client → Server", s["h2"]))
    ws_c2s = [
        ("{type:'ready', session_id, basic_info}",       "Handshake after WS open"),
        ("Binary PCM frames",                            "16 kHz / 16-bit mono audio stream for Transcribe"),
        ("{type:'audio_end'}",                           "STT recording finished"),
        ("{type:'answer_confirm'} / {type:'answer_retry'}", "Confirm transcript or request re-record"),
        ("{type:'tts_done'}",                            "Device finished playing TTS audio"),
        ("{type:'photo_taken', filename}",               "Photo uploaded; acknowledge server"),
        ("{type:'document_ready', filename}",            "Bank statement uploaded"),
    ]
    story.append(_kv(ws_c2s, s, lw=7.0*cm))

    # ── 7. Report generation ──────────────────────────────────────────────
    story += _sec_header("7.  Post-Submission Report Generation", s)
    pipeline_steps = [
        ("Geo\nVerify", BLUE),
        ("Geocode\nAddress", L_BLUE),
        ("Nameplate\nOCR", colors.HexColor("#1B5E20")),
        ("PAN\nVerify", colors.HexColor("#4A148C")),
        ("Image\nAnalysis", colors.HexColor("#E65100")),
        ("Income\nAnalysis", GOLD),
        ("Credit\nAssessment", RED),
        ("PDF\nReport", GREEN),
    ]
    story.append(FlowDiagram(pipeline_steps, width=CONTENT_W, orientation="horizontal"))
    story.append(Spacer(1, 12))

    report_secs = [
        ("Sec 1 — Application Details",   "Basic info from form"),
        ("Sec 2 — Executive Summary",      "Session KPIs, risk preview"),
        ("Sec 3 — Field Interview",        "Q&A table with GPS per answer"),
        ("Sec 4 — Location Verification",  "GPS spread, geocoded address, PASS/FAIL"),
        ("Sec 5 — Home Evidence",          "Photos + analysis + blur + nameplate OCR"),
        ("Sec 6 — PAN Verification",       "OCR, 3-way name match, NSDL, face match"),
        ("Sec 7 — Income Analysis",        "Bank statement metrics + risk/positive flags"),
        ("Sec 8 — Credit Assessment",      "Score + grade + 4-pillar breakdown + conditions"),
        ("Sec 9 — Scoring & Risk",         "Rule-based cross-check score"),
        ("Sec 10 — Recommendations",       "Findings, final decision box, signature block"),
    ]
    story.append(_kv(report_secs, s, lw=5.5*cm))

    # ── Disclaimer ────────────────────────────────────────────────────────
    story += [Spacer(1, 16), HRFlowable(width="100%", thickness=0.5, color=B_GREY),
              Spacer(1, 6)]
    story.append(Paragraph(
        "This document is for internal technical reference only. "
        "ABC Bank  |  Technology & Digital Banking Division  |  CONFIDENTIAL",
        s["small"],
    ))

    doc.build(story, onFirstPage=draw_pg, onLaterPages=draw_pg)
    print(f"Created: {out_path}  ({out_path.stat().st_size//1024} KB)")


# ══════════════════════════════════════════════════════════════════════════════
#  DOCUMENT 2: AUDITOR PORTAL
# ══════════════════════════════════════════════════════════════════════════════

def build_auditor_doc(out_path: Path) -> None:
    s       = _styles()
    gen_ts  = datetime.now().strftime("%d %b %Y %H:%M")
    draw_pg = _make_page("Auditor Portal Guide", "Bank Employee Reference", gen_ts)

    doc = SimpleDocTemplate(
        str(out_path), pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=2.2*cm, bottomMargin=1.6*cm,
        title="ABC Bank FI Agent — Auditor Portal",
        author="ABC Bank Technology",
    )

    story = []

    # ── Cover ─────────────────────────────────────────────────────────────
    cover = Table(
        [[Paragraph("ABC BANK  —  BANK EMPLOYEE PORTAL", s["doc_sub"])],
         [Paragraph("FI Auditor Portal", s["doc_title"])],
         [Spacer(1, 6)],
         [Paragraph("Case Management · Review Workflow · Decision Guide", s["doc_sub"])],
         [Spacer(1, 4)],
         [Paragraph(f"Prepared: {gen_ts}  |  Login: test / test",
                    ParagraphStyle('c2', parent=s["doc_sub"], fontSize=10))]],
        colWidths=[CONTENT_W],
    )
    cover.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#1B5E20")),
        ("TOPPADDING",    (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
    ]))
    story += [Spacer(1, 0.4*cm), cover, Spacer(1, 14)]
    story += [HRFlowable(width="100%", thickness=2, color=GOLD), Spacer(1, 10)]

    # ── 1. Overview ───────────────────────────────────────────────────────
    story += _sec_header("1.  Purpose & Access", s)
    story.append(_kv([
        ("URL",          "http://<server>/auditor/"),
        ("Credentials",  "Username: test  |  Password: test  (bank employee access)"),
        ("Purpose",      "Review submitted FI cases, inspect all captured data, view the credit "
                         "assessment report, and record an Accept or Reject decision"),
        ("Access scope", "All submitted cases across all field officers"),
    ], s))

    # ── 2. Auditor flow ───────────────────────────────────────────────────
    story += _sec_header("2.  Auditor Workflow", s)
    story.append(Spacer(1, 4))
    aud_steps = [
        ("Login\n/auditor/",     colors.HexColor("#1B5E20")),
        ("Case List\nTable",     BLUE),
        ("Click\nCase ID",       L_BLUE),
        ("Review\nAll Sections", colors.HexColor("#4A148C")),
        ("Record\nDecision",     colors.HexColor("#E65100")),
    ]
    story.append(FlowDiagram(aud_steps, width=CONTENT_W, orientation="horizontal"))
    story.append(Spacer(1, 14))

    story.append(_kv([
        ("1. Login",          "Enter bank employee credentials. Session stored as a secure cookie (24 h TTL)"),
        ("2. Case List",      "Table showing: Date, Case ID (link), Customer Name, PAN Number, "
                              "Status (Complete / Incomplete), Decision (Pending / Accepted / Rejected), "
                              "Reviewed By (auditor name + timestamp), Download PDF"),
        ("3. Open Case",      "Click Case ID — opens in a new browser tab for side-by-side review"),
        ("4. Review Sections","Scroll through all 8 sections on a single page; "
                              "use the jump-nav bar at the top to skip to any section"),
        ("5. Decision",       "Enter optional notes in the notes field; "
                              "tap Accept or Reject in the sticky bottom bar"),
        ("6. Result",         "Decision saved to disk (decision.json); "
                              "Case List updated with auditor name + timestamp"),
    ], s))

    # ── 3. Case list page ─────────────────────────────────────────────────
    story += _sec_header("3.  Case List Page", s)
    story += _box("Table Columns", [
        "#  —  row number",
        "Date  —  session start date",
        "Case ID  —  unique identifier (clickable, opens detail in new tab)",
        "Customer Name  —  from application form or Q&A fallback",
        "PAN  —  masked PAN number from form",
        "Status  —  Complete (green) when answers + photos + report all present; Incomplete otherwise",
        "Decision  —  Pending (purple) | Accepted (blue) | Rejected (pink)",
        "Reviewed By  —  auditor username + decision timestamp",
        "Report  —  direct PDF download button",
    ], s)
    story += _box("Search & Refresh", [
        "Search box filters by Case ID or Customer Name in real time",
        "Refresh button (top right) reloads the case list from the server",
    ], s)

    # ── 4. Case detail page ───────────────────────────────────────────────
    story += _sec_header("4.  Case Detail Page", s)
    story.append(Paragraph("Layout", s["h2"]))
    layout_rows = [
        ("Sticky header",   "Case ID + customer name + session dates + Download PDF button (top right)"),
        ("Jump navigation", "8 anchor links for instant scroll to any section"),
        ("8 sections",      "All data rendered in one scrollable page — no tabs"),
        ("Sticky footer",   "Notes textarea + Accept / Reject buttons — always visible"),
    ]
    story.append(_kv(layout_rows, s, lw=4.5*cm))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Section Reference", s["h2"]))
    sec_rows = [
        ("Overview",           "Applicant details (form data) + session info + completeness checklist"),
        ("Field Interview",    "All Q&A answers with GPS coordinates; INCOMPLETE shown if answer missing"),
        ("Home Evidence",      "Photo grid with: tag, blur score, GPS, nameplate OCR, image analysis"),
        ("PAN Verification",   "OCR results, 3-way name match, NSDL status, face match similarity score"),
        ("Income Analysis",    "Bank statement metrics: income, expenses, savings, bounces, creditworthiness"),
        ("Location Report",    "GPS spread PASS/FAIL (500m threshold), geocoded address, per-point table"),
        ("Credit Assessment",  "Score (0-100), grade, recommendation, 4 pillar scores, loan eligibility"),
        ("Report PDF",         "Embedded PDF viewer + Download button"),
    ]
    story.append(_kv(sec_rows, s, lw=4.5*cm))

    # ── 5. Completeness indicators ────────────────────────────────────────
    story += _sec_header("5.  Completeness & Incomplete Indicators", s)
    story += _box("A case is marked Complete when ALL of these are present", [
        "At least one Q&A answer recorded",
        "At least one property photo captured",
        "PDF credit report generated",
    ], s, bullet_char="✓")
    story += _box("INCOMPLETE notices appear in the report and case detail when", [
        "Application form data not submitted",
        "Q&A answers missing or GPS not captured for an answer",
        "Home photos not captured",
        "PAN card not captured or OCR failed",
        "Bank statement not uploaded",
        "Credit analysis not performed (OpenAI key not configured)",
    ], s, bullet_char="⚠")

    # ── 6. Decision workflow ──────────────────────────────────────────────
    story += _sec_header("6.  Decision Recording", s)
    story += _box("Process", [
        "Review all 8 sections thoroughly, especially PAN verification and income analysis",
        "Enter any relevant notes in the notes field (optional, free text)",
        "Tap Accept to approve the case for further processing",
        "Tap Reject to decline the application",
        "Decision is saved immediately to disk with auditor name + timestamp",
        "The Case List page reflects the decision instantly on next refresh",
    ], s)
    story += _box("Decision Criteria Guidelines", [
        "ACCEPT:  Location verified (PASS) + PAN matched + income sufficient + no major risk flags",
        "REJECT:  Location FAIL (spread > 500m) OR PAN mismatch OR income inadequate OR "
                 "multiple bounced transactions",
        "INCOMPLETE cases should be escalated to the field officer before a decision is made",
    ], s)

    # ── 7. API reference ──────────────────────────────────────────────────
    story += _sec_header("7.  API Reference (Auditor Endpoints)", s)
    api_rows = [
        ("GET  /auditor/",                        "Login page (redirects to case list if authenticated)"),
        ("GET  /auditor/cases",                   "Case list page (authenticated)"),
        ("GET  /auditor/cases/{id}",              "Case detail page — opens in new tab"),
        ("POST /auditor/api/login",               "Authenticate  |  body: {username, password}"),
        ("GET  /auditor/api/cases",               "JSON list: all cases with summary fields"),
        ("GET  /auditor/api/cases/{id}",          "JSON full detail including session_data, photos, analyses"),
        ("POST /auditor/api/cases/{id}/decision", "Save decision  |  body: {decision, notes, auditor_name}"),
    ]
    story.append(_kv(api_rows, s, lw=5.5*cm))

    # ── 8. Case folder structure ──────────────────────────────────────────
    story += _sec_header("8.  Case Folder Structure on Disk", s)
    story.append(Paragraph(
        "All data is stored under the configured storage root (FI_STORAGE_ROOT).\n"
        "Each case folder is named {firstName}_{uuid8}.",
        s["body"],
    ))
    story.append(Spacer(1, 8))
    folder_rows = [
        ("metadata.json",           "Submitted session metadata — basic info, Q&A, photo list, documents"),
        ("session_data.json",       "Denormalised snapshot — all data in one JSON for auditor/reporting"),
        ("decision.json",           "Auditor decision: decision, notes, decided_by, decided_at"),
        ("selfie.jpg, hall.jpg …",  "Captured photos (JPEG)"),
        ("recording_*.webm",        "Full session video+audio recording (browser captureStream)"),
        ("statement.pdf",           "Applicant's bank statement"),
        ("responses/",              "Analysis outputs: geo_verification.json, pan_verification.json, "
                                    "nameplate_ocr.json, income_analysis.json, credit_analysis.json, "
                                    "photo_N_analysis.txt"),
        ("fi_report_*.pdf",         "Generated credit report (10-section PDF)"),
    ]
    story.append(_kv(folder_rows, s, lw=5.0*cm))

    # ── Disclaimer ────────────────────────────────────────────────────────
    story += [Spacer(1, 16), HRFlowable(width="100%", thickness=0.5, color=B_GREY),
              Spacer(1, 6)]
    story.append(Paragraph(
        "This document is for internal use by authorised bank employees only. "
        "ABC Bank  |  Credit & Risk Operations  |  CONFIDENTIAL",
        s["small"],
    ))

    doc.build(story, onFirstPage=draw_pg, onLaterPages=draw_pg)
    print(f"Created: {out_path}  ({out_path.stat().st_size//1024} KB)")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    docs_dir = Path(__file__).parent / "docs"
    docs_dir.mkdir(exist_ok=True)

    build_customer_doc(docs_dir / "customer_flow.pdf")
    build_auditor_doc(docs_dir  / "auditor_portal.pdf")
    print("Done.")
