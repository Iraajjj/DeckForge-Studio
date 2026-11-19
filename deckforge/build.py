"""DeckForge V4 pipeline: reproducible technical QA, preview, QR and integrity-checked ZIP.

NOT a factory-certified print package or pre-press ICC/dieline substitute.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import zipfile

from .advanced import enrich_report
from .dashboard import write_dashboard
from .project import read_config, safe_relative_file
from .validation import inspect_deck
from .proofs import create_contact_sheet, create_safety_proof
from .qr import export_qr_assets, check_url
from .actual_size import create_actual_size_proof
from .reviews import review_status
from .printer import load_printer_profile, release_gate
from .costing import load_costs, write_cost_reports
from .vision import read_vision_results
from .manufacturing import inspect_template, create_packaging_overlay


MANAGED = {
    'qa_report.json','qa_report.md','qa_dashboard.html','contact_sheet_REVIEW_ONLY.pdf',
    'safe_area_REVIEW_ONLY.pdf','qr_25mm_600dpi.png','qr_30mm_600dpi.png',
    'qr_30mm_vector.svg','qr_30mm_vector.pdf','deckforge_package.zip',
    'README_PRINTER_HANDOFF.txt','SHA256SUMS.txt',
    'actual_size_REVIEW_ONLY.pdf', 'release_gate.json', 'release_gate.md',
    'cost_report.json','cost_report.csv','cost_report.md',
    'packaging_ARTWORK_ONLY_PROVISIONAL.pdf','packaging_SUPPLIER_LINES_REVIEW_ONLY.pdf',
}


def write_markdown(report: dict, destination: Path) -> None:
    status = report.get('readiness','REVIEW_REQUIRED')
    lines = [f"# DeckForge v4 | {report['deck_name']}", '',
             f"**Technical status:** `{status}` (not a factory print certification)", '',
             f"- Inventory: **{report['present_cards']}/78**",
             f"- Errors: **{report['errors']}**",f"- Warnings: **{report['warnings']}**",
             f"- Nominal trim: **{report['card_width_mm']:g} × {report['card_height_mm']:g} mm**",
             f"- Resolution target: **{report['min_dpi']} effective DPI at trim**",
             f"- Safe inset guide: **{report.get('safe_area_mm',4.0):g} mm**",
             f"- Requested bleed (not synthesized): **{report.get('bleed_required_mm',3.0):g} mm**",
             f"- Embedded ICC profiles: **{report.get('icc_embedded_count',0)} of {report['present_cards']}**",
             '', '## Card back reversibility (approximation)', '']
    back=report['back']
    score=back.get('rotation_difference')
    if score is None:
        lines.append('Back not present or not inspected.')
    else:
        lines.append(f"Rotation difference: **{score*100:.2f}%**. Automated heuristic: **{'likely symmetric' if back['reversible_by_heuristic'] else 'may reveal reversed cards'}**. Confirm by visual inspection and printed proof.")
    lines += ['', '## Findings', '']
    if not report['issues']:
        lines.append('No issues detected by the automated checks. This is not press approval.')
    for i in report['issues']:
        lines.append(f"- **{i['severity'].upper()} · {i['code']}**: {i['message']}")
    lines += ['', '## Print-house handoff — must be verified manually', '']
    for item in report.get('manual_checks',[]):
        lines.append('- [ ] '+item)
    lines += ['', '## What V4 intentionally does not do', '',
              '- Optional AI vision can suggest counts, but cannot certify symbols, identities or trademark rights.',
              '- Does not invent missing bleed or run manufacturer dielines.',
              '- Does not guarantee CMYK/ICC requirements or exact colour on substrate.',
              '- Does not guarantee a QR is publicly accessible, even if it scans.',
              '- Review PDFs have REVIEW_ONLY in the filename and should not be sent as print impositions.', '']
    approvals=report.get('human_reviews',{}).get('counts',{})
    gate=report.get('release_gate',{})
    lines += ['', '## Human review & release gate', '',
              f"- Visual sign-offs: **{approvals.get('approved',0)}/79**; stale: **{approvals.get('stale',0)}**",
              f"- Readiness: **{gate.get('status','UNKNOWN')}**", '']
    for reason in gate.get('blockers',[]): lines.append('- [ ] ' + reason)
    lines += ['', '## Physical-size card proof', '',
              'actual_size_REVIEW_ONLY.pdf has true physical trim dimensions when printed at 100%.',
              'It is not a production imposition, bleed expansion, or guaranteed color conversion.']
    vision=report.get('vision_assistance',{})
    template=report.get('packaging_template',{})
    lines += ['', '## Optional AI vision observations — NEVER APPROVAL', '',
              f"- Stored current AI observations: {vision.get('counts',{}).get('current',0)}",
              f"- Stale observations after image changes: {vision.get('counts',{}).get('stale',0)}",
              '- Live vision uploads only occur through an explicit user-triggered review; may incur separate API fees.',
              '', '## Supplier packaging template', '',
              f"- Status: {template.get('status','not_configured')}",
              f"- Registered panels: {template.get('panels',0)}",]
    for item in template.get('issues',[]):lines.append('- [ ] '+item)
    lines += ['', '- CMYK TIFF export requires a separate explicit `color-export` with the manufacturer ICC file.',
              '- Neither ICC conversion nor the PDF overlay replaces physical proof / manufacturer acceptance.']
    destination.write_text('\n'.join(lines),encoding='utf-8')


def _readme_handoff(report: dict) -> str:
    return (f"DECKFORGE V4 – TECHNICAL REVIEW PACKAGE\n"
            f"Deck: {report['deck_name']}\n"
            f"Status: {report.get('readiness','UNKNOWN')} (technical checks only)\n"
            f"Inventory: {report['present_cards']}/78 | Errors: {report['errors']} | Warnings: {report['warnings']}\n\n"
            f"PLEASE NOTE:\n"
            f"1. Contact and safe-area PDFs are REVIEW ONLY, not manufacturer impositions.\n"
            f"2. No bleed pixels have been added to artwork.\n"
            f"3. Use the printer's actual dieline, bleed, safe area, color/ICC and file specs.\n"
            f"4. Test QR links in private browsing and by scanning a physical proof.\n"
            f"5. Review licensing and commercial permissions independently.\n"
            f"6. Verify SHA256SUMS.txt after transferring files.\n"
            f"7. Human-review sign-offs and supplier specifications are tracked separately.\n")


def _zipinfo(name: str) -> zipfile.ZipInfo:
    zi = zipfile.ZipInfo(name, date_time=(2024,1,1,0,0,0))
    zi.compress_type = zipfile.ZIP_DEFLATED
    zi.external_attr = 0o644 << 16
    return zi


def create_package(project_dir: Path, output_dir: Path, report: dict) -> Path:
    """Consistent-order ZIP with original artwork, review outputs, and file checksums.

    PDF metadata may change between runs; byte-for-byte archive reproducibility is NOT promised."""
    paths: dict[str, Path] = {'deckforge.json':project_dir/'deckforge.json'}
    for name in ('printer_profile.json','human_reviews.json','pricing_scenarios.json',
                 'vision_brief.json','vision_reviews.json','packaging_template.json'):
        if (project_dir/name).is_file(): paths[name]=project_dir/name
    # Include only project-contained, safe supplier source references when configured.
    template = report.get('packaging_template',{}).get('configuration') or {}
    if template.get('official_template_pdf'):
        try:
            src,rel=safe_relative_file(project_dir,template['official_template_pdf'])
            if src.is_file(): paths[rel]=src
        except ValueError: pass
    for panel in template.get('panels',[]):
        try:
            src,rel=safe_relative_file(project_dir,panel['image_file'])
            if src.is_file(): paths[rel]=src
        except (ValueError,KeyError): pass
    for c in report['cards']:
        if c.get('present') and c.get('file'):
            p,rel = safe_relative_file(project_dir,c['file'])
            paths[rel] = p
    back=report.get('back',{})
    if back.get('present') and back.get('file'):
        p,rel=safe_relative_file(project_dir,back['file'])
        paths[rel]=p
    for p in sorted(output_dir.iterdir()):
        if p.is_file() and p.name in MANAGED and p.name not in {'deckforge_package.zip','SHA256SUMS.txt'}:
            paths['production_review/'+p.name]=p
    sums=[]
    zip_path=output_dir/'deckforge_package.zip'
    with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for name,p in sorted(paths.items()):
            contents=p.read_bytes()
            sums.append(f"{sha256(contents).hexdigest()}  {name}")
            z.writestr(_zipinfo(name),contents)
        z.writestr(_zipinfo('SHA256SUMS.txt'), ('\n'.join(sums)+'\n').encode('utf-8'))
    (output_dir/'SHA256SUMS.txt').write_text('\n'.join(sums)+'\n',encoding='utf-8')
    return zip_path


def verify_package(archive: Path) -> dict:
    """Stream-verify ZIP SHA-256 with size/path limits; never extract untrusted data.

    This detects tampering and corrupt/malicious archive entries. It does not
    authenticate who originally created the package (no digital signature).
    """
    max_member = 512 * 1024 * 1024  # 512 MiB
    max_total = 4 * 1024 * 1024 * 1024  # 4 GiB
    with zipfile.ZipFile(archive, 'r') as z:
        info = z.infolist()
        names = [item.filename for item in info]
        if len(names) != len(set(names)) or len(names) != len(set(n.casefold() for n in names)):
            return {'ok': False, 'checked': 0, 'issues': ['Duplicate or case-colliding ZIP members']}
        if 'SHA256SUMS.txt' not in names:
            return {'ok': False, 'checked': 0, 'issues': ['Missing SHA256SUMS.txt']}
        issues, count = [], 0
        total = sum(item.file_size for item in info)
        if total > max_total or any(item.file_size > max_member for item in info):
            return {'ok':False,'checked':0,'issues':['Archive exceeds safe verification limits']}
        for item in info:
            name = item.filename
            if (name.startswith('/') or '\\' in name or '..' in Path(name).parts or
                name == '' or name.startswith('./') or ':' in name.split('/')[0]):
                issues.append(f'Unsafe ZIP member path: {name}')
            # POSIX symlink file mode in ZIP external attributes.
            if (item.external_attr >> 16) & 0o170000 == 0o120000:
                issues.append(f'ZIP symlink member disallowed: {name}')
        if issues:
            return {'ok':False,'checked':0,'issues':issues}
        if z.getinfo('SHA256SUMS.txt').file_size > 2 * 1024 * 1024:
            return {'ok':False,'checked':0,'issues':['Checksum manifest too large']}
        known = set()
        for line in z.read('SHA256SUMS.txt').decode('utf-8').splitlines():
            if not line.strip():
                continue
            try:
                digest, name = line.split('  ', 1)
            except ValueError:
                issues.append('Malformed checksum entry'); continue
            if len(digest) != 64 or any(ch not in '0123456789abcdef' for ch in digest):
                issues.append(f'Invalid SHA256 digest for {name}'); continue
            if name in known:
                issues.append(f'Duplicate manifest entry: {name}'); continue
            known.add(name)
            if name not in names:
                issues.append(f'Missing member: {name}'); continue
            h = sha256()
            with z.open(name, 'r') as stream:
                while True:
                    chunk = stream.read(1024 * 1024)
                    if not chunk: break
                    h.update(chunk)
            if h.hexdigest() != digest:
                issues.append(f'Checksum mismatch: {name}')
            count += 1
        stray = set(names) - known - {'SHA256SUMS.txt'}
        if stray:
            issues.append('Unexpected members: ' + ', '.join(sorted(stray)))
        return {'ok': not issues, 'checked': count, 'issues': issues}


def run_audit(project_dir: Path) -> dict:
    """Inspect without writing output; safe for GUIs and CI."""
    project_dir=project_dir.resolve()
    cfg=read_config(project_dir)
    report = enrich_report(project_dir,cfg,inspect_deck(project_dir,cfg))
    report['human_reviews'] = review_status(project_dir,cfg)
    profile = load_printer_profile(project_dir)
    report['printer_profile'] = profile
    report['release_gate'] = release_gate(report,profile)
    report['cost_report'] = load_costs(project_dir)
    report['vision_assistance'] = read_vision_results(project_dir,cfg)
    try:
        report['packaging_template'] = inspect_template(project_dir)
    except (ValueError,OSError) as exc:
        report['packaging_template'] = {'status':'invalid', 'issues':[str(exc)],'panels':0}
    return report


def run_build(project_dir: Path, output_dir: Path, *, strict: bool = False,
              skip_safety: bool = False) -> tuple[dict, Path, int]:
    project_dir=project_dir.resolve()
    output_dir=output_dir.resolve()
    if output_dir==project_dir:
        raise ValueError('Output directory cannot be the project root')
    cfg=read_config(project_dir)
    url=(cfg.get('guide_url') or '').strip()
    if url:check_url(url)
    output_dir.mkdir(parents=True,exist_ok=True)
    # Remove only our known files from previous builds; never delete user files.
    for name in MANAGED:
        p=output_dir/name
        if p.exists() and p.is_file():p.unlink()
    report=run_audit(project_dir)
    (output_dir/'qa_report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    write_markdown(report,output_dir/'qa_report.md')
    create_contact_sheet(project_dir,report,output_dir/'contact_sheet_REVIEW_ONLY.pdf')
    if not skip_safety:
        create_safety_proof(project_dir,report,output_dir/'safe_area_REVIEW_ONLY.pdf')
    create_actual_size_proof(project_dir,report,output_dir/'actual_size_REVIEW_ONLY.pdf')
    if report.get('cost_report'):
        write_cost_reports(report['cost_report'],output_dir)
    if report.get('packaging_template',{}).get('status')=='ready_for_provisional_overlay':
        create_packaging_overlay(project_dir,output_dir)
    (output_dir/'release_gate.json').write_text(json.dumps(report['release_gate'],indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    (output_dir/'release_gate.md').write_text(
        '# DeckForge release gate (not printer certification)\n\n'+
        f"**Status:** {report['release_gate']['status']}\n\n"+
        '\n'.join('- [ ] '+x for x in report['release_gate']['blockers'])+'\n\n'+
        '\n'.join('- [ ] '+x for x in report['release_gate']['manual_final_verifications'])+'\n',encoding='utf-8')
    qr_png=None
    if url:
        export_qr_assets(url,output_dir)
        qr_png=output_dir/'qr_30mm_600dpi.png'
    write_dashboard(report,project_dir,output_dir/'qa_dashboard.html',qr_png)
    (output_dir/'README_PRINTER_HANDOFF.txt').write_text(_readme_handoff(report),encoding='utf-8')
    package=create_package(project_dir,output_dir,report)
    code=2 if report['errors'] or (strict and report['warnings']) else 0
    return report,package,code
