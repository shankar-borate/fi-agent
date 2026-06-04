"""
Export all 6 project diagrams to a PowerPoint file — one diagram per slide.
Run: python generate_ppt.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

# Import all diagram generators from the report script
from generate_report import (
    make_arch, make_flowchart, make_dfd,
    make_activity, make_ui_mockup, make_ai_output,
)

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from io import BytesIO

SLIDE_W = Inches(13.33)   # widescreen 16:9
SLIDE_H = Inches(7.5)

TITLE_H     = Inches(0.60)
IMG_TOP     = Inches(0.75)
IMG_H       = Inches(6.55)
IMG_W       = Inches(12.5)
IMG_LEFT    = (SLIDE_W - IMG_W) / 2

TITLE_COLOR = RGBColor(0x1a, 0x23, 0x7e)
BG_COLOR    = RGBColor(0xFA, 0xFA, 0xFC)

slides_info = [
    ("Figure 1 — System Architecture",
     "Six-layer architecture: Mobile Web App → FastAPI → Session Conductor → AI Engine → Report Generator → Storage",
     make_arch),
    ("Figure 2 — Application Flowchart",
     "End-to-end user flow: OTP → Form → FI Session → Q&A → Photo Capture → PAN → Submit → Report",
     make_flowchart),
    ("Figure 3 — Data Flow Diagram (Level 0 + Level 1)",
     "Context diagram and process decomposition showing data flow from Borrower through the FI System to Lender/LOS",
     make_dfd),
    ("Figure 4 — Activity Diagram",
     "Session activity flow with decision gates for form completion, question loop, and photo capture loop",
     make_activity),
    ("Figure 5 — Application Screenshots",
     "Loan Application Form · FI Session Recording screen · Photo Review screen (simulated mobile UI)",
     make_ui_mockup),
    ("Figure 6 — AI Analysis Output",
     "Sample credit report summary: Credit Score, CIBIL Score, Recommendation, and four assessment panels",
     make_ai_output),
]

def make_ppt():
    prs = Presentation()
    prs.slide_width  = SLIDE_W
    prs.slide_height = SLIDE_H

    blank_layout = prs.slide_layouts[6]  # completely blank

    for title_text, subtitle_text, diagram_fn in slides_info:
        print(f"  Generating: {title_text}")

        slide = prs.slides.add_slide(blank_layout)

        # Background
        bg = slide.background
        fill = bg.fill
        fill.solid()
        fill.fore_color.rgb = BG_COLOR

        # Title bar rectangle
        title_box = slide.shapes.add_textbox(
            Inches(0.2), Inches(0.05), Inches(12.93), TITLE_H
        )
        tf = title_box.text_frame
        tf.word_wrap = False
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = title_text
        run.font.name  = 'Calibri'
        run.font.size  = Pt(20)
        run.font.bold  = True
        run.font.color.rgb = TITLE_COLOR

        # Subtitle
        sub_box = slide.shapes.add_textbox(
            Inches(0.2), Inches(0.62), Inches(12.93), Inches(0.35)
        )
        stf = sub_box.text_frame
        sp = stf.paragraphs[0]
        sp.alignment = PP_ALIGN.LEFT
        srun = sp.add_run()
        srun.text = subtitle_text
        srun.font.name  = 'Calibri'
        srun.font.size  = Pt(10)
        srun.font.color.rgb = RGBColor(0x55, 0x55, 0x55)

        # Divider line
        line = slide.shapes.add_shape(
            1,  # MSO_SHAPE_TYPE.LINE
            Inches(0.2), Inches(0.98),
            Inches(12.93), Pt(1)
        )
        line.line.color.rgb = TITLE_COLOR
        line.line.width = Pt(1.5)

        # Diagram image
        img_bytes = diagram_fn()
        slide.shapes.add_picture(
            img_bytes,
            IMG_LEFT, IMG_TOP,
            width=IMG_W, height=IMG_H,
        )

    return prs


if __name__ == '__main__':
    out = r'd:\videocx\trunk\fi-agent\docs\FI_Project_Diagrams.pptx'
    os.makedirs(os.path.dirname(out), exist_ok=True)
    print("Generating diagrams for PowerPoint...")
    prs = make_ppt()
    prs.save(out)
    print(f"\nDone!  Saved to: {out}")
    # Open it
    import subprocess
    subprocess.Popen(['start', '', out], shell=True)
