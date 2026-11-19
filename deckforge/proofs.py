"""Image proof sheets - visual review only, not a printer imposition file."""
from __future__ import annotations

from io import BytesIO
from math import ceil
from pathlib import Path

from PIL import Image, ImageOps
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from .project import safe_relative_file


def create_contact_sheet(project_dir: Path, report: dict, destination: Path) -> None:
    """5-page contact proof, 6 columns by 3 rows, complete with missing-art placeholders."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    page_width, page_height = landscape(A4)
    pdf = canvas.Canvas(str(destination), pagesize=(page_width, page_height), pageCompression=1)
    pdf.setTitle(f"{report['deck_name']} - deck preview (not for printing)")
    items = report["cards"]
    columns, rows = 6, 3
    per_page = columns * rows
    pages = ceil(len(items) / per_page)
    left, right = 13 * mm, 13 * mm
    top, bottom = 28 * mm, 18 * mm
    cell_width = (page_width - left - right) / columns
    cell_height = (page_height - top - bottom) / rows

    for page in range(pages):
        pdf.setFillColor(colors.HexColor("#2C2144"))
        pdf.rect(0, page_height - 20 * mm, page_width, 20 * mm, stroke=0, fill=1)
        pdf.setFillColor(colors.whitesmoke)
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(left, page_height - 12 * mm, report["deck_name"][:52])
        pdf.setFont("Helvetica", 8)
        pdf.drawRightString(page_width - right, page_height - 11 * mm,
                            "REVIEW PROOF - NOT PRINT IMPOSITION")

        for spot, entry in enumerate(items[page * per_page:(page + 1) * per_page]):
            col, row = spot % columns, spot // columns
            x = left + col * cell_width
            cy = page_height - top - (row+1) * cell_height
            frame_width = min(cell_width - 7*mm, (cell_height - 12*mm) * 0.58333)
            frame_height = min(cell_height - 12*mm, frame_width / 0.58333)
            frame_width = frame_height * 0.58333
            cx = x + (cell_width - frame_width) / 2
            fy = cy + 9*mm
            pdf.setFillColor(colors.HexColor("#F7F1FC"))
            pdf.roundRect(cx, fy, frame_width, frame_height, 2.5*mm, fill=1, stroke=0)
            if entry["present"] and entry["file"]:
                try:
                    filepath, _ = safe_relative_file(project_dir, entry["file"])
                    with Image.open(filepath) as im:
                        rgb = ImageOps.exif_transpose(im).convert("RGB")
                        rgb.thumbnail((300, 550), Image.Resampling.LANCZOS)
                        ratio = rgb.width / rgb.height
                        dw = min(frame_width, frame_height*ratio)
                        dh = dw/ratio
                        if dh > frame_height:
                            dh=frame_height; dw=dh*ratio
                        buffer=BytesIO()
                        rgb.save(buffer, format="JPEG", quality=75)
                        buffer.seek(0)
                        pdf.drawImage(ImageReader(buffer), cx+(frame_width-dw)/2,
                                      fy+(frame_height-dh)/2, dw, dh)
                except (OSError, ValueError):
                    _missing(pdf, cx, fy, frame_width, frame_height)
            else:
                _missing(pdf, cx, fy, frame_width, frame_height)
            pdf.setFillColor(colors.HexColor("#342448"))
            pdf.setFont("Helvetica-Bold", 7.2)
            pdf.drawCentredString(x+cell_width/2, cy+5*mm, entry["id"])
            pdf.setFont("Helvetica", 6.5)
            pdf.drawCentredString(x+cell_width/2, cy+2*mm, entry["title"][:30])
        pdf.setFillColor(colors.HexColor("#777084"))
        pdf.setFont("Helvetica", 8)
        pdf.drawString(left, 7*mm, f"Present artwork: {report['present_cards']}/78  |  Errors: {report['errors']}  |  Warnings: {report['warnings']}")
        pdf.drawRightString(page_width-right, 7*mm, f"Page {page+1}/{pages}")
        pdf.showPage()
    pdf.save()


def _missing(pdf, x, y, w, h):
    pdf.setStrokeColor(colors.HexColor("#D68C9A"))
    pdf.setLineWidth(.6)
    pdf.rect(x, y, w, h, fill=0, stroke=1)
    pdf.setFillColor(colors.HexColor("#963D55"))
    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawCentredString(x+w/2, y+h/2, "MISSING")


def create_safety_proof(project_dir: Path, report: dict, destination: Path) -> None:
    """Review-only overlay showing the configured safety inset from the TRIM edge.

    THIS DOES NOT EXTEND BLEED or locate semantically important content.
    """
    from math import ceil
    destination.parent.mkdir(parents=True, exist_ok=True)
    pw, ph = landscape(A4)
    c = canvas.Canvas(str(destination),pagesize=(pw,ph),pageCompression=1)
    c.setTitle(f"{report['deck_name']} - safety line review ONLY")
    cols, rows = 6, 3
    per_page=cols*rows
    mx=12*mm; top=27*mm; bottom=17*mm
    cell_w=(pw-2*mx)/cols
    cell_h=(ph-top-bottom)/rows
    trim_ratio=report['card_width_mm']/report['card_height_mm']
    safety_mm=report.get('safe_area_mm',4.0)
    width_mm=report['card_width_mm']; height_mm=report['card_height_mm']
    for page in range(ceil(len(report['cards'])/per_page)):
        c.setFillColor(colors.HexColor('#2C2144'))
        c.rect(0,ph-18*mm,pw,18*mm,stroke=0,fill=1)
        c.setFillColor(colors.white);c.setFont('Helvetica-Bold',12)
        c.drawString(mx,ph-11*mm,'DECKFORGE · SAFE-AREA REVIEW')
        c.setFont('Helvetica',8)
        c.drawRightString(pw-mx,ph-11*mm,f"Inset: {safety_mm:g}mm  |  NOT printer bleed")
        for pos,rec in enumerate(report['cards'][page*per_page:(page+1)*per_page]):
            col,row=pos%cols,pos//cols
            x0=mx+col*cell_w; y0=ph-top-(row+1)*cell_h
            max_h=cell_h-13*mm; max_w=cell_w-6*mm
            frame_h=min(max_h,max_w/trim_ratio)
            frame_w=frame_h*trim_ratio
            fx=x0+(cell_w-frame_w)/2
            fy=y0+8.5*mm
            c.setFillColor(colors.HexColor('#F5EAF7'))
            c.roundRect(fx,fy,frame_w,frame_h,1.6*mm,fill=1,stroke=0)
            if rec['present'] and rec.get('file'):
                try:
                    p,_=safe_relative_file(project_dir,rec['file'])
                    with Image.open(p) as im:
                        im=ImageOps.exif_transpose(im).convert('RGB')
                        im.thumbnail((300,540),Image.Resampling.LANCZOS)
                        buff=BytesIO();im.save(buff,format='JPEG',quality=82);buff.seek(0)
                        ratio=im.width/im.height
                        aw=min(frame_w,frame_h*ratio);ah=aw/ratio
                        if ah>frame_h:
                            ah=frame_h;aw=ah*ratio
                        c.drawImage(ImageReader(buff),fx+(frame_w-aw)/2,fy+(frame_h-ah)/2,aw,ah)
                except (OSError,ValueError):
                    _missing(c,fx,fy,frame_w,frame_h)
            else:
                _missing(c,fx,fy,frame_w,frame_h)
            in_x=frame_w*safety_mm/width_mm
            in_y=frame_h*safety_mm/height_mm
            c.setStrokeColor(colors.HexColor('#F5D35E'))
            c.setDash(3,2);c.setLineWidth(1.5)
            c.rect(fx+in_x,fy+in_y,frame_w-2*in_x,frame_h-2*in_y,fill=0,stroke=1)
            c.setDash();c.setStrokeColor(colors.HexColor('#D96D97'))
            c.setLineWidth(.6);c.rect(fx,fy,frame_w,frame_h,fill=0,stroke=1)
            c.setFont('Helvetica-Bold',7.2)
            c.setFillColor(colors.HexColor('#352645'))
            c.drawCentredString(x0+cell_w/2,y0+4*mm,rec['id'])
        c.setFont('Helvetica',8)
        c.setFillColor(colors.HexColor('#74657F'))
        c.drawString(mx,6*mm,'Gold dashed = suggested safety inset. Pink = nominal trim. Manual review required.')
        c.drawRightString(pw-mx,6*mm,f'Page {page+1}')
        c.showPage()
    c.save()
