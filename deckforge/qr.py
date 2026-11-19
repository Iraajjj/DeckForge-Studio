"""Static, offline QR generation in raster and real vector formats."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import qrcode
from qrcode.constants import ERROR_CORRECT_M
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm


def check_url(url: str) -> None:
    if not isinstance(url, str) or not url.strip():
        raise ValueError("A public HTTP(S) guide URL is required for QR generation")
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Guide URL must start with http:// or https:// and contain a hostname")


def qr_matrix(url: str) -> list[list[bool]]:
    check_url(url)
    qr = qrcode.QRCode(version=None, error_correction=ERROR_CORRECT_M,
                       box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    return qr.get_matrix()


def export_qr_assets(url: str, out_dir: Path) -> list[Path]:
    """Create 25/30-mm 600-DPI PNGs and a 30-mm SVG/PDF, preserving quiet zones."""
    matrix = qr_matrix(url)
    n = len(matrix)
    out_dir.mkdir(parents=True, exist_ok=True)
    files = []
    # Each source pixel maps to an entire module; nearest-neighbour is essential.
    pil = Image.new("RGB", (n, n), "white")
    pixels = pil.load()
    for y, row in enumerate(matrix):
        for x, cell in enumerate(row):
            if cell:
                pixels[x, y] = (0, 0, 0)
    for size_mm in (30, 25):
        px = round(size_mm / 25.4 * 600)
        image = pil.resize((px, px), Image.Resampling.NEAREST)
        path = out_dir / f"qr_{size_mm}mm_600dpi.png"
        image.save(path, dpi=(600, 600))
        files.append(path)

    # XML is editable SVG with exact mm size and filled vector rectangles.
    size_mm = 30
    svg_path = out_dir / "qr_30mm_vector.svg"
    squares = "".join(f'<rect x="{x}" y="{y}" width="1" height="1"/>'
                      for y, row in enumerate(matrix) for x, black in enumerate(row) if black)
    svg_path.write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size_mm}mm" height="{size_mm}mm" viewBox="0 0 {n} {n}">\n'
        f'<rect width="{n}" height="{n}" fill="white"/><g fill="black">{squares}</g></svg>\n',
        encoding="utf-8")
    files.append(svg_path)

    pdf_path = out_dir / "qr_30mm_vector.pdf"
    pdf = canvas.Canvas(str(pdf_path), pagesize=(size_mm * mm, size_mm * mm), pageCompression=1)
    pdf.setTitle("DeckForge - 30 mm vector QR code")
    pdf.setFillColorRGB(1, 1, 1)
    pdf.rect(0, 0, size_mm * mm, size_mm * mm, stroke=0, fill=1)
    pdf.setFillColorRGB(0, 0, 0)
    side = size_mm * mm / n
    for y, row in enumerate(matrix):
        for x, black in enumerate(row):
            if black:
                pdf.rect(x * side, (n - 1 - y) * side, side, side, stroke=0, fill=1)
    pdf.showPage()
    pdf.save()
    files.append(pdf_path)
    return files
