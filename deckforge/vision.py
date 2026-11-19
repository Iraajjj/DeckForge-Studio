"""Optional AI-assisted visual review and local palette diagnostics.

No network request happens during audit, build, or demo. A user must explicitly
run ``vision-review`` (or confirm the GUI action) and set OPENAI_API_KEY.
Vision output is non-authoritative; it NEVER signs off card artwork.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import urllib.error
import urllib.request
from typing import Callable

from PIL import Image, ImageOps

from .project import read_config, safe_relative_file

VISION_FILE = 'vision_reviews.json'
BRIEF_FILE = 'vision_brief.json'
SCHEMA_VERSION = 1

SUIT_OBJECTS = {'W': 'wooden wands / staffs', 'C': 'golden chalices / cups',
                'S': 'silver swords', 'P': 'golden five-pointed-star discs / pentacles'}

AI_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'properties': {
        'observed_symbol_count': {'type': ['integer', 'null']},
        'count_confidence': {'type': 'string', 'enum': ['high','medium','low','unavailable']},
        'count_explanation': {'type': 'string'},
        'style_match': {'type': 'string', 'enum': ['consistent','possible_difference','uncertain','not_assessed']},
        'style_explanation': {'type': 'string'},
        'identity_findings': {'type': 'array','items': {'type':'string'}},
        'text_findings': {'type': 'array','items': {'type':'string'}},
        'other_findings': {'type': 'array','items': {'type':'string'}},
    },
    'required': ['observed_symbol_count','count_confidence','count_explanation',
                 'style_match','style_explanation','identity_findings','text_findings','other_findings'],
}


def expected_suit_count(card_id: str) -> tuple[str | None, int | None]:
    if len(card_id) != 3 or card_id[0] not in SUIT_OBJECTS or not card_id[1:].isdigit():
        return None, None
    rank = int(card_id[1:])
    if rank < 1 or rank > 14:
        return None, None
    return SUIT_OBJECTS[card_id[0]], rank if rank <= 10 else 1


def default_brief() -> dict:
    return {
        'schema_version': 1,
        'style_reference_file': None,
        'cards': {
            'S07': {'expected_characters': [], 'special_checks': ['Count physical swords only, not printed motifs.']},
            'P09': {'expected_characters': [], 'special_checks': ['Verify upright five-pointed-star discs are distinct.']},
        },
        'note': 'Optional human-authored art direction. Add named cast and mandatory scene elements per card.',
    }


def load_brief(project: Path) -> dict:
    path = project / BRIEF_FILE
    if not path.exists():
        return default_brief()
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or data.get('schema_version') != SCHEMA_VERSION:
        raise ValueError('vision_brief.json requires schema_version 1')
    cards = data.get('cards', {})
    if not isinstance(cards, dict):
        raise ValueError('vision_brief cards must be an object')
    ref = data.get('style_reference_file')
    if ref is not None:
        p, _ = safe_relative_file(project, ref)
        if not p.is_file():
            raise ValueError('Style reference image does not exist')
    for cid, spec in cards.items():
        if not isinstance(spec, dict):
            raise ValueError(f'Invalid vision brief for {cid}')
        for key in ('expected_characters','special_checks'):
            if key in spec and (not isinstance(spec[key], list) or
                                any(not isinstance(v,str) for v in spec[key])):
                raise ValueError(f'{cid}: {key} must be a list of text strings')
    return data


def init_brief(project: Path, *, overwrite: bool = False) -> Path:
    target = project / BRIEF_FILE
    if target.exists() and not overwrite:
        raise FileExistsError('vision_brief.json already exists; editing it is non-destructive')
    target.write_text(json.dumps(default_brief(), indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    return target


def _jpeg_data_url(path: Path, max_edge: int = 1600) -> str:
    if max_edge < 512 or max_edge > 2500:
        raise ValueError('max_edge must be between 512 and 2500 pixels')
    with Image.open(path) as image:
        im = ImageOps.exif_transpose(image).convert('RGB')
        im.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
        buf = BytesIO()
        im.save(buf, 'JPEG', quality=89, subsampling=0)
    return 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')


def _palette(path: Path) -> list[float]:
    """HS(V) histogram: conservative whole-image colour distribution, not semantics."""
    with Image.open(path) as original:
        im = ImageOps.exif_transpose(original).convert('RGB').resize((96, 96))
    hsv = im.convert('HSV')
    bins = [0] * (12 + 4 + 4)
    for h,s,v in (hsv.get_flattened_data() if hasattr(hsv,"get_flattened_data") else hsv.getdata()):
        bins[min(h * 12 // 256, 11)] += 1
        bins[12 + min(s * 4 // 256, 3)] += 1
        bins[16 + min(v * 4 // 256, 3)] += 1
    size = 96 * 96
    return [n / size for n in bins]


def palette_distance(path: Path, reference: Path) -> float:
    """0=equal HSV distributions, 1=strongly different. NOT a style validator."""
    a, b = _palette(path), _palette(reference)
    return round(sum(abs(x-y) for x,y in zip(a,b)) / 6, 4)


def build_request(project: Path, cid: str, *, model: str, max_edge: int = 1600,
                  include_reference: bool = True) -> tuple[dict, str, float | None]:
    cfg = read_config(project)
    matches = [x for x in cfg['cards'] if x['id'] == cid]
    if len(matches) != 1:
        raise ValueError(f'Unknown card ID: {cid}')
    path, _ = safe_relative_file(project, matches[0]['file'])
    if not path.is_file():
        raise FileNotFoundError(f'{cid} image not found: {path}')
    brief = load_brief(project)
    spec = brief.get('cards',{}).get(cid,{})
    object_name, expected = expected_suit_count(cid)
    cast = spec.get('expected_characters', [])
    checks = spec.get('special_checks', [])
    prompt = (
        'You are a cautious visual QA assistant for an illustrated tarot card. ' 
        'Identify only what you can SEE; do not make up hidden objects or assume numbers from the title. ' 
        f'Card: {cid} - {matches[0]["title"]}. '
        f'Physical suit objects: {object_name or "no fixed counted suit object for a Major Arcana"}. '
        f'Expected physical quantity: {expected if expected is not None else "not specified"}. '
        f'Expected named characters: {json.dumps(cast)}. Other editorial checks: {json.dumps(checks)}. '
        'Count independently separated physical objects, including held items. ' 
        'A star printed on a belly badge or clothing is NOT a separate suit object. '
        'If overlapping or uncertain, set count_confidence low or unavailable. '
        'Do not infer license status, print readiness or character identity with certainty. '
        'Give short, actionable, non-definitive findings; no automatic approval.'
    )
    content = [{'type':'input_text','text':prompt},
               {'type':'input_image','image_url':_jpeg_data_url(path,max_edge),'detail':'high'}]
    distance = None
    ref = brief.get('style_reference_file')
    if ref:
        refpath, _ = safe_relative_file(project,ref)
        distance = palette_distance(path,refpath)
        if include_reference:
            content[0]['text'] += (' The SECOND image is an approved visual style reference, ' 
                                   'NOT another card; do not include its objects when counting.')
            content.append({'type':'input_image','image_url':_jpeg_data_url(refpath,max_edge),'detail':'low'})
        else:
            content[0]['text'] += ' No image style reference is available for comparison.'
    else:
        content[0]['text'] += ' No image style reference is available; mark style_match not_assessed.'
    payload = {
        'model': model,
        'store': False,
        'input': [{'role':'user','content':content}],
        'text': {'format': {'type':'json_schema','name':'deckforge_visual_audit',
                            'strict':True,'schema':AI_SCHEMA}},
        'max_output_tokens': 1100,
    }
    return payload, sha256(path.read_bytes()).hexdigest(), distance


def _post_responses(payload: dict, api_key: str) -> dict:
    url = 'https://api.openai.com/v1/responses'
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, method='POST', headers={
        'Content-Type':'application/json',
        'Authorization':'Bearer ' + api_key,
    })
    try:
        with urllib.request.urlopen(req, timeout=100) as response:
            return json.loads(response.read(2_000_000))
    except urllib.error.HTTPError as ex:
        # Do NOT print token, input image or whole response bodies to logs.
        raise RuntimeError(f'Vision API returned HTTP {ex.code}. Check model, billing and permissions.') from None
    except urllib.error.URLError:
        raise RuntimeError('Vision API unavailable: check network and API endpoint.') from None


def _extract_structured_answer(response: dict) -> dict:
    if not isinstance(response,dict):
        raise ValueError('Invalid API response')
    parts = [c.get('text','') for out in response.get('output',[]) if out.get('type')=='message'
             for c in out.get('content',[]) if c.get('type')=='output_text']
    if not parts:
        raise ValueError('Model did not return structured text (may be refusal/incomplete).')
    answer = json.loads(''.join(parts))
    if not isinstance(answer,dict) or set(answer)!=set(AI_SCHEMA['properties']):
        raise ValueError('Model output schema did not match requirements')
    for fld in ('identity_findings','text_findings','other_findings'):
        if not isinstance(answer[fld],list) or any(not isinstance(x,str) for x in answer[fld]):
            raise ValueError('Invalid findings list')
    if answer['observed_symbol_count'] is not None and (
        not isinstance(answer['observed_symbol_count'],int) or
        isinstance(answer['observed_symbol_count'],bool) or
        not 0 <= answer['observed_symbol_count'] <= 78
    ):
        raise ValueError('Invalid visual count')
    if answer['count_confidence'] not in ['high','medium','low','unavailable']:
        raise ValueError('Invalid count confidence')
    return answer


def read_vision_results(project: Path, config: dict | None = None) -> dict:
    """Mark cached findings stale if the image has since changed; never approve."""
    cfg = config or read_config(project)
    path = project / VISION_FILE
    if not path.exists():
        return {'status':'not_run', 'items':{}, 'counts':{'current':0,'stale':0}}
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data,dict) or data.get('schema_version') != 1 or not isinstance(data.get('results'),dict):
        raise ValueError('vision_reviews.json is not a valid V4 review file')
    by_id={x['id']:x for x in cfg['cards']}
    items={}
    for cid,v in data['results'].items():
        if cid not in by_id or not isinstance(v,dict):
            continue
        try:
            image,_=safe_relative_file(project,by_id[cid]['file'])
            valid=image.is_file() and sha256(image.read_bytes()).hexdigest()==v.get('image_sha256')
        except (ValueError,OSError):
            valid=False
        items[cid]={**v,'cache_status': 'current' if valid else 'stale'}
    current=sum(v['cache_status']=='current' for v in items.values())
    return {'status':'suggestions_only', 'items':items,
            'counts':{'current':current,'stale':len(items)-current},
            'disclaimer':'Model-suggested observations are NOT human approvals or verified physical counts.'}


def vision_review(project: Path, card_ids: list[str], *, model: str,
                  api_key: str | None = None, request_fn: Callable[[dict,str],dict] | None = None,
                  max_cards: int = 5, include_reference: bool = True) -> dict:
    """Run ONLY for explicitly selected artwork; may incur third-party API fees.

    Inject request_fn in tests to exercise the full response path without network.
    """
    if not card_ids or len(card_ids)>max_cards or max_cards>78 or len(set(card_ids))!=len(card_ids):
        raise ValueError('Select distinct card IDs within the explicit --max-cards limit')
    if not model.strip():
        raise ValueError('Select an explicit vision-capable model')
    token = api_key or os.environ.get('OPENAI_API_KEY','')
    if not token:
        raise ValueError('Set OPENAI_API_KEY in your environment before explicitly requesting AI review')
    existing = project / VISION_FILE
    data = {'schema_version':1,'results':{}}
    if existing.exists():
        prior=json.loads(existing.read_text(encoding='utf-8'))
        if prior.get('schema_version')!=1 or not isinstance(prior.get('results'),dict):
            raise ValueError('Existing vision_reviews.json has an unsupported format')
        data=prior
    fn=request_fn or _post_responses
    updates={}
    for cid in card_ids:
        payload, fingerprint, distance = build_request(project,cid,model=model,
                                                       include_reference=include_reference)
        response=fn(payload,token)
        obs=_extract_structured_answer(response)
        obj,n=expected_suit_count(cid)
        observed=obs['observed_symbol_count']
        mismatch=(n is not None and observed is not None and observed != n)
        # Even a matching count remains an uncertain machine suggestion.
        updates[cid]={
            'card_id':cid, 'model':model, 'image_sha256':fingerprint,
            'reviewed_at_utc':datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'expected_symbol':obj, 'expected_symbol_count':n,
            'palette_distance_heuristic':distance,
            'possible_count_mismatch':mismatch,
            'requires_human_check':True,
            'observations':obs,
            'usage':response.get('usage',{}),
        }
    # Save only after all selected cards succeed, and use atomic replacement.
    data['results'].update(updates)
    tmp=existing.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    tmp.replace(existing)
    return {'reviewed':len(updates),'path':str(existing),
            'possible_mismatches':[cid for cid,v in updates.items() if v['possible_count_mismatch']],
            'status':'SUGGESTIONS_ONLY','records':updates}
