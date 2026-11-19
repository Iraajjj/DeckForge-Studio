# DeckForge Studio V4 — architecture and trust boundaries

`catalog.py` → `project.py` → `validation.py` / `advanced.py` → `reviews.py` → `build.py` → local `dashboard.py` & PDFs.

- `vision.py`: explicit, per-card optional HTTPS Responses API adapter; strictly structured observations; fingerprinters for staleness; local palette comparison. No API call from normal audit, demo or build.
- `manufacturing.py`: separate official PDF template registration and safe panel bounds; true ICC source→target transforms through Pillow LittleCMS; never silently manufactures bleed or vendor specifications.
- `printer.py`: unconfirmed supplier profile and human release gate, independent from optional AI suggestions.
- `installer/`: PyInstaller standard GUI entrypoint with `--self-test`, Windows GitHub Action and Inno Setup script. Cannot be built/tested for Windows on Linux.
- Existing protections retained: safe relative file paths; conservative imports; human approvals hash-bound to images; original demo art; SHA256 streamed ZIP verification; offline dashboard; user-supplied cost inputs.

## Security model

Offline by default. The only outbound network request from DeckForge logic is an explicit `vision_review` invoked by the CLI or confirmed desktop UI, using the user's own API token from `OPENAI_API_KEY`. The tool never copies the token into JSON files or the final ZIP. The model sees the selected artwork and optional style reference only; no full repository upload. Vision outputs are **advisory, not safety or manufacturing certifications**.

The vendor's own PDF, numeric panel extents and CMYK ICC must be explicitly provided and reviewed by the user. The demo template is not a print specification. ZIP integrity is not creator authentication; signatures and supply-chain provenance remain out of scope.
