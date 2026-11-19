"""Review-sized preflight checks; does not certify physical print production."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from .catalog import expected_cards
from .project import safe_relative_file


@dataclass(frozen=True)
class Issue:
    severity: str
    code: str
    message: str
    card_id: str | None = None


def issue(severity: str, code: str, message: str, card_id: str | None = None) -> dict:
    return asdict(Issue(severity, code, message, card_id))


def inspect_deck(project_dir: Path, config: dict) -> dict:
    issues: list[dict] = []
    records: list[dict] = []
    indexed_by_id: dict[str, dict] = {}
    seen_files: dict[str, str] = {}
    seen_pixels: dict[str, str] = {}
    expected = expected_cards()
    canonical = {c["id"]: c["title"] for c in expected}

    for index, item in enumerate(config["cards"]):
        if not isinstance(item, dict):
            issues.append(issue("error", "INVALID_MANIFEST_ENTRY", f"Entry {index+1} is not an object"))
            continue
        card_id, title, raw_path = item.get("id"), item.get("title"), item.get("file")
        if not isinstance(card_id, str) or not isinstance(title, str):
            issues.append(issue("error", "INVALID_MANIFEST_ENTRY", f"Entry {index+1} requires a text id and title"))
            continue
        if card_id not in canonical:
            issues.append(issue("error", "UNKNOWN_CARD_ID", f"Unexpected card ID {card_id}", card_id))
            continue
        if card_id in indexed_by_id:
            issues.append(issue("error", "DUPLICATE_CARD_ID", f"Repeated manifest card {card_id}", card_id))
            continue
        indexed_by_id[card_id] = item
        if title != canonical[card_id]:
            issues.append(issue("warning", "TITLE_MISMATCH", f"{card_id}: expected '{canonical[card_id]}', got '{title}'", card_id))

    missing_entries = set(canonical) - set(indexed_by_id)
    for cid in sorted(missing_entries):
        issues.append(issue("error", "MISSING_MANIFEST_CARD", f"{cid}: {canonical[cid]} absent from manifest", cid))
    if len(config["cards"]) != 78:
        issues.append(issue("error", "CARD_COUNT", f"Manifest has {len(config['cards'])} entries; a full tarot deck needs 78"))

    width_mm = float(config["card_width_mm"])
    height_mm = float(config["card_height_mm"])
    dpi = int(config["min_dpi"])
    source_bleed = float(config.get("source_bleed_mm", 0.0))
    physical_w = width_mm + 2*source_bleed
    physical_h = height_mm + 2*source_bleed
    ratio = physical_w / physical_h
    tolerance = float(config.get("ratio_tolerance", 0.025))
    min_w, min_h = physical_w / 25.4 * dpi, physical_h / 25.4 * dpi

    for entry in expected:
        cid, canonical_title = entry["id"], entry["title"]
        item = indexed_by_id.get(cid)
        record = {"id": cid, "title": canonical_title,
                  "file": item.get("file") if item else None, "present": False, "size_px": None,
                  "dpi_at_trim": None}
        records.append(record)
        if not item:
            continue
        try:
            path, posix = safe_relative_file(project_dir, item.get("file"))
        except ValueError as e:
            issues.append(issue("error", "UNSAFE_PATH", f"{cid}: {e}", cid))
            continue
        if posix in seen_files:
            issues.append(issue("error", "DUPLICATE_PATH", f"{cid} and {seen_files[posix]} point to {posix}", cid))
        seen_files[posix] = cid
        if not path.is_file():
            issues.append(issue("error", "MISSING_IMAGE", f"{cid}: missing {posix}", cid))
            continue
        if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"}:
            issues.append(issue("error", "UNSUPPORTED_FORMAT", f"{cid}: unsupported extension {path.suffix}", cid))
            continue
        try:
            with Image.open(path) as im:
                orientation_corrected = ImageOps.exif_transpose(im)
                w, h = orientation_corrected.size
                # Pillow can decode the image fully here; truncated files cause an error.
                orientation_corrected.load()
                record["present"] = True
                record["size_px"] = [w, h]
                record["dpi_at_trim"] = [round(w / (physical_w / 25.4)), round(h / (physical_h / 25.4))]
                if abs(w / h - ratio) > tolerance:
                    issues.append(issue("warning", "ASPECT_RATIO", f"{cid}: {w}x{h} differs from source-art geometry {physical_w:g}:{physical_h:g} mm", cid))
                if w < min_w or h < min_h:
                    issues.append(issue("warning", "LOW_RESOLUTION", f"{cid}: {w}x{h}px is below {dpi} DPI at {physical_w:g}x{physical_h:g} mm source extent", cid))
                if orientation_corrected.mode in ("RGBA", "LA", "P") or "transparency" in orientation_corrected.info:
                    issues.append(issue("warning", "TRANSPARENCY_OR_PALETTE", f"{cid}: {orientation_corrected.mode} may need flattening for the printer", cid))
                # Compare normalized pixel samples for identical artwork, not just filenames.
                sample = orientation_corrected.convert("RGB").resize((64, 64), Image.Resampling.LANCZOS)
                digest = sha256(sample.tobytes()).hexdigest()
                if digest in seen_pixels:
                    issues.append(issue("warning", "IDENTICAL_ART", f"{cid} appears identical to {seen_pixels[digest]}; review duplicate artwork", cid))
                else:
                    seen_pixels[digest] = cid
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as e:
            issues.append(issue("error", "UNREADABLE_IMAGE", f"{cid}: cannot read {posix}: {type(e).__name__}", cid))

    back_file = config.get("back_file")
    back_info = {"file": back_file or None, "present": False}
    if back_file:
        try:
            back_path, rel_back = safe_relative_file(project_dir, back_file)
            if back_path.is_file():
                with Image.open(back_path) as im:
                    im.load()
                    back_info["present"] = True
                    bw, bh = ImageOps.exif_transpose(im).size
                    back_info["size_px"] = [bw, bh]
                    if abs(bw / bh - ratio) > tolerance:
                        issues.append(issue("warning", "BACK_RATIO", f"Back image ratio {bw}x{bh} differs from trim ratio"))
                    if bw < min_w or bh < min_h:
                        issues.append(issue("warning", "BACK_LOW_RESOLUTION", f"Back: {bw}x{bh}px is below target {dpi} DPI at trim"))
            else:
                issues.append(issue("warning", "MISSING_BACK", f"Optional back artwork not found: {rel_back}"))
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as e:
            issues.append(issue("warning", "INVALID_BACK", f"Cannot use back image: {type(e).__name__}"))
    else:
        issues.append(issue("warning", "NO_BACK_CONFIG", "No back_file provided; only fronts will be reviewed"))

    listed_files = {v.get("file") for v in indexed_by_id.values()}
    card_root = project_dir / "cards"
    if card_root.exists():
        supported = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"}
        for extra in sorted(p for p in card_root.rglob('*') if p.is_file() and p.suffix.lower() in supported):
            if extra.relative_to(project_dir).as_posix() not in listed_files:
                issues.append(issue("warning", "UNREFERENCED_IMAGE", f"Artwork not listed in manifest: {extra.relative_to(project_dir).as_posix()}"))

    counts = Counter(a["severity"] for a in issues)
    return {"tool": "DeckForge", "version": "0.1.0", "deck_name": config["deck_name"],
            "expected_cards": 78, "present_cards": sum(r["present"] for r in records),
            "errors": counts["error"], "warnings": counts["warning"],
            "card_width_mm": width_mm, "card_height_mm": height_mm,
            "min_dpi": dpi, "source_bleed_mm": source_bleed, "back": back_info,
            "cards": records, "issues": issues}
