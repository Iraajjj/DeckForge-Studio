# DeckForge Studio V4 — Print Production Intelligence

**A local-first 78-card tarot QA application with human sign-offs, optional vision suggestions, ICC colour conversion, supplier-registered packaging PDFs, and a Windows installer build pipeline.** Designed as a real, testable developer portfolio project—not as printer certification.

**Version 0.4.0 · Python 3.10+ · MIT source code · no server**

> **Important:** The demonstration cards are original procedural illustrations. DeckForge does not verify copyright, brand licensing, actual card artwork symbolism, supplier quality, colour matching or legal rights. Human approval and the printer's actual specifications are indispensable.

## What's genuinely new in V4

| Improvement | Implemented and tested | Remaining limitation |
|---|---|---|
| **Opt-in AI visual QA** | Structured image-analysis request with expected suit counts (Ace–Ten and court), card-specific briefs, optional reference image, model uncertainty, image SHA-256 staleness, no automatic approvals | Actual model accuracy and any live API call cannot be tested without the user's own API key; the service may charge separately |
| **Style consistency** | Optional approved-style reference and offline HSV palette-distance metric, plus AI prompts for style/identity concerns | A whole-image colour histogram is only a heuristic, not proof of character consistency or style correctness |
| **Factory PDF panel registration** | Validate official PDF page size, measured front/back/flap/spine coordinates, image aspect/DPI, and export separate artwork-only and review-with-dieline PDFs | Exact cut/fold geometry must come from the printer. A conceptual mockup is NOT a factory template; no automatic dieline recognition or bleed manufacture |
| **Colour management** | Source-profile-to-printer-profile ICC transforms using Pillow LittleCMS, opt-in CMYK TIFF exports, SHA-256 manifest and explicit sRGB assumptions | Needs printer-supplied CMYK ICC and a physical press proof; no automatic output PDF/X certification |
| **Native Windows installer pipeline** | PyInstaller frozen-app recipe, noninteractive self-test, Inno Setup installer script, Windows GitHub Actions workflow and checksum artifact | This Linux build cannot compile/test a Windows `.exe`. Publish source, run GitHub Actions on Windows and perform a clean-machine test first |

### Existing V3 functionality retained

78-card inventory; card/front/back image checks; measured resolution, aspect, ICC metadata, duplicate detection and 180° back symmetry; reversible-back heuristic; conservative filename importer; human SHA-256-bound review ledger; online-free QR PNG/SVG/PDF generation; actual-size/bleed/safe-area review PDFs; interactive offline gallery; supplier release gate; pricing scenarios; integrity-verified ZIP; Windows launcher when Python is installed.

## Start on Windows today — from the Complete Kit

1. Extract the **Complete Starter Kit** and enter `DeckForge_Studio_V4`.
2. Until a native Windows installer has been compiled on Windows, install Python 3.10+ once.
3. Double-click `START_STUDIO_WINDOWS.bat` to create the virtual environment and launch the GUI.
4. Choose `demo_project`, click **Run preflight → Build package → Open dashboard**.
5. The demo is purposefully local and original, and passes technical preflight; its human and printer release gate remains blocked.

The GUI now has three additional controls: **AI vision review**, **Supplier box**, and **CMYK export**. The optional AI button requires a separately configured `OPENAI_API_KEY` and asks explicit permission before sending selected artwork to the service.

## Optional AI-assisted checks

A traditional deck has 78 IDs (M00–M21, W01–W14, C01–C14, S01–S14, P01–P14). Numbered Minor Arcana should display the appropriate number of physical suit objects. Court cards normally feature a single principal suit object. Major Arcana are not subjected to a made-up suit-object count.

**AI analysis is never automatic on build.** To enable it:

```powershell
python -m deckforge vision-init my_deck
# Edit my_deck/vision_brief.json: optional approved reference image, named cast and checks
$env:OPENAI_API_KEY = "your-own-api-key"   # Do not put this in Git or any document
python -m deckforge vision-review my_deck --id P09 --model gpt-4.1-mini
python -m deckforge vision-status my_deck
python -m deckforge build my_deck
```

The tool uploads **only explicitly selected card images** (and the style reference, if configured) to the OpenAI API for that command. It requests structured, fallible observations: estimated object count, confidence, style/identity/text observations, and mismatch suggestions. It does not recognize all art reliably and cannot replace the human sign-off. Images are resized before API submission to control cost; even then, pricing depends on the selected model and usage. **ChatGPT app subscriptions do not automatically provide API billing access.** Review `vision_reviews.json` and the **AI review notes** dashboard tab; results become stale if the source artwork changes.

## Manufacturer-specific packaging template / panel placement

```powershell
python -m deckforge template-init my_deck --supplier "Print Europe - UNCONFIRMED"
# Obtain actual printer PDF and save as my_deck/factory/official_tuck_box_dieline.pdf
# Edit my_deck/packaging_template.json with measured panel rectangles and artwork paths
python -m deckforge template-check my_deck
python -m deckforge packaging-overlay my_deck --output my_deck/build
```

All panel coordinates are in **millimetres measured from the TOP-LEFT of the selected official PDF page**. The template is considered ready for a *provisional overlay* only if the user attests to receiving it from the supplier, it exists, image ratios match, panels fit, DPI passes, and placements do not overlap. This attestation cannot be independently verified. The output is:

- `packaging_ARTWORK_ONLY_PROVISIONAL.pdf` — registered artwork on the sheet, no printer die lines embedded by DeckForge.
- `packaging_SUPPLIER_LINES_REVIEW_ONLY.pdf` — same artwork with the supplier's original PDF page superimposed for visual review.

A real printer may request separate artwork PDFs, PDF/X, specific spot-colour cut lines, dieline layer names or other deliverables. DeckForge does not declare either PDF certified. **Do not fake bleed, infer panel measurements from a 3D mockup, or claim the vendor accepted the layout.** For Print Europe, use its particular étui template for your confirmed selection, not an assumed 72 × 122 × 30 mm box.

## ICC-managed CMYK conversion

```powershell
# Requires your printer's ACTUAL ICC; never guess a standard profile as authoritative
python -m deckforge color-export my_deck --id P09 --icc C:/path/PrinterApproved.icc --output my_deck/cmyk_export --assume-srgb
```

The `--assume-srgb` option is required for untagged source images; omit it if every selected source includes a suitable embedded profile. Output TIFFs retain an embedded copy of the chosen target ICC and a manifest of source/output SHA-256 fingerprints, assumptions and profile identity. It refuses to overwrite existing output. This does **not** substitute for colour proofs, dot-gain/ink-limit measurements, paper-stock checks or PDF/X prepress.

## Standalone Windows .exe (no Python required for end user)

The source includes `.github/workflows/windows-installer.yml` and `installer/`. On **GitHub Actions → DeckForge V4 Windows installer → Run workflow**, a Windows runner installs Python/build tools, executes tests, packages the Tkinter GUI with PyInstaller, runs `--self-test` on the actual frozen executable, and compiles an Inno Setup installer. Download the unsigned installer from that workflow's **Artifacts** when it succeeds. Read [installer/README_WINDOWS.md](installer/README_WINDOWS.md).

**No `.exe` was built in the current Linux environment.** GitHub Actions must run successfully before describing an installer as tested. The unsigned installer may trigger SmartScreen and should be signed and tested on clean Windows 10/11 machines before distribution.

## Testing and QA

```bash
python -m pip install -e '.[dev]'
python -m pytest -q
python -m deckforge build demo_project --strict
python -m deckforge verify demo_project/build/deckforge_package.zip
```

The new tests use mocked API responses—**zero money spent and no real user images uploaded**—plus a synthetic supplier PDF and a real local Ghostscript CMYK ICC when available. They assert that stale AI conclusions cannot approve art, malformed templates fail, missing profiles fail, and overlays produce valid PDF pages.

## Security and privacy

Default runs are entirely offline. API requests occur only through opt-in `vision-review` or a GUI confirmation, never via `build`/`audit`. Keys are read from environment variables and not saved in project files. Dashboard embeds thumbnails and does not access a CDN. Source artwork and feedback stay inside the project unless the user explicitly exports or uploads them. **Do not publish the private images or the proprietary printer ICC of a third-party supplier to GitHub.**

## License

Code is MIT-licensed. Original procedural demo art is included for technical testing only. Production use must respect ownership, privacy, and commercial permissions of third-party artwork and brands.
