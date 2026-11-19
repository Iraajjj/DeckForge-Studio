"""Regression tests for V3's human sign-off, supplier profile and cost model."""
from __future__ import annotations

import json
from pathlib import Path
import zipfile

import pytest
from PIL import Image

from deckforge.actual_size import create_actual_size_proof
from deckforge.build import run_audit, run_build, verify_package
from deckforge.costing import calculate, example
from deckforge.printer import default_printer_profile, load_printer_profile, release_gate, write_printer_profile
from deckforge.project import default_config, read_config, write_config
from deckforge.reviews import CRITERIA, BACK_CRITERIA, approve, import_reviews, load_reviews, review_status, revoke


def project(tmp_path):
    p=tmp_path/'project'
    write_config(p,default_config('V3 fixture'))
    write_printer_profile(p,default_printer_profile())
    return p


def test_manual_review_requires_every_check_and_reviewer(tmp_path):
    p=project(tmp_path)
    file=p/read_config(p)['cards'][0]['file']
    Image.new('RGB',(840,1440),'pink').save(file)
    with pytest.raises(ValueError,match='every required'):
        approve(p,'M00','tester',list(CRITERIA[:-1]))
    with pytest.raises(ValueError,match='reviewer'):
        approve(p,'M00','   ',list(CRITERIA))
    assert not (p/'human_reviews.json').exists()


def test_review_is_bound_to_art_sha256_and_expires_after_change(tmp_path):
    p=project(tmp_path)
    path=p/read_config(p)['cards'][0]['file']
    Image.new('RGB',(840,1440),'pink').save(path)
    approve(p,'M00','Artist',list(CRITERIA),note='Hand-counted suit objects')
    assert review_status(p)['cards']['M00']['status']=='approved'
    Image.new('RGB',(840,1440),'purple').save(path)
    status=review_status(p)
    assert status['cards']['M00']['status']=='stale'
    assert status['counts']=={'approved':0,'stale':1,'unreviewed':78}


def test_back_review_uses_different_checks(tmp_path):
    p=project(tmp_path)
    Image.new('RGB',(840,1440),'#201030').save(p/'back.png')
    approve(p,'BACK','Designer',list(BACK_CRITERIA))
    assert review_status(p)['cards']['BACK']['status']=='approved'
    with pytest.raises(ValueError):approve(p,'BACK','Designer',list(CRITERIA))
    revoke(p,'BACK')
    assert review_status(p)['cards']['BACK']['status']=='unreviewed'


def test_review_import_rejects_changed_file_and_accepts_valid(tmp_path):
    p=project(tmp_path)
    path=p/read_config(p)['cards'][0]['file']
    Image.new('RGB',(840,1440),'pink').save(path)
    approve(p,'M00','Editor',list(CRITERIA))
    exported={'schema_version':1,'reviews':load_reviews(p)['reviews'].copy()}
    revoke(p,'M00')
    src=tmp_path/'manual-review.json';src.write_text(json.dumps(exported))
    result=import_reviews(p,src)
    assert result['accepted']==['M00']
    Image.new('RGB',(840,1440),'violet').save(path)
    revoke(p,'M00')
    result=import_reviews(p,src)
    assert result['rejected']==['M00']
    assert not load_reviews(p)['reviews']


def test_review_json_revocation(tmp_path):
    p=project(tmp_path)
    path=p/read_config(p)['cards'][0]['file']
    Image.new('RGB',(840,1440),'pink').save(path)
    approve(p,'M00','Artist',list(CRITERIA))
    revoked={'schema_version':1,'reviews':{},'revoked':['M00']}
    src=tmp_path/'revoked.json';src.write_text(json.dumps(revoked))
    result=import_reviews(p,src)
    assert result['revoked']==['M00']
    assert not load_reviews(p)['reviews']


def test_release_gate_requires_profile_bleed_and_79_approvals(tmp_path):
    p=project(tmp_path)
    report=run_audit(p)
    gate=report['release_gate']
    assert gate['status']=='REVIEW_PENDING'
    assert any('human visual reviews' in s for s in gate['blockers'])
    assert any('source bleed' in s for s in gate['blockers'])
    assert any('printer profile' in s for s in gate['blockers'])
    assert gate['manual_final_verifications']


def test_release_gate_individual_checks_are_independent():
    profile=default_printer_profile()
    profile.update(printer_name='Verified local print shop',verified_against_printer=True,
                   verified_by='Artist',packaging_dieline_supplied=True)
    report={'errors':0,'warnings':0,'card_width_mm':70,'card_height_mm':120,
            'source_bleed_mm':3,'human_reviews':{'counts':{'approved':79,'stale':0,'unreviewed':0}},
            'back':{'present':True}}
    gate=release_gate(report,profile)
    assert gate['status']=='TECHNICAL_HANDOFF_CANDIDATE'
    assert not gate['blockers']
    assert gate['manual_final_verifications']
    profile['printer_name']='UNCONFIRMED printer'
    assert release_gate(report,profile)['status']=='REVIEW_PENDING'


def test_nonexistent_printer_profile_defaults_to_unconfirmed(tmp_path):
    p=tmp_path/'empty';p.mkdir()
    assert load_printer_profile(p)['verified_against_printer'] is False


def test_printer_profile_rejects_invalid_numbers(tmp_path):
    p=project(tmp_path)
    profile=default_printer_profile();profile['required_bleed_mm']=-2
    (p/'printer_profile.json').write_text(json.dumps(profile))
    with pytest.raises(ValueError):load_printer_profile(p)


def test_source_bleed_changes_expected_aspect_without_auto_generation(tmp_path):
    p=project(tmp_path)
    cfg=read_config(p);cfg['source_bleed_mm']=3
    (p/'deckforge.json').write_text(json.dumps(cfg))
    path=p/cfg['cards'][0]['file']
    # Source dimensions are (70+6):(120+6), with actual 3 mm art extension.
    Image.new('RGB',(912,1512),'plum').save(path)
    report=run_audit(p)
    issue_codes=[i['code'] for i in report['issues'] if i['card_id']=='M00']
    assert 'ASPECT_RATIO' not in issue_codes
    assert 'LOW_RESOLUTION' not in issue_codes
    assert report['cards'][0]['dpi_at_trim']==[305,305]
    assert report['source_bleed_mm']==3


def test_actual_size_proof_produces_pdf(tmp_path):
    p=project(tmp_path)
    cfg=read_config(p)
    path=p/cfg['cards'][0]['file']
    Image.new('RGB',(840,1440),'blue').save(path)
    r=run_audit(p)
    out=tmp_path/'physical.pdf'
    create_actual_size_proof(p,r,out)
    assert out.read_bytes().startswith(b'%PDF')
    assert out.stat().st_size>10000


def test_cost_model_scenarios_are_estimates_only():
    x=example()
    report=calculate(x)
    assert report['illustrative_data_only'] is True
    assert len(report['rows'])==3
    assert report['rows'][0]['quantity']==20
    assert report['rows'][0]['estimated_unit_cost_landed']==15.8
    assert report['assumptions']['fees_are_user_supplied_not_current_platform_rates'] is True
    assert report['rows'][2]['estimated_profit_if_sold_out'] > report['rows'][0]['estimated_profit_if_sold_out']


def test_cost_model_rejects_invalid_marketplace_rate():
    x=example();x['marketplace_fee_fraction']=1.2
    with pytest.raises(ValueError):calculate(x)
    x=example();x['quotes'][0]['quantity']=0
    with pytest.raises(ValueError):calculate(x)


def test_package_includes_review_gate_cost_outputs_and_checksums(tmp_path):
    p=project(tmp_path)
    (p/'pricing_scenarios.json').write_text(json.dumps(example()))
    r,z,code=run_build(p,p/'build',skip_safety=True)
    assert code!=0  # 78 missing artworks
    assert r['release_gate']['status']=='REVIEW_PENDING'
    assert (p/'build'/'actual_size_REVIEW_ONLY.pdf').exists()
    assert (p/'build'/'cost_report.csv').exists()
    assert (p/'build'/'release_gate.md').exists()
    with zipfile.ZipFile(z) as archive:
        for name in ('printer_profile.json','pricing_scenarios.json','production_review/cost_report.csv',
                     'production_review/actual_size_REVIEW_ONLY.pdf','production_review/release_gate.json'):
            assert name in archive.namelist()
    assert verify_package(z)['ok']


def test_html_review_screen_and_malicious_title_are_escaped(tmp_path):
    p=tmp_path/'test';write_config(p,default_config('O <script>alert(6)</script>'))
    run_build(p,p/'build',skip_safety=True)
    html=(p/'build'/'qa_dashboard.html').read_text()
    assert 'Review &amp; sign off' in html
    assert 'Download review JSON' in html
    assert 'Batch cost scenarios' in html
    assert 'O <script>alert(6)</script>' not in html


def test_zip_verifier_rejects_unsafe_members_and_case_collisions(tmp_path):
    p=tmp_path/'unsafe.zip'
    with zipfile.ZipFile(p,'w') as z:
        z.writestr('../escaped.txt', 'data')
        z.writestr('SHA256SUMS.txt', '')
    assert not verify_package(p)['ok']
    q=tmp_path/'case.zip'
    with zipfile.ZipFile(q,'w') as z:
        z.writestr('COPY.txt','a')
        z.writestr('copy.txt','b')
        z.writestr('SHA256SUMS.txt','')
    assert not verify_package(q)['ok']
