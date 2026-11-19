# DeckForge Studio V4 — hands-on test drive

- [ ] Extract starter ZIP and open GUI using `START_STUDIO_WINDOWS.bat` (Python version).
- [ ] Choose `demo_project`, audit 78/78 cards, and build package with zero technical errors/warnings.
- [ ] Open `build/qa_dashboard.html`: gallery, human reviews, AI review notes, supplier template, costs.
- [ ] Confirm the AI tab says **No AI reviews recorded**. No API upload should occur during normal builds.
- [ ] Edit one image → previous human and AI observations are stale; replace the image to restore fresh reviews.
- [ ] Use `vision-init` and set a reference image; run an API review only by explicit consent with your OWN key (optional; can incur charges).
- [ ] Create a template manifest from a TRUE factory PDF; enter measured panels; confirm errors for low DPI, overlap and incompatible ratios.
- [ ] Inspect `packaging_ARTWORK_ONLY_PROVISIONAL.pdf` and `packaging_SUPPLIER_LINES_REVIEW_ONLY.pdf` side by side. Neither is manufacturer certified.
- [ ] Use a printer-supplied CMYK ICC and confirm TIFFs embed it. Untagged sources need explicit `--assume-srgb`.
- [ ] Verify the package with `python -m deckforge verify` and confirm checksum success.
- [ ] On a public/private GitHub repository, run the Windows installer Actions workflow; retrieve the unsigned exe from artifacts, verify checksum, test on a clean Windows PC.
- [ ] Review copyright/trademarks, printed QR accessibility, paper stocks and printer BAT manually before commercial sale.
