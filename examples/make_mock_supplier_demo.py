"""Create a synthetic six-panel carton training fixture; NEVER use for manufacture."""
from pathlib import Path
import json
import math
from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm


def make(root: Path) -> Path:
    root.mkdir(parents=True,exist_ok=True)
    (root/'factory').mkdir(exist_ok=True)
    (root/'packaging').mkdir(exist_ok=True)
    panels=[('left_spine',24,44,26,120,390,1800),('front',50,44,72,120,900,1500),
            ('right_spine',122,44,26,120,390,1800),('back',148,44,72,120,900,1500),
            ('top_flap',50,14,72,30,1200,500),('bottom_flap',50,164,72,30,1200,500)]
    font='/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf'
    for name,x,y,w,h,px,py in panels:
        im=Image.new('RGB',(px,py));d=ImageDraw.Draw(im)
        for v in range(py):
            t=v/max(1,py-1)
            d.line([(0,v),(px,v)],fill=(int(71+115*t),int(44+78*t),int(110+115*t)))
        margin=int(px*.035)
        d.rounded_rectangle((margin,margin,px-margin,py-margin),radius=int(px*.08),outline=(247,204,130),width=max(4,int(px*.016)))
        d.ellipse((px*.25,py*.27,px*.75,py*.27+px*.5),outline=(244,220,154),width=max(4,int(px*.016)))
        d.ellipse((px*.40,py*.27+px*.06,px*.72,py*.27+px*.38), fill=(248,220,153))
        d.ellipse((px*.48,py*.27+px*.055,px*.79,py*.27+px*.37), fill=(121,83,175))
        for i in range(25):
            xx=(i*149+23)%px; yy=(i*349+51)%py
            d.ellipse((xx,yy,xx+max(3,px//160),yy+max(3,px//160)),fill=(252,226,161))
        try:ft=ImageFont.truetype(font,max(17,round(px*.07)))
        except OSError:ft=ImageFont.load_default()
        label='CELESTIAL TAROT' if name in ('front','back') else name.upper().replace('_',' ')
        d.text((px/2,py*.70),label,anchor='mm',font=ft,fill=(250,227,188),stroke_width=0)
        im.save(root/'packaging'/f'{name}.png')
    c=canvas.Canvas(str(root/'factory'/'SIMULATED_TRAINING_DIELINE.pdf'),pagesize=(297*mm,210*mm))
    c.setFont('Helvetica-Bold',16);c.setFillColorRGB(0.65,0.12,0.21)
    c.drawString(20*mm,202*mm,'SYNTHETIC DEMO - NOT A MANUFACTURER DIELINE')
    c.setStrokeColorRGB(.9,.18,.35);c.setLineWidth(1.2)
    for name,x,y,w,h,*_ in panels:
        c.rect(x*mm,(210-y-h)*mm,w*mm,h*mm,fill=0,stroke=1)
        c.setFont('Helvetica',7);c.drawString((x+3)*mm,(210-y-4)*mm,name)
    c.setStrokeColorRGB(.2,.2,.9);c.setDash(3,3)
    c.line(24*mm,(210-44)*mm,220*mm,(210-44)*mm)
    c.line(24*mm,(210-164)*mm,220*mm,(210-164)*mm)
    c.setDash();c.showPage();c.save()
    config={'schema_version':1,'manufacturer':'SYNTHETIC TRAINING FIXTURE - NOT A REAL SUPPLIER',
       'official_template_pdf':'factory/SIMULATED_TRAINING_DIELINE.pdf',
       'template_received_from_manufacturer':True, # Demonstrates the gate only; no real vendor attestation.
       'page_index':0,'coordinates':'top_left_mm',
       'panels':[{'name':n,'x_mm':x,'y_mm':y,'width_mm':w,'height_mm':h,'image_file':f'packaging/{n}.png'}
                 for n,x,y,w,h,*_ in panels],
       'explicit_demo_warning':'SIMULATION ONLY; these coordinates must NEVER be used as real print-house specifications.'}
    (root/'packaging_template.json').write_text(json.dumps(config,indent=2)+'\n')
    (root/'DO_NOT_PRINT.txt').write_text('SYNTHETIC DECKFORGE TRAINING DIELINE, NOT A SUPPLIER PROVIDED TEMPLATE. NEVER USE FOR COMMERCIAL MANUFACTURING.\n')
    return root

if __name__=='__main__':
    import sys
    make(Path(sys.argv[1] if len(sys.argv)>1 else 'supplier_demo').resolve())
