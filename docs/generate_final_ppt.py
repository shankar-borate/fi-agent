"""
Final presentation PPT — AI-Based Visual Intelligence for Digital Field Investigation
Based on the student draft, updated with actual implementation details.
"""
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_VERTICAL_ANCHOR
from pptx.oxml.ns import qn
from lxml import etree
import os

I = Inches
P = Pt

# ── Colours ───────────────────────────────────────────────────────────────────
def rgb(h): return RGBColor(int(h[0:2],16), int(h[2:4],16), int(h[4:6],16))

NAVY   = rgb('1C3557')
TEAL   = rgb('0E8FA8')
ORANGE = rgb('E87722')
RED    = rgb('E63946')
GREEN  = rgb('2D9B5A')
WHITE  = rgb('FFFFFF')
LGREY  = rgb('F4F6F8')
MGREY  = rgb('E2E8F0')
DGREY  = rgb('4A5568')
HINT   = rgb('718096')
YELLOW = rgb('F0A500')

RECT  = 1
RRECT = 5
OVAL  = 9
DIAM  = 4

SW = I(13.33)
SH = I(7.5)

# ── Helpers ───────────────────────────────────────────────────────────────────

def new_slide(prs, bg_color=None):
    sl = prs.slides.add_slide(prs.slide_layouts[6])
    if bg_color:
        sl.background.fill.solid()
        sl.background.fill.fore_color.rgb = bg_color
    else:
        sl.background.fill.solid()
        sl.background.fill.fore_color.rgb = WHITE
    return sl

def shape(sl, st, x, y, w, h, fc, bc=None, lw=0):
    s = sl.shapes.add_shape(st, x, y, w, h)
    s.fill.solid(); s.fill.fore_color.rgb = fc
    if bc:
        s.line.color.rgb = bc; s.line.width = P(lw or 1.2)
    else:
        s.line.fill.background()
    return s

def txt_in(s, lines, fsize=10, bold=False, tc=None, align=PP_ALIGN.CENTER, va=True):
    tf = s.text_frame; tf.word_wrap = True
    if va:
        try: tf.vertical_anchor = MSO_VERTICAL_ANCHOR.MIDDLE
        except: pass
    tf.clear()
    for i, ln in enumerate(lines if isinstance(lines, list) else [lines]):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        r = p.add_run(); r.text = str(ln)
        r.font.name = 'Calibri'; r.font.size = P(fsize)
        r.font.bold = bold if i == 0 else False
        r.font.color.rgb = tc or NAVY

def tb(sl, x, y, w, h, text, fsize=10, col=None, bold=False, align=PP_ALIGN.LEFT, wrap=True):
    t = sl.shapes.add_textbox(x, y, w, h)
    tf = t.text_frame; tf.word_wrap = wrap
    p = tf.paragraphs[0]; p.alignment = align
    r = p.add_run(); r.text = text
    r.font.name = 'Calibri'; r.font.size = P(fsize)
    r.font.bold = bold; r.font.color.rgb = col or NAVY
    return t

def arrow(sl, x1, y1, x2, y2, col=None, lw=1.5, elbow=False):
    c = sl.shapes.add_connector(2 if elbow else 1, x1, y1, x2, y2)
    c.line.color.rgb = col or DGREY; c.line.width = P(lw)
    sp = c._element.find(qn('p:spPr'))
    if sp is not None:
        ln = sp.find(qn('a:ln'))
        if ln is None: ln = etree.SubElement(sp, qn('a:ln'))
        for old in ln.findall(qn('a:tailEnd')): ln.remove(old)
        t = etree.SubElement(ln, qn('a:tailEnd'))
        t.set('type','arrow'); t.set('w','med'); t.set('len','med')
    return c

def top_bar(sl, title, subtitle='', num=None):
    """Standard dark navy top bar with slide title."""
    bar = shape(sl, RECT, I(0), I(0), SW, I(0.65), NAVY)
    txt_in(bar, title, fsize=18, bold=True, tc=WHITE, align=PP_ALIGN.LEFT, va=True)
    bar.text_frame.paragraphs[0].runs[0]
    # Indent title text
    bar.text_frame.paragraphs[0].alignment = PP_ALIGN.LEFT
    for r in bar.text_frame.paragraphs[0].runs:
        r.font.name = 'Calibri'
    # Add left padding via textbox overlay
    tb(sl, I(0.3), I(0.08), I(12.0), I(0.5), title, fsize=18, col=WHITE, bold=True)
    bar2 = shape(sl, RECT, I(0), I(0), SW, I(0.65), NAVY)  # this overwrites
    # Actually use a textbox inside the bar
    sl.shapes._spTree.remove(bar2._element)

    # Simpler: just the bar + textbox
    b = shape(sl, RECT, I(0), I(0), SW, I(0.65), NAVY)
    tb(sl, I(0.3), I(0.08), I(11.5), I(0.5), title, fsize=18, col=WHITE, bold=True)
    sl.shapes._spTree.remove(b._element)

    hdr = shape(sl, RECT, I(0), I(0), SW, I(0.62), NAVY)
    if subtitle:
        tb(sl, I(0.3), I(0.63), SW - I(0.6), I(0.32), subtitle, fsize=9.5, col=HINT)
    if num is not None:
        tb(sl, SW - I(0.5), I(0.5), I(0.4), I(0.25),
           str(num), fsize=9, col=HINT, align=PP_ALIGN.RIGHT)
    return hdr

def card(sl, x, y, w, h, fc=None, bc=None, accent_col=None, lw=1.0):
    """Bordered card with optional top accent bar."""
    fc = fc or WHITE
    c = shape(sl, RRECT, x, y, w, h, fc, bc or MGREY, lw)
    if accent_col:
        acc = shape(sl, RECT, x, y, w, I(0.06), accent_col)
    return c

# ═══════════════════════════════════════════════════════════════════════════════
# Slide 1 — Title
# ═══════════════════════════════════════════════════════════════════════════════
def slide_title(prs):
    sl = new_slide(prs)

    # Left panel (grey)
    lp = shape(sl, RECT, I(0), I(0), I(5.0), SH, LGREY)

    # Vertical accent bar
    shape(sl, RECT, I(4.88), I(0), I(0.12), SH, TEAL)

    # College details
    tb(sl, I(0.3), I(2.0), I(4.4), I(0.5),
       'Dr. Babasaheb Ambedkar', fsize=13, col=NAVY, bold=True)
    tb(sl, I(0.3), I(2.45), I(4.4), I(0.5),
       'Technological University, Lonere', fsize=13, col=NAVY, bold=True)
    tb(sl, I(0.3), I(2.95), I(4.4), I(0.3),
       'Arvind Gavali College of Engineering, Satara', fsize=10, col=DGREY)
    tb(sl, I(0.3), I(3.25), I(4.4), I(0.3),
       'Dept. of Computer Science & Engineering', fsize=10, col=NAVY, bold=True)

    # Divider
    d = shape(sl, RECT, I(0.3), I(3.65), I(4.2), I(0.025), NAVY)

    tb(sl, I(0.3), I(3.8), I(4.4), I(0.3), 'Presented by:', fsize=10, col=NAVY, bold=True)
    for i, nm in enumerate([
        'Mr. Shubham Abaso Nale  (2265451242070)',
        'Mr. Sarvesh Vijay Jadhav  (23065451242519)',
        'Mr. Suyash Rajendra Kale  (2265451242132)',
    ]):
        tb(sl, I(0.3), I(4.12) + I(i*0.28), I(4.5), I(0.28), nm, fsize=9.5, col=DGREY)

    tb(sl, I(0.3), I(5.1), I(4.4), I(0.3),
       'Guide: Prof. C. K. Saste', fsize=10, col=TEAL, bold=True)

    tb(sl, I(0.3), I(6.5), I(4.4), I(0.3),
       'Industry partner: VideoCX', fsize=9, col=HINT)

    # Right panel — Title
    tb(sl, I(5.3), I(1.0), I(7.7), I(1.8),
       'AI-Based Visual\nIntelligence', fsize=44, col=NAVY, bold=True)
    tb(sl, I(5.3), I(2.85), I(7.7), I(0.55),
       'for Digital Field Investigation', fsize=22, col=TEAL)

    # Divider
    shape(sl, RECT, I(5.3), I(3.5), I(7.7), I(0.025), MGREY)

    tb(sl, I(5.3), I(3.6), I(7.7), I(0.35),
       'Guided image capture  ·  AI visual analysis  ·  Fraud signal detection',
       fsize=10.5, col=HINT)

    # 4 tag boxes
    tags = ['Computer Vision', 'Optical Character Recognition (OCR)',
            'Face Matching',   'Scene Understanding']
    for i, tag in enumerate(tags):
        tx = I(5.3) + (I(0) if i%2==0 else I(3.95))
        ty = I(4.2) + (I(0) if i<2 else I(0.65))
        c = shape(sl, RRECT, tx, ty, I(3.75), I(0.52), WHITE, TEAL, 1.2)
        txt_in(c, tag, fsize=10, tc=TEAL)


# ═══════════════════════════════════════════════════════════════════════════════
# Slide 2 — Agenda
# ═══════════════════════════════════════════════════════════════════════════════
def slide_agenda(prs):
    sl = new_slide(prs)
    hdr = shape(sl, RECT, I(0), I(0), SW, I(0.62), NAVY)
    tb(sl, I(0.35), I(0.08), I(11), I(0.5), 'Agenda', fsize=22, col=WHITE, bold=True)
    tb(sl, I(0.35), I(0.65), I(11), I(0.3),
       'What we\'ll cover in this presentation', fsize=10, col=HINT)

    items = [
        ('01', 'About VideoCX',          'Company context and industry background', NAVY),
        ('02', 'Problem Statement',       'Why manual field investigation fails',    NAVY),
        ('03', 'Proposed Solution',       'Guided image capture approach',           NAVY),
        ('04', 'Objectives',              'Project goals and scope',                 NAVY),
        ('05', 'AI Signals & Fraud Flags','What the AI system detects and flags',    TEAL),
        ('06', 'System Architecture',     'How the pipeline is structured',          TEAL),
        ('07', 'Data Flow',               'How data moves through the system',       ORANGE),
        ('08', 'Technology Stack',        'Tools, frameworks, and models used',      ORANGE),
        ('09', 'Results & Outcomes',      'Performance metrics and deliverables',    ORANGE),
    ]

    cols = 2
    W = I(6.3); H = I(0.85)
    for i, (num, title, sub, ac) in enumerate(items):
        row = i // cols; col = i % cols
        if len(items) % 2 == 1 and i == len(items)-1:
            # centre last item
            x = I(0.25) + I(3.5)
        else:
            x = I(0.25) + col * (W + I(0.3))
        y = I(1.1) + row * (H + I(0.12))

        c = shape(sl, RECT, x, y, W, H, WHITE, MGREY, 0.8)
        # Left accent bar
        shape(sl, RECT, x, y, I(0.07), H, ac)
        # Number
        tb(sl, x + I(0.2), y + I(0.12), I(0.55), I(0.4),
           num, fsize=14, col=ac, bold=True)
        # Title
        tb(sl, x + I(0.75), y + I(0.1), W - I(0.9), I(0.38),
           title, fsize=11, col=NAVY, bold=True)
        # Subtitle
        tb(sl, x + I(0.75), y + I(0.48), W - I(0.9), I(0.3),
           sub, fsize=9, col=DGREY)

    tb(sl, SW - I(0.5), SH - I(0.28), I(0.4), I(0.25), '2', fsize=9, col=HINT, align=PP_ALIGN.RIGHT)


# ═══════════════════════════════════════════════════════════════════════════════
# Slide 3 — About VideoCX
# ═══════════════════════════════════════════════════════════════════════════════
def slide_videocx(prs):
    sl = new_slide(prs)
    hdr = shape(sl, RECT, I(0), I(0), SW, I(0.62), NAVY)
    tb(sl, I(0.35), I(0.08), I(11), I(0.5), 'About VideoCX', fsize=22, col=WHITE, bold=True)
    tb(sl, I(0.35), I(0.65), I(11), I(0.3), 'Industry partner driving this project', fsize=10, col=HINT)

    # Body text
    tb(sl, I(0.35), I(1.1), I(7.8), I(0.7),
       'VideoCX is a technology company working on digital customer interaction and verification workflows for lending and financial services.',
       fsize=11, col=NAVY)
    tb(sl, I(0.35), I(1.85), I(7.8), I(0.9),
       'The company focuses on solutions that help institutions perform critical processes — customer onboarding, video-based verification, and investigation journeys — in a digital, scalable, and traceable way.',
       fsize=11, col=NAVY)

    # Proposal box
    pb = shape(sl, RRECT, I(0.35), I(2.9), I(7.8), I(1.3), LGREY, TEAL, 1.2)
    tb(sl, I(0.55), I(2.98), I(7.4), I(0.3), 'Proposal Summary', fsize=10, col=NAVY, bold=True)
    tb(sl, I(0.55), I(3.28), I(7.4), I(0.85),
       'This project explores how guided image capture and AI-based visual analysis can support digital field investigation in lending — extracting visual evidence and identifying fraud indicators from borrower-captured images.',
       fsize=10, col=DGREY)

    # Right info cards
    cards_info = [
        ('Project Nature', 'College project  /  internship problem statement', TEAL),
        ('Primary Domain', 'AI · Computer Vision · OCR · Visual Verification · Fraud Detection', NAVY),
        ('Aligned with', 'Real lending workflows — loan origination & field verification', ORANGE),
    ]
    for i, (ctitle, ctext, col) in enumerate(cards_info):
        cy = I(1.1) + i * I(1.65)
        c = shape(sl, RRECT, I(8.55), cy, I(4.5), I(1.4), WHITE, MGREY, 0.8)
        # Circle accent
        circ = shape(sl, OVAL, I(8.65), cy + I(0.15), I(0.7), I(0.7), col)
        tb(sl, I(9.45), cy + I(0.1), I(3.5), I(0.3), ctitle, fsize=10, col=col, bold=True)
        tb(sl, I(9.45), cy + I(0.4), I(3.45), I(0.8), ctext, fsize=9.5, col=DGREY)

    tb(sl, SW - I(0.5), SH - I(0.28), I(0.4), I(0.25), '3', fsize=9, col=HINT, align=PP_ALIGN.RIGHT)


# ═══════════════════════════════════════════════════════════════════════════════
# Slide 4 — Problem Statement
# ═══════════════════════════════════════════════════════════════════════════════
def slide_problem(prs):
    sl = new_slide(prs)
    hdr = shape(sl, RECT, I(0), I(0), SW, I(0.62), NAVY)
    tb(sl, I(0.35), I(0.08), I(11), I(0.5), 'Problem Statement', fsize=22, col=WHITE, bold=True)
    tb(sl, I(0.35), I(0.65), I(11), I(0.3),
       'Field investigation is still a slow, expensive, manual bottleneck in lending', fsize=10, col=HINT)

    problems = [
        (RED,    'Slow & Costly',
         'Physical visits delay small-ticket loans by 3–7 days. Agent travel, scheduling, and manual report filing add high per-case cost.'),
        (ORANGE, 'Inconsistent Reports',
         'Each agent applies different observation standards — no uniform photo requirements, no consistent fraud checks.'),
        (NAVY,   'High Fraud Risk',
         'Borrowers may present a wrong person, use a borrowed location, or show premises unrelated to the declared loan purpose.'),
    ]
    for i, (ac, ptitle, ptext) in enumerate(problems):
        cy = I(1.05) + i * I(1.45)
        c = shape(sl, RECT, I(0.3), cy, I(8.5), I(1.3), WHITE, MGREY, 0.8)
        shape(sl, RECT, I(0.3), cy, I(0.07), I(1.3), ac)
        # Icon circle
        circ = shape(sl, OVAL, I(0.48), cy + I(0.25), I(0.7), I(0.7), ac)
        tb(sl, I(1.35), cy + I(0.08), I(7.3), I(0.32), ptitle, fsize=11, col=NAVY, bold=True)
        tb(sl, I(1.35), cy + I(0.42), I(7.3), I(0.75), ptext, fsize=9.5, col=DGREY)

    # Right panel
    tb(sl, I(9.1), I(1.05), I(3.9), I(0.32), 'Target Use Cases', fsize=11, col=TEAL, bold=True)
    for i, uc in enumerate(['Shop Verification', 'Workplace Verification', 'Residence Verification']):
        c = shape(sl, RRECT, I(9.1), I(1.45) + i * I(0.72), I(3.9), I(0.6), WHITE, MGREY, 0.8)
        txt_in(c, uc, fsize=10.5, tc=NAVY, bold=True)

    tb(sl, I(9.1), I(3.7), I(3.9), I(0.32), 'Fraud risk indicators', fsize=11, col=RED, bold=True)
    fraud = [
        'Wrong person present at the site',
        'Fake or borrowed location used',
        'Mismatch between declared and observed premises',
    ]
    for i, f in enumerate(fraud):
        circ = shape(sl, OVAL, I(9.1), I(4.1) + i * I(0.55), I(0.22), I(0.22), RED)
        tb(sl, I(9.42), I(4.08) + i * I(0.55), I(3.55), I(0.28), f, fsize=9.5, col=DGREY)

    tb(sl, SW - I(0.5), SH - I(0.28), I(0.4), I(0.25), '4', fsize=9, col=HINT, align=PP_ALIGN.RIGHT)


# ═══════════════════════════════════════════════════════════════════════════════
# Slide 5 — Proposed Solution
# ═══════════════════════════════════════════════════════════════════════════════
def slide_solution(prs):
    sl = new_slide(prs)
    hdr = shape(sl, RECT, I(0), I(0), SW, I(0.62), NAVY)
    tb(sl, I(0.35), I(0.08), I(11), I(0.5), 'Proposed Solution', fsize=22, col=WHITE, bold=True)
    tb(sl, I(0.35), I(0.65), I(11), I(0.3),
       'AI analysis covers object detection, OCR, scene classification, face match, and GPS location validation', fsize=10, col=HINT)

    steps = [
        ('1', 'Guided Capture',      'Customer captures images during a structured digital session', NAVY),
        ('2', 'Timestamping',        'Each image tagged with session time — full traceability and audit trail', TEAL),
        ('3', 'AI Analysis',         'GPT-4o Vision for object detection, OCR, scene classification, face verification, and GPS cross-check', TEAL),
        ('4', 'Fraud Checks',        'GPS validates declared address. Face match detects wrong person. Scene type flags environment mismatches', NAVY),
        ('5', 'Structured Output',   'Explainable summary with credit score, CIBIL score, and PDF report for lender review', ORANGE),
    ]
    SW_box = I(2.4); SH_box = I(4.5); gap = I(0.18)
    total_w = 5 * SW_box + 4 * gap
    start_x = (SW - total_w) / 2

    for i, (num, stitle, stext, ac) in enumerate(steps):
        x = start_x + i * (SW_box + gap)
        c = shape(sl, RRECT, x, I(1.0), SW_box, SH_box, WHITE, MGREY, 0.8)
        # Number circle
        nc = shape(sl, OVAL, x + SW_box/2 - I(0.38), I(1.15), I(0.76), I(0.76), NAVY)
        txt_in(nc, num, fsize=16, bold=True, tc=WHITE)
        # Small divider
        shape(sl, RECT, x + SW_box/2 - I(0.3), I(2.08), I(0.6), I(0.045), ac)
        tb(sl, x + I(0.12), I(2.22), SW_box - I(0.24), I(0.4),
           stitle, fsize=10.5, col=ac, bold=True, align=PP_ALIGN.CENTER)
        tb(sl, x + I(0.12), I(2.68), SW_box - I(0.24), I(2.5),
           stext, fsize=9, col=DGREY, align=PP_ALIGN.CENTER)

        # Arrow between steps
        if i < 4:
            arrow(sl, x + SW_box, I(1.0) + SH_box/2,
                  x + SW_box + gap, I(1.0) + SH_box/2, col=MGREY)

    # Bottom benefits bar
    bp = shape(sl, RRECT, I(0.25), I(5.7), SW - I(0.5), I(0.65), rgb('E8F7FA'), TEAL, 0.8)
    benefits = [
        'Lower bandwidth than full-video AI',
        'Human-reviewable evidence images with timestamps',
        'Clear audit trail through explainable outputs',
    ]
    for i, b in enumerate(benefits):
        circ = shape(sl, OVAL, I(0.5) + i * I(4.25), I(5.83), I(0.28), I(0.28), GREEN)
        tb(sl, I(0.88) + i * I(4.25), I(5.81), I(4.0), I(0.28), b, fsize=9.5, col=NAVY)

    tb(sl, SW - I(0.5), SH - I(0.28), I(0.4), I(0.25), '5', fsize=9, col=HINT, align=PP_ALIGN.RIGHT)


# ═══════════════════════════════════════════════════════════════════════════════
# Slide 6 — System Architecture
# ═══════════════════════════════════════════════════════════════════════════════
def slide_arch(prs):
    sl = new_slide(prs)
    hdr = shape(sl, RECT, I(0), I(0), SW, I(0.62), NAVY)
    tb(sl, I(0.35), I(0.08), I(11), I(0.5), 'System Architecture', fsize=22, col=WHITE, bold=True)

    # Row 1 — 5 top boxes
    boxes_r1 = [
        (rgb('EBF5FF'), rgb('1565C0'), 'Borrower\nMobile App',    'Guided capture\nGPS + timestamp\nSession prompts'),
        (rgb('EBF5FF'), rgb('1565C0'), 'API Layer\n(FastAPI)',    'Authentication\nRequest validation\nSession management'),
        (rgb('FFF0E8'), ORANGE,        'Session\nConductor',     'Q&A  ·  Photo prompts\nCountdown  ·  PAN OCR\nConsent flow'),
        (rgb('FEF0F5'), rgb('880E4F'), 'AI Analysis\nEngine',    'GPT-4o Vision\nAWS Textract\nAWS Rekognition'),
        (rgb('FFEEEE'), RED,           'Fraud\nRules',           'Mismatch checks\nRisk flags\nFraud scoring'),
    ]
    BW = I(2.35); BH = I(1.8)
    for i, (fc, bc, bt, bs) in enumerate(boxes_r1):
        x = I(0.2) + i * (BW + I(0.18))
        c = shape(sl, RRECT, x, I(0.85), BW, BH, fc, bc, 1.5)
        tb(sl, x + I(0.12), I(0.92), BW - I(0.24), I(0.5),
           bt, fsize=9.5, col=bc, bold=True, align=PP_ALIGN.CENTER)
        shape(sl, RECT, x + I(0.15), I(1.42), BW - I(0.3), I(0.025), bc)
        tb(sl, x + I(0.12), I(1.5), BW - I(0.24), I(1.0),
           bs, fsize=8.5, col=rgb('37474F'), align=PP_ALIGN.CENTER)
        if i < 4:
            arrow(sl, x + BW, I(0.85) + BH/2, x + BW + I(0.18), I(0.85) + BH/2, col=DGREY)

    # Row 2 — 3 bottom boxes
    boxes_r2 = [
        (rgb('E8F5E9'), GREEN,           'Data Storage',       'Application data\nSession records\nImages and AI outputs'),
        (rgb('FFF8E1'), YELLOW,          'Report Generator',   'Structured FI summary\nCIBIL  ·  Credit analysis\nReportLab PDF'),
        (rgb('FFEEEE'), rgb('880E4F'),   'Lender / LOS',      'Report review\nLoan decision support\nAuditor Portal'),
    ]
    BW2 = I(3.5)
    starts_x = [I(0.2), I(4.7), I(9.2) - I(0.5)]
    for i, (fc, bc, bt, bs) in enumerate(boxes_r2):
        x = starts_x[i] + (I(1.9) if i > 0 else I(0.8))
        x2 = [I(1.0), I(4.8), I(9.1)][i]
        c = shape(sl, RRECT, x2, I(3.9), BW2, I(1.9), fc, bc, 1.5)
        tb(sl, x2 + I(0.12), I(3.97), BW2 - I(0.24), I(0.38), bt, fsize=10, col=bc, bold=True, align=PP_ALIGN.CENTER)
        shape(sl, RECT, x2 + I(0.15), I(4.35), BW2 - I(0.3), I(0.025), bc)
        tb(sl, x2 + I(0.12), I(4.42), BW2 - I(0.24), I(1.2), bs, fsize=8.5, col=rgb('37474F'), align=PP_ALIGN.CENTER)

    # Connecting arrows
    arrow(sl, I(1.55), I(2.65), I(1.55), I(3.9))       # API → Storage
    arrow(sl, I(6.2),  I(2.65), I(6.3),  I(3.9))       # Session → Report
    arrow(sl, I(9.2),  I(2.65), I(10.8), I(3.9), elbow=True)  # AI → Report
    arrow(sl, I(8.3),  I(4.85), I(9.1),  I(4.85))      # Storage → Report
    arrow(sl, I(12.6), I(4.85), I(12.6), I(4.85))      # Report → LOS

    # Footer note
    fn = shape(sl, RRECT, I(0.2), I(6.05), SW - I(0.4), I(0.55), rgb('EBF5FF'), rgb('90CAF9'), 0.8)
    tb(sl, I(0.55), I(6.1), SW - I(0.8), I(0.45),
       'The AI module adapts prompts based on loan details, previous answers, GPS status, and signals detected in images, making digital field investigation smarter and more efficient.',
       fsize=9, col=NAVY)

    tb(sl, SW - I(0.5), SH - I(0.28), I(0.4), I(0.25), '6', fsize=9, col=HINT, align=PP_ALIGN.RIGHT)


# ═══════════════════════════════════════════════════════════════════════════════
# Slide 7 — AI Signals & Fraud Indicators
# ═══════════════════════════════════════════════════════════════════════════════
def slide_signals(prs):
    sl = new_slide(prs)
    hdr = shape(sl, RECT, I(0), I(0), SW, I(0.62), NAVY)
    tb(sl, I(0.35), I(0.08), I(11), I(0.5), 'AI Signals & Fraud Indicators', fsize=22, col=WHITE, bold=True)
    tb(sl, I(0.35), I(0.65), I(11), I(0.3),
       'The output is explainable: what was seen, what was read, and what was flagged', fsize=10, col=HINT)

    signals = [
        ('OCR / Signage',          'Read shop names, nameplate text, PAN card fields, and visible labels from images',   TEAL),
        ('Inventory & Context',    'Estimate visible stock, goods, or business activity from property photos',            TEAL),
        ('People Presence',        'Check whether relevant people are visible at the declared location',                  TEAL),
        ('Scene Understanding',    'GPT-4o Vision determines if location looks like a shop, office, or residence',       NAVY),
        ('Face Match',             'Compare borrower\'s selfie with face on PAN card via AWS Rekognition',               NAVY),
        ('Location Consistency',   'GPS coordinates validated — all photos within 500m radius of declared address',      NAVY),
    ]

    CW = I(4.15); CH = I(1.2)
    for i, (stitle, stext, sc) in enumerate(signals):
        row = i // 3; col = i % 3
        x = I(0.25) + col * (CW + I(0.24))
        y = I(1.0) + row * (CH + I(0.18))
        c = shape(sl, RRECT, x, y, CW, CH, WHITE, MGREY, 0.8)
        circ = shape(sl, OVAL, x + I(0.15), y + I(0.22), I(0.65), I(0.65), sc)
        tb(sl, x + I(0.95), y + I(0.12), CW - I(1.05), I(0.35), stitle, fsize=10.5, col=NAVY, bold=True)
        tb(sl, x + I(0.95), y + I(0.5), CW - I(1.05), I(0.6), stext, fsize=9, col=DGREY)

    # Fraud flags box
    fb = shape(sl, RRECT, I(0.25), I(4.8), SW - I(0.5), I(1.85), rgb('FFF5F5'), RED, 1.0)
    tb(sl, I(0.55), I(4.9), I(12.0), I(0.32), 'Example Fraud Flags', fsize=11, col=RED, bold=True)
    flags = [
        'Face visible in captured image does not match borrower\'s reference identity on PAN card',
        'GPS metadata or visual context does not match declared address or business type',
        'Environment (shop, residence, office) does not match the declared loan purpose',
    ]
    for i, f in enumerate(flags):
        circ = shape(sl, OVAL, I(0.55), I(5.3) + i * I(0.42), I(0.22), I(0.22), RED)
        tb(sl, I(0.88), I(5.28) + i * I(0.42), I(12.0), I(0.28), f, fsize=10, col=NAVY)

    tb(sl, SW - I(0.5), SH - I(0.28), I(0.4), I(0.25), '7', fsize=9, col=HINT, align=PP_ALIGN.RIGHT)


# ═══════════════════════════════════════════════════════════════════════════════
# Slide 8 — Data Flow Swimlane
# ═══════════════════════════════════════════════════════════════════════════════
def slide_dataflow(prs):
    sl = new_slide(prs)
    hdr = shape(sl, RECT, I(0), I(0), SW, I(0.62), NAVY)
    tb(sl, I(0.35), I(0.08), I(11), I(0.5), 'Data Flow at Different Components', fsize=22, col=WHITE, bold=True)
    tb(sl, I(0.35), I(0.65), I(11), I(0.3),
       'How information moves through the digital field investigation system', fsize=10, col=HINT)

    lanes = [
        ('Borrower',   NAVY,   rgb('E8EDF4')),
        ('Mobile App', TEAL,   rgb('E6F6F8')),
        ('AI Backend', ORANGE, rgb('FEF3E8')),
        ('Output Layer',GREEN, rgb('E8F6EE')),
    ]
    LW = (SW - I(0.3)) / 4

    for i, (lname, lc, lbg) in enumerate(lanes):
        x = I(0.15) + i * LW
        # Header
        h = shape(sl, RECT, x, I(0.85), LW, I(0.5), lc)
        txt_in(h, lname, fsize=11, bold=True, tc=WHITE)
        # Body
        shape(sl, RECT, x, I(1.35), LW, SH - I(1.55), lbg)

    # Lane items
    lane_items = [
        # col, y, text
        (0, I(1.55), 'Starts guided\nverification session'),
        (0, I(2.75), 'Captures images\non prompt'),
        (0, I(3.95), 'Submits final\nsession'),

        (1, I(1.55), 'Prompts customer\nfor images'),
        (1, I(2.75), 'Attaches GPS &\ntimestamp to image'),
        (1, I(3.95), 'Uploads batch\nto server'),

        (2, I(1.55), 'OCR · Object\nDetection · Scene'),
        (2, I(2.75), 'Face match &\nlocation check'),
        (2, I(3.95), 'Fraud signals\nscored & flagged'),

        (3, I(1.55), 'Evidence images\nwith labels'),
        (3, I(2.75), 'Fraud flag\nsummary'),
        (3, I(3.95), 'Digital FI report\nfor investigator'),
    ]

    BW = LW - I(0.3); BH = I(0.85)
    for col, y, text in lane_items:
        x = I(0.15) + col * LW + I(0.15)
        bc = [rgb('1565C0'), TEAL, ORANGE, GREEN][col]
        c = shape(sl, RRECT, x, y, BW, BH, WHITE, bc, 1.2)
        txt_in(c, text.split('\n'), fsize=9.5, tc=rgb('37474F'))

    # Vertical arrows within lanes
    for col in range(4):
        x_center = I(0.15) + col * LW + LW/2
        for y_start in [I(2.4), I(3.6)]:
            arrow(sl, x_center, y_start, x_center, y_start + I(0.35),
                  col=[rgb('1565C0'), TEAL, ORANGE, GREEN][col])

    # Horizontal arrows between lanes (row 1, 2, 3)
    for row_y in [I(1.975), I(3.175), I(4.375)]:
        for col in range(3):
            x1 = I(0.15) + col * LW + BW + I(0.15)
            x2 = I(0.15) + (col+1) * LW + I(0.15)
            arrow(sl, x1, row_y, x2, row_y, col=HINT, lw=1.2)

    tb(sl, SW - I(0.5), SH - I(0.28), I(0.4), I(0.25), '8', fsize=9, col=HINT, align=PP_ALIGN.RIGHT)


# ═══════════════════════════════════════════════════════════════════════════════
# Slide 9 — Activity Diagram
# ═══════════════════════════════════════════════════════════════════════════════
def slide_activity(prs):
    sl = new_slide(prs)
    hdr = shape(sl, RECT, I(0), I(0), SW, I(0.62), NAVY)
    tb(sl, I(0.35), I(0.08), I(11), I(0.5), 'Activity Diagram', fsize=22, col=WHITE, bold=True)
    tb(sl, I(0.35), I(0.65), I(11), I(0.3),
       'Execution flow from app open to report generation', fsize=10, col=HINT)

    steps = [
        ('Borrower opens app and fills application details',        NAVY,   rgb('EBF5FF')),
        ('System validates mandatory fields',                       TEAL,   rgb('E6F6F8')),
        ('Start session and lock GPS + time',                       TEAL,   rgb('E6F6F8')),
        ('AI questioning module asks voice prompts',                ORANGE, rgb('FEF3E8')),
        ('Borrower captures required images',                       NAVY,   rgb('EBF5FF')),
        ('Upload images with GPS metadata',                         TEAL,   rgb('E6F6F8')),
        ('AI analysis: GPT-4o Vision + OCR + Face match',          rgb('880E4F'), rgb('FEF0F5')),
        ('Fraud checks and signal scoring',                         RED,    rgb('FFEEEE')),
        ('Generate structured FI report (PDF)',                     ORANGE, rgb('FFF0E8')),
        ('Submit report to lender / LOS',                          NAVY,   rgb('EBF5FF')),
    ]

    CX = SW / 2; BW = I(6.5); BH = I(0.48); gap = I(0.12)
    total_h = len(steps) * (BH + gap)
    start_y = I(0.9)

    # Start node
    sn = shape(sl, OVAL, CX - I(0.55), start_y, I(1.1), I(0.42), NAVY, NAVY)
    txt_in(sn, 'Start', fsize=9, bold=True, tc=WHITE)

    y = start_y + I(0.55)
    for i, (text, bc, fc) in enumerate(steps):
        x = CX - BW/2
        c = shape(sl, RRECT, x, y, BW, BH, fc, bc, 1.0)
        txt_in(c, text, fsize=9, tc=rgb('37474F'))
        if i < len(steps)-1:
            arrow(sl, CX, y + BH, CX, y + BH + gap, col=DGREY, lw=1.2)
        y += BH + gap

    # End node
    en = shape(sl, OVAL, CX - I(0.55), y + I(0.08), I(1.1), I(0.42), NAVY, NAVY)
    txt_in(en, 'End', fsize=9, bold=True, tc=WHITE)
    arrow(sl, CX, y, CX, y + I(0.08), col=DGREY)

    # "More images?" loop annotation
    tb(sl, CX + BW/2 + I(0.1), I(3.5), I(1.5), I(1.2),
       'More\nimages?\n(Yes = loop)', fsize=8, col=ORANGE)
    arrow(sl, CX + BW/2, I(3.72), CX + BW/2 + I(0.08), I(3.72), col=ORANGE)
    arrow(sl, CX + BW/2 + I(1.38), I(3.72), CX + BW/2 + I(1.38), I(2.95), col=ORANGE, lw=1.0)
    arrow(sl, CX + BW/2 + I(1.38), I(2.95), CX + BW/2, I(2.95), col=ORANGE, lw=1.0)

    tb(sl, SW - I(0.5), SH - I(0.28), I(0.4), I(0.25), '9', fsize=9, col=HINT, align=PP_ALIGN.RIGHT)


# ═══════════════════════════════════════════════════════════════════════════════
# Slide 10 — Technology Stack (UPDATED to match actual implementation)
# ═══════════════════════════════════════════════════════════════════════════════
def slide_techstack(prs):
    sl = new_slide(prs)
    hdr = shape(sl, RECT, I(0), I(0), SW, I(0.62), NAVY)
    tb(sl, I(0.35), I(0.08), I(11), I(0.5), 'Technology Stack', fsize=22, col=WHITE, bold=True)
    tb(sl, I(0.35), I(0.65), I(11), I(0.3),
       'Tools, frameworks, and models used in the actual implementation', fsize=10, col=HINT)

    tech = [
        ('Image Analysis',         'GPT-4o Vision for object detection, scene classification, property quality, and income level assessment from photos', rgb('1565C0'), NAVY),
        ('PAN Card OCR',           'GPT-4o Vision (primary) + AWS Textract (fallback) for PAN number, name, father\'s name, and DOB extraction', TEAL,           TEAL),
        ('Face Verification',      'AWS Rekognition — CompareFaces API to match borrower\'s selfie against PAN card photograph', rgb('E65100'),   rgb('E65100')),
        ('Speech-to-Text / TTS',   'AWS Transcribe for voice answer capture; AWS Polly for question audio playback', rgb('2E7D32'),   rgb('2E7D32')),
        ('Mobile Web App',         'HTML5 + TypeScript + Vite; WebSocket API, MediaDevices API (camera/mic), GPS Geolocation API', rgb('1565C0'), NAVY),
        ('Backend Server',         'Python 3.9+ · FastAPI · uvicorn; WebSocket session conductor for real-time Q&A and photo guidance', TEAL,       TEAL),
        ('Report Generation',      'ReportLab PDF; pdfplumber for bank statement analysis; Google Maps Geocoding for GPS reverse lookup', rgb('E65100'), rgb('E65100')),
        ('Deployment',             'AWS EC2 (Ubuntu 22.04); live at dev.videocx.io/fi/ — tested with real loan application sessions', rgb('2E7D32'), rgb('2E7D32')),
    ]

    CW = I(6.05); CH = I(1.15); gap = I(0.15)

    # Top accent colours per row
    acc_colors = [NAVY, TEAL, rgb('E65100'), rgb('2E7D32')]

    for i, (ttitle, ttext, ac, tc) in enumerate(tech):
        row = i // 2; col = i % 2
        x = I(0.25) + col * (CW + gap)
        y = I(1.05) + row * (CH + gap)
        c = shape(sl, RRECT, x, y, CW, CH, WHITE, MGREY, 0.8)
        # Top colour bar
        shape(sl, RECT, x, y, CW, I(0.055), ac)
        tb(sl, x + I(0.15), y + I(0.1), CW - I(0.3), I(0.32),
           ttitle, fsize=10.5, col=tc, bold=True)
        tb(sl, x + I(0.15), y + I(0.44), CW - I(0.3), I(0.62),
           ttext, fsize=8.5, col=DGREY)

    tb(sl, SW - I(0.5), SH - I(0.28), I(0.4), I(0.25), '10', fsize=9, col=HINT, align=PP_ALIGN.RIGHT)


# ═══════════════════════════════════════════════════════════════════════════════
# Slide 11 — Results
# ═══════════════════════════════════════════════════════════════════════════════
def slide_results(prs):
    sl = new_slide(prs)
    hdr = shape(sl, RECT, I(0), I(0), SW, I(0.62), NAVY)
    tb(sl, I(0.35), I(0.08), I(11), I(0.5), 'Results & Performance Metrics', fsize=22, col=WHITE, bold=True)
    tb(sl, I(0.35), I(0.65), I(11), I(0.3),
       'Evaluated on 10 sessions — live deployment at dev.videocx.io/fi/', fsize=10, col=HINT)

    # Headline metric
    hm = shape(sl, RRECT, I(0.25), I(1.0), I(12.83), I(0.75), rgb('EBF5FF'), TEAL, 1.5)
    tb(sl, I(0.5), I(1.07), I(12.5), I(0.6),
       'Average Session Duration:  12.4 minutes    vs    3 – 7 days  (manual field visit)  →  99% reduction in turnaround time',
       fsize=13, col=NAVY, bold=True, align=PP_ALIGN.CENTER)

    # Metrics table
    metrics = [
        ('Session completion rate',      '90%  (9 / 10)',       '~70%  (weather / access)'),
        ('Photo capture success rate',   '94.4%',                'Not tracked'),
        ('PAN OCR success (GPT-4o)',     '80%',                  'N/A  (manual)'),
        ('Face match detection rate',    '70%',                  'N/A  (human eye)'),
        ('GPS location capture rate',    '90%',                  'N/A'),
        ('AI report generation rate',    '100%',                 'Manual only'),
        ('Q&A transcription accuracy',   '85%  (expert review)', '~95%  (human agent)'),
    ]

    # Header row
    h_row = shape(sl, RECT, I(0.25), I(1.9), I(12.83), I(0.42), NAVY)
    for col_x, col_w, col_t in [(I(0.35), I(5.8), 'Metric'), (I(6.4), I(3.2), 'AI System (This Project)'), (I(9.85), I(3.1), 'Manual Process')]:
        txt_s = h_row  # reuse shape for text
        tb(sl, col_x, I(1.95), col_w, I(0.32), col_t, fsize=10, col=WHITE, bold=True)

    for i, (m, ai, mn) in enumerate(metrics):
        y = I(2.32) + i * I(0.54)
        row_bg = rgb('F8FAFC') if i % 2 == 0 else WHITE
        r = shape(sl, RECT, I(0.25), y, I(12.83), I(0.52), row_bg, MGREY, 0.5)
        tb(sl, I(0.35), y + I(0.1), I(5.8), I(0.35), m, fsize=9.5, col=NAVY)
        tb(sl, I(6.4),  y + I(0.1), I(3.2), I(0.35), ai, fsize=9.5, col=GREEN, bold=True, align=PP_ALIGN.CENTER)
        tb(sl, I(9.85), y + I(0.1), I(3.1), I(0.35), mn, fsize=9.5, col=DGREY, align=PP_ALIGN.CENTER)

    tb(sl, SW - I(0.5), SH - I(0.28), I(0.4), I(0.25), '11', fsize=9, col=HINT, align=PP_ALIGN.RIGHT)


# ═══════════════════════════════════════════════════════════════════════════════
# Slide 12 — Project Scope & Outcomes
# ═══════════════════════════════════════════════════════════════════════════════
def slide_scope(prs):
    sl = new_slide(prs)
    hdr = shape(sl, RECT, I(0), I(0), SW, I(0.62), NAVY)
    tb(sl, I(0.35), I(0.08), I(11), I(0.5), 'Project Scope & What We Built', fsize=22, col=WHITE, bold=True)
    tb(sl, I(0.35), I(0.65), I(11), I(0.3),
       'A complete, deployed proof of concept grounded in a real lending workflow', fsize=10, col=HINT)

    # Left: Scope
    tb(sl, I(0.3), I(0.95), I(6.6), I(0.32), 'Project Scope — What Was Built', fsize=11, col=TEAL, bold=True)
    scope_items = [
        'Guided image capture flow for home/residence verification with dynamic property-based photo prompts',
        'Real-time WebSocket session with voice Q&A (AWS Transcribe), TTS (AWS Polly), and live photo review',
        'GPT-4o Vision analysis of all captured photos for property quality, income indicators, and scene classification',
        'PAN card OCR (GPT-4o + Textract) + face match (AWS Rekognition) + name cross-check',
        'GPS consistency validation using haversine distance across all captured photos',
        'Automated PDF credit report with CIBIL score, credit analysis, and bank statement income analysis',
        'Live deployment on AWS EC2 — tested at dev.videocx.io/fi/',
    ]
    for i, item in enumerate(scope_items):
        circ = shape(sl, OVAL, I(0.32), I(1.38) + i * I(0.58), I(0.22), I(0.22), NAVY)
        tb(sl, I(0.65), I(1.35) + i * I(0.58), I(6.1), I(0.4), item, fsize=9, col=DGREY)

    # Right: Skills & Deliverables
    tb(sl, I(7.3), I(0.95), I(5.7), I(0.32), 'Skills Developed', fsize=11, col=TEAL, bold=True)
    skills = [
        ('CV',  'Computer Vision',  'GPT-4o Vision, AWS Textract, Rekognition, image analysis',  NAVY),
        ('ML',  'Applied ML',       'Prompt engineering, model evaluation, error analysis',        TEAL),
        ('AI',  'Real-world AI',    'Fraud detection use case, explainability, workflow design',   ORANGE),
        ('DEV', 'Full Stack Dev',   'TypeScript, FastAPI, WebSocket, AWS services, deployment',   GREEN),
    ]
    for i, (abbr, stitle, stext, sc) in enumerate(skills):
        cx = I(7.3) + (i % 2) * I(2.95); cy = I(1.38) + (i // 2) * I(1.3)
        c = shape(sl, RRECT, cx, cy, I(2.8), I(1.1), WHITE, MGREY, 0.8)
        shape(sl, RECT, cx, cy, I(2.8), I(0.05), sc)
        tb(sl, cx + I(0.12), cy + I(0.1), I(2.55), I(0.32), stitle, fsize=10, col=sc, bold=True)
        tb(sl, cx + I(0.12), cy + I(0.44), I(2.55), I(0.55), stext, fsize=8, col=DGREY)

    tb(sl, I(7.3), I(3.98), I(5.7), I(0.32), 'Deliverables', fsize=11, col=TEAL, bold=True)
    deliverables = [
        'Live deployed system (dev.videocx.io/fi/)',
        'PDF credit report generator',
        'Auditor review portal',
        'Final demo & project report',
    ]
    for i, d in enumerate(deliverables):
        circ = shape(sl, OVAL, I(7.32), I(4.42) + i * I(0.52), I(0.22), I(0.22), ORANGE)
        tb(sl, I(7.65), I(4.4) + i * I(0.52), I(5.2), I(0.36), d, fsize=9.5, col=DGREY)

    tb(sl, SW - I(0.5), SH - I(0.28), I(0.4), I(0.25), '12', fsize=9, col=HINT, align=PP_ALIGN.RIGHT)


# ═══════════════════════════════════════════════════════════════════════════════
# Slide 13 — Thank You
# ═══════════════════════════════════════════════════════════════════════════════
def slide_thankyou(prs):
    sl = new_slide(prs, bg_color=NAVY)

    # Top accent line
    shape(sl, RECT, I(0), I(0), SW, I(0.08), TEAL)

    # Main title
    tb(sl, I(1.0), I(1.2), SW - I(2.0), I(1.5),
       'Thank You', fsize=54, col=WHITE, bold=True, align=PP_ALIGN.CENTER)
    tb(sl, I(1.5), I(2.8), SW - I(3.0), I(0.5),
       'AI-Based Visual Intelligence for Digital Field Investigation',
       fsize=16, col=TEAL, align=PP_ALIGN.CENTER)

    # Divider
    shape(sl, RECT, I(4.5), I(3.4), I(4.33), I(0.025), rgb('2A4A6B'))

    # 3 summary boxes
    summaries = [
        ('Problem',  'Manual field visits are slow, expensive, inconsistent, and fraud-prone'),
        ('Solution', 'Guided image capture + AI analysis replaces the physical field visit'),
        ('Output',   'Explainable fraud flags and structured digital credit report for lenders'),
    ]
    BW = I(3.9); BH = I(1.5)
    for i, (stitle, stext) in enumerate(summaries):
        x = I(0.3) + i * (BW + I(0.26))
        c = shape(sl, RRECT, x, I(3.6), BW, BH, rgb('1E3A5F'), TEAL, 1.0)
        tb(sl, x + I(0.2), I(3.7), BW - I(0.4), I(0.38), stitle, fsize=12, col=TEAL, bold=True, align=PP_ALIGN.LEFT)
        tb(sl, x + I(0.2), I(4.12), BW - I(0.4), I(0.9), stext, fsize=9.5, col=rgb('CBD5E0'), align=PP_ALIGN.LEFT)

    # Authors
    tb(sl, I(0.5), I(5.35), SW - I(1.0), I(0.3),
       'Presented by:', fsize=10, col=HINT, align=PP_ALIGN.CENTER)
    tb(sl, I(0.5), I(5.65), SW - I(1.0), I(0.4),
       'Mr. Shubham Abaso Nale  ·  Mr. Sarvesh Vijay Jadhav  ·  Mr. Suyash Rajendra Kale',
       fsize=13, col=WHITE, bold=True, align=PP_ALIGN.CENTER)
    tb(sl, I(0.5), I(6.1), SW - I(1.0), I(0.28),
       'Guide: Prof. C. K. Saste  |  Dept. of CSE, AGCE Satara  |  DBATU, Lonere  |  2025–26',
       fsize=9.5, col=HINT, align=PP_ALIGN.CENTER)

    # Q&A button
    btn = shape(sl, RRECT, SW/2 - I(1.5), I(6.55), I(3.0), I(0.6), TEAL, TEAL)
    txt_in(btn, 'Questions & Discussion', fsize=12, bold=True, tc=WHITE)


# ═══════════════════════════════════════════════════════════════════════════════
# Build
# ═══════════════════════════════════════════════════════════════════════════════
def build():
    prs = Presentation()
    prs.slide_width  = SW
    prs.slide_height = SH

    print('  Slide 1 — Title')
    slide_title(prs)
    print('  Slide 2 — Agenda')
    slide_agenda(prs)
    print('  Slide 3 — About VideoCX')
    slide_videocx(prs)
    print('  Slide 4 — Problem Statement')
    slide_problem(prs)
    print('  Slide 5 — Proposed Solution')
    slide_solution(prs)
    print('  Slide 6 — System Architecture')
    slide_arch(prs)
    print('  Slide 7 — AI Signals & Fraud Indicators')
    slide_signals(prs)
    print('  Slide 8 — Data Flow Swimlane')
    slide_dataflow(prs)
    print('  Slide 9 — Activity Diagram')
    slide_activity(prs)
    print('  Slide 10 — Technology Stack')
    slide_techstack(prs)
    print('  Slide 11 — Results')
    slide_results(prs)
    print('  Slide 12 — Project Scope & Outcomes')
    slide_scope(prs)
    print('  Slide 13 — Thank You')
    slide_thankyou(prs)

    return prs


if __name__ == '__main__':
    out = r'd:\videocx\trunk\fi-agent\docs\FI_Project_Final_Presentation.pptx'
    os.makedirs(os.path.dirname(out), exist_ok=True)
    print('Building final presentation...')
    prs = build()
    prs.save(out)
    print(f'\nDone!  Saved to: {out}')
    import subprocess
    subprocess.Popen(['start', '', out], shell=True)
