"""V4 regression tests: opt-in AI, approval isolation, dieline overlays, ICC and packaging."""
from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image, ImageCms
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from pypdf import PdfReader

from deckforge.build import run_audit,run_build,verify_package
from deckforge.catalog import expected_cards
from deckforge.manufacturing import (init_template,inspect_template,create_packaging_overlay,
                                      convert_cmyk)
from deckforge.project import default_config,write_config
from deckforge.vision import (build_request,expected_suit_count,init_brief,palette_distance,
                              vision_review,read_vision_results)


def fixture_project(tmp_path:Path) -> Path:
    folder=tmp_path/'deck'
    write_config(folder,default_config('V4 sample'))
    return folder


def test_suit_counts_and_court_rules():
    assert expected_suit_count('P09')==('golden five-pointed-star discs / pentacles',9)
    assert expected_suit_count('S07')[1]==7
    assert expected_suit_count('C10')[1]==10
    assert expected_suit_count('W13')[1]==1
    assert expected_suit_count('M03')==(None,None)
    assert expected_suit_count('Z10')==(None,None)


def test_vision_requires_explicit_key_and_selection(tmp_path,monkeypatch):
    p=fixture_project(tmp_path)
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    with pytest.raises(ValueError,match='OPENAI_API_KEY'):
        vision_review(p,['P09'],model='test-model')
    with pytest.raises(ValueError,match='distinct'):
        vision_review(p,['P09']*6,model='test-model',api_key='test')
    assert not (p/'vision_reviews.json').exists()


def test_vision_mocked_api_detects_mismatch_but_no_human_approval(tmp_path):
    p=fixture_project(tmp_path)
    cfg=default_config()
    target=next(x for x in cfg['cards'] if x['id']=='P09')
    img=p/target['file']
    Image.new('RGB',(840,1440),'#b987da').save(img)
    init_brief(p)
    seen=[]
    answer={
        'observed_symbol_count':8,
        'count_confidence':'medium',
        'count_explanation':'eight clearly visible gold discs; one may be hidden',
        'style_match':'not_assessed',
        'style_explanation':'No reference supplied',
        'identity_findings':[], 'text_findings':[], 'other_findings':[],
    }
    def fake_api(req,key):
        assert key=='FAKE_FOR_TESTS'
        assert req['model']=='test-vision'
        assert req['store'] is False
        assert req['input'][0]['content'][1]['type']=='input_image'
        seen.append(req)
        return {'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(answer)}]}],
                'usage':{'input_tokens':8,'output_tokens':16}}
    r=vision_review(p,['P09'],model='test-vision',api_key='FAKE_FOR_TESTS',request_fn=fake_api)
    assert r['possible_mismatches']==['P09']
    assert len(seen)==1
    assert not (p/'human_reviews.json').exists()
    st=read_vision_results(p)
    assert st['counts']=={'current':1,'stale':0}
    assert st['items']['P09']['requires_human_check']
    Image.new('RGB',(840,1440),'#6944ca').save(img)
    assert read_vision_results(p)['counts']['stale']==1


def test_palette_style_reference_is_descriptive_only(tmp_path):
    a=tmp_path/'a.png';b=tmp_path/'b.png';c=tmp_path/'c.png'
    Image.new('RGB',(120,200),'purple').save(a)
    Image.new('RGB',(120,200),'purple').save(b)
    Image.new('RGB',(120,200),'lime').save(c)
    assert palette_distance(a,b)==0
    assert palette_distance(a,c)>0.2


def _make_factory_example(p:Path):
    (p/'factory').mkdir()
    path=p/'factory'/'die.pdf'
    c=canvas.Canvas(str(path),pagesize=(200*mm,130*mm))
    c.setStrokeColorRGB(1,0,0)
    c.rect(10*mm,10*mm,70*mm,110*mm)
    c.rect(100*mm,10*mm,70*mm,110*mm)
    c.setFont('Helvetica-Bold',10)
    c.drawString(15*mm,110*mm,'ILLUSTRATIVE TEST ONLY -- NOT SUPPLIER DIE')
    c.showPage();c.save()
    (p/'packaging').mkdir()
    Image.new('RGB',(840,1320),'#7750af').save(p/'packaging/front.png')
    Image.new('RGB',(840,1320),'#cf80aa').save(p/'packaging/back.png')
    data={
        'schema_version':1,'manufacturer':'ILLUSTRATIVE TEST SHEET ONLY',
        'official_template_pdf':'factory/die.pdf','template_received_from_manufacturer':True,
        'page_index':0,'coordinates':'top_left_mm',
        'panels':[{'name':'front','image_file':'packaging/front.png','x_mm':10,'y_mm':10,'width_mm':70,'height_mm':110},
                  {'name':'back','image_file':'packaging/back.png','x_mm':100,'y_mm':10,'width_mm':70,'height_mm':110}],
    }
    (p/'packaging_template.json').write_text(json.dumps(data))
    return data


def test_supplier_template_requires_real_pdf_and_geometry(tmp_path):
    p=fixture_project(tmp_path)
    init_template(p)
    r=inspect_template(p)
    assert r['status']=='needs_setup'
    assert r['panels']==0
    with pytest.raises(ValueError,match='Packaging template requires review'):
        create_packaging_overlay(p,p/'build')
    data=_make_factory_example(p)
    data['template_received_from_manufacturer']=False
    (p/'packaging_template.json').write_text(json.dumps(data))
    assert inspect_template(p)['status']=='needs_setup'
    data['template_received_from_manufacturer']=True
    data['panels'][1]['width_mm']=73
    (p/'packaging_template.json').write_text(json.dumps(data))
    assert any('aspect mismatch' in x for x in inspect_template(p)['issues'])


def test_provisional_overlay_two_pdfs_produced_and_one_page(tmp_path):
    p=fixture_project(tmp_path)
    _make_factory_example(p)
    r=create_packaging_overlay(p,p/'proofs')
    assert r['status']=='PROVISIONAL_NOT_PRINTER_APPROVED'
    assert r['panel_count']==2
    for target in (r['artwork_only'],r['proof']):
        pdf=PdfReader(target)
        assert len(pdf.pages)==1
        assert round(float(pdf.pages[0].mediabox.width)/mm)==200
    report=run_audit(p)
    assert report['packaging_template']['status']=='ready_for_provisional_overlay'


def test_template_path_traversal_rejected(tmp_path):
    p=fixture_project(tmp_path)
    d={'schema_version':1,'manufacturer':'test','official_template_pdf':'../escape.pdf',
       'template_received_from_manufacturer':True,'page_index':0,
       'coordinates':'top_left_mm','panels':[]}
    (p/'packaging_template.json').write_text(json.dumps(d))
    with pytest.raises(ValueError,match='project-relative'):
        inspect_template(p)


def test_color_export_rejects_rgb_icc_and_missing_source(tmp_path):
    p=fixture_project(tmp_path)
    rgb_profile=tmp_path/'rgb.icc'
    rgb_profile.write_bytes(ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes())
    with pytest.raises(ValueError,match='CMYK'):
        convert_cmyk(p,tmp_path/'out',rgb_profile,card_ids=['P09'])


def test_real_cmyk_profile_conversion_when_system_profile_available(tmp_path):
    profile=Path('/usr/share/color/icc/ghostscript/default_cmyk.icc')
    if not profile.exists():pytest.skip('A real CMYK ICC is not installed on this platform')
    p=fixture_project(tmp_path)
    item=next(x for x in default_config()['cards'] if x['id']=='P09')
    Image.new('RGB',(210,360),'#dd70cc').save(p/item['file'])
    with pytest.raises(ValueError,match='missing embedded source ICC'):
        convert_cmyk(p,tmp_path/'exports',profile,card_ids=['P09'])
    report=convert_cmyk(p,tmp_path/'exports',profile,card_ids=['P09'],assume_srgb_when_missing=True)
    assert report['items'][0]['source_icc_assumed_srgb']
    with Image.open(tmp_path/'exports'/'P09_CMYK.tif') as converted:
        assert converted.mode=='CMYK'
        assert converted.info.get('icc_profile')
    with pytest.raises(FileExistsError):
        convert_cmyk(p,tmp_path/'exports',profile,card_ids=['P09'],assume_srgb_when_missing=True)


def test_v4_build_includes_supplied_template_overlay_and_offline_vision_status(tmp_path):
    p=fixture_project(tmp_path)
    _make_factory_example(p)
    r,z,_=run_build(p,p/'build',skip_safety=True)
    assert r['vision_assistance']['status']=='not_run'
    assert r['packaging_template']['status']=='ready_for_provisional_overlay'
    assert (p/'build'/'packaging_ARTWORK_ONLY_PROVISIONAL.pdf').exists()
    assert (p/'build'/'packaging_SUPPLIER_LINES_REVIEW_ONLY.pdf').exists()
    text=(p/'build'/'qa_dashboard.html').read_text()
    assert 'AI-assisted artwork review' in text
    assert 'Official box template' in text
    assert verify_package(z)['ok']
