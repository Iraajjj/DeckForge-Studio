"""Human visual sign-offs, cryptographically bound to the exact source image.

A review is an attestation by a person, NOT automatic inspection, rights clearance,
or a substitute for manufacturer proof approval.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from .catalog import expected_cards
from .project import read_config, safe_relative_file

REVIEW_FILE = 'human_reviews.json'
CRITERIA = (
    'tarot_symbols_and_counts',
    'character_identity_and_badges',
    'title_and_typography',
    'composition_and_safe_edges',
    'artwork_rights_checked',
)
BACK_CRITERIA = (
    'rotation_and_symmetry',
    'colors_and_design',
    'safe_edges_and_bleed',
    'artwork_rights_checked',
)
ALL_IDS = {c['id'] for c in expected_cards()} | {'BACK'}


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _json_path(project: Path) -> Path:
    return project / REVIEW_FILE


def load_reviews(project: Path) -> dict:
    path = _json_path(project)
    if not path.is_file():
        return {'schema_version': 1, 'reviews': {}}
    obj = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(obj, dict) or obj.get('schema_version') != 1 or not isinstance(obj.get('reviews'), dict):
        raise ValueError('human_reviews.json has an invalid schema')
    return obj


def save_reviews(project: Path, ledger: dict) -> Path:
    # Write atomically to prevent a partial review ledger after interruption.
    path = _json_path(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(path)
    return path


def _card_path(project: Path, card_id: str, config: dict) -> Path:
    if card_id not in ALL_IDS:
        raise ValueError(f'Unknown card ID: {card_id}')
    if card_id == 'BACK':
        raw = config.get('back_file')
    else:
        matching = [c for c in config['cards'] if isinstance(c, dict) and c.get('id') == card_id]
        raw = matching[0].get('file') if len(matching) == 1 else None
    if not raw:
        raise ValueError(f'No artwork mapped to {card_id}')
    path, _ = safe_relative_file(project, raw)
    if not path.is_file():
        raise FileNotFoundError(f'Artwork missing for {card_id}: {path}')
    return path


def _hash_card(project: Path, cid: str, config: dict) -> str | None:
    try:
        return sha256(_card_path(project, cid, config).read_bytes()).hexdigest()
    except (FileNotFoundError, ValueError, OSError):
        return None


def approve(project: Path, card_id: str, reviewer: str, checks: list[str], *, note: str = '') -> Path:
    """Record a fully checked visual approval. One card, one explicit human decision."""
    if card_id not in ALL_IDS:
        raise ValueError(f'Unknown card ID: {card_id}')
    if not isinstance(reviewer, str) or not reviewer.strip() or len(reviewer) > 120:
        raise ValueError('Provide a reviewer name (1-120 characters)')
    required = set(BACK_CRITERIA if card_id == 'BACK' else CRITERIA)
    if not isinstance(checks, list) or set(checks) != required or len(checks) != len(required):
        raise ValueError('Check every required human review criterion for this artwork')
    if len(note) > 1000:
        raise ValueError('Review note is limited to 1,000 characters')
    cfg = read_config(project)
    digest = _hash_card(project, card_id, cfg)
    if digest is None:
        raise FileNotFoundError(f'Artwork missing for {card_id}')
    ledger = load_reviews(project)
    ledger['reviews'][card_id] = {
        'asset_sha256': digest,
        'reviewer': reviewer.strip(),
        'approved_at_utc': _utc(),
        'checks': list(checks),
        'note': note,
    }
    return save_reviews(project, ledger)


def revoke(project: Path, card_id: str) -> Path:
    if card_id not in ALL_IDS:
        raise ValueError(f'Unknown card ID: {card_id}')
    ledger = load_reviews(project)
    ledger['reviews'].pop(card_id, None)
    return save_reviews(project, ledger)


def review_status(project: Path, config: dict | None = None) -> dict:
    cfg = config or read_config(project)
    ledger = load_reviews(project)
    per_card = {}
    totals = {'approved': 0, 'stale': 0, 'unreviewed': 0}
    for card_id in [c['id'] for c in expected_cards()] + ['BACK']:
        rec = ledger['reviews'].get(card_id)
        digest = _hash_card(project, card_id, cfg)
        required = set(BACK_CRITERIA if card_id == 'BACK' else CRITERIA)
        if not rec:
            state = 'unreviewed'
        elif (not isinstance(rec, dict) or rec.get('asset_sha256') != digest or digest is None or
              set(rec.get('checks', [])) != required):
            state = 'stale'
        else:
            state = 'approved'
        totals[state] += 1
        per_card[card_id] = {
            'status': state,
            'asset_sha256': digest,
            'reviewer': rec.get('reviewer') if isinstance(rec, dict) else None,
            'approved_at_utc': rec.get('approved_at_utc') if isinstance(rec, dict) else None,
        }
    return {'counts': totals, 'cards': per_card, 'total': len(per_card), 'criteria': list(CRITERIA),
            'back_criteria': list(BACK_CRITERIA)}


def import_reviews(project: Path, inbound: Path) -> dict:
    """Validate external review entries against current file fingerprints; never accept stale IDs."""
    obj = json.loads(inbound.read_text(encoding='utf-8'))
    if not isinstance(obj, dict) or obj.get('schema_version') != 1 or not isinstance(obj.get('reviews'), dict):
        raise ValueError('Invalid review import format')
    current = load_reviews(project)
    cfg = read_config(project)
    accepted, rejected, revoked = [], [], []
    to_revoke = obj.get('revoked', [])
    if not isinstance(to_revoke,list) or any(cid not in ALL_IDS for cid in to_revoke):
        raise ValueError('Invalid revoked review IDs')
    for cid in to_revoke:
        current['reviews'].pop(cid, None)
        revoked.append(cid)
    for cid, rec in obj['reviews'].items():
        if cid not in ALL_IDS or not isinstance(rec, dict):
            rejected.append(cid); continue
        digest = _hash_card(project, cid, cfg)
        required = set(BACK_CRITERIA if cid == 'BACK' else CRITERIA)
        checks = rec.get('checks')
        valid = (digest is not None and rec.get('asset_sha256') == digest and
                 isinstance(checks, list) and set(checks) == required and len(checks) == len(required) and
                 isinstance(rec.get('reviewer'), str) and bool(rec['reviewer'].strip()) and
                 isinstance(rec.get('approved_at_utc'), str) and
                 isinstance(rec.get('note', ''), str))
        if not valid:
            rejected.append(cid); continue
        current['reviews'][cid] = {k: rec.get(k) for k in ('asset_sha256','reviewer','approved_at_utc','checks','note')}
        accepted.append(cid)
    if accepted or revoked:
        save_reviews(project, current)
    return {'accepted': accepted, 'rejected': rejected, 'accepted_count': len(accepted),
            'rejected_count': len(rejected), 'revoked': revoked}
