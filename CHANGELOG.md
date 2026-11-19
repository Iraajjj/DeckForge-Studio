# Changelog

## 0.4.0 — Vision suggestions, supplier PDF overlays, ICC workflows and Windows build

- Introduced **opt-in** structured Responses API visual suggestions with per-suit physical-object expectations and mandatory confidence fields. No network on regular builds.
- Added per-card casting and scene checklists, optional approved reference image, local HSV palette-distance metric and SHA-256 stale observation detection.
- Added supplier PDF template mapping: millimetre top-left panel coordinates, image aspect/resolution bounds, overlap and path safety, two distinct packaging proof PDFs.
- Added opt-in CMYK TIFF conversion using a *real printer-supplied output ICC*, explicit handling of untagged sRGB assumptions and an auditable file manifest. No generic hidden CMYK profile.
- Added Windows PyInstaller freezing and Inno Setup installer scripts with GitHub Actions runner, built-executable smoke check and SHA256 output manifest.
- Added GUI actions for three upgrades plus two new offline dashboard tabs, with consent before any AI upload.
- Added V4 regression suite and retained all V1–V3 features and original demo art.
- Limitations: live AI calls not exercised without user API credentials; supplier-specific overlay needs the real manufacturer PDF; native installer still needs a Windows build.

## Earlier history

V3 delivered human approval, real-size proofs, supplier readiness and costs. V2 added desktop workflow, searchable QA, back symmetry and stronger duplicate checks. V1 introduced core 78-card validation, QR generation, contact sheets and verified ZIP packaging.
