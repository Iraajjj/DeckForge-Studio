# DeckForge V4 verification snapshot — 2026-11-19

**Local source test status:** `46 passed` using `python -m pytest -q`.

**E2E original demonstration:** 78/78 cards, zero automated technical errors/warnings, 20-page physical-size proof, QR files, offline dashboard and a ZIP with 99 SHA-256 verified entries. Printer release remains REVIEW_PENDING (correct: missing actual supplier approval and human sign-off).

**V4 focused validation:** 10 tests for opt-in vision payload and no-key refusal, model-mocked symbol mismatch and SHA staleness, palette metric, supplier template bounds/ratio/origin and overlay, RGB ICC rejection and real local Ghostscript CMYK ICC TIFF conversion, output overwrite refusal, and build/report ZIP integration.

**Browser:** V4 overview, AI review and supplier template tabs render and respond without JavaScript exceptions in headless Chromium. `docs/v4_ai_review_empty.png` is an authentic screenshot, not a generated UI concept.

**Supplier PDF:** `docs/v4_supplier_overlay_demo.png` shows a real code-generated PDF with six artwork panels and top-layer line guides, using a clearly labelled synthetic test sheet. This is **not** a real factory dieline.

**Not performed:** A real OpenAI API request (no API key/billing supplied); official printer geometry/ICC approval (no supplier-delivered template/profile supplied); build and install of a Windows `.exe` (Linux environment). Windows workflow included but requires a Windows runner to execute and inspect.

All three improvements have an implemented code path with local automated coverage. None of these tests establishes real-world manufacturing or model accuracy.
