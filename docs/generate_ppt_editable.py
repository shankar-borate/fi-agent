"""
Generate an editable PowerPoint with all 6 diagrams as native PPT shapes.
Every box, arrow and label is a separate shape — click and edit in PowerPoint.
Run: python generate_ppt_editable.py
"""
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_VERTICAL_ANCHOR
from pptx.oxml.ns import qn
from lxml import etree
import os

# ── Unit shortcuts ────────────────────────────────────────────────────────────
I = Inches
P = Pt

# ── Shape type constants ──────────────────────────────────────────────────────
RECT         = 1   # Rectangle
RRECT        = 5   # Rounded Rectangle
OVAL         = 9   # Oval / Circle
DIAMOND      = 4   # Diamond
CONN_STRAIGHT = 1  # Straight connector
CONN_ELBOW    = 2  # Elbow connector

# ── Colour palette ────────────────────────────────────────────────────────────
def rgb(h): return RGBColor(int(h[0:2],16), int(h[2:4],16), int(h[4:6],16))

C = dict(
    title   = rgb('1a237e'),
    white   = rgb('FFFFFF'),
    bg      = rgb('F8F9FA'),
    arrow   = rgb('546E7A'),
    text    = rgb('212121'),
    hint    = rgb('78909C'),
    mid     = rgb('37474F'),

    # Client (blue)
    c_bg = rgb('E3F2FD'), c_bd = rgb('1565C0'),
    # API / Server (green)
    s_bg = rgb('E8F5E9'), s_bd = rgb('2E7D32'),
    # Session (orange)
    o_bg = rgb('FFF3E0'), o_bd = rgb('E65100'),
    # AI engine (deep pink)
    a_bg = rgb('FCE4EC'), a_bd = rgb('880E4F'),
    # Report (teal)
    r_bg = rgb('E0F2F1'), r_bd = rgb('00695C'),
    # Storage (purple)
    p_bg = rgb('F3E5F5'), p_bd = rgb('6A1B9A'),
    # Decision (yellow)
    d_bg = rgb('FFF9C4'), d_bd = rgb('F9A825'),
    # Start/End (dark green)
    e_bg = rgb('1B5E20'), e_bd = rgb('1B5E20'),
    # Score green/orange/red
    score_g = rgb('4CAF50'), score_o = rgb('FF9800'), score_r = rgb('F44336'),
)

SLIDE_W = I(13.33)
SLIDE_H = I(7.5)

# ── Shape helpers ─────────────────────────────────────────────────────────────

def box(slide, x, y, w, h, fc, bc, lines=None, fsize=9.5, bold=False,
        shape=RRECT, align=PP_ALIGN.CENTER, tc=None, lw=1.5):
    """Add a shape with fill, border and optional text."""
    s = slide.shapes.add_shape(shape, x, y, w, h)
    s.fill.solid()
    s.fill.fore_color.rgb = fc
    s.line.color.rgb = bc
    s.line.width = P(lw)

    if lines:
        tf = s.text_frame
        tf.word_wrap = True
        try:
            tf.vertical_anchor = MSO_VERTICAL_ANCHOR.MIDDLE
        except Exception:
            pass
        tf.clear()
        for i, line in enumerate(lines if isinstance(lines, list) else [lines]):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = align
            r = p.add_run()
            r.text = line
            r.font.name  = 'Calibri'
            r.font.size  = P(fsize)
            r.font.bold  = bold if i == 0 else False
            r.font.color.rgb = tc if tc else C['text']
    return s


def txt(slide, x, y, w, h, text, fsize=9, col=None, bold=False,
        align=PP_ALIGN.CENTER):
    """Add a transparent text box."""
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = align
    r = p.add_run()
    r.text  = text
    r.font.name  = 'Calibri'
    r.font.size  = P(fsize)
    r.font.bold  = bold
    if col:
        r.font.color.rgb = col
    return tb


def conn(slide, x1, y1, x2, y2, col=None, arrow=True, lw=1.5, elbow=False):
    """Add a connector with optional arrowhead at destination."""
    col = col or C['arrow']
    ct  = CONN_ELBOW if elbow else CONN_STRAIGHT
    c   = slide.shapes.add_connector(ct, x1, y1, x2, y2)
    c.line.color.rgb = col
    c.line.width = P(lw)

    if arrow:
        sp_pr = c._element.find(qn('p:spPr'))
        if sp_pr is not None:
            ln_el = sp_pr.find(qn('a:ln'))
            if ln_el is None:
                ln_el = etree.SubElement(sp_pr, qn('a:ln'))
            for old in ln_el.findall(qn('a:tailEnd')):
                ln_el.remove(old)
            tail = etree.SubElement(ln_el, qn('a:tailEnd'))
            tail.set('type', 'arrow')
            tail.set('w', 'med')
            tail.set('len', 'med')
    return c


def divider_line(slide, y):
    """Thin horizontal divider line."""
    d = slide.shapes.add_shape(RECT, I(0.15), y, I(13.0), I(0.02))
    d.fill.solid(); d.fill.fore_color.rgb = C['title']
    d.line.fill.background()


def slide_header(prs, title, subtitle=''):
    """Create a new blank slide with a coloured title bar."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    bg = slide.background.fill
    bg.solid(); bg.fore_color.rgb = C['bg']

    # Title bar
    box(slide, I(0.15), I(0.07), I(13.0), I(0.56),
        C['title'], C['title'], lines=title,
        fsize=18, bold=True, tc=C['white'], lw=0)

    if subtitle:
        txt(slide, I(0.2), I(0.66), I(13.0), I(0.3),
            subtitle, fsize=9.5, col=C['mid'])

    divider_line(slide, I(1.0))
    return slide


# ── Slide 1: System Architecture ─────────────────────────────────────────────

def s_arch(prs):
    sl = slide_header(prs,
        'Figure 1 — System Architecture',
        'Six-layer architecture: Mobile Web App → FastAPI → Session Conductor → AI Engine → Report → Storage')

    # ── Row 1 boxes ───────────────────────────────────────────────────────────
    box(sl, I(0.2),  I(1.15), I(3.5), I(1.7), C['c_bg'], C['c_bd'],
        ['Borrower','Mobile Web App','','OTP  ·  Form','Camera  ·  Mic  ·  GPS'],
        fsize=9, bold=True, tc=C['c_bd'])

    box(sl, I(4.9),  I(1.15), I(3.5), I(1.7), C['s_bg'], C['s_bd'],
        ['FastAPI Server','(API Gateway)','','WebSocket /fi/ws/','REST /fi/api/'],
        fsize=9, bold=True, tc=C['s_bd'])

    box(sl, I(9.6),  I(1.15), I(3.5), I(1.7), C['o_bg'], C['o_bd'],
        ['Session Conductor','','Q&A  ·  Photo prompts','Countdown  ·  PAN OCR','Consent flow'],
        fsize=9, bold=True, tc=C['o_bd'])

    # Row 1 arrows
    conn(sl, I(3.7),  I(2.0),  I(4.9),  I(2.0))   # Client → API
    conn(sl, I(8.4),  I(2.0),  I(9.6),  I(2.0))   # API → Conductor

    # ── Row 2 boxes ───────────────────────────────────────────────────────────
    # AI Engine outer frame
    box(sl, I(0.2),  I(3.15), I(7.6), I(2.6), C['a_bg'], C['a_bd'],
        ['AI Analysis Engine'], fsize=11, bold=True, tc=C['a_bd'])

    # Sub-boxes inside AI
    ai_items = [
        ('GPT-4o Vision\nPhotos',   I(0.35)),
        ('PAN OCR\nTextract',       I(2.25)),
        ('Face Match\nRekognition', I(4.15)),
        ('STT / TTS\nTranscribe / Polly', I(6.05)),
    ]
    for label, lx in ai_items:
        box(sl, lx, I(3.7), I(1.7), I(1.7), C['white'], C['a_bd'],
            label.split('\n'), fsize=8, tc=C['a_bd'])

    box(sl, I(8.1),  I(3.15), I(2.3), I(2.6), C['r_bg'], C['r_bd'],
        ['Report','Generator','','CIBIL  ·  Credit Analysis','ReportLab PDF'],
        fsize=9, bold=True, tc=C['r_bd'])

    box(sl, I(10.7), I(3.15), I(2.45),I(2.6), C['p_bg'], C['p_bd'],
        ['Storage &','Auditor Portal','','JSON  ·  Photos','PDF Reports'],
        fsize=9, bold=True, tc=C['p_bd'])

    # Row 2 arrows
    conn(sl, I(6.7),  I(2.1),  I(3.8),  I(3.15), elbow=True)  # API → AI (down-left)
    conn(sl, I(7.8),  I(4.45), I(8.1),  I(4.45))               # AI → Report
    conn(sl, I(10.4), I(4.45), I(10.7), I(4.45))               # Report → Storage
    conn(sl, I(11.35),I(2.85), I(3.8),  I(3.15), elbow=True)   # Conductor → AI

    # Footer note
    txt(sl, I(0.2), I(6.0), I(13.0), I(0.4),
        'After session submit, the AI pipeline runs asynchronously — '
        'a failure in any step is logged and the remaining steps still execute.',
        fsize=8.5, col=C['hint'])


# ── Slide 2: Flowchart ────────────────────────────────────────────────────────

def s_flow(prs):
    sl = slide_header(prs,
        'Figure 2 — Application Flowchart',
        'Complete user journey: OTP Verification → Loan Form → FI Session → Q&A → Photos → Submit → Report')

    # Two-column layout to fit vertical flow
    # Column 1: Start → OTP → Form → Property → Review?
    # Column 2: Session → Q&A loop → Photos → PAN → Submit → End

    W, H = I(3.5), I(0.55)
    OW   = I(1.6)   # oval width
    DW   = I(3.0)   # diamond width

    # ── Column 1 (x centre = 3.4") ───────────────────────────────────────────
    cx1 = I(1.65)
    steps_l = [
        (I(1.2), I(1.15), OW,  I(0.45), OVAL,    C['e_bg'], C['e_bg'], ['Start'],           9, True,  C['white']),
        (I(0.2), I(1.75), W,   H,       RRECT,   C['c_bg'], C['c_bd'], ['Open Mobile Web App'], 9, False, C['c_bd']),
        (I(0.2), I(2.45), W,   H,       RRECT,   C['c_bg'], C['c_bd'], ['OTP Mobile Verification'], 9, False, C['c_bd']),
        (I(0.2), I(3.15), W,   H,       RRECT,   C['c_bg'], C['c_bd'], ['Fill Loan Application Form'], 9, False, C['c_bd']),
        (I(0.2), I(3.85), W,   H,       RRECT,   C['c_bg'], C['c_bd'], ['Property Info (Type · Bedrooms · Hall)'], 9, False, C['c_bd']),
        (I(0.35),I(4.6),  DW,  I(0.8),  DIAMOND, C['d_bg'], C['d_bd'], ['Review &', 'Confirm?'], 9, False, C['mid']),
    ]
    ys_l = []
    for x, y, w, h, sh, fc, bc, lines, fs, bold, tc in steps_l:
        box(sl, x, y, w, h, fc, bc, lines, fsize=fs, bold=bold, tc=tc, shape=sh)
        ys_l.append((x, y, w, h, sh))

    # Arrows column 1
    for i in range(len(ys_l)-1):
        _, y, _, h, _ = ys_l[i]
        x2,y2,_,_,sh2 = ys_l[i+1]
        cx = I(1.95)
        conn(sl, cx, y+h, cx, y2)

    # "No" back-arrow from diamond to form
    conn(sl, I(0.35), I(5.0), I(0.35), I(3.15), elbow=True, col=C['score_r'])
    txt(sl, I(0.02), I(4.15), I(0.5), I(0.4), 'No\n(Edit)', fsize=8, col=C['score_r'])

    # ── Column 2 (x centre = 9.7") ───────────────────────────────────────────
    cx2  = I(7.6)
    W2, H2 = I(4.2), I(0.55)
    steps_r = [
        (I(7.6), I(1.15), W2, H2,     RRECT,   C['s_bg'], C['s_bd'], ['Start FI Session (WebSocket + GPS)'],       9, False, C['s_bd']),
        (I(7.6), I(1.85), W2, H2,     RRECT,   C['s_bg'], C['s_bd'], ['Ask Question via Voice (AWS Transcribe)'],  9, False, C['s_bd']),
        (I(7.8), I(2.6),  I(3.8), I(0.75), DIAMOND, C['d_bg'], C['d_bd'], ['All Questions', 'Done?'],              9, False, C['mid']),
        (I(7.6), I(3.5),  W2, H2,     RRECT,   C['o_bg'], C['o_bd'], ['Guided Photo Capture (Signage→Hall→Kitchen→Bedrooms→Outside)'], 9, False, C['o_bd']),
        (I(7.6), I(4.2),  W2, H2,     RRECT,   C['o_bg'], C['o_bd'], ['PAN Card (GPT-4o OCR + Face Match)'],       9, False, C['o_bd']),
        (I(7.6), I(4.9),  W2, H2,     RRECT,   C['o_bg'], C['o_bd'], ['Bank Statement Consent'],                   9, False, C['o_bd']),
        (I(7.6), I(5.6),  W2, H2,     RRECT,   C['a_bg'], C['a_bd'], ['Submit Session'],                           9, False, C['a_bd']),
        (I(7.6), I(6.3),  W2, H2,     RRECT,   C['p_bg'], C['p_bd'], ['AI Pipeline + Report Generation'],          9, False, C['p_bd']),
        (I(8.7), I(7.1),  I(2.0), I(0.45), OVAL, C['e_bg'], C['e_bg'], ['End'],                                   9, True,  C['white']),
    ]
    ys_r = []
    for x, y, w, h, sh, fc, bc, lines, fs, bold, tc in steps_r:
        box(sl, x, y, w, h, fc, bc, lines, fsize=fs, bold=bold, tc=tc, shape=sh)
        ys_r.append((x, y, w, h, sh))

    # Arrows column 2 (sequential)
    for i in range(len(ys_r)-1):
        x1, y1, w1, h1, _ = ys_r[i]
        x2, y2, w2, h2, _ = ys_r[i+1]
        cx = x1 + w1/2
        conn(sl, cx, y1+h1, cx, y2)

    # "No" loop for questions
    conn(sl, I(11.6), I(2.97), I(11.6), I(1.85), col=C['score_r'])
    txt(sl, I(11.62), I(2.4), I(0.5), I(0.4), 'No\n(loop)', fsize=8, col=C['score_r'])

    # Transition arrow: col1 diamond "Yes" → col2 start
    conn(sl, I(3.35), I(5.0), I(7.6), I(1.42))
    txt(sl, I(4.5), I(4.6), I(0.8), I(0.35), 'Yes', fsize=9, col=C['s_bd'])


# ── Slide 3: DFD ─────────────────────────────────────────────────────────────

def s_dfd(prs):
    sl = slide_header(prs,
        'Figure 3 — Data Flow Diagram (Level 0 + Level 1)',
        'Context Diagram and Process Decomposition showing data flow from Borrower through the FI System to Lender/LOS')

    divider_line(sl, I(4.0))  # vertical split line (use shape as vertical bar)
    vbar = sl.shapes.add_shape(RECT, I(6.55), I(1.1), I(0.03), I(6.25))
    vbar.fill.solid(); vbar.fill.fore_color.rgb = rgb('CFD8DC')
    vbar.line.fill.background()

    # ── Level 0 (left half) ──────────────────────────────────────────────────
    txt(sl, I(1.5), I(1.1), I(3.6), I(0.4), 'Level 0 — Context Diagram',
        fsize=11, col=C['title'], bold=True)

    # Borrower
    box(sl, I(0.3), I(2.2), I(1.8), I(1.2), C['c_bg'], C['c_bd'],
        ['Borrower'], fsize=11, bold=True, tc=C['c_bd'])

    # System circle
    circ = sl.shapes.add_shape(OVAL, I(2.6), I(1.8), I(1.8), I(1.8))
    circ.fill.solid(); circ.fill.fore_color.rgb = C['s_bg']
    circ.line.color.rgb = C['s_bd']; circ.line.width = P(2)
    tf = circ.text_frame
    tf.word_wrap = True
    try: tf.vertical_anchor = MSO_VERTICAL_ANCHOR.MIDDLE
    except: pass
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); r.text = 'Digital FI'; r.font.name='Calibri'; r.font.size=P(9); r.font.bold=True
    r.font.color.rgb = C['s_bd']
    p2 = tf.add_paragraph(); p2.alignment = PP_ALIGN.CENTER
    r2 = p2.add_run(); r2.text = 'System'; r2.font.name='Calibri'; r2.font.size=P(9); r2.font.bold=True
    r2.font.color.rgb = C['s_bd']

    # Lender
    box(sl, I(5.0), I(2.2), I(1.4), I(1.2), C['o_bg'], C['o_bd'],
        ['Lender / LOS'], fsize=10, bold=True, tc=C['o_bd'])

    # Arrows
    conn(sl, I(2.1), I(2.8), I(2.6), I(2.7))
    conn(sl, I(4.4), I(2.7), I(5.0), I(2.8))
    txt(sl, I(2.0), I(2.35), I(0.9), I(0.6), 'App data\nimages', fsize=7.5, col=C['c_bd'])
    txt(sl, I(4.3), I(2.35), I(0.9), I(0.6), 'FI Report\nPDF', fsize=7.5, col=C['o_bd'])

    # Caption
    txt(sl, I(0.3), I(3.55), I(6.1), I(0.55),
        'Borrower provides application details, answers and photos.\n'
        'System processes them and delivers the FI report to the lender.',
        fsize=8, col=C['hint'])

    # ── Level 1 (right half) ─────────────────────────────────────────────────
    txt(sl, I(7.3), I(1.1), I(5.8), I(0.4), 'Level 1 — Process Decomposition',
        fsize=11, col=C['title'], bold=True)

    # Processes (circles)
    procs = [
        ('P1\nSession\nSetup',    I(7.5),  I(1.7),  C['c_bg'], C['c_bd']),
        ('P2\nGuided\nCapture',   I(10.6), I(1.7),  C['s_bg'], C['s_bd']),
        ('P3\nAI Analysis\nEngine', I(7.5), I(3.8), C['a_bg'], C['a_bd']),
        ('P4\nFraud\nCheck',      I(10.6), I(3.8),  C['o_bg'], C['o_bd']),
        ('P5\nReport\nGenerator', I(9.0),  I(5.7),  C['r_bg'], C['r_bd']),
    ]
    proc_shapes = {}
    for label, px, py, fc, bc in procs:
        sh = sl.shapes.add_shape(OVAL, px, py, I(1.5), I(1.5))
        sh.fill.solid(); sh.fill.fore_color.rgb = fc
        sh.line.color.rgb = bc; sh.line.width = P(1.5)
        tf = sh.text_frame; tf.word_wrap = True
        try: tf.vertical_anchor = MSO_VERTICAL_ANCHOR.MIDDLE
        except: pass
        tf.clear()
        for i, ln in enumerate(label.split('\n')):
            p = tf.paragraphs[0] if i==0 else tf.add_paragraph()
            p.alignment = PP_ALIGN.CENTER
            r = p.add_run(); r.text = ln
            r.font.name='Calibri'; r.font.size=P(7.5)
            r.font.bold = (i==0)
            r.font.color.rgb = bc
        proc_shapes[label.split('\n')[0]] = (px, py)

    # Data stores (open rectangles)
    stores = [
        ('D1 Session DB',    I(7.5),  I(3.2)),
        ('D2 Image Store',   I(10.6), I(3.2)),
        ('D3 AI Results',    I(7.5),  I(5.3)),
        ('D4 Report Store',  I(10.6), I(5.3)),
    ]
    for label, sx, sy in stores:
        # Open-sided rectangle: draw as thin box
        s = sl.shapes.add_shape(RECT, sx, sy, I(1.5), I(0.4))
        s.fill.solid(); s.fill.fore_color.rgb = rgb('ECEFF1')
        s.line.color.rgb = rgb('546E7A'); s.line.width = P(1.2)
        tf = s.text_frame; p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
        r = p.add_run(); r.text = label
        r.font.name='Calibri'; r.font.size=P(7.5); r.font.color.rgb=C['mid']

    # Process flow arrows (simplified)
    flow_arrows = [
        (I(8.25), I(3.2), I(8.25), I(3.2)),  # P1 → D1
        (I(11.35),I(3.2), I(11.35),I(3.2)),  # P2 → D2
        (I(8.25), I(2.47),I(11.35),I(1.7)),  # P1 → P2
        (I(8.25), I(3.6), I(8.25), I(3.8)),  # D1 → P3
        (I(11.35),I(3.6), I(11.35),I(3.8)),  # D2 → P4
        (I(9.0),  I(4.55),I(11.35),I(3.8)),  # P3 → P4
        (I(8.25), I(5.3), I(8.25), I(5.3)),  # P3 → D3
        (I(9.75), I(5.9), I(9.75), I(5.7)),  # D3 → P5
        (I(11.35),I(5.3), I(11.35),I(5.3)),  # P4 → D4
        (I(10.55),I(5.9), I(10.55),I(5.7)),  # D4 → P5
    ]

    # Simplified arrows for DFD
    conn(sl, I(8.25), I(3.2), I(8.25), I(3.6))   # P1 → D1
    conn(sl, I(11.35),I(3.2), I(11.35),I(3.6))   # P2 → D2
    conn(sl, I(9.0), I(2.45), I(10.6), I(2.45))  # P1 → P2
    conn(sl, I(8.25), I(4.0), I(8.25), I(4.3))   # D1 → P3 (elbow)
    conn(sl, I(11.35),I(4.0), I(11.35),I(4.3))   # D2 → P4
    conn(sl, I(9.0), I(4.55), I(10.6), I(4.55))  # P3 → P4
    conn(sl, I(8.25), I(5.3), I(8.25), I(5.5))   # P3 → D3
    conn(sl, I(11.35),I(4.55),I(11.35),I(5.5))   # P4 → D4
    conn(sl, I(9.0), I(5.9), I(9.75), I(5.7))    # D3 → P5
    conn(sl, I(11.1),I(5.7), I(10.5), I(5.7))    # D4 → P5

    # External entities
    box(sl, I(6.7), I(1.15), I(0.8), I(0.5), C['c_bg'], C['c_bd'],
        ['Borrower'], fsize=7.5, bold=True, tc=C['c_bd'])
    box(sl, I(12.3),I(6.1),  I(0.9), I(0.5), C['o_bg'], C['o_bd'],
        ['LOS'], fsize=9, bold=True, tc=C['o_bd'])
    conn(sl, I(7.1), I(1.42), I(7.5), I(2.2))   # Borrower → P1
    conn(sl, I(10.5),I(6.2), I(12.3), I(6.35))  # P5 → LOS


# ── Slide 4: Activity Diagram ─────────────────────────────────────────────────

def s_activity(prs):
    sl = slide_header(prs,
        'Figure 4 — Activity Diagram',
        'Execution flow with decision gates for form validation, question loop and photo capture loop')

    # Two columns — each column has its own flow
    col1_x = I(0.3);  col2_x = I(7.0)
    W = I(5.6);       H = I(0.55)
    DW = I(5.0)

    # ── Column 1 ──────────────────────────────────────────────────────────────
    # Start node
    start = sl.shapes.add_shape(OVAL, I(2.3), I(1.15), I(1.0), I(0.5))
    start.fill.solid(); start.fill.fore_color.rgb = C['e_bg']
    start.line.color.rgb = C['e_bg']
    tf = start.text_frame; p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); r.text = 'Start'; r.font.name='Calibri'; r.font.size=P(9)
    r.font.bold=True; r.font.color.rgb = C['white']

    c1_steps = [
        (I(0.3), I(1.85), W, H, RRECT, C['c_bg'], C['c_bd'], 'Open Mobile Web App', 9, C['c_bd']),
        (I(0.3), I(2.55), W, H, RRECT, C['c_bg'], C['c_bd'], 'Verify Mobile OTP', 9, C['c_bd']),
        (I(0.3), I(3.25), W, H, RRECT, C['c_bg'], C['c_bd'], 'Fill Loan Application Form', 9, C['c_bd']),
        (I(0.3), I(3.95), W, H, RRECT, C['c_bg'], C['c_bd'], 'Add Property Info  (Type · Bedrooms · Hall)', 9, C['c_bd']),
        (I(0.55),I(4.75), DW, I(0.8), DIAMOND, C['d_bg'], C['d_bd'], 'Form Complete?', 9, C['mid']),
        (I(0.3), I(5.75), W, H, RRECT, C['s_bg'], C['s_bd'], 'Create FI Session  (WebSocket + GPS lock)', 9, C['s_bd']),
        (I(0.3), I(6.45), W, H, RRECT, C['s_bg'], C['s_bd'], 'Display Question Prompt  →  Record Voice Answer', 9, C['s_bd']),
    ]
    ys1 = []
    for x, y, w, h, sh, fc, bc, lbl, fs, tc in c1_steps:
        box(sl, x, y, w, h, fc, bc, [lbl], fsize=fs, tc=tc, shape=sh)
        ys1.append((x, y, w, h, sh))

    # Column 1 arrows
    conn(sl, I(2.8), I(1.65), I(2.8), I(1.85))  # Start → step1
    for i in range(len(ys1)-1):
        x,y,w,h,_ = ys1[i]
        _,y2,_,_,_ = ys1[i+1]
        conn(sl, x+w/2, y+h, x+w/2, y2)

    # No loop (form incomplete)
    conn(sl, I(0.55), I(5.15), I(0.55), I(3.25), col=C['score_r'])
    txt(sl, I(0.02), I(4.1), I(0.6), I(0.5), 'No\n(Edit)', fsize=8, col=C['score_r'])
    txt(sl, I(2.85), I(5.35), I(0.5), I(0.3), 'Yes', fsize=9, col=C['s_bd'])

    # ── Column 2 ──────────────────────────────────────────────────────────────
    c2_steps = [
        (col2_x, I(1.15), W, H, DIAMOND, C['d_bg'], C['d_bd'], 'All Questions Done?', 9, C['mid']),
        (col2_x, I(2.05), W, H, RRECT, C['o_bg'], C['o_bd'], 'Display Photo Prompt  →  Capture Photo', 9, C['o_bd']),
        (col2_x, I(2.75), W, H, RRECT, C['o_bg'], C['o_bd'], 'Review Photo  →  Save or Retake', 9, C['o_bd']),
        (col2_x, I(3.45), W, H, DIAMOND, C['d_bg'], C['d_bd'], 'All Photos Done?', 9, C['mid']),
        (col2_x, I(4.35), W, H, RRECT, C['o_bg'], C['o_bd'], 'PAN Card Capture + OCR', 9, C['o_bd']),
        (col2_x, I(5.05), W, H, RRECT, C['o_bg'], C['o_bd'], 'Bank Statement Consent', 9, C['o_bd']),
        (col2_x, I(5.75), W, H, RRECT, C['a_bg'], C['a_bd'], 'Submit Session', 9, C['a_bd']),
        (col2_x, I(6.45), W, H, RRECT, C['p_bg'], C['p_bd'], 'Run AI Pipeline  →  Generate PDF Report', 9, C['p_bd']),
    ]
    ys2 = []
    for x, y, w, h, sh, fc, bc, lbl, fs, tc in c2_steps:
        box(sl, x, y, w, h, fc, bc, [lbl], fsize=fs, tc=tc, shape=sh)
        ys2.append((x, y, w, h, sh))

    # Arrows column 2
    for i in range(len(ys2)-1):
        x,y,w,h,_ = ys2[i]
        _,y2,_,_,_ = ys2[i+1]
        conn(sl, x+w/2, y+h, x+w/2, y2)

    # "No" loops
    conn(sl, I(12.6), I(1.75), I(12.6), I(7.0), col=C['score_r'])
    conn(sl, I(12.6), I(7.0),  col2_x+W, I(7.0), col=C['score_r'], arrow=False)
    conn(sl, col2_x+W, I(7.0), col2_x+W, I(2.05), col=C['score_r'])
    txt(sl, I(12.62), I(2.0), I(0.6), I(0.5), 'No\n(loop)', fsize=8, col=C['score_r'])

    conn(sl, I(12.6), I(4.05), I(12.6), I(4.35), col=C['score_r'])
    txt(sl, I(12.62), I(3.5), I(0.6), I(0.5), 'No\n(loop)', fsize=8, col=C['score_r'])

    txt(sl, col2_x + W/2 + I(0.05), I(1.75), I(0.5), I(0.25), 'Yes', fsize=9, col=C['s_bd'])
    txt(sl, col2_x + W/2 + I(0.05), I(4.05), I(0.5), I(0.25), 'Yes', fsize=9, col=C['s_bd'])

    # End node
    end = sl.shapes.add_shape(OVAL, I(9.5), I(7.1), I(1.0), I(0.45))
    end.fill.solid(); end.fill.fore_color.rgb = C['e_bg']
    end.line.color.rgb = C['e_bg']
    tf2 = end.text_frame; p2 = tf2.paragraphs[0]; p2.alignment = PP_ALIGN.CENTER
    r2 = p2.add_run(); r2.text = 'End'; r2.font.name='Calibri'; r2.font.size=P(9)
    r2.font.bold=True; r2.font.color.rgb=C['white']

    # Transition: col1 last step → col2 first
    conn(sl, I(5.9), I(6.72), col2_x + W/2, I(6.72), elbow=True)
    conn(sl, col2_x + W/2, I(6.72), col2_x + W/2, I(1.15), elbow=True)
    txt(sl, I(5.95), I(6.5), I(0.9), I(0.35), 'To Q&A →', fsize=8, col=C['s_bd'])


# ── Slide 5: Application Screenshots ─────────────────────────────────────────

def s_screenshots(prs):
    sl = slide_header(prs,
        'Figure 5 — Application Screenshots (Simulated UI)',
        'Loan Application Form  ·  FI Session Recording screen  ·  Photo Review screen')

    panels = [
        # (x, title, color, content lines)
        (I(0.25), 'Loan Application Form', C['c_bd'], [
            ('hdr', 'ABC Bank — Personal Loan'),
            ('sep',),
            ('row', 'First Name', 'Rahul'),
            ('row', 'Last Name',  'Sharma'),
            ('row', 'DOB',        '15-May-1990'),
            ('row', 'PAN',        'ABCPS1234R'),
            ('row', 'Income',     '₹5L – ₹20L'),
            ('row', 'Loan Amt',   '₹3,00,000'),
            ('sep',),
            ('hdr', 'Property Info'),
            ('row', 'Type',      'Flat / Apartment'),
            ('row', 'Bedrooms',  '2'),
            ('row', 'Hall',      'Yes'),
            ('sep',),
            ('btn', 'Review Application'),
        ]),
        (I(4.6), 'FI Session — Recording', C['s_bd'], [
            ('cam', '[FRONT CAMERA PREVIEW]'),
            ('sep',),
            ('hdr', 'Question 2 of 3'),
            ('lbl', '"What is your'),
            ('lbl', ' residential PIN code?"'),
            ('sep',),
            ('rec', '[REC]  Recording...'),
            ('lbl', 'Please speak now'),
            ('sep',),
            ('lbl', 'Partial: "my pin'),
            ('lbl', '         code is 40..."'),
        ]),
        (I(8.95), 'Photo Review — Nameplate', C['p_bd'], [
            ('cam', '[REAR CAMERA PHOTO]'),
            ('sep',),
            ('hdr', 'Nameplate — Review before saving'),
            ('sep',),
            ('lbl', 'GPS  Lat: 19.07602'),
            ('lbl', '     Lon: 72.87743'),
            ('sep',),
            ('lbl', 'OCR detected text:'),
            ('lbl', '"Sharma Residence"'),
            ('sep',),
            ('btn2', '[X] Retake', '[✓] Save Photo'),
        ]),
    ]

    PW = I(4.1); PH = I(6.15)

    for px, ptitle, pcol, plines in panels:
        # Phone shell
        shell = sl.shapes.add_shape(RRECT, px, I(1.12), PW, PH)
        shell.fill.solid(); shell.fill.fore_color.rgb = rgb('1C1C1E')
        shell.line.color.rgb = rgb('3A3A3C'); shell.line.width = P(3)

        # Screen area
        scr = sl.shapes.add_shape(RRECT, px+I(0.1), I(1.28), PW-I(0.2), PH-I(0.22))
        scr.fill.solid(); scr.fill.fore_color.rgb = C['white']
        scr.line.fill.background()

        # Title bar
        tbar = sl.shapes.add_shape(RECT, px+I(0.1), I(1.28), PW-I(0.2), I(0.42))
        tbar.fill.solid(); tbar.fill.fore_color.rgb = pcol
        tbar.line.fill.background()
        tf = tbar.text_frame; p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
        try: tf.vertical_anchor = MSO_VERTICAL_ANCHOR.MIDDLE
        except: pass
        r = p.add_run(); r.text = ptitle
        r.font.name='Calibri'; r.font.size=P(8); r.font.bold=True
        r.font.color.rgb = C['white']

        # Content
        cy = I(1.78)
        line_h = I(0.37)
        for item in plines:
            kind = item[0]
            if kind == 'sep':
                sep = sl.shapes.add_shape(RECT, px+I(0.15), cy, PW-I(0.3), I(0.02))
                sep.fill.solid(); sep.fill.fore_color.rgb = rgb('E0E0E0')
                sep.line.fill.background()
                cy += I(0.08)
            elif kind == 'hdr':
                tb = sl.shapes.add_textbox(px+I(0.15), cy, PW-I(0.3), I(0.35))
                tf = tb.text_frame; p = tf.paragraphs[0]; p.alignment=PP_ALIGN.CENTER
                r = p.add_run(); r.text=item[1]; r.font.name='Calibri'; r.font.size=P(8.5)
                r.font.bold=True; r.font.color.rgb=pcol
                cy += I(0.38)
            elif kind == 'row':
                tb = sl.shapes.add_textbox(px+I(0.18), cy, PW-I(0.3), I(0.33))
                tf = tb.text_frame; p = tf.paragraphs[0]; p.alignment=PP_ALIGN.LEFT
                r = p.add_run(); r.text=f'{item[1]}: '; r.font.name='Calibri'; r.font.size=P(8)
                r.font.bold=True; r.font.color.rgb=C['mid']
                r2 = p.add_run(); r2.text=item[2]; r2.font.name='Calibri'; r2.font.size=P(8)
                r2.font.color.rgb=C['text']
                cy += I(0.34)
            elif kind in ('lbl', 'rec'):
                tb = sl.shapes.add_textbox(px+I(0.18), cy, PW-I(0.3), I(0.33))
                tf = tb.text_frame; p = tf.paragraphs[0]; p.alignment=PP_ALIGN.LEFT
                r = p.add_run(); r.text=item[1]; r.font.name='Calibri'; r.font.size=P(8)
                r.font.color.rgb = C['score_r'] if kind=='rec' else C['text']
                r.font.bold = (kind=='rec')
                cy += I(0.33)
            elif kind == 'cam':
                cam = sl.shapes.add_shape(RRECT, px+I(0.18), cy, PW-I(0.3), I(0.85))
                cam.fill.solid(); cam.fill.fore_color.rgb = rgb('ECEFF1')
                cam.line.color.rgb = rgb('90A4AE'); cam.line.width = P(1)
                tf = cam.text_frame; p = tf.paragraphs[0]; p.alignment=PP_ALIGN.CENTER
                try: tf.vertical_anchor = MSO_VERTICAL_ANCHOR.MIDDLE
                except: pass
                r = p.add_run(); r.text=item[1]; r.font.name='Calibri'; r.font.size=P(8)
                r.font.color.rgb = C['hint']
                cy += I(0.92)
            elif kind == 'btn':
                btn = sl.shapes.add_shape(RRECT, px+I(0.18), cy, PW-I(0.3), I(0.42))
                btn.fill.solid(); btn.fill.fore_color.rgb = pcol
                btn.line.fill.background()
                tf = btn.text_frame; p = tf.paragraphs[0]; p.alignment=PP_ALIGN.CENTER
                try: tf.vertical_anchor = MSO_VERTICAL_ANCHOR.MIDDLE
                except: pass
                r = p.add_run(); r.text=item[1]; r.font.name='Calibri'; r.font.size=P(8.5)
                r.font.bold=True; r.font.color.rgb=C['white']
                cy += I(0.46)
            elif kind == 'btn2':
                bw = (PW-I(0.4)) / 2
                for bi, (bc2, blab) in enumerate([(C['score_r'], item[1]), (rgb('2E7D32'), item[2])]):
                    bx = px+I(0.18) + bi*(bw+I(0.05))
                    b = sl.shapes.add_shape(RRECT, bx, cy, bw, I(0.42))
                    b.fill.solid(); b.fill.fore_color.rgb = bc2; b.line.fill.background()
                    tf = b.text_frame; p = tf.paragraphs[0]; p.alignment=PP_ALIGN.CENTER
                    try: tf.vertical_anchor = MSO_VERTICAL_ANCHOR.MIDDLE
                    except: pass
                    r = p.add_run(); r.text=blab; r.font.name='Calibri'; r.font.size=P(8)
                    r.font.bold=True; r.font.color.rgb=C['white']
                cy += I(0.46)


# ── Slide 6: AI Analysis Output ───────────────────────────────────────────────

def s_report(prs):
    sl = slide_header(prs,
        'Figure 6 — AI Analysis Output: Sample Credit Report',
        'Credit Score  ·  CIBIL Score  ·  Recommendation  ·  Identity / Residence / Income / Location assessments')

    # ── Score panel row ───────────────────────────────────────────────────────
    panels_top = [
        (I(0.2),  C['s_bg'], C['s_bd'], 'CREDIT SCORE',    '72 / 100',         'Grade: BBB  ·  Conditional Approval'),
        (I(4.55), C['o_bg'], C['o_bd'], 'RECOMMENDATION',  'APPROVE WITH',      'CONDITIONS'),
        (I(8.9),  C['c_bg'], C['c_bd'], 'CIBIL SCORE',     '695',               'FAIR  ·  TransUnion CIBIL'),
    ]
    for px, fc, bc, title, val, sub in panels_top:
        box(sl, px, I(1.12), I(4.1), I(1.5), fc, bc, [], lw=2)
        txt(sl, px, I(1.15), I(4.1), I(0.4), title, fsize=9, col=bc, bold=True)
        txt(sl, px, I(1.52), I(4.1), I(0.6), val,   fsize=20, col=bc, bold=True)
        txt(sl, px, I(2.1), I(4.1), I(0.35), sub,   fsize=8.5, col=bc)

    # ── Four assessment cards ──────────────────────────────────────────────────
    cards = [
        (I(0.2),  I(2.85), C['s_bg'], C['s_bd'], 'Identity Assessment',  85, C['score_g'],
         'PAN OCR: ABCPS1234R  ✓\nFace similarity: 78%\nName match: PASS'),
        (I(6.7),  I(2.85), C['c_bg'], C['c_bd'], 'Residence Assessment', 80, C['score_g'],
         'GPS spread: 42 m (8 points)\nNameplate OCR: "Sharma Residence"\nAddress verified  ✓'),
        (I(0.2),  I(5.15), C['o_bg'], C['o_bd'], 'Income Assessment',    70, C['score_o'],
         'Avg income: ₹68,400 / mo\nExpense ratio: 58%\nCreditworthiness: 7 / 10'),
        (I(6.7),  I(5.15), C['s_bg'], C['s_bd'], 'Location Assessment',  92, C['score_g'],
         'All photos within 312 m\nGPS status: PASS\nGoogle Maps: Mumbai, MH'),
    ]
    for cx, cy, fc, bc, title, score, scol, detail in cards:
        box(sl, cx, cy, I(6.2), I(2.0), fc, bc, [], lw=1.5)
        txt(sl, cx+I(0.1), cy+I(0.1), I(6.0), I(0.38), title, fsize=10, col=bc, bold=True)

        # Score bar background
        bar_bg = sl.shapes.add_shape(RRECT, cx+I(0.1), cy+I(0.58), I(4.0), I(0.28))
        bar_bg.fill.solid(); bar_bg.fill.fore_color.rgb = rgb('E0E0E0')
        bar_bg.line.fill.background()

        # Score bar foreground
        bar_fg = sl.shapes.add_shape(RRECT, cx+I(0.1), cy+I(0.58), I(4.0 * score / 100), I(0.28))
        bar_fg.fill.solid(); bar_fg.fill.fore_color.rgb = scol
        bar_fg.line.fill.background()

        txt(sl, cx+I(4.2), cy+I(0.52), I(1.8), I(0.38),
            f'{score} / 100', fsize=11, col=scol, bold=True)

        txt(sl, cx+I(0.1), cy+I(0.97), I(6.0), I(0.9),
            detail, fsize=8.5, col=C['mid'], align=PP_ALIGN.LEFT)

    # ── Footer ─────────────────────────────────────────────────────────────────
    footer = sl.shapes.add_shape(RRECT, I(0.2), I(7.12), I(12.93), I(0.3))
    footer.fill.solid(); footer.fill.fore_color.rgb = C['s_bg']
    footer.line.color.rgb = C['s_bd']; footer.line.width = P(1)
    tf = footer.text_frame; p = tf.paragraphs[0]; p.alignment=PP_ALIGN.CENTER
    try: tf.vertical_anchor = MSO_VERTICAL_ANCHOR.MIDDLE
    except: pass
    r = p.add_run()
    r.text = ('Case: rahul_a3b4c5d6  ·  Loan: ₹3,00,000  ·  EMI (est.): ₹6,660/mo  ·  '
              'EMI:Income = 9.7%  ·  Status: AFFORDABLE  ·  Powered by VideoCX FI Agent')
    r.font.name='Calibri'; r.font.size=P(8); r.font.color.rgb=C['s_bd']


# ── Build PPT ─────────────────────────────────────────────────────────────────

def build():
    prs = Presentation()
    prs.slide_width  = I(13.33)
    prs.slide_height = I(7.5)

    print('  Slide 1: System Architecture')
    s_arch(prs)
    print('  Slide 2: Flowchart')
    s_flow(prs)
    print('  Slide 3: DFD')
    s_dfd(prs)
    print('  Slide 4: Activity Diagram')
    s_activity(prs)
    print('  Slide 5: App Screenshots')
    s_screenshots(prs)
    print('  Slide 6: AI Analysis Output')
    s_report(prs)

    return prs


if __name__ == '__main__':
    out = r'd:\videocx\trunk\fi-agent\docs\FI_Project_Diagrams_Editable.pptx'
    os.makedirs(os.path.dirname(out), exist_ok=True)
    print('Generating editable PowerPoint...')
    prs = build()
    prs.save(out)
    print(f'\nDone!  Saved to: {out}')
    import subprocess
    subprocess.Popen(['start', '', out], shell=True)
