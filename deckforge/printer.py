"""Printer specifications and review-only release readiness.

Values must come from the selected manufacturer. Defaults are illustrative, NOT
Print Europe or any other provider's published production requirements.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import math
from pathlib import Path


PROFILE_FILE = 'printer_profile.json'


def default_printer_profile() -> dict:
    return {
        'schema_version': 1,
        'printer_name': 'UNCONFIRMED — obtain factory specification',
        'verified_against_printer': False,
        'verified_at_utc': None,
        'verified_by': None,
        'trim_width_mm': 70.0,
        'trim_height_mm': 120.0,
        'required_bleed_mm': 3.0,
        'safe_inset_mm': 4.0,
        'minimum_effective_dpi': 300,
        'color_profile_instruction': 'Confirm exact CMYK/ICC or RGB acceptance with manufacturer',
        'packaging_dieline_supplied': False,
        'notes': 'Provisional example values. Must confirm stock, finish, cut tolerances and box dieline.',
    }


def load_printer_profile(project: Path) -> dict:
    path = project / PROFILE_FILE
    if not path.is_file():
        return default_printer_profile()
    obj = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(obj, dict) or obj.get('schema_version') != 1:
        raise ValueError('printer_profile.json must contain schema_version 1')
    for key in ('trim_width_mm','trim_height_mm','required_bleed_mm','safe_inset_mm','minimum_effective_dpi'):
        v = obj.get(key)
        if (not isinstance(v,(int,float)) or isinstance(v,bool) or not math.isfinite(v) or
                v < 0 or (key in ('trim_width_mm','trim_height_mm','minimum_effective_dpi') and v == 0)):
            raise ValueError(f'Invalid printer profile value: {key}')
    if obj['safe_inset_mm'] * 2 >= min(obj['trim_width_mm'],obj['trim_height_mm']):
        raise ValueError('Printer safe inset must leave space inside trim')
    if obj['required_bleed_mm'] > 15:
        raise ValueError('Bleed over 15 mm requires a custom workflow')
    if not isinstance(obj.get('verified_against_printer'),bool):
        raise ValueError('verified_against_printer must be true/false')
    return obj


def write_printer_profile(project: Path, profile: dict, *, overwrite: bool=False) -> Path:
    path = project / PROFILE_FILE
    if path.exists() and not overwrite:
        raise FileExistsError(f'Printer profile already exists: {path}')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile, indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    return path


def release_gate(report: dict, profile: dict) -> dict:
    """A transparent readiness checklist, NOT an automatic manufacturing approval."""
    blockers=[]
    if report['errors']:
        blockers.append(f"Resolve {report['errors']} automated error(s)")
    if report['warnings']:
        blockers.append(f"Review {report['warnings']} automated warning(s)")
    if (not profile.get('verified_against_printer') or 'UNCONFIRMED' in profile.get('printer_name','').upper()
        or not str(profile.get('verified_by') or '').strip()):
        blockers.append('Confirm the printer profile against the actual manufacturer quote/template')
    for key, report_key in [('trim_width_mm','card_width_mm'),('trim_height_mm','card_height_mm')]:
        if abs(profile[key] - report[report_key]) > 0.001:
            blockers.append(f'Printer {key} differs from the deck manifest')
    reviews=report.get('human_reviews',{}).get('counts',{})
    pending=reviews.get('unreviewed',79)+reviews.get('stale',0)
    if pending:
        blockers.append(f'Complete human visual reviews for {pending} unapproved/stale artwork item(s)')
    required_bleed=float(profile['required_bleed_mm'])
    supplied_bleed=float(report.get('source_bleed_mm',0))
    if supplied_bleed + 1e-8 < required_bleed:
        blockers.append(f'Artwork has {supplied_bleed:g} mm declared source bleed; printer requires {required_bleed:g} mm')
    if (report.get('back',{}).get('present') is not True):
        blockers.append('Provide and review the common card back')
    if not profile.get('packaging_dieline_supplied'):
        blockers.append('Obtain and verify the exact supplier tuck-box dieline, if packaging is in scope')
    blockers += [
        'Final printed proof, colour conversion, QR physical scan and licensing still require human/manufacturer confirmation'
    ]
    # The last item is not a machine-checkable blocker. Keep a separate manual list.
    manual=blockers.pop()
    return {
        'status': 'REVIEW_PENDING' if blockers else 'TECHNICAL_HANDOFF_CANDIDATE',
        'blockers': blockers,
        'manual_final_verifications': [manual,
           'Packaging geometry, colour/ICC, paper stock and press proof must be signed off by the printer'],
        'printer': profile.get('printer_name'),
        'verified_against_printer': profile.get('verified_against_printer',False),
    }
