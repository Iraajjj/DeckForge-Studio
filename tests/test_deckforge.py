from __future__ import annotations

import json
import zipfile
from pathlib import Path

from PIL import Image

from deckforge.catalog import expected_cards
from deckforge.project import default_config, write_config, safe_relative_file
from deckforge.validation import inspect_deck
from deckforge.qr import export_qr_assets, qr_matrix
from deckforge.build import run_build
from deckforge.cli import main


def test_catalog_has_78_unique_cards():
    cards = expected_cards()
    assert len(cards) == 78
    assert len({c['id'] for c in cards}) == 78
    assert len({c['file'] for c in cards}) == 78
    assert cards[0]['id'] == 'M00'
    assert cards[-1]['title'] == 'King of Pentacles'


def test_init_and_missing_art_are_reported(tmp_path):
    project = tmp_path/'deck'
    write_config(project,default_config('Sample', 'png'))
    r=inspect_deck(project,default_config('Sample', 'png'))
    assert r['present_cards'] == 0
    assert sum(i['code']=='MISSING_IMAGE' for i in r['issues']) == 78
    assert r['errors'] == 78


def test_duplicate_art_and_low_dpi(tmp_path):
    project = tmp_path/'deck'
    cfg=default_config('Sample', 'png')
    write_config(project,cfg)
    same=Image.new('RGB',(140,240),'pink')
    for entry in cfg['cards'][:2]:
        same.save(project/entry['file'])
    r=inspect_deck(project,cfg)
    assert r['present_cards'] == 2
    assert any(i['code']=='IDENTICAL_ART' for i in r['issues'])
    assert sum(i['code']=='LOW_RESOLUTION' for i in r['issues']) == 2


def test_unsafe_path_does_not_escape_project(tmp_path):
    cfg=default_config()
    cfg['cards'][0]['file']='../../secrets.png'
    write_config(tmp_path,cfg)
    assert any(i['code']=='UNSAFE_PATH' for i in inspect_deck(tmp_path,cfg)['issues'])
    try:
        safe_relative_file(tmp_path,'../../secrets.png')
        assert False, 'should block traversal'
    except ValueError:
        pass


def test_qr_is_vector_and_raster(tmp_path):
    files=export_qr_assets('https://example.org/guide',tmp_path)
    assert len(files)==4
    assert all(p.is_file() and p.stat().st_size>100 for p in files)
    assert len(qr_matrix('https://example.org/guide'))>20
    assert 'viewBox' in (tmp_path/'qr_30mm_vector.svg').read_text()
    from PIL import Image
    with Image.open(tmp_path/'qr_30mm_600dpi.png') as im:
        assert im.size[0]>=700


def test_build_creates_review_files_and_zip(tmp_path):
    project=tmp_path/'deck'
    cfg=default_config('Test Deck','png',guide_url='https://example.org/guide')
    write_config(project,cfg)
    out=tmp_path/'deliverables'
    report,package,code=run_build(project,out)
    assert code==2  # missing real art
    assert report['errors']==78
    assert (out/'contact_sheet_REVIEW_ONLY.pdf').exists()
    assert (out/'qa_report.md').exists()
    assert (out/'qr_30mm_vector.svg').exists()
    with zipfile.ZipFile(package) as z:
        names=z.namelist()
        assert 'deckforge.json' in names
        assert 'production_review/contact_sheet_REVIEW_ONLY.pdf' in names
        assert 'production_review/qr_30mm_vector.svg' in names


def test_cli_help(capsys):
    try:
        main(['--help'])
    except SystemExit as e:
        assert e.code == 0
    assert 'DeckForge Studio' in capsys.readouterr().out


def test_invalid_url_rejected(tmp_path):
    from deckforge.qr import check_url
    import pytest
    with pytest.raises(ValueError):
        check_url('file:///home/secret')
