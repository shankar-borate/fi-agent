"""
Rich presentation generator — all slides drawn with matplotlib,
embedded as high-resolution images in PPTX.
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mp
from matplotlib.patches import FancyBboxPatch
from io import BytesIO
from pptx import Presentation
from pptx.util import Inches, Emu
import os

# ── Palette ────────────────────────────────────────────────────────────────────
NAVY   = '#1C3557'
NAVY2  = '#162944'
TEAL   = '#0891B2'
TEAL2  = '#E0F7FA'
ORANGE = '#EA580C'
ORAN2  = '#FFF3EE'
GREEN  = '#16A34A'
GREEN2 = '#DCFCE7'
RED    = '#DC2626'
RED2   = '#FEE2E2'
GOLD   = '#D97706'
PURP   = '#7C3AED'
WHITE  = '#FFFFFF'
LGREY  = '#F8FAFC'
MGREY  = '#E2E8F0'
DGREY  = '#475569'
HINT   = '#94A3B8'
CARD   = '#FAFCFE'

# ── Drawing helpers ─────────────────────────────────────────────────────────────

def new_fig():
    fig, ax = plt.subplots(figsize=(16, 9))
    ax.set_xlim(0, 16); ax.set_ylim(9, 0)
    ax.axis('off')
    ax.set_facecolor(WHITE); fig.patch.set_facecolor(WHITE)
    fig.subplots_adjust(0, 0, 1, 1)
    return fig, ax

def to_png(fig):
    buf = BytesIO()
    fig.savefig(buf, format='png', dpi=180, bbox_inches=None,
                facecolor=fig.get_facecolor())
    buf.seek(0); plt.close(fig); return buf

def R(ax, x, y, w, h, fc, ec='none', lw=0, r=0, z=2, alpha=1):
    if r:
        p = FancyBboxPatch((x, y), w, h, f"round,pad={r}",
                           facecolor=fc, edgecolor=ec, linewidth=lw, alpha=alpha, zorder=z)
    else:
        p = mp.Rectangle((x, y), w, h,
                          facecolor=fc, edgecolor=ec, linewidth=lw, alpha=alpha, zorder=z)
    ax.add_patch(p); return p

def C(ax, cx, cy, radius, fc, ec='none', lw=0, z=4):
    ax.add_patch(mp.Ellipse((cx, cy), radius*2, radius*2,
                             facecolor=fc, edgecolor=ec, linewidth=lw, zorder=z))

def T(ax, x, y, s, fs=10, c=NAVY, ha='left', va='top', bold=False, alpha=1, z=5, wrap_w=None):
    ax.text(x, y, s, fontsize=fs, color=c, ha=ha, va=va,
            fontweight='bold' if bold else 'normal',
            multialignment=ha if ha in ('left','center','right') else 'left',
            wrap=bool(wrap_w), alpha=alpha, zorder=z)

def Arr(ax, x1, y1, x2, y2, c=MGREY, lw=1.8, style='->'):
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle=style, color=c, lw=lw,
                                connectionstyle='arc3,rad=0'))

def header(ax, title, sub=''):
    R(ax, 0, 0, 16, 0.08, TEAL, z=10)           # top teal strip
    R(ax, 0, 0.08, 16, 0.82, NAVY, z=9)          # navy header
    T(ax, 0.4, 0.55, title, 22, WHITE, va='center', bold=True, z=11)
    if sub:
        T(ax, 0.4, 0.92, sub, 10, HINT, va='top', z=11)

def card(ax, x, y, w, h, fc=WHITE, accent=None, shadow=True, r=0.1, ec=MGREY, lw=0.6):
    if shadow:
        R(ax, x+0.04, y+0.04, w, h, '#00000011', r=r, z=1, alpha=0.6)
    R(ax, x, y, w, h, fc, ec, lw, r=r, z=2)
    if accent:
        R(ax, x, y, w, 0.07, accent, r=0, z=3)

def numcircle(ax, cx, cy, n, col=NAVY, r=0.35, fs=14):
    C(ax, cx, cy, r, col, z=6)
    T(ax, cx, cy, str(n), fs, WHITE, ha='center', va='center', bold=True, z=7)

def bar(ax, x, y, w, h, val, tot=100, fg=GREEN, bg=MGREY):
    R(ax, x, y, w, h, bg, r=0.04)
    R(ax, x, y, w*val/tot, h, fg, r=0.04)

def slide_num(ax, n):
    T(ax, 15.65, 8.75, str(n), 9, HINT, ha='right', va='bottom')

# ══════════════════════════════════════════════════════════════════════════════
# Slide 1 — Title
# ══════════════════════════════════════════════════════════════════════════════
def s01_title():
    fig, ax = new_fig()
    # Left panel
    R(ax, 0, 0, 5.8, 9, LGREY)
    R(ax, 5.65, 0, 0.15, 9, TEAL)                  # vertical accent
    R(ax, 0, 0, 5.8, 0.07, NAVY)                   # top dark bar

    # College details
    T(ax, 0.35, 1.8, 'Dr. Babasaheb Ambedkar', 14, NAVY, bold=True)
    T(ax, 0.35, 2.22, 'Technological University, Lonere', 14, NAVY, bold=True)
    T(ax, 0.35, 2.68, 'Arvind Gavali College of Engineering, Satara', 10, DGREY)
    T(ax, 0.35, 3.05, 'Dept. of Computer Science & Engineering', 10.5, NAVY, bold=True)
    R(ax, 0.35, 3.42, 4.9, 0.035, '#BDC8D5')

    T(ax, 0.35, 3.65, 'Presented by:', 10.5, NAVY, bold=True)
    for i, nm in enumerate([
        'Mr. Shubham Abaso Nale  (2265451242070)',
        'Mr. Sarvesh Vijay Jadhav  (23065451242519)',
        'Mr. Suyash Rajendra Kale  (2265451242132)',
    ]):
        T(ax, 0.35, 4.0 + i*0.35, nm, 10, DGREY)
    T(ax, 0.35, 5.2, 'Guide: Prof. C. K. Saste', 11, TEAL, bold=True, z=6)

    # Bottom badge
    R(ax, 0.3, 7.8, 5.1, 0.55, TEAL, r=0.08, z=3)
    T(ax, 2.85, 8.08, 'Industry partner: VideoCX', 10.5, WHITE, ha='center', va='center', bold=True)

    # Right panel — title
    R(ax, 5.8, 0, 10.2, 9, WHITE)
    T(ax, 6.2, 1.3, 'AI-Based Visual', 46, NAVY, bold=True)
    T(ax, 6.2, 2.7, 'Intelligence', 46, NAVY, bold=True)
    T(ax, 6.2, 3.9, 'for Digital Field Investigation', 24, TEAL)
    R(ax, 6.2, 4.55, 9.35, 0.04, MGREY)
    T(ax, 6.2, 4.75, 'Guided image capture  ·  AI visual analysis  ·  Fraud signal detection',
      11, HINT)

    # Tech tags
    tags = ['Computer Vision', 'Optical Character Recognition (OCR)',
            'Face Matching', 'Scene Understanding']
    for i, tag in enumerate(tags):
        tx = 6.2 + (i%2)*4.8; ty = 5.35 + (i//2)*0.75
        card(ax, tx, ty, 4.5, 0.6, WHITE, accent=None, shadow=False, r=0.1, ec=TEAL, lw=1.2)
        T(ax, tx+2.25, ty+0.3, tag, 10.5, TEAL, ha='center', va='center')

    # 2025-26 badge
    T(ax, 13.0, 8.7, '2025–26', 9.5, HINT, ha='right', va='bottom')
    return to_png(fig)

# ══════════════════════════════════════════════════════════════════════════════
# Slide 2 — Agenda
# ══════════════════════════════════════════════════════════════════════════════
def s02_agenda():
    fig, ax = new_fig()
    header(ax, 'Agenda', 'What we\'ll cover in this presentation')

    items = [
        ('01','About VideoCX',          'Company context and industry background',     NAVY),
        ('02','Problem Statement',       'Why manual field investigation fails',        NAVY),
        ('03','Proposed Solution',       'Guided image capture approach',               NAVY),
        ('04','Objectives',              'Project goals and scope',                     NAVY),
        ('05','AI Signals & Fraud Flags','What the AI system detects and flags',        TEAL),
        ('06','System Architecture',     'How the pipeline is structured',              TEAL),
        ('07','Data Flow',               'How data moves through the system',           ORANGE),
        ('08','Technology Stack',        'Tools, frameworks, and models used',          ORANGE),
        ('09','Results & Outcomes',      'Performance metrics and deliverables',        GREEN),
    ]
    W=7.5; H=1.0; GAP=0.15
    for i,(num,ti,sub,ac) in enumerate(items):
        row=i//2; col=i%2
        if len(items)%2==1 and i==len(items)-1:
            x=4.25; col_=0
        else:
            x=0.35+col*(W+0.45)
        y=1.2+row*(H+GAP)
        card(ax,x,y,W,H,WHITE,shadow=True,r=0.08,ec=MGREY,lw=0.5)
        R(ax,x,y,0.07,H,ac,z=4)              # left accent bar
        # Numbered box
        R(ax,x+0.18,y+0.22,0.6,0.56,ac,r=0.06,z=4)
        T(ax,x+0.48,y+0.5,num,11,WHITE,ha='center',va='center',bold=True)
        T(ax,x+0.92,y+0.2,ti,11.5,NAVY,bold=True)
        T(ax,x+0.92,y+0.6,sub,9.5,DGREY)

    slide_num(ax,2)
    return to_png(fig)

# ══════════════════════════════════════════════════════════════════════════════
# Slide 3 — About VideoCX
# ══════════════════════════════════════════════════════════════════════════════
def s03_videocx():
    fig,ax=new_fig()
    header(ax,'About VideoCX','Industry partner driving this project')

    T(ax,0.35,1.12,'VideoCX is a technology company working on digital customer interaction and',11,NAVY)
    T(ax,0.35,1.45,'verification workflows for lending and financial services.',11,NAVY)
    T(ax,0.35,1.9,'The company focuses on solutions that help institutions perform critical processes — customer',11,DGREY)
    T(ax,0.35,2.25,'onboarding, video-based verification, and investigation journeys — in a digital, scalable way.',11,DGREY)

    # Proposal box
    R(ax,0.3,2.8,8.8,1.55,TEAL2,ec=TEAL,lw=1.2,r=0.1,z=2)
    R(ax,0.3,2.8,0.07,1.55,TEAL,z=4)
    T(ax,0.55,3.03,'Proposal Summary',10.5,NAVY,bold=True)
    T(ax,0.55,3.38,'This project explores how guided image capture and AI-based visual analysis can support',9.5,DGREY)
    T(ax,0.55,3.7,'digital field investigation — extracting visual evidence and identifying fraud indicators.',9.5,DGREY)
    T(ax,0.55,4.0,'Deployed live at dev.videocx.io/fi/ with real loan application sessions.',9.5,TEAL,bold=True)

    # Right cards
    info=[
        ('Project Nature','College project  /  internship problem statement',TEAL),
        ('Primary Domain','AI · Computer Vision · OCR · Visual Verification · Fraud Detection',NAVY),
        ('Aligned with','Real lending workflows — loan origination & field verification',ORANGE),
    ]
    for i,(ct,cv,cc) in enumerate(info):
        cy=1.1+i*1.85
        card(ax,9.3,cy,6.3,1.55,WHITE,shadow=True,r=0.1,ec=MGREY)
        C(ax,9.85,cy+0.78,0.42,cc,z=5)
        # icon letter
        icon=['N','D','A'][i]
        T(ax,9.85,cy+0.78,icon,11,WHITE,ha='center',va='center',bold=True)
        T(ax,10.45,cy+0.38,ct,11,cc,bold=True)
        T(ax,10.45,cy+0.72,cv,9.5,DGREY,wrap_w=4.5)

    slide_num(ax,3)
    return to_png(fig)

# ══════════════════════════════════════════════════════════════════════════════
# Slide 4 — Problem Statement
# ══════════════════════════════════════════════════════════════════════════════
def s04_problem():
    fig,ax=new_fig()
    header(ax,'Problem Statement','Field investigation is a slow, expensive, manual bottleneck in lending')

    probs=[
        (RED,'Slow & Costly',
         'Physical visits delay loans by 3–7 days. Agent travel, scheduling, and manual report filing add high per-case cost.',RED2),
        (ORANGE,'Inconsistent Reports',
         'Each agent applies different standards — no structured checklist, no uniform photo requirements, no consistent fraud checks.',ORAN2),
        (NAVY,'High Fraud Risk',
         'Borrowers may present the wrong person, use a borrowed location, or show premises unrelated to the declared loan purpose.',TEAL2),
    ]
    for i,(ac,pt,pb,bg) in enumerate(probs):
        y=1.1+i*1.65
        card(ax,0.3,y,8.8,1.45,bg,shadow=True,r=0.1,ec=ac,lw=1.2)
        R(ax,0.3,y,0.1,1.45,ac,z=4)
        C(ax,1.05,y+0.72,0.44,ac,z=5)
        T(ax,1.75,y+0.28,pt,11.5,ac,bold=True)
        T(ax,1.75,y+0.62,pb,9.5,DGREY,wrap_w=6.5)

    # Right panel
    T(ax,9.5,1.1,'Target Use Cases',11,TEAL,bold=True)
    for i,uc in enumerate(['  Shop Verification','  Workplace Verification','  Residence Verification']):
        cy=1.5+i*0.82
        card(ax,9.4,cy,6.15,0.68,WHITE,shadow=False,r=0.08,ec=MGREY)
        C(ax,9.7,cy+0.34,0.24,TEAL,z=5)
        T(ax,10.1,cy+0.34,uc,10.5,NAVY,va='center')

    T(ax,9.5,4.0,'Fraud Risk Indicators',11,RED,bold=True)
    flags=['Wrong person present at the site',
           'Fake or borrowed location used',
           'Mismatch — declared vs. observed premises']
    for i,f in enumerate(flags):
        C(ax,9.65,4.45+i*0.52,0.14,RED,z=5)
        T(ax,9.92,4.44+i*0.52,f,9.5,DGREY)

    slide_num(ax,4)
    return to_png(fig)

# ══════════════════════════════════════════════════════════════════════════════
# Slide 5 — Proposed Solution
# ══════════════════════════════════════════════════════════════════════════════
def s05_solution():
    fig,ax=new_fig()
    header(ax,'Proposed Solution','Guided capture · AI analysis · Fraud detection · Structured output')

    steps=[
        ('1','Guided\nCapture',    'Borrower captures images during a structured digital session',NAVY),
        ('2','Timestamp\n& GPS',   'Each image tagged with session time and GPS coordinates',     TEAL),
        ('3','AI Analysis',        'GPT-4o Vision: object detection, OCR, scene classification, face match', '#7C3AED'),
        ('4','Fraud\nChecks',      'GPS validates address. Face match detects wrong person. Scene flags mismatch', ORANGE),
        ('5','Structured\nOutput', 'PDF credit report with CIBIL score, fraud flags, and recommendation', GREEN),
    ]
    BW=2.8; BH=5.2
    for i,(n,st,sb,ac) in enumerate(steps):
        x=0.3+i*(BW+0.25)
        card(ax,x,1.1,BW,BH,WHITE,shadow=True,r=0.12,ec=ac,lw=1.0)
        R(ax,x,1.1,BW,0.06,ac,z=4)
        # Number circle
        numcircle(ax,x+BW/2,1.65,n,ac,0.42,16)
        T(ax,x+BW/2,2.4,st,12,ac,ha='center',va='top',bold=True)
        # Body
        words=sb.split()
        lines=[]; cur=''
        for w in words:
            if len(cur+' '+w)<28:
                cur=(cur+' '+w).strip()
            else:
                lines.append(cur); cur=w
        lines.append(cur)
        for j,ln in enumerate(lines[:5]):
            T(ax,x+BW/2,3.3+j*0.38,ln,9,DGREY,ha='center')
        if i<4:
            Arr(ax,x+BW+0.06,1.1+BH/2,x+BW+0.2,1.1+BH/2,MGREY,1.5)

    # Benefits strip
    R(ax,0.3,6.55,15.4,0.85,TEAL2,ec=TEAL,lw=0.8,r=0.1,z=2)
    bens=['Lower bandwidth than full-video AI',
          'Human-reviewable evidence with timestamps',
          'Full audit trail — explainable outputs']
    for i,b in enumerate(bens):
        C(ax,1.0+i*5.15,6.97,0.17,GREEN,z=5)
        T(ax,1.28+i*5.15,6.96,b,10,NAVY,va='center')

    slide_num(ax,5)
    return to_png(fig)

# ══════════════════════════════════════════════════════════════════════════════
# Slide 6 — System Architecture
# ══════════════════════════════════════════════════════════════════════════════
def s06_arch():
    fig,ax=new_fig()
    header(ax,'System Architecture','Six-layer pipeline from mobile capture to lender report')

    # Row 1
    r1=[
        ('#EBF5FF','#1565C0','Borrower\nMobile App',    'Guided capture\nGPS + timestamp\nOTP · Form · Camera'),
        ('#EBF5FF','#1565C0','FastAPI Server\n(API GW)','WebSocket /fi/ws/\nREST /fi/api/\nSession management'),
        (ORAN2,    ORANGE,   'Session\nConductor',      'Q&A · Photo prompts\nCountdown · PAN OCR\nConsent flow'),
        ('#FEF0F5','#880E4F','AI Analysis\nEngine',     'GPT-4o Vision\nAWS Textract\nAWS Rekognition'),
        ('#FFEEEE',RED,      'Fraud Rules',              'Mismatch checks\nRisk flags\nScoring'),
    ]
    BW=2.8; BH=1.95
    for i,(fc,bc,bt,bs) in enumerate(r1):
        x=0.35+i*(BW+0.27)
        card(ax,x,1.05,BW,BH,fc,shadow=True,r=0.1,ec=bc,lw=1.3)
        R(ax,x,1.05,BW,0.07,bc,z=4)
        T(ax,x+BW/2,1.72,bt,10.5,bc,ha='center',va='center',bold=True)
        R(ax,x+0.2,2.12,BW-0.4,0.03,'#D0D0D0',z=4)
        for j,ln in enumerate(bs.split('\n')):
            T(ax,x+BW/2,2.28+j*0.34,ln,9,DGREY,ha='center')
        if i<4:
            Arr(ax,x+BW+0.04,1.05+BH/2,x+BW+0.24,1.05+BH/2,'#B0BEC5',1.6)

    # Row 2
    r2=[
        (GREEN2,GREEN, 'Data Storage',      'App data · Session records\nPhotos · AI outputs',  1.6),
        ('#FFF8E1',GOLD,'Report Generator',  'CIBIL · Credit analysis\nReportLab PDF · JSON',   5.5),
        ('#FFEEEE',RED, 'Lender / LOS',     'Report review\nLoan decision support\nAuditor Portal',9.5),
    ]
    BW2=4.5; BH2=2.0
    for fc,bc,bt,bs,x in r2:
        card(ax,x,3.6,BW2,BH2,fc,shadow=True,r=0.1,ec=bc,lw=1.3)
        R(ax,x,3.6,BW2,0.07,bc,z=4)
        T(ax,x+BW2/2,4.2,bt,11,bc,ha='center',bold=True)
        R(ax,x+0.3,4.6,BW2-0.6,0.03,'#D0D0D0',z=4)
        for j,ln in enumerate(bs.split('\n')):
            T(ax,x+BW2/2,4.8+j*0.38,ln,9,DGREY,ha='center')

    # Arrows down
    Arr(ax,2.75,3.0,3.85,3.6,'#78909C',1.5)     # API→Storage
    Arr(ax,8.5,3.0,7.75,3.6,'#78909C',1.5)      # Session→Report
    Arr(ax,10.6,3.0,11.5,3.6,'#78909C',1.5,style='->')  # AI→Report
    Arr(ax,6.1,4.6,5.5+4.5,4.6,'#78909C',1.5)  # Storage→Report
    Arr(ax,14.0,4.6,14.0,4.6,'#78909C',1.5)

    # Footer
    R(ax,0.35,5.82,15.3,0.72,TEAL2,ec=TEAL,lw=0.8,r=0.08,z=2)
    T(ax,0.7,6.18,'The AI module adapts prompts based on loan details, previous answers, GPS status, and image signals — making digital field investigation smarter and more efficient.',
      9.5,NAVY)

    slide_num(ax,6)
    return to_png(fig)

# ══════════════════════════════════════════════════════════════════════════════
# Slide 7 — AI Signals
# ══════════════════════════════════════════════════════════════════════════════
def s07_signals():
    fig,ax=new_fig()
    header(ax,'AI Signals & Fraud Indicators','Explainable output: what was seen, what was read, what was flagged')

    signals=[
        ('OCR / Signage',        'Read shop names, nameplate text,\nPAN fields, and visible labels',       TEAL),
        ('Inventory & Context',  'Estimate visible stock, goods,\nor business activity present',           '#7C3AED'),
        ('People Presence',      'Check whether staff or relevant\npeople are visible at the site',        NAVY),
        ('Scene Understanding',  'GPT-4o Vision classifies location\nas shop, office, or residence',       ORANGE),
        ('Face Match',           'AWS Rekognition compares selfie\nagainst PAN card photograph',           RED),
        ('Location Consistency', 'GPS validated — all photos within\n500m radius of declared address',     GREEN),
    ]
    CW=4.85; CH=1.5
    for i,(st,sb,sc) in enumerate(signals):
        row=i//3; col=i%3
        x=0.35+col*(CW+0.28); y=1.12+row*(CH+0.22)
        card(ax,x,y,CW,CH,WHITE,shadow=True,r=0.1,ec=sc,lw=0.8)
        R(ax,x,y,CW,0.07,sc,z=4)
        C(ax,x+0.55,y+CH/2,0.38,sc,z=5)
        T(ax,x+0.55,y+CH/2,'✓',11,WHITE,ha='center',va='center',bold=True,z=6)
        T(ax,x+1.15,y+0.25,st,11,NAVY,bold=True)
        for j,ln in enumerate(sb.split('\n')):
            T(ax,x+1.15,y+0.65+j*0.33,ln,9.5,DGREY)

    # Fraud flags
    R(ax,0.35,4.48,15.3,1.88,RED2,ec=RED,lw=1.0,r=0.1,z=2)
    T(ax,0.65,4.68,'⚑  Example Fraud Flags',11.5,RED,bold=True)
    flags=[
        'Face visible in captured image does not match borrower\'s reference identity on PAN card',
        'GPS metadata or visual context does not match the declared address or business type',
        'Environment (shop, residence, office) does not match the declared loan purpose',
    ]
    for i,f in enumerate(flags):
        C(ax,0.7,5.18+i*0.44,0.13,RED,z=5)
        T(ax,0.96,5.17+i*0.44,f,10,NAVY)

    slide_num(ax,7)
    return to_png(fig)

# ══════════════════════════════════════════════════════════════════════════════
# Slide 8 — Data Flow Swimlane
# ══════════════════════════════════════════════════════════════════════════════
def s08_dataflow():
    fig,ax=new_fig()
    header(ax,'Data Flow at Different Components','How information moves through the digital field investigation system')

    lanes=[
        ('Borrower',    NAVY,   '#E8EDF4'),
        ('Mobile App',  TEAL,   '#E6F7FA'),
        ('AI Backend',  ORANGE, '#FEF3E8'),
        ('Output Layer',GREEN,  '#EDFAF3'),
    ]
    LW=3.8; LH=7.1
    for i,(ln,lc,lbg) in enumerate(lanes):
        x=0.3+i*LW
        R(ax,x,0.92,LW,0.65,lc)
        T(ax,x+LW/2,1.24,ln,12,WHITE,ha='center',va='center',bold=True)
        R(ax,x,1.57,LW,LH-1.55,lbg,z=1)

    # Items per lane [col, y, text]
    items=[
        (0,1.8,'Starts guided\nverification session'),
        (0,3.05,'Captures images\non prompt'),
        (0,4.3,'Submits final\nsession'),
        (1,1.8,'Prompts customer\nfor images'),
        (1,3.05,'Attaches GPS &\ntimestamp to image'),
        (1,4.3,'Uploads batch\nto server'),
        (2,1.8,'GPT-4o Vision\nOCR · Scene · Objects'),
        (2,3.05,'Face match &\nlocation check'),
        (2,4.3,'Fraud signals\nscored & flagged'),
        (3,1.8,'Evidence images\nwith AI labels'),
        (3,3.05,'Fraud flag\nsummary'),
        (3,4.3,'Digital FI report\nfor investigator'),
    ]
    BW=3.3; BH=1.0
    colors=[NAVY,TEAL,ORANGE,GREEN]
    for col,y,txt_ in items:
        x=0.3+col*LW+0.25
        card(ax,x,y,BW,BH,WHITE,shadow=True,r=0.1,ec=colors[col],lw=1.0)
        for j,ln in enumerate(txt_.split('\n')):
            T(ax,x+BW/2,y+0.25+j*0.4,ln,9.5,DGREY,ha='center')

    # Down arrows within lanes
    for col in range(4):
        xc=0.3+col*LW+0.25+BW/2
        for ya in [2.8,4.05]:
            Arr(ax,xc,ya,xc,ya+0.25,colors[col],1.3)

    # Horizontal arrows across lanes
    for row_y in [2.3,3.55,4.8]:
        for col in range(3):
            x1=0.3+col*LW+0.25+BW
            x2=0.3+(col+1)*LW+0.25
            Arr(ax,x1,row_y,x2,row_y,HINT,1.2)

    # Legend strip
    R(ax,0.3,5.65,15.4,0.65,LGREY,ec=MGREY,lw=0.5,r=0.06,z=2)
    legend=[('Process',WHITE,colors[0]),('Store',WHITE,colors[2]),
            ('External Entity',WHITE,colors[3])]
    for i,(lbl,fc,bc) in enumerate(legend):
        x=1.2+i*4.5
        card(ax,x,5.77,2.0,0.42,fc,shadow=False,r=0.06,ec=bc,lw=1.0)
        T(ax,x+1.0,5.98,lbl,9,bc,ha='center',va='center')

    slide_num(ax,8)
    return to_png(fig)

# ══════════════════════════════════════════════════════════════════════════════
# Slide 9 — Activity Diagram
# ══════════════════════════════════════════════════════════════════════════════
def s09_activity():
    fig,ax=new_fig()
    header(ax,'Activity Diagram','Session execution flow with decision gates and loops')

    acts=[
        ('Borrower opens app and fills application details',        '#EBF5FF','#1565C0'),
        ('System validates mandatory fields',                       TEAL2,    TEAL),
        ('Start session and lock GPS + time',                       TEAL2,    TEAL),
        ('AI questioning module asks voice prompts',                ORAN2,    ORANGE),
        ('Borrower captures required images',                       '#EBF5FF','#1565C0'),
        ('Upload images with GPS metadata to server',               TEAL2,    TEAL),
        ('AI analysis: GPT-4o Vision + OCR + Face match',          '#FEF0F5','#880E4F'),
        ('Fraud checks and signal scoring',                         RED2,     RED),
        ('Generate structured PDF FI report',                       ORAN2,    ORANGE),
        ('Submit report to Lender / LOS',                          '#EBF5FF','#1565C0'),
    ]
    CX=8.0; BW=7.5; BH=0.53; GAP=0.13
    TotalH=len(acts)*(BH+GAP)
    # Start node
    C(ax,CX,1.08,0.35,NAVY,z=6)
    T(ax,CX,1.08,'▶',11,WHITE,ha='center',va='center',bold=True)
    T(ax,CX,1.08,'  Start',10,NAVY,ha='center',va='center')

    y=1.55
    for i,(act,fc,bc) in enumerate(acts):
        card(ax,CX-BW/2,y,BW,BH,fc,shadow=True,r=0.08,ec=bc,lw=0.9)
        T(ax,CX,y+BH/2,act,9.5,DGREY,ha='center',va='center')
        if i<len(acts)-1:
            Arr(ax,CX,y+BH,CX,y+BH+GAP,'#90A4AE',1.3)
        y+=BH+GAP

    # End node
    C(ax,CX,y+0.2,0.35,NAVY,z=6)
    T(ax,CX,y+0.2,'◼',11,WHITE,ha='center',va='center',bold=True)

    # Loop annotation
    loop_x=CX+BW/2+0.15
    Arr(ax,loop_x,2.75,loop_x+0.8,2.75,ORANGE,1.2)
    R(ax,loop_x+0.8,2.2,1.5,1.5,ORAN2,ec=ORANGE,lw=0.8,r=0.08)
    T(ax,loop_x+1.55,2.56,'More\nimages?\n(Yes=loop)',9,ORANGE,ha='center')
    Arr(ax,loop_x+0.8,2.75,loop_x+0.8,2.21,ORANGE,1.2)
    Arr(ax,loop_x+0.8,2.21,loop_x,2.21,ORANGE,1.2)

    # Left notes
    notes=[
        (1.55,'Open app'),
        (2.08,'Validate form'),
        (2.61,'GPS session'),
        (3.14,'Voice Q&A'),
        (3.67,'Capture'),
        (4.2,'Upload'),
        (4.73,'AI pipeline'),
        (5.26,'Fraud check'),
        (5.79,'PDF report'),
        (6.32,'Submit'),
    ]
    for ny,nl in notes:
        T(ax,0.3,ny+BH/2,nl,8,HINT,va='center')

    slide_num(ax,9)
    return to_png(fig)

# ══════════════════════════════════════════════════════════════════════════════
# Slide 10 — Technology Stack
# ══════════════════════════════════════════════════════════════════════════════
def s10_tech():
    fig,ax=new_fig()
    header(ax,'Technology Stack','Actual tools and frameworks used in the deployed implementation')

    tech=[
        ('Image Analysis',      'GPT-4o Vision — object detection,\nscene classification, income level\nassessment from property photos', '#1565C0', '#EBF5FF'),
        ('PAN Card OCR',        'GPT-4o Vision (primary) + AWS\nTextract (fallback) — PAN number,\nname, DOB extraction',              TEAL,      TEAL2),
        ('Face Verification',   'AWS Rekognition — CompareFaces\nAPI — selfie vs PAN card photo\nwith similarity scoring',             ORANGE,    ORAN2),
        ('Voice Q&A',           'AWS Transcribe (speech-to-text)\n+ AWS Polly (text-to-speech)\nfor real-time voice interaction',      GREEN,     GREEN2),
        ('Mobile Web App',      'HTML5 + TypeScript + Vite\nWebSocket · MediaDevices API\nGPS Geolocation API',                       NAVY,      '#EBF5FF'),
        ('Backend Server',      'Python 3.9 + FastAPI + uvicorn\nWebSocket session conductor\nAsync AI pipeline',                     '#7C3AED',  '#F3E8FF'),
        ('Report Generation',   'ReportLab PDF · pdfplumber\nGoogle Maps Geocoding\nBank statement income analysis',                  ORANGE,    ORAN2),
        ('Deployment',          'AWS EC2 Ubuntu 22.04\nLive at dev.videocx.io/fi/\nTested with real sessions',                        GREEN,     GREEN2),
    ]
    CW=7.55; CH=1.55; GAP=0.2
    for i,(tt,td,ac,bg) in enumerate(tech):
        row=i//2; col=i%2
        x=0.3+col*(CW+0.3); y=1.08+row*(CH+GAP)
        card(ax,x,y,CW,CH,bg,shadow=True,r=0.1,ec=ac,lw=1.0)
        R(ax,x,y,CW,0.07,ac,z=4)
        # Coloured left badge
        R(ax,x,y,0.55,CH,ac,z=3)
        # Title
        T(ax,x+0.72,y+0.22,tt,11,ac,bold=True)
        # Badge letter
        T(ax,x+0.28,y+CH/2,tt[0],14,WHITE,ha='center',va='center',bold=True,z=5)
        for j,ln in enumerate(td.split('\n')):
            T(ax,x+0.72,y+0.6+j*0.3,ln,9,DGREY)

    slide_num(ax,10)
    return to_png(fig)

# ══════════════════════════════════════════════════════════════════════════════
# Slide 11 — Results
# ══════════════════════════════════════════════════════════════════════════════
def s11_results():
    fig,ax=new_fig()
    header(ax,'Results & Performance Metrics','Evaluated on 10 live sessions at dev.videocx.io/fi/')

    # Hero metric
    R(ax,0.3,1.05,15.4,1.05,NAVY,r=0.1,z=2)
    T(ax,8.0,1.35,'Average Session Duration:  12.4 minutes   vs   3-7 days (manual)',
      16,WHITE,ha='center',va='center',bold=True,z=3)
    T(ax,8.0,1.85,'99% reduction in turnaround time',
      11,TEAL,ha='center',va='center',z=3)

    # Metrics with visual bars
    metrics=[
        ('Session Completion Rate',   90,'',  GREEN),
        ('Photo Capture Success',      94,'',  GREEN),
        ('PAN OCR Success (GPT-4o)',   80,'',  TEAL),
        ('Face Match Detection',       70,'',  ORANGE),
        ('GPS Location Capture',       90,'',  GREEN),
        ('AI Report Generation',      100,'',  GREEN),
        ('Q&A Transcription Accuracy', 85,'',  TEAL),
    ]

    # Header row
    R(ax,0.3,2.28,15.4,0.5,NAVY,r=0.0,z=2)
    T(ax,0.55,2.53,'Metric',10.5,WHITE,bold=True,va='center',z=3)
    T(ax,8.5,2.53,'AI System',10.5,WHITE,bold=True,ha='center',va='center',z=3)
    T(ax,11.2,2.53,'Score',10.5,WHITE,bold=True,ha='center',va='center',z=3)
    T(ax,14.0,2.53,'Manual Process',10.5,WHITE,bold=True,ha='center',va='center',z=3)

    manual=[
        '~70%', 'Not tracked', 'N/A', 'N/A', 'N/A', 'Manual only', '~95%'
    ]
    for i,(m,v,_,c) in enumerate(metrics):
        y=2.78+i*0.72
        bg=LGREY if i%2==0 else WHITE
        R(ax,0.3,y,15.4,0.7,bg,ec=MGREY,lw=0.4,z=1)
        T(ax,0.55,y+0.35,m,9.5,NAVY,va='center')
        # Progress bar
        bar(ax,7.0,y+0.22,4.5,0.25,v,100,c,MGREY)
        T(ax,11.7,y+0.35,f'{v}%',11,c,bold=True,ha='center',va='center')
        T(ax,14.3,y+0.35,manual[i],9.5,DGREY,ha='center',va='center')

    slide_num(ax,11)
    return to_png(fig)

# ══════════════════════════════════════════════════════════════════════════════
# Slide 12 — Project Scope
# ══════════════════════════════════════════════════════════════════════════════
def s12_scope():
    fig,ax=new_fig()
    header(ax,'Project Scope & What We Built','Complete, deployed proof of concept on a real lending workflow')

    # Left: what was built
    T(ax,0.35,1.05,'What Was Built',11.5,TEAL,bold=True)
    scope=[
        'Guided image capture flow with dynamic property-based photo prompts',
        'Real-time WebSocket session: voice Q&A (AWS Transcribe), TTS (AWS Polly)',
        'GPT-4o Vision analysis of all photos for quality, income, scene classification',
        'PAN OCR (GPT-4o+Textract) + face match (AWS Rekognition) + name cross-check',
        'GPS consistency validation — haversine distance across all captured photos',
        'Automated PDF credit report: CIBIL score, credit analysis, bank statement',
        'Live deployment on AWS EC2 at dev.videocx.io/fi/',
    ]
    for i,s in enumerate(scope):
        C(ax,0.55,1.52+i*0.6,0.16,NAVY,z=5)
        T(ax,0.83,1.51+i*0.6,s,9.5,DGREY)

    # Right top: Skills grid
    T(ax,9.2,1.05,'Skills Developed',11.5,TEAL,bold=True)
    skills=[
        ('CV','Computer Vision','GPT-4o Vision, OCR, Rekognition',NAVY),
        ('ML','Applied ML','Prompt engineering, evaluation',TEAL),
        ('AI','Real-world AI','Fraud detection, explainability',ORANGE),
        ('DEV','Full Stack Dev','TypeScript, FastAPI, AWS, Deploy',GREEN),
    ]
    for i,(ab,st,sd,sc) in enumerate(skills):
        cx=9.2+(i%2)*3.25; cy=1.45+(i//2)*1.45
        card(ax,cx,cy,3.0,1.25,WHITE,shadow=True,r=0.1,ec=sc,lw=0.8)
        R(ax,cx,cy,3.0,0.06,sc,z=4)
        C(ax,cx+0.5,cy+0.62,0.32,sc,z=5)
        T(ax,cx+0.5,cy+0.62,ab,9,WHITE,ha='center',va='center',bold=True,z=6)
        T(ax,cx+1.05,cy+0.3,st,10,sc,bold=True)
        T(ax,cx+1.05,cy+0.65,sd,8.5,DGREY)

    # Right bottom: Deliverables
    T(ax,9.2,4.55,'Deliverables',11.5,TEAL,bold=True)
    delivs=[
        'Live deployed system (dev.videocx.io/fi/)',
        'Automated PDF credit report generator',
        'Auditor review portal for bankers',
        'Complete project report + this presentation',
    ]
    for i,d in enumerate(delivs):
        C(ax,9.35,4.98+i*0.52,0.15,ORANGE,z=5)
        T(ax,9.62,4.97+i*0.52,d,10,DGREY)

    slide_num(ax,12)
    return to_png(fig)

# ══════════════════════════════════════════════════════════════════════════════
# Slide 13 — Thank You
# ══════════════════════════════════════════════════════════════════════════════
def s13_thanks():
    fig,ax=new_fig()
    R(ax,0,0,16,9,NAVY2)
    R(ax,0,0,16,0.1,TEAL)
    R(ax,0,8.9,16,0.1,TEAL)

    # Decorative circles
    C(ax,-1.5,0.5,3.0,'#1E3A5F',z=1)
    C(ax,17.5,8.5,3.0,'#1E3A5F',z=1)

    T(ax,8.0,2.1,'Thank You',56,WHITE,ha='center',bold=True)
    T(ax,8.0,3.45,'AI-Based Visual Intelligence for Digital Field Investigation',17,TEAL,ha='center')
    R(ax,4.5,4.0,7.0,0.04,'#2A4A6B',z=3)

    # 3 summary cards
    summaries=[
        ('Problem','Manual field visits: slow, expensive,\ninconsistent, and fraud-prone',RED),
        ('Solution','Guided capture + AI analysis\nreplaces the physical field visit',TEAL),
        ('Output','Structured PDF credit report +\nexplainable fraud flags for lenders',GREEN),
    ]
    for i,(st,sb,sc) in enumerate(summaries):
        x=0.5+i*5.15
        card(ax,x,4.35,4.8,1.9,'#1E3A5F',shadow=False,r=0.12,ec=sc,lw=1.2)
        R(ax,x,4.35,4.8,0.07,sc,z=4)
        T(ax,x+0.2,4.62,st,11,sc,bold=True)
        for j,ln in enumerate(sb.split('\n')):
            T(ax,x+0.2,5.05+j*0.42,ln,9.5,'#CBD5E0')

    T(ax,8.0,6.55,'Presented by:',10,HINT,ha='center')
    T(ax,8.0,6.9,'Mr. Shubham Abaso Nale  ·  Mr. Sarvesh Vijay Jadhav  ·  Mr. Suyash Rajendra Kale',
      13,WHITE,ha='center',bold=True)
    T(ax,8.0,7.32,'Guide: Prof. C. K. Saste  |  Dept. of CSE, AGCE Satara  |  DBATU, Lonere  |  2025–26',
      10,HINT,ha='center')

    # Q&A button
    R(ax,5.8,7.72,4.4,0.75,TEAL,r=0.1,z=3)
    T(ax,8.0,8.1,'Questions & Discussion',12,WHITE,ha='center',va='center',bold=True,z=4)

    return to_png(fig)

# ══════════════════════════════════════════════════════════════════════════════
# Build PPTX
# ══════════════════════════════════════════════════════════════════════════════

SLIDES = [
    ('Slide 1  — Title',              s01_title),
    ('Slide 2  — Agenda',             s02_agenda),
    ('Slide 3  — About VideoCX',      s03_videocx),
    ('Slide 4  — Problem Statement',  s04_problem),
    ('Slide 5  — Proposed Solution',  s05_solution),
    ('Slide 6  — System Architecture',s06_arch),
    ('Slide 7  — AI Signals',         s07_signals),
    ('Slide 8  — Data Flow',          s08_dataflow),
    ('Slide 9  — Activity Diagram',   s09_activity),
    ('Slide 10 — Technology Stack',   s10_tech),
    ('Slide 11 — Results',            s11_results),
    ('Slide 12 — Project Scope',      s12_scope),
    ('Slide 13 — Thank You',          s13_thanks),
]

def build():
    prs = Presentation()
    prs.slide_width  = Inches(16)
    prs.slide_height = Inches(9)

    for label, fn in SLIDES:
        print(f'  {label}')
        img = fn()
        sl  = prs.slides.add_slide(prs.slide_layouts[6])
        sl.shapes.add_picture(img, 0, 0, Inches(16), Inches(9))

    return prs

if __name__ == '__main__':
    out = r'd:\videocx\trunk\fi-agent\docs\FI_Project_Final_Presentation_Rich.pptx'
    os.makedirs(os.path.dirname(out), exist_ok=True)
    print('Generating rich presentation...')
    prs = build()
    prs.save(out)
    print(f'\nDone! Saved to: {out}')
    import subprocess
    subprocess.Popen(['start', '', out], shell=True)
