"""Supplier PDF dieline registration and opt-in ICC colour exports.

No actual manufacturer dimensions or CMYK profile are invented. Artwork overlays
are provisional until the real factory template is received and verified.
"""
from __future__ import annotations

from hashlib import sha256
from io import BytesIO
import json
import math
from pathlib import Path

from PIL import Image, ImageCms, ImageOps
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.lib.units import mm
from pypdf import PdfReader, PdfWriter

from .project import safe_relative_file, read_config

TEMPLATE_FILE = 'packaging_template.json'


def default_template(vendor: str = 'Print Europe / other - NOT VERIFIED') -> dict:
    return {
        'schema_version': 1,
        'manufacturer': vendor,
        'official_template_pdf': 'factory/official_tuck_box_dieline.pdf',
        'template_received_from_manufacturer': False,
        'page_index': 0,
        'coordinates': 'top_left_mm',
        'panels': [],
        'instructions': (
            'Get the exact official dieline from your chosen supplier. Read panel bounds in mm, '
            'enter them below with artwork file paths, then verify physical panel orientation and bleed. '
            'Do not use the conceptual box illustration as the actual dieline.'
        ),
        'example_panel_DO_NOT_UNCOMMENT_WITHOUT_MEASURING': {
            'name':'front', 'image_file':'packaging/front.png',
            'x_mm':0, 'y_mm':0, 'width_mm':0, 'height_mm':0,
        },
    }


def init_template(project: Path, *, vendor: str='Print Europe - UNCONFIRMED') -> Path:
    target=project / TEMPLATE_FILE
    if target.exists():
        raise FileExistsError(f'{target} already exists')
    target.write_text(json.dumps(default_template(vendor),indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    return target


def inspect_template(project: Path, *, require_complete: bool = False) -> dict:
    path=project/TEMPLATE_FILE
    if not path.exists():
        return {'status':'not_configured','issues':['No packaging_template.json'], 'panels':0}
    cfg=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(cfg,dict) or cfg.get('schema_version') != 1:
        raise ValueError('packaging_template.json must have schema_version 1')
    if cfg.get('coordinates')!='top_left_mm':
        raise ValueError('Only top_left_mm coordinates are currently supported')
    if not isinstance(cfg.get('panels'),list):
        raise ValueError('Template panels must be an array')
    if len(cfg['panels'])>16:
        raise ValueError('Too many panels; maximum 16')
    issues=[]
    template=cfg.get('official_template_pdf','')
    if not template:
        issues.append('No official factory PDF path configured')
        source=None
    else:
        source,_=safe_relative_file(project,template)
        if not source.is_file():
            issues.append('Official factory PDF not found at configured path')
            source=None
    page_w=page_h=None
    if source:
        reader=PdfReader(str(source))
        idx=cfg.get('page_index',0)
        if not isinstance(idx,int) or not 0<=idx<len(reader.pages):
            raise ValueError('Invalid selected factory PDF page index')
        page=reader.pages[idx]
        if page.rotation not in (0,None):
            raise ValueError('Rotated template PDF pages are not supported; normalize rotation first')
        page_w=float(page.mediabox.width)/mm
        page_h=float(page.mediabox.height)/mm
        if page_w<=0 or page_h<=0 or page_w>1200 or page_h>1200:
            raise ValueError('Unsupported packaging sheet size')
    if not cfg.get('template_received_from_manufacturer'):
        issues.append('Supplier-origin template not confirmed (cannot certify geometry)')
    seen=set()
    boxes=[]
    try:
        from .printer import load_printer_profile
        min_dpi=float(load_printer_profile(project)['minimum_effective_dpi'])
    except (ValueError,OSError,KeyError):
        min_dpi=300.0
    for i,p in enumerate(cfg['panels']):
        if not isinstance(p,dict):
            raise ValueError(f'Panel {i} must be an object')
        for key in ('name','image_file'):
            if not isinstance(p.get(key),str) or not p[key].strip():
                raise ValueError(f'Panel {i} requires {key}')
        name=p['name'].strip().lower()
        if name in seen:
            raise ValueError(f'Duplicate panel name: {name}')
        seen.add(name)
        for key in ('x_mm','y_mm','width_mm','height_mm'):
            v=p.get(key)
            if (not isinstance(v,(int,float)) or isinstance(v,bool)
                or not math.isfinite(v) or v < 0 or (key in ('width_mm','height_mm') and v==0)):
                raise ValueError(f'Invalid {key} for {name}')
        if page_w is not None and (p['x_mm']+p['width_mm']>page_w+0.001 or
                                   p['y_mm']+p['height_mm']>page_h+0.001):
            raise ValueError(f'{name}: artwork outside official template page')
        art,_=safe_relative_file(project,p['image_file'])
        if not art.is_file():
            issues.append(f'{name}: missing panel artwork')
            continue
        try:
            with Image.open(art) as image:
                image.load()
                aw,ah=ImageOps.exif_transpose(image).size
        except (OSError,Image.DecompressionBombError) as ex:
            raise ValueError(f'{name}: unreadable image') from ex
        delta=abs((aw/ah) - (p['width_mm']/p['height_mm']))
        if delta>0.005:
            issues.append(f'{name}: aspect mismatch; exact fit would distort/crop artwork')
        effective_dpi=min(aw / (p['width_mm']/25.4), ah / (p['height_mm']/25.4))
        if effective_dpi < min_dpi:
            issues.append(f'{name}: {effective_dpi:.0f} effective DPI below configured {min_dpi:g} target')
        boxes.append((name,p['x_mm'],p['y_mm'],p['width_mm'],p['height_mm']))
    for i,(na,ax,ay,aw,ah) in enumerate(boxes):
        for nb,bx,by,bw,bh in boxes[i+1:]:
            if max(ax,bx)<min(ax+aw,bx+bw)-0.001 and max(ay,by)<min(ay+ah,by+bh)-0.001:
                issues.append(f'{na} and {nb}: panel extents overlap; check supplied coordinates')
    if not cfg['panels']:
        issues.append('No measured panels configured from supplier dieline')
    if require_complete and issues:
        raise ValueError('Packaging template requires review: ' + '; '.join(issues))
    return {'status':'ready_for_provisional_overlay' if not issues else 'needs_setup',
            'manufacturer':cfg.get('manufacturer','Unspecified'), 'page_mm':[page_w,page_h],
            'panels':len(cfg['panels']), 'issues':issues, 'configuration':cfg}


def create_packaging_overlay(project: Path, destination: Path) -> dict:
    """Create artwork-only page and registered proof with actual supplier PDF above art.

    Never auto-stretch or fabricate bleed; refusal on any ratio mismatch.
    """
    summary=inspect_template(project, require_complete=True)
    cfg=summary['configuration']
    source,_=safe_relative_file(project,cfg['official_template_pdf'])
    base=PdfReader(str(source)).pages[cfg['page_index']]
    width=float(base.mediabox.width);height=float(base.mediabox.height)
    dest=destination
    dest.mkdir(parents=True,exist_ok=True)
    buf=BytesIO()
    c=canvas.Canvas(buf,pagesize=(width,height),pageCompression=1)
    for p in cfg['panels']:
        art,_=safe_relative_file(project,p['image_file'])
        x=p['x_mm']*mm
        y=height-(p['y_mm']+p['height_mm'])*mm
        w,h=p['width_mm']*mm,p['height_mm']*mm
        with Image.open(art) as image:
            im=ImageOps.exif_transpose(image).convert('RGB')
            im.thumbnail((9000,9000))
            # The ratio is already validated; contains small rounding from pixel aspect.
            c.drawImage(ImageReader(im),x,y,w,h,mask='auto')
    c.showPage();c.save()
    buf.seek(0)
    clean=dest/'packaging_ARTWORK_ONLY_PROVISIONAL.pdf'
    clean.write_bytes(buf.getvalue())
    overlay=PdfReader(buf).pages[0]
    # Draw artwork first, and original supplier lines above as review-only overlay.
    overlay.merge_page(base)
    wtr=PdfWriter();wtr.add_page(overlay)
    proof=dest/'packaging_SUPPLIER_LINES_REVIEW_ONLY.pdf'
    with proof.open('wb') as f:wtr.write(f)
    return {'artwork_only':str(clean),'proof':str(proof),
            'panel_count':len(cfg['panels']),'manufacturer':cfg.get('manufacturer'),
            'status':'PROVISIONAL_NOT_PRINTER_APPROVED'}


def convert_cmyk(project: Path, dest: Path, output_profile: Path,
                 *, assume_srgb_when_missing: bool = False,
                 card_ids: list[str] | None = None) -> dict:
    """ICC transform to CMYK TIFFs using the supplied profile; never a generic fake profile.

    Source images without ICC require an explicit, documented sRGB assumption.
    """
    if not output_profile.is_file():
        raise FileNotFoundError('Provide a real printer-specified ICC profile file')
    data=output_profile.read_bytes()
    if len(data)>8*1024*1024 or len(data)<128:
        raise ValueError('ICC profile size outside safe bounds')
    try:
        cmyk=ImageCms.ImageCmsProfile(BytesIO(data))
    except (ValueError,OSError) as ex:
        raise ValueError('Invalid output ICC profile') from ex
    if cmyk.profile.xcolor_space.strip().upper()!='CMYK':
        raise ValueError('Output ICC profile must be CMYK (not RGB)')
    cfg=read_config(project)
    selected=set(card_ids) if card_ids else None
    available={x['id'] for x in cfg['cards']} | {'BACK'}
    if selected is not None and (not selected or selected-available):
        raise ValueError('Unknown or empty selected card IDs')
    entries=[{'id':x['id'],'file':x['file']} for x in cfg['cards']]
    entries.append({'id':'BACK','file':cfg.get('back_file')})
    # Validate all inputs before creating outputs.
    prepared=[]
    for entry in entries:
        if selected is not None and entry['id'] not in selected:
            continue
        if not entry['file']:
            raise ValueError(f"{entry['id']}: no artwork file")
        path,_=safe_relative_file(project,entry['file'])
        if not path.is_file():
            raise FileNotFoundError(f"Missing artwork for {entry['id']}")
        with Image.open(path) as im:
            if not im.info.get('icc_profile') and not assume_srgb_when_missing:
                raise ValueError(f"{entry['id']}: missing embedded source ICC; use --assume-srgb only if appropriate")
        prepared.append((entry['id'],path))
    if not prepared:
        raise ValueError('No artwork files selected')
    # Pre-check output collisions for the full batch; never leave partial results due to overwrite.
    for cid,_ in prepared:
        if (dest/f'{cid}_CMYK.tif').exists():
            raise FileExistsError(f'Will not overwrite existing CMYK output: {cid}_CMYK.tif')
    if (dest/'ICC_EXPORT_MANIFEST.json').exists():
        raise FileExistsError('Will not overwrite an existing ICC export manifest')
    dest.mkdir(parents=True,exist_ok=True)
    profile_sha=sha256(data).hexdigest()
    manifest=[]
    for cid,path in prepared:
        with Image.open(path) as original:
            exif=ImageOps.exif_transpose(original)
            embedded=original.info.get('icc_profile')
            if embedded:
                try:src_profile=ImageCms.ImageCmsProfile(BytesIO(embedded))
                except (OSError,ValueError) as ex:
                    raise ValueError(f'{cid}: corrupt source ICC profile') from ex
            else:
                src_profile=ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB'))
            if exif.mode in ('RGBA','LA') or 'transparency' in original.info:
                rgba=exif.convert('RGBA')
                background=Image.new('RGBA',rgba.size,(255,255,255,255))
                background.alpha_composite(rgba)
                rgb=background.convert('RGB')
            else:
                rgb=exif.convert('RGB')
            try:
                # Embedded CMYK assets must first be transformed from their
                # true source space; converting raw numbers with PIL alone
                # would discard that meaning and produce incorrect colours.
                source_space=src_profile.profile.xcolor_space.strip().upper()
                if source_space=='CMYK' and exif.mode=='CMYK':
                    rgb=ImageCms.profileToProfile(exif,src_profile,
                        ImageCms.createProfile('sRGB'),outputMode='RGB')
                    src_profile=ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB'))
                elif source_space!='RGB':
                    raise ValueError(f'Unsupported source ICC space: {source_space}')
                converted=ImageCms.profileToProfile(rgb,src_profile,cmyk,
                                                   renderingIntent=0,outputMode='CMYK')
            except (OSError,ValueError) as ex:
                raise ValueError(f'{cid}: ICC conversion failed') from ex
            if converted.mode!='CMYK':
                raise RuntimeError('ICC conversion did not produce CMYK pixels')
            out=dest/f'{cid}_CMYK.tif'
            if out.exists():
                raise FileExistsError(f'Will not overwrite existing CMYK output: {out}')
            converted.save(out,format='TIFF',compression='tiff_lzw',icc_profile=data)
            manifest.append({'id':cid, 'source':str(path.relative_to(project)),
                             'source_sha256':sha256(path.read_bytes()).hexdigest(),
                             'file':out.name,'sha256':sha256(out.read_bytes()).hexdigest(),
                             'source_icc_assumed_srgb':not bool(embedded),'mode':'CMYK'})
    report={'schema_version':1,'status':'COLOUR_CONVERTED_NOT_PRESS_APPROVED',
            'target_icc_filename':output_profile.name,'target_icc_sha256':profile_sha,
            'rendering_intent':'perceptual','source_assumption_explicit':assume_srgb_when_missing,
            'items':manifest,'warning':'Obtain printer approval/soft proof on correct paper; this is not certified prepress.'}
    (dest/'ICC_EXPORT_MANIFEST.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report
