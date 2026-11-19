"""DeckForge Studio V4 command-line interface."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from . import __version__
from .build import run_build, run_audit, verify_package
from .demo import create_demo
from .importer import plan_import, apply_import
from .project import default_config, write_config
from .reviews import approve,revoke,review_status,import_reviews,CRITERIA,BACK_CRITERIA
from .printer import default_printer_profile,write_printer_profile,load_printer_profile
from .costing import load_costs
from .vision import init_brief, vision_review, read_vision_results
from .manufacturing import init_template, inspect_template, create_packaging_overlay, convert_cmyk


def parser() -> argparse.ArgumentParser:
    p=argparse.ArgumentParser(prog='deckforge', description='DeckForge Studio: tarot QA, visual dashboard, reversible-back checks, import, QR and review packaging')
    p.add_argument('--version',action='version',version=f'DeckForge Studio {__version__}')
    sub=p.add_subparsers(dest='command',required=True)
    init=sub.add_parser('init', help='Create an empty 78-card project manifest')
    init.add_argument('project_dir',type=Path); init.add_argument('--name',default='My Tarot Deck')
    init.add_argument('--extension',default='png',choices=['png','jpg','jpeg','webp','tif','tiff'])
    init.add_argument('--guide-url',default='')
    demo=sub.add_parser('demo',help='Create 78 original sample cards and reversible card back')
    demo.add_argument('project_dir',type=Path)
    audit=sub.add_parser('audit',help='Run preflight without generating PDFs or a ZIP')
    audit.add_argument('project_dir',type=Path);audit.add_argument('--json',action='store_true')
    build=sub.add_parser('build',help='QA, interactive dashboard, review PDFs, QR and integrity-checked ZIP')
    build.add_argument('project_dir',type=Path)
    build.add_argument('--output',type=Path,default=None)
    build.add_argument('--strict',action='store_true',help='Fail on warnings as well as errors')
    build.add_argument('--skip-safety',action='store_true',help='Skip the safe-area overlay PDF')
    imports=sub.add_parser('import',help='Plan filename-based imports; copies only with --apply')
    imports.add_argument('project_dir',type=Path);imports.add_argument('incoming_dir',type=Path)
    imports.add_argument('--apply',action='store_true',help='Copy uniquely matched files and update the manifest')
    imports.add_argument('--json',action='store_true')
    verify=sub.add_parser('verify',help='Verify checksums inside a DeckForge ZIP')
    verify.add_argument('package',type=Path)
    rev=sub.add_parser('review',help='Show human review progress for all 78 fronts and common back')
    rev.add_argument('project_dir',type=Path)
    appr=sub.add_parser('approve',help='Manually approve one image after all checks')
    appr.add_argument('project_dir',type=Path);appr.add_argument('card_id')
    appr.add_argument('--reviewer',required=True)
    appr.add_argument('--check',action='append',default=[],help='Repeat once for each mandatory criterion (see review --help)')
    appr.add_argument('--note',default='')
    rej=sub.add_parser('revoke',help='Revoke a prior manual sign-off')
    rej.add_argument('project_dir',type=Path);rej.add_argument('card_id')
    imp=sub.add_parser('reviews-import',help='Import human approvals exported by the offline HTML dashboard')
    imp.add_argument('project_dir',type=Path);imp.add_argument('review_file',type=Path)
    profile=sub.add_parser('profile-init',help='Create an unconfirmed generic manufacturer profile to fill in')
    profile.add_argument('project_dir',type=Path)
    gate=sub.add_parser('release-check',help='Explain why a deck is or is not ready for a printer handoff')
    gate.add_argument('project_dir',type=Path);gate.add_argument('--json',action='store_true')
    costs=sub.add_parser('costs',help='Calculate editable, illustrative production-cost scenarios')
    costs.add_argument('project_dir',type=Path);costs.add_argument('--json',action='store_true')
    visionbrief=sub.add_parser('vision-init',help='Create optional visual QA casting/style brief; no API calls')
    visionbrief.add_argument('project_dir',type=Path)
    vision=sub.add_parser('vision-review',help='OPT-IN paid API vision suggestions (never human approval)')
    vision.add_argument('project_dir',type=Path)
    vision.add_argument('--id',dest='card_ids',action='append',required=True,help='Repeat for selected card IDs')
    vision.add_argument('--model',default='gpt-4.1-mini',help='Vision-capable model name')
    vision.add_argument('--max-cards',type=int,default=5,help='Safety cap; default 5 cards per command')
    vision.add_argument('--without-style-image',action='store_true',help='Skip sending second reference image')
    visionstatus=sub.add_parser('vision-status',help='Display stored AI suggestions and stale-image indicators; offline')
    visionstatus.add_argument('project_dir',type=Path)
    templateinit=sub.add_parser('template-init',help='Set up custom supplier PDF dieline manifest; UNCONFIRMED')
    templateinit.add_argument('project_dir',type=Path)
    templateinit.add_argument('--supplier',default='Print Europe - UNCONFIRMED')
    templatecheck=sub.add_parser('template-check',help='Verify official PDF coordinates and panels; no modifications')
    templatecheck.add_argument('project_dir',type=Path)
    overlay=sub.add_parser('packaging-overlay',help='Create registered provisional PDF artwork and die-line review')
    overlay.add_argument('project_dir',type=Path)
    overlay.add_argument('--output',type=Path,default=None)
    cmyk=sub.add_parser('color-export',help='Convert selected artwork to CMYK TIFF with SUPPLIER ICC')
    cmyk.add_argument('project_dir',type=Path)
    cmyk.add_argument('--icc',required=True,type=Path,help='Actual printer-specified CMYK ICC file')
    cmyk.add_argument('--output',required=True,type=Path)
    cmyk.add_argument('--id',dest='card_ids',action='append',default=None)
    cmyk.add_argument('--assume-srgb',action='store_true',help='Explicit assumption for untagged source art')
    studio=sub.add_parser('studio',help='Open simple desktop GUI; no server or account required')
    studio.add_argument('--project',type=Path,default=None)
    return p


def main(argv: list[str] | None = None) -> int:
    args=parser().parse_args(argv)
    try:
        if args.command=='init':
            file=write_config(args.project_dir,default_config(args.name,args.extension,guide_url=args.guide_url))
            if not (args.project_dir/'printer_profile.json').exists():
                write_printer_profile(args.project_dir,default_printer_profile())
            print('Created:',file,'\nPlace your cards in the generated folders or use `deckforge import`.')
            return 0
        if args.command=='demo':
            create_demo(args.project_dir)
            if not (args.project_dir/'printer_profile.json').exists():
                write_printer_profile(args.project_dir,default_printer_profile())
            print('Created original demonstration deck:',args.project_dir)
            return 0
        if args.command=='audit':
            r=run_audit(args.project_dir)
            if args.json:print(json.dumps(r,indent=2,ensure_ascii=False))
            else:
                print(f"{r['deck_name']} | {r['present_cards']}/78 cards | errors={r['errors']} warnings={r['warnings']} | back symmetry={r['back'].get('rotation_difference')}")
                for i in r['issues'][:35]:print(f"  {i['severity'].upper():7} {i['code']}: {i['message']}")
                if len(r['issues'])>35:print(f"  (+{len(r['issues'])-35} additional findings)")
            return 2 if r['errors'] else 0
        if args.command=='build':
            out=args.output or args.project_dir/'build'
            r,z,code=run_build(args.project_dir,out,strict=args.strict,skip_safety=args.skip_safety)
            print(f"DeckForge v4 | {r['deck_name']}")
            print(f"Status: {r['readiness']} | cards: {r['present_cards']}/78 | errors: {r['errors']} | warnings: {r['warnings']}")
            print('Interactive dashboard:',out/'qa_dashboard.html')
            print('Contact proof:',out/'contact_sheet_REVIEW_ONLY.pdf')
            print('Safety proof:', 'skipped' if args.skip_safety else out/'safe_area_REVIEW_ONLY.pdf')
            print('Physical-size proof:',out/'actual_size_REVIEW_ONLY.pdf')
            print('Release gate:',r['release_gate']['status'],'blockers:',len(r['release_gate']['blockers']))
            print('Review ZIP:',z)
            return code
        if args.command=='import':
            r=(apply_import if args.apply else plan_import)(args.project_dir,args.incoming_dir)
            if args.json:print(json.dumps(r,indent=2,ensure_ascii=False))
            else:
                print('Import', 'APPLIED' if args.apply else 'PLAN (DRY RUN)')
                print('Counts:',r['counts'])
                for row in r['items']:
                    print(f"  {row['status']:10} {row['source']} -> {row['card_id'] or 'unmatched'}")
                if args.apply:print('Copied:',len(r['applied']))
                else:print('No files changed; rerun with --apply to copy READY rows only.')
            return 0 if not any(r['counts'][k] for k in ('CONFLICT','BLOCKED')) else 1
        if args.command=='verify':
            result=verify_package(args.package)
            print('PACKAGE', 'VALID' if result['ok'] else 'INVALID', '| verified files:',result['checked'])
            for issue in result['issues']:print(' -',issue)
            return 0 if result['ok'] else 2
        if args.command=='review':
            status=review_status(args.project_dir)
            print('Human review (not automatic):',status['counts'],'of 79 items')
            print('Card checklist: '+', '.join(CRITERIA))
            print('Back checklist: '+', '.join(BACK_CRITERIA))
            for cid,r in status['cards'].items():
                if r['status'] != 'approved':print('  '+cid+': '+r['status'])
            return 0
        if args.command=='approve':
            path=approve(args.project_dir,args.card_id.upper(),args.reviewer,args.check,note=args.note)
            print('Saved human review:',path)
            return 0
        if args.command=='revoke':
            path=revoke(args.project_dir,args.card_id.upper())
            print('Revoked human review:',path)
            return 0
        if args.command=='reviews-import':
            result=import_reviews(args.project_dir,args.review_file)
            print('Review import:',result)
            return 0 if not result['rejected_count'] else 2
        if args.command=='profile-init':
            path=write_printer_profile(args.project_dir,default_printer_profile())
            print('Created unconfirmed vendor profile:',path)
            return 0
        if args.command=='release-check':
            r=run_audit(args.project_dir)
            gate=r['release_gate']
            if args.json:print(json.dumps(gate,indent=2,ensure_ascii=False))
            else:
                print(gate['status'],'| open blockers:',len(gate['blockers']))
                for i in gate['blockers']:print(' -',i)
                print('Manual final verifications:')
                for i in gate['manual_final_verifications']:print(' -',i)
            return 0 if gate['status']=='TECHNICAL_HANDOFF_CANDIDATE' else 3
        if args.command=='costs':
            rows=load_costs(args.project_dir)
            if rows is None:
                print('No pricing_scenarios.json; copy examples/ILLUSTRATIVE_pricing_scenarios.json and replace fictional values.')
                return 1
            if args.json: print(json.dumps(rows,indent=2,ensure_ascii=False))
            else:
                print('SCENARIO ESTIMATES / NOT VERIFIED FEES:', rows['currency'])
                for row in rows['rows']:
                    print(f"  {row['supplier']}: {row['quantity']} decks, {row['estimated_profit_per_deck']:.2f} profit/deck if sold")
            return 0
        if args.command=='vision-init':
            print('Visual QA brief:',init_brief(args.project_dir))
            return 0
        if args.command=='vision-review':
            # This command is deliberately the ONLY code path that makes an AI API request.
            r=vision_review(args.project_dir,[x.upper() for x in args.card_ids],
                model=args.model,max_cards=args.max_cards,include_reference=not args.without_style_image)
            print('AI SUGGESTIONS, NOT APPROVAL:',r['reviewed'],'card(s)')
            print('Possible mismatches:',r['possible_mismatches'])
            print('Saved:',r['path'])
            return 0
        if args.command=='vision-status':
            r=read_vision_results(args.project_dir)
            print('AI suggestions only (NOT human approvals):',r['status'],'counts:',r['counts'])
            for cid, v in r['items'].items():
                print(' ',cid,v['cache_status'],'possible mismatch:',v.get('possible_count_mismatch',False))
            return 0
        if args.command=='template-init':
            print('Created UNCONFIRMED supplier template mapping:',init_template(args.project_dir,vendor=args.supplier))
            return 0
        if args.command=='template-check':
            print(json.dumps(inspect_template(args.project_dir),indent=2,ensure_ascii=False))
            return 0
        if args.command=='packaging-overlay':
            r=create_packaging_overlay(args.project_dir,args.output or args.project_dir/'build')
            print(json.dumps(r,indent=2,ensure_ascii=False))
            return 0
        if args.command=='color-export':
            r=convert_cmyk(args.project_dir,args.output,args.icc,
                assume_srgb_when_missing=args.assume_srgb,card_ids=[x.upper() for x in args.card_ids] if args.card_ids else None)
            print('Converted',len(r['items']),'image(s) to CMYK with ICC:',r['target_icc_filename'])
            print('STATUS:',r['status'],'(requires printer proof)')
            return 0
        if args.command=='studio':
            from .studio import launch
            launch(args.project)
            return 0
    except (ValueError,FileExistsError,FileNotFoundError,OSError,KeyError) as ex:
        print('ERROR:',ex,file=sys.stderr)
        return 2
    return 1

if __name__=='__main__':
    raise SystemExit(main())
