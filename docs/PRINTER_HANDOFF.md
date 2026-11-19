# Printer handoff — what V4 can and cannot supply

1. Obtain the actual manufacturer's specification, including card cut size, source bleed, required safe area, paper stock, printable colour space and complete packaging dieline.
2. The project `printer_profile.json` is never verified automatically. Enter real values and confirm only after documentary checks.
3. Use `template-init` and populate `packaging_template.json` with panel positions **measured** from the supplied PDF. The program checks ratio, bounds, DPI and overlap, then creates two provisional overlays.
4. Convert artwork with a **printer-approved** ICC only if required, document whether source ICC was present, inspect overprint and colour results with the supplier.
5. PDF/print operations are for technical review. Neither package is a production-ready PDF/X, die-cut layout certified by the print house or a guaranteed bleed asset.
6. Obtain a digital proof (BAT) and preferably a physical printed proof before ordering a commercial quantity. Test QR at final print scale and verify public access to the linked digital guide.
