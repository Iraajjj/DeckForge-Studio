"""Desktop companion to DeckForge CLI. Standard library only (Tkinter).

Runs the same tested pipeline. No network, accounts, or third-party GUI runtime.
"""
from __future__ import annotations

from pathlib import Path
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
import webbrowser

from .build import run_audit,run_build
from .importer import plan_import,apply_import
from .project import default_config,write_config
from .reviews import import_reviews, review_status
from .printer import default_printer_profile, write_printer_profile, load_printer_profile
from .vision import vision_review
from .manufacturing import inspect_template, init_template, create_packaging_overlay, convert_cmyk
from datetime import datetime, timezone

PAPER = '#F7F2FA'
DEEP = '#2C203B'
VIOLET = '#67487B'
GOLD = '#D7B87C'
GRAY = '#7E7285'
MINT = '#197B65'


class Studio(tk.Tk):
    def __init__(self, project: Path | None):
        super().__init__()
        self.title('DeckForge Studio V4 | Tarot Production & Human QA')
        self.geometry('1020x760')
        self.minsize(820,650)
        self.configure(bg=PAPER)
        self.project = project.resolve() if project else None
        self.events: queue.Queue = queue.Queue()
        self.is_running=False
        self._build_ui()
        self.after(130,self._poll)
        self._refresh()

    def _build_ui(self):
        self.option_add('*Font','SegoeUI 10')
        header=tk.Frame(self,bg=DEEP,height=120)
        header.pack(fill='x')
        header.pack_propagate(False)
        tk.Label(header,text='✦ DeckForge',font=('Georgia',27,'bold'),bg=DEEP,fg='#FFF5E7').pack(anchor='w',padx=34,pady=(22,0))
        tk.Label(header,text='STUDIO  /  TAROT PRODUCTION QA     •     LOCAL & PRIVATE',font=('Segoe UI',9,'bold'),bg=DEEP,fg=GOLD).pack(anchor='w',padx=35,pady=(5,0))

        top=tk.Frame(self,bg=PAPER)
        top.pack(fill='x',padx=30,pady=(22,12))
        tk.Label(top,text='PROJECT WORKSPACE',font=('Segoe UI',9,'bold'),bg=PAPER,fg=GRAY).pack(anchor='w')
        self.deck=tk.Label(top,text='No project selected',font=('Georgia',21),bg=PAPER,fg=DEEP,anchor='w')
        self.deck.pack(anchor='w',fill='x',pady=(4,2))
        self.pathlabel=tk.Label(top,text='Select a folder containing deckforge.json, or create one below.',font=('Segoe UI',9),bg=PAPER,fg=GRAY,anchor='w')
        self.pathlabel.pack(anchor='w',fill='x')

        actions=tk.Frame(self,bg=PAPER)
        actions.pack(fill='x',padx=27,pady=8)
        for col in range(4):actions.grid_columnconfigure(col,weight=1)
        self.btns=[]
        buttons=[('📂  Choose project',self.choose),('＋  New project',self.new),
                 ('↳  Import artwork',self.import_files),('✓  Run preflight',self.audit),
                 ('⚙  Build package',self.build),('▦  Open dashboard',self.open_dashboard),
                 ('⌁  Open build folder',self.open_folder),('✍  Import reviews',self.import_reviews),
                 ('⚙  Printer profile',self.edit_profile),('▣  Size proof',self.open_actual_size),
                 ('✧  AI vision review',self.vision_review_action),('▣  Supplier box',self.box_template_action),
                 ('◐  CMYK export',self.cmyk_export_action),('◈  About this tool',self.about)]
        for i,(title,fn) in enumerate(buttons):
            btn=tk.Button(actions,text=title,command=fn,bg=DEEP if i in (3,4) else '#FFFFFF',
                          fg='white' if i in (3,4) else DEEP,relief='flat',bd=0,
                          cursor='hand2',font=('Segoe UI',10,'bold'),activebackground='#CDB5DE',
                          activeforeground=DEEP,padx=10,pady=13)
            btn.grid(row=i//4,column=i%4,padx=5,pady=5,sticky='ew')
            self.btns.append(btn)

        info=tk.Frame(self,bg=PAPER)
        info.pack(fill='x',padx=32,pady=(12,12))
        self.info_labels=[]
        for label in ('CARDS FOUND','ERRORS','WARNINGS','STATUS'):
            box=tk.Frame(info,bg='#FFFFFF',highlightbackground='#E5DCEA',highlightthickness=1)
            box.pack(side='left',fill='x',expand=True,padx=5)
            tk.Label(box,text=label,font=('Segoe UI',9,'bold'),bg='white',fg=GRAY).pack(pady=(15,3))
            val=tk.Label(box,text='—',font=('Georgia',23,'bold'),bg='white',fg=DEEP)
            val.pack(pady=(0,15))
            self.info_labels.append(val)

        logframe=tk.Frame(self,bg=PAPER)
        logframe.pack(fill='both',expand=True,padx=34,pady=(8,15))
        tk.Label(logframe,text='ACTIVITY & FINDINGS',font=('Segoe UI',9,'bold'),bg=PAPER,fg=GRAY).pack(anchor='w',pady=(0,8))
        self.log=tk.Text(logframe,wrap='word',font=('Consolas',10),height=13,
                         bg='#FFFFFF',fg=DEEP,relief='flat',bd=0,padx=15,pady=15)
        scroll=ttk.Scrollbar(logframe,orient='vertical',command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        self.log.pack(side='left',fill='both',expand=True)
        scroll.pack(side='right',fill='y')
        self.log.insert('end','Welcome to DeckForge Studio.\n\nChoose a project and click Run preflight.\nLocal by default. Only explicit AI vision requests upload selected artwork.\n')
        self.log.config(state='disabled')

        footer=tk.Frame(self,bg=PAPER)
        footer.pack(fill='x',padx=34,pady=(0,16))
        self.progress=ttk.Progressbar(footer,mode='indeterminate',length=130)
        self.progress.pack(side='left')
        tk.Label(footer,text='V4.0  •  QA ≠ printer approval. Use the manufacturer’s exact dieline and ICC profile.',
                 bg=PAPER,fg=GRAY,font=('Segoe UI',9)).pack(side='right')

    def say(self,message:str):
        self.log.config(state='normal')
        self.log.insert('end',message+'\n')
        self.log.see('end')
        self.log.config(state='disabled')

    def _refresh(self):
        if self.project and (self.project/'deckforge.json').exists():
            self.deck.config(text=self.project.name)
            self.pathlabel.config(text=str(self.project))
        elif self.project:
            self.deck.config(text='Not a DeckForge project')
            self.pathlabel.config(text=str(self.project))
        else:
            self.deck.config(text='No project selected')
            self.pathlabel.config(text='Select a project to begin.')

    def _require(self) -> bool:
        if not self.project or not (self.project/'deckforge.json').is_file():
            messagebox.showinfo('Select a project','Choose a folder containing deckforge.json first.')
            return False
        return True

    def choose(self):
        path=filedialog.askdirectory(title='Select DeckForge project folder')
        if path:
            self.project=Path(path).resolve(); self._refresh()
            self.say('Selected: '+str(self.project))

    def new(self):
        path=filedialog.askdirectory(title='Choose where to create new deck')
        if not path:return
        name=simpledialog.askstring('Deck name','Name your collection:',parent=self,initialvalue='My Tarot Deck')
        if not name:return
        try:
            path=Path(path)/('deck_'+''.join(ch.lower() if ch.isalnum() else '_' for ch in name).strip('_')[:45])
            write_config(path,default_config(name))
            write_printer_profile(path,default_printer_profile())
        except Exception as ex:
            messagebox.showerror('Cannot create deck',str(ex));return
        self.project=path;self._refresh();self.say('Created project: '+str(path))
        self.say('Next: import your artwork or copy files into the folders.')

    def _work(self, label: str, fn):
        if self.is_running:return
        self.is_running=True
        self.say('▶ '+label)
        self.progress.start(14)
        for btn in self.btns:btn.config(state='disabled')
        def worker():
            try:self.events.put(('done',label,fn()))
            except Exception as exc:self.events.put(('error',label,str(exc)))
        threading.Thread(target=worker,daemon=True).start()

    def _poll(self):
        try:
            while True:
                kind,label,result=self.events.get_nowait()
                if kind=='done':
                    self.say('✓ '+label+' complete')
                    if isinstance(result,dict) and 'report' in result:
                        r=result['report']
                        vals=[f"{r['present_cards']}/78",str(r['errors']),str(r['warnings']),r['readiness'].replace('_',' ').lower()]
                        for item,text in zip(self.info_labels,vals):item.config(text=text)
                        self.say(f"QA: {r['present_cards']}/78 · errors {r['errors']} · warnings {r['warnings']}")
                        for i in r['issues'][:12]:self.say(f"  {i['severity']}: {i['code']} — {i['message']}")
                        if len(r['issues'])>12:self.say(f"  …and {len(r['issues'])-12} more; see the HTML dashboard.")
                        if 'package' in result:self.say('ZIP: '+result['package'])
                    else:self.say(str(result))
                else:
                    self.say('✕ '+label+': '+str(result))
                    messagebox.showerror('DeckForge error',str(result))
                self.progress.stop();self.is_running=False
                for btn in self.btns:btn.config(state='normal')
        except queue.Empty:
            pass
        self.after(130,self._poll)

    def audit(self):
        if self._require():self._work('Technical preflight',lambda:{'report':run_audit(self.project)})

    def build(self):
        if self._require():
            def go():
                r,z,_=run_build(self.project,self.project/'build')
                return {'report':r,'package':str(z)}
            self._work('Review package generation',go)

    def import_reviews(self):
        if not self._require():return
        review_file=filedialog.askopenfilename(title='Choose downloaded review JSON',filetypes=[('JSON','*.json')])
        if not review_file:return
        if not messagebox.askyesno('Import manual sign-offs?',
            'This imports only reviews that match the SHA-256 hashes of your current artwork.\n\nThese are HUMAN sign-offs, not automatic approval. Continue?'):
            return
        try:
            result=import_reviews(self.project,Path(review_file))
            self.say('Review import: '+str(result))
            if result['rejected_count']:
                messagebox.showwarning('Some reviews rejected',
                    f"{result['rejected_count']} stale or invalid reviews were rejected; no images were changed.")
            else:
                messagebox.showinfo('Reviews imported',f"{result['accepted_count']} reviews imported. Rebuild your dashboard to update release gate.")
        except Exception as ex:
            messagebox.showerror('Review import failed',str(ex))

    def edit_profile(self):
        if not self._require():return
        try: profile=load_printer_profile(self.project)
        except Exception as exc:
            messagebox.showerror('Invalid profile',str(exc));return
        popup=tk.Toplevel(self);popup.title('DeckForge · Manufacturer specifications')
        popup.geometry('590x700');popup.minsize(510,660);popup.configure(bg=PAPER)
        content=tk.Frame(popup,bg=PAPER);content.pack(fill='both',expand=True,padx=23,pady=12)
        tk.Label(content,text='Printer profile',font=('Georgia',21,'bold'),bg=PAPER,fg=DEEP).pack(anchor='w',pady=(0,7))
        tk.Label(content,text='Use the values supplied by your ACTUAL printer. Defaults are placeholders.\nEven a confirmed profile does not replace final proof approval.',
            font=('Segoe UI',9),justify='left',bg=PAPER,fg=GRAY).pack(anchor='w',pady=(0,14))
        fields=(('printer_name','Printer / supplier name'),('trim_width_mm','Card width (mm)'),
            ('trim_height_mm','Card height (mm)'),('required_bleed_mm','Required bleed (mm)'),
            ('safe_inset_mm','Safe inset (mm)'),('minimum_effective_dpi','Minimum effective DPI'),
            ('color_profile_instruction','ICC / colour instructions'),('verified_by','Confirmed by (name/initials)'))
        inputs={}
        for key,label in fields:
            tk.Label(content,text=label,font=('Segoe UI',9,'bold'),bg=PAPER,fg=GRAY).pack(anchor='w')
            var=tk.StringVar(value=str(profile.get(key) if profile.get(key) is not None else ''))
            tk.Entry(content,textvariable=var,font=('Segoe UI',10),bg='white',relief='solid',bd=1).pack(fill='x',pady=(2,9))
            inputs[key]=var
        confirmed=tk.BooleanVar(value=profile.get('verified_against_printer',False))
        dieline=tk.BooleanVar(value=profile.get('packaging_dieline_supplied',False))
        tk.Checkbutton(content,text='I personally verified these values against the selected printer',variable=confirmed,
            bg=PAPER,fg=DEEP,anchor='w').pack(anchor='w',pady=5)
        tk.Checkbutton(content,text='I have received the official packaging dieline',variable=dieline,
            bg=PAPER,fg=DEEP,anchor='w').pack(anchor='w',pady=5)
        def save():
            try:
                changed=dict(profile)
                for key,var in inputs.items():
                    changed[key]=var.get().strip()
                for key in ('trim_width_mm','trim_height_mm','required_bleed_mm','safe_inset_mm'):
                    changed[key]=float(changed[key])
                changed['minimum_effective_dpi']=int(changed['minimum_effective_dpi'])
                changed['verified_against_printer']=confirmed.get()
                changed['packaging_dieline_supplied']=dieline.get()
                changed['verified_at_utc']=datetime.now(timezone.utc).isoformat(timespec='seconds') if confirmed.get() else None
                if confirmed.get() and (not changed['verified_by'] or 'UNCONFIRMED' in changed['printer_name'].upper()):
                    raise ValueError('Provide the real printer name and a reviewer before confirming.')
                # Validate against same bounds as core profile loader without committing invalid edits.
                if changed['required_bleed_mm']<0 or changed['required_bleed_mm']>15 or changed['safe_inset_mm']<0:
                    raise ValueError('Bleed must be 0–15mm and safe inset cannot be negative.')
                if changed['trim_width_mm']<=0 or changed['trim_height_mm']<=0 or changed['minimum_effective_dpi']<=0:
                    raise ValueError('Trim dimensions and resolution must be positive.')
                if changed['safe_inset_mm']*2>=min(changed['trim_width_mm'],changed['trim_height_mm']):
                    raise ValueError('Safe inset cannot cover the entire card.')
                write_printer_profile(self.project,changed,overwrite=True)
                popup.destroy()
                self.say('Printer profile updated; run a new preflight to see release blockers.')
            except (ValueError,OSError) as ex:messagebox.showerror('Cannot save profile',str(ex),parent=popup)
        tk.Button(content,text='Save supplier specifications',command=save,bg=DEEP,fg='white',
            font=('Segoe UI',10,'bold'),padx=11,pady=10,relief='flat').pack(fill='x',pady=(12,3))

    def vision_review_action(self):
        if not self._require():return
        if not os.environ.get('OPENAI_API_KEY'):
            messagebox.showinfo('AI review is opt-in',
                'Set OPENAI_API_KEY in your Windows environment and restart DeckForge first.\n'
                'AI analysis is optional, billed separately and NEVER replaces human review.')
            return
        cid=simpledialog.askstring('AI visual review','Which card ID? Example: P09 or S07',parent=self)
        if not cid:return
        cid=cid.strip().upper()
        model=simpledialog.askstring('Vision model','Choose an image-capable API model:',
                                     initialvalue='gpt-4.1-mini',parent=self)
        if not model:return
        if not messagebox.askyesno('Upload selected card to AI?',
            f'This sends image {cid} to an external AI provider using your own API key, '
            'and can incur API fees. The result is only a suggestion, never a sign-off.\n\nContinue?'):
            return
        self._work(f'Optional AI visual suggestion for {cid}',
                   lambda:vision_review(self.project,[cid],model=model))

    def box_template_action(self):
        if not self._require():return
        target=self.project/'packaging_template.json'
        try:
            if not target.exists():
                init_template(self.project)
                self.say('Created UNCONFIRMED template manifest: '+str(target))
                messagebox.showinfo('Supplier template created',
                    'Put the OFFICIAL manufacturer PDF in your project/factory folder, '
                    'then edit packaging_template.json with measured top-left millimeter coordinates. '
                    'This never infers geometry from a mockup.')
                return
            result=inspect_template(self.project)
            if result['status']!='ready_for_provisional_overlay':
                messagebox.showinfo('Supplier template needs setup',
                    '\n'.join(result.get('issues',[]))+'\n\nEdit: '+str(target))
                return
            if messagebox.askyesno('Register supplier artwork?',
                'Create the provisional artwork-only PDF and review PDF with official cut/fold lines? '
                'The printer still must approve the results.'):
                self._work('Supplier packaging PDFs',
                           lambda:create_packaging_overlay(self.project,self.project/'build'))
        except (ValueError,OSError) as ex:
            messagebox.showerror('Supplier template error',str(ex))

    def cmyk_export_action(self):
        if not self._require():return
        profile=filedialog.askopenfilename(title='Select YOUR printer-provided CMYK ICC',
            filetypes=[('ICC profiles','*.icc *.icm'),('All files','*.*')])
        if not profile:return
        cid=simpledialog.askstring('Select artwork','Card ID to convert, e.g. P09, or ALL:',
                                   initialvalue='P09',parent=self)
        if not cid:return
        cid=cid.strip().upper()
        dest=filedialog.askdirectory(title='Select new empty output folder (will not overwrite)')
        if not dest:return
        if not messagebox.askyesno('Colour management reminder',
            'Only use an ICC profile provided or approved by the actual printer. '
            'Untagged source artwork will be ASSUMED sRGB, which may be wrong. '
            'The final colour proof must be approved by the manufacturer. Continue?'):
            return
        ids=None if cid=='ALL' else [cid]
        self._work('ICC-managed CMYK TIFF export',lambda:convert_cmyk(
            self.project,Path(dest),Path(profile),card_ids=ids,assume_srgb_when_missing=True))

    def open_actual_size(self):
        if not self._require():return
        path=self.project/'build'/'actual_size_REVIEW_ONLY.pdf'
        if not path.is_file():
            messagebox.showinfo('Proof not built','Build the project first, then reopen the real-size PDF.')
            return
        webbrowser.open(path.resolve().as_uri())

    def import_files(self):
        if not self._require():return
        incoming=filedialog.askdirectory(title='Choose folder with incoming card images')
        if not incoming:return
        try:
            plan=plan_import(self.project,Path(incoming))
        except Exception as ex:
            messagebox.showerror('Import error',str(ex));return
        ready=plan['counts']['READY']
        self.say('Import preview: '+str(plan['counts']))
        for item in plan['items'][:15]:self.say(f"  {item['status']:10} {item['source']} -> {item['card_id'] or '?'}")
        if ready and messagebox.askyesno('Import matching art?',f"{ready} file(s) have a unique match.\n\nCopy them to the project and update deckforge.json?\nFiles already present will NOT be overwritten."):
            self._work('Import artwork',lambda:apply_import(self.project,Path(incoming)))

    def open_dashboard(self):
        if not self._require():return
        file=self.project/'build'/'qa_dashboard.html'
        if not file.is_file():
            messagebox.showinfo('Dashboard not generated','Build the review package first.')
            return
        webbrowser.open(file.resolve().as_uri())

    def open_folder(self):
        if not self._require():return
        path=self.project/'build'
        if not path.exists():
            messagebox.showinfo('Nothing built yet','Build the review package first.')
            return
        if sys.platform.startswith('win'):
            subprocess.Popen(['explorer',str(path)])
        elif sys.platform=='darwin':
            subprocess.Popen(['open',str(path)])
        else:
            subprocess.Popen(['xdg-open',str(path)])

    def about(self):
        messagebox.showinfo('DeckForge Studio',
            'Local-first technical preflight for 78-card tarot decks.\n\n'
            'Checks dimensions, effective DPI, duplicates, colour modes, reversible back heuristics and more. '
            'Creates gallery dashboards, real-size proof PDFs, QR assets, human approvals, cost scenarios and integrity-checked packages.\n\n'
            'Does not provide automatic factory print approval or commercial artwork rights.')


def launch(project: Path | None = None):
    Studio(project).mainloop()
