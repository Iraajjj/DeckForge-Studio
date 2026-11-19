from __future__ import annotations

import json
from pathlib import Path
import zipfile

import pytest
from PIL import Image,ImageDraw

from deckforge.advanced import dhash, near_duplicate_score, rotation_difference
from deckforge.build import run_audit, run_build, verify_package
from deckforge.importer import plan_import, apply_import, _lookup_file_id
from deckforge.project import default_config, read_config, write_config


def test_filename_mapping_is_conservative():
    assert _lookup_file_id('M00_the_fool_final')=='M00'
    assert _lookup_file_id('Nine_of_Pentacles_v2')=='P09'
    assert _lookup_file_id('P14_king_of_pentacles')=='P14'
    assert _lookup_file_id('amazing_mystical_card') is None
    assert _lookup_file_id('my_five_swords_like_card') is None


def test_import_plan_and_apply_never_overwrite(tmp_path):
    project=tmp_path/'project';incoming=tmp_path/'incoming';incoming.mkdir()
    write_config(project,default_config('My cards'))
    im=Image.new('RGB',(840,1440),'pink')
    im.save(incoming/'Nine Of Pentacles.png')
    im.save(incoming/'M00_the_fool_final.jpg')
    im.save(incoming/'unmapped_art.png')
    r=plan_import(project,incoming)
    assert r['counts']['READY']==2
    assert r['counts']['UNMATCHED']==1
    assert not (project/'cards'/'pentacles'/'09_nine_of_pentacles.png').exists()
    apply=apply_import(project,incoming)
    assert len(apply['applied'])==2
    assert (project/'deckforge_before_import.json').exists()
    cfg=read_config(project)
    assert next(c for c in cfg['cards'] if c['id']=='M00')['file'].endswith('.jpg')
    assert (project/'cards'/'major_arcana'/'00_the_fool.jpg').exists()
    repeat=plan_import(project,incoming)
    assert repeat['counts']['EXISTS']==2


def test_conflicting_imports_are_never_copied(tmp_path):
    project=tmp_path/'project';incoming=tmp_path/'incoming';incoming.mkdir()
    write_config(project,default_config())
    im=Image.new('RGB',(840,1440),'purple')
    im.save(incoming/'M00_the_fool.png')
    im.save(incoming/'the_fool_final.png')
    planned=plan_import(project,incoming)
    assert planned['counts']['CONFLICT']==2
    result=apply_import(project,incoming)
    assert not result['applied']


def test_reversible_back_heuristic_identifies_asymmetry(tmp_path):
    project=tmp_path/'project'
    cfg=default_config()
    write_config(project,cfg)
    back=Image.new('RGB',(700,1200),'#30244a')
    draw=ImageDraw.Draw(back)
    draw.ellipse((60,100,300,360),fill='#ffff66')
    back.save(project/'back.png')
    report=run_audit(project)
    assert report['back']['present']
    assert report['back']['rotation_difference']>0.04
    assert any(i['code']=='BACK_ROTATION_MISMATCH' for i in report['issues'])


def test_exact_rotational_symmetry_does_not_warn(tmp_path):
    project=tmp_path/'project'
    cfg=default_config()
    write_config(project,cfg)
    back=Image.new('RGB',(840,1440),'#30244a')
    d=ImageDraw.Draw(back)
    d.rectangle((220,220,300,320),fill='gold')
    d.rectangle((840-300,1440-320,840-220,1440-220),fill='gold')
    back.save(project/'back.png')
    result=run_audit(project)
    assert result['back']['rotation_difference']<0.02
    assert not any(i['code']=='BACK_ROTATION_MISMATCH' for i in result['issues'])


def test_near_duplicate_warns_on_modified_pixels(tmp_path):
    project=tmp_path/'project';cfg=default_config();write_config(project,cfg)
    art=Image.new('RGB',(840,1440),'plum')
    d=ImageDraw.Draw(art);d.ellipse((180,290,700,890),fill='pink')
    p1=project/cfg['cards'][0]['file'];p2=project/cfg['cards'][1]['file']
    art.save(p1)
    art2=art.copy()
    d=ImageDraw.Draw(art2);d.ellipse((410,700,425,715),fill='white')
    art2.save(p2)
    r=run_audit(project)
    assert not any(i['code']=='IDENTICAL_ART' for i in r['issues'])
    assert any(i['code']=='NEAR_DUPLICATE_ART' for i in r['issues'])


def test_html_dashboard_safe_and_offline(tmp_path):
    project=tmp_path/'project';cfg=default_config('Sample <script>alert(1)</script>')
    write_config(project,cfg)
    report,_,_=run_build(project,project/'build',skip_safety=True)
    html=(project/'build'/'qa_dashboard.html').read_text(encoding="utf-8")
    assert 'data:image' not in html or 'data:image/png' in html # QR omitted if no link
    assert 'qa_dashboard' not in str(report)
    assert '<script>alert(1)</script>' not in html
    assert 'Card gallery' in html and 'Issue explorer' in html
    assert not (project/'build'/'safe_area_REVIEW_ONLY.pdf').exists()


def test_zip_integrity_detects_tampering(tmp_path):
    project=tmp_path/'project';write_config(project,default_config())
    _,path,_=run_build(project,project/'build',skip_safety=True)
    valid=verify_package(path)
    assert valid['ok'] and valid['checked']>3
    modified=tmp_path/'tampered.zip'
    with zipfile.ZipFile(path) as z0, zipfile.ZipFile(modified,'w') as z1:
        for name in z0.namelist():
            payload=z0.read(name)
            if name=='production_review/qa_report.md':payload+=b'garbage'
            z1.writestr(name,payload)
    assert not verify_package(modified)['ok']


def test_build_does_not_leave_stale_qr(tmp_path):
    project=tmp_path/'project'
    cfg=default_config(guide_url='https://example.org/guide')
    write_config(project,cfg)
    output=project/'build';run_build(project,output,skip_safety=True)
    assert (output/'qr_30mm_vector.svg').is_file()
    cfg['guide_url']=''
    (project/'deckforge.json').write_text(json.dumps(cfg))
    run_build(project,output,skip_safety=True)
    assert not (output/'qr_30mm_vector.svg').exists()


def test_config_print_limits(tmp_path):
    p=tmp_path/'deck';cfg=default_config();cfg['safe_area_mm']=999
    write_config(p,cfg)
    with pytest.raises(ValueError):read_config(p)


def test_generate_safety_pdf(tmp_path):
    project=tmp_path/'project';write_config(project,default_config())
    _,_,_=run_build(project,project/'build')
    pdf=project/'build'/'safe_area_REVIEW_ONLY.pdf'
    assert pdf.is_file() and pdf.stat().st_size>2000


def test_back_difference_zero_for_uniform():
    im=Image.new('RGB',(700,1200),'purple')
    assert rotation_difference(im)==0
