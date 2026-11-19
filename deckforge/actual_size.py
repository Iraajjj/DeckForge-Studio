"""Real-size physical card inspection proof (2 × 2 per A4 page).

Output is NOT imposition, manufacturer's bleed, or calibrated press color. If input
is trim-only, no bleed is synthesized; if source declares bleed, it is displayed.
"""
from __future__ import annotations

from io import BytesIO
from math import ceil
from pathlib import Path

from PIL import Image, ImageOps
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader

from .project import safe_relative_file


def _art(c: canvas.Canvas, project: Path, raw: str, x: float, y: float,
         trim_w_mm: float, trim_h_mm: float, bleed_mm: float, safe_mm: float):
    actual_w = (trim_w_mm + 2 * bleed_mm) * mm
    actual_h = (trim_h_mm + 2 * bleed_mm) * mm
    with Image.open(safe_relative_file(project,raw)[0]) as image:
        im = ImageOps.exif_transpose(image).convert('RGB')
        # Embed at natural resolution (no enlargement of data): the PDF stores source pixels.
        buffer = BytesIO()
        im.save(buffer,format='JPEG',quality=88,optimize=True,subsampling=0)
        buffer.seek(0)
        ratio=im.width/im.height
        width=min(actual_w,actual_h*ratio)
        height=width/ratio
        if height > actual_h:
            height=actual_h
            width=height*ratio
        c.drawImage(ImageReader(buffer),x+(actual_w-width)/2,y+(actual_h-height)/2,
                    width,height)
    # mark the source extent, nominal trim, and safe inset
    c.setDash(2,2)
    c.setStrokeColor(colors.HexColor('#B18BA5'))
    c.rect(x,y,actual_w,actual_h,fill=0,stroke=1)
    c.setDash()
    c.setLineWidth(.6)
    c.setStrokeColor(colors.HexColor('#D94B8A'))
    c.rect(x+bleed_mm*mm,y+bleed_mm*mm,trim_w_mm*mm,trim_h_mm*mm,fill=0,stroke=1)
    c.setStrokeColor(colors.HexColor('#E5C74D'))
    c.setDash(3,3)
    c.rect(x+(bleed_mm+safe_mm)*mm,y+(bleed_mm+safe_mm)*mm,
           (trim_w_mm-2*safe_mm)*mm,(trim_h_mm-2*safe_mm)*mm,fill=0,stroke=1)
    c.setDash()


def create_actual_size_proof(project_dir: Path, report: dict, destination: Path) -> None:
    """At 100% print size, 4-up proof pages with an optional final common back."""
    trim_w=report['card_width_mm']; trim_h=report['card_height_mm']
    bleed=report.get('source_bleed_mm',0.0)
    safe=report.get('safe_area_mm',4.0)
    width=(trim_w+2*bleed)*mm
    height=(trim_h+2*bleed)*mm
    pw,ph=A4
    gutter=10*mm
    # We need room for 2×2 cards, captions and fixed header/footer.
    if width*2+gutter > pw-14*mm or height*2+gutter > ph-20*mm:
        raise ValueError('Card extent too large for the 2×2 A4 physical-size proof; use smaller cards or different paper')
    x_l=(pw-(width*2+gutter))/2
    y_bottom=(ph-(height*2+gutter))/2
    positions=[(x_l,y_bottom+height+gutter),(x_l+width+gutter,y_bottom+height+gutter),
               (x_l,y_bottom),(x_l+width+gutter,y_bottom)]
    items=report['cards'][:]
    if report.get('back',{}).get('present'):
        items.append({'id':'BACK','present':True,'file':report['back']['file']})
    c=canvas.Canvas(str(destination),pagesize=A4,pageCompression=1)
    c.setTitle('DeckForge physical-size review – print at actual size; not manufacturing imposition')
    total=ceil(len(items)/4)
    for page in range(total):
        c.setFillColor(colors.HexColor('#302341'))
        c.rect(0,ph-10*mm,pw,10*mm,stroke=0,fill=1)
        c.setFillColor(colors.white)
        c.setFont('Helvetica-Bold',8)
        c.drawString(8*mm,ph-6.4*mm,'DECKFORGE  ·  PHYSICAL SIZE REVIEW / PRINT AT 100%')
        for idx,entry in enumerate(items[page*4:(page+1)*4]):
            x,y=positions[idx]
            if entry['present'] and entry.get('file'):
                try:
                    _art(c,project_dir,entry['file'],x,y,trim_w,trim_h,bleed,safe)
                except (OSError,ValueError):
                    c.setStrokeColor(colors.red);c.rect(x,y,width,height,fill=0,stroke=1)
            else:
                c.setStrokeColor(colors.red);c.rect(x,y,width,height,fill=0,stroke=1)
            c.setFillColor(colors.HexColor('#392E4E'))
            c.setFont('Helvetica-Bold',7)
            c.drawCentredString(x+width/2,y-4*mm,entry['id'])
        c.setFont('Helvetica',7)
        c.setFillColor(colors.HexColor('#655A6C'))
        c.drawString(8*mm,5*mm,f'Pink=nominal trim · gold=safe inset · dashed plum=source edge · declared bleed: {bleed:g}mm')
        c.drawRightString(pw-8*mm,5*mm,f'{page+1}/{total}   |   REVIEW ONLY')
        c.showPage()
    c.save()
