"""Reviewable artwork import planner; never guesses or overwrites silently."""
from __future__ import annotations

from dataclasses import dataclass, asdict
import json
from pathlib import Path
import re
import shutil

from .catalog import expected_cards, slugify
from .project import read_config, safe_relative_file

SUPPORTED = {'.jpg', '.jpeg', '.png', '.webp', '.tif', '.tiff'}


@dataclass
class ImportRow:
    source: str
    destination: str | None
    card_id: str | None
    title: str | None
    status: str
    explanation: str


def _lookup_file_id(stem: str) -> str | None:
    """Accept only well-defined IDs or a unique canonical card title."""
    norm = slugify(stem)
    id_match = re.search(r'(?:^|_)(m(?:0\d|1\d|2[01])|[wcsp](?:0?[1-9]|1[0-4]))(?:_|$)', norm)
    if id_match:
        match = id_match.group(1).upper()
        if match[0] != 'M':
            match = match[0] + match[1:].zfill(2)
        return match
    hits=[]
    for card in expected_cards():
        slug = slugify(card['title'])
        # Full consecutive title token match only, avoid vague fuzzy guesses.
        if re.search(r'(?:^|_)'+re.escape(slug)+r'(?:_|$)', norm):
            hits.append(card['id'])
    return hits[0] if len(hits) == 1 else None


def plan_import(project_dir: Path, incoming_dir: Path) -> dict:
    """Return unambiguous mappings and conflict rows without mutating anything."""
    cfg = read_config(project_dir)
    if not incoming_dir.is_dir():
        raise FileNotFoundError(f"Not a folder: {incoming_dir}")
    by_id = {c['id']: c for c in cfg['cards'] if isinstance(c, dict) and isinstance(c.get('id'), str)}
    existing: dict[str, list[Path]] = {}
    candidate_files = sorted((p for p in incoming_dir.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED), key=lambda p:p.name.casefold())
    for p in candidate_files:
        cid = _lookup_file_id(p.stem)
        if cid and cid in by_id:
            existing.setdefault(cid,[]).append(p)
    results=[]
    for src in candidate_files:
        cid = _lookup_file_id(src.stem)
        if not cid or cid not in by_id:
            results.append(ImportRow(src.name,None,None,None,'UNMATCHED','No unique canonical title or valid ID found'))
            continue
        c=by_id[cid]
        try:
            target, _ = safe_relative_file(project_dir,c['file'])
        except ValueError:
            results.append(ImportRow(src.name,None,cid,c.get('title'),'BLOCKED','Manifest has unsafe destination path'))
            continue
        dest_rel = target.relative_to(project_dir.resolve())
        dest_rel = dest_rel.with_suffix(src.suffix.lower())
        dest, _ = safe_relative_file(project_dir,str(dest_rel))
        if len(existing.get(cid,[])) > 1:
            status,desc='CONFLICT','Several files match the same card. Rename or remove duplicates before importing.'
        elif target.exists() or dest.exists():
            status,desc='EXISTS','Target card image already exists; never overwrite automatically.'
        else:
            status,desc='READY','Unique title or ID match; safe to import.'
        results.append(ImportRow(src.name, str(dest_rel.as_posix()),cid,c.get('title'),status,desc))
    counts={s:sum(r.status==s for r in results) for s in ('READY','CONFLICT','EXISTS','UNMATCHED','BLOCKED')}
    return {'project':str(project_dir.resolve()),'incoming':str(incoming_dir.resolve()),'counts':counts,'items':[asdict(r) for r in results]}


def apply_import(project_dir: Path, incoming_dir: Path) -> dict:
    """Copy ONLY READY files; update manifest extension; never overwrite or move sources."""
    result = plan_import(project_dir,incoming_dir)
    cfg = read_config(project_dir)
    by_id = {c['id']:c for c in cfg['cards']}
    changes=[]
    for row in result['items']:
        if row['status'] != 'READY':
            continue
        src = incoming_dir / row['source']
        dest, rel = safe_relative_file(project_dir, row['destination'])
        dest.parent.mkdir(parents=True, exist_ok=True)
        # Race-safe file creation: 'xb' will fail instead of overwriting.
        with src.open('rb') as fi, dest.open('xb') as fo:
            shutil.copyfileobj(fi,fo)
        by_id[row['card_id']]['file'] = rel
        changes.append({'card_id':row['card_id'],'source':row['source'],'destination':rel})
    if changes:
        manifest=project_dir/'deckforge.json'
        backup=project_dir/'deckforge_before_import.json'
        if not backup.exists():
            shutil.copy2(manifest,backup)
        temp=manifest.with_suffix('.json.tmp')
        temp.write_text(json.dumps(cfg,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
        temp.replace(manifest)
    result['applied']=changes
    return result
