"""V2 image analysis: metadata, subtle duplicates and 180-degree back review.

All results are PRE-FLIGHT HEURISTICS, not AI interpretation or printer certification.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
from pathlib import Path

from PIL import Image, ImageChops, ImageOps, ImageStat

from .project import safe_relative_file
from .validation import issue


def normalized_rgb(path: Path, size: tuple[int, int] = (64, 64)) -> Image.Image:
    with Image.open(path) as original:
        image = ImageOps.exif_transpose(original).convert("RGB")
        image.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
        return image.resize(size, Image.Resampling.LANCZOS)


def dhash(image: Image.Image) -> int:
    """64-bit difference hash of a 9x8 greyscale thumbnail."""
    gray = image.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    pixels = gray.tobytes()
    result = 0
    for row in range(8):
        for col in range(8):
            result = (result << 1) | int(pixels[row * 9 + col] > pixels[row * 9 + col + 1])
    return result


def near_duplicate_score(a: Image.Image, b: Image.Image) -> float:
    """Average absolute RGB difference, normalized to [0, 1]."""
    return sum(ImageStat.Stat(ImageChops.difference(a, b)).mean) / (3 * 255)


def rotation_difference(image: Image.Image) -> float:
    """Compare card back to its own 180-degree rotation; 0=identical.

    This cannot verify reversible meaning, crop safety, or printing tolerances.
    """
    image = image.convert("RGB").resize((120, 208), Image.Resampling.LANCZOS)
    return round(near_duplicate_score(image, image.transpose(Image.Transpose.ROTATE_180)), 4)


def enrich_report(project_dir: Path, config: dict, report: dict) -> dict:
    """Add detailed metrics while preserving the V1 report schema."""
    issues = list(report["issues"])
    seen: list[tuple[str, int, Image.Image]] = []
    mode_counts: Counter[str] = Counter()
    icc_count = 0

    for card in report["cards"]:
        card.update({"color_mode": None, "has_icc_profile": None,
                     "embedded_dpi": None, "image_sha256": None})
        if not card["present"] or not card["file"]:
            continue
        try:
            path, _ = safe_relative_file(project_dir, card["file"])
            with Image.open(path) as im:
                card["color_mode"] = im.mode
                mode_counts[im.mode] += 1
                card["has_icc_profile"] = bool(im.info.get("icc_profile"))
                if card["has_icc_profile"]:
                    icc_count += 1
                dp = im.info.get("dpi")
                if isinstance(dp, (tuple, list)) and len(dp) >= 2:
                    card["embedded_dpi"] = [round(float(dp[0]),1), round(float(dp[1]),1)]
            card["image_sha256"] = sha256(path.read_bytes()).hexdigest()
            thumb = normalized_rgb(path, (64, 64))
            new_hash = dhash(thumb)
            # Compare only candidates with nearby perceptual fingerprints.
            for old_id, old_hash, old_thumb in seen:
                distance = (new_hash ^ old_hash).bit_count()
                if distance <= 6:
                    difference = near_duplicate_score(thumb, old_thumb)
                    if difference <= 0.020:  # very close, conservative threshold to avoid same-template false alarms
                        issues.append(issue("warning", "NEAR_DUPLICATE_ART",
                                            f"{card['id']} and {old_id} look very similar "
                                            f"(hash distance {distance}/64; normalized colour difference {difference:.3f}); review both", card["id"]))
                        break
            seen.append((card["id"], new_hash, thumb))
        except (OSError, ValueError, Image.DecompressionBombError):
            # V1 already reports unreadable images.
            pass

    back = report.get("back", {})
    back["rotation_difference"] = None
    back["reversible_by_heuristic"] = None
    if back.get("present") and back.get("file"):
        try:
            path, _ = safe_relative_file(project_dir, back["file"])
            with Image.open(path) as im:
                corrected = ImageOps.exif_transpose(im)
                score = rotation_difference(corrected)
                back["rotation_difference"] = score
                tolerance = float(config.get("reversibility_tolerance", 0.04))
                back["reversible_by_heuristic"] = score <= tolerance
                if score > tolerance:
                    issues.append(issue("warning", "BACK_ROTATION_MISMATCH",
                                        f"Card back differs by {score*100:.1f}% from its 180-degree rotation "
                                        f"(threshold {tolerance*100:.1f}%); reversed cards may be identifiable"))
        except (OSError, ValueError, Image.DecompressionBombError):
            pass

    report["issues"] = issues
    report["errors"] = sum(i["severity"] == "error" for i in issues)
    report["warnings"] = sum(i["severity"] == "warning" for i in issues)
    report["version"] = "0.4.0"
    report["safe_area_mm"] = float(config.get("safe_area_mm", 4.0))
    report["bleed_required_mm"] = float(config.get("bleed_required_mm", 3.0))
    report["color_modes"] = dict(mode_counts)
    report["icc_embedded_count"] = icc_count
    report["readiness"] = ("INCOMPLETE" if report["errors"] else
                           "REVIEW_REQUIRED" if report["warnings"] else "TECHNICAL_CHECKS_PASS")
    report["manual_checks"] = [
        "Artwork symbolism, suit-object counts, spelling and title placement",
        "Printer-specific dieline, bleed artwork and cutter tolerance",
        "Colour space, ICC profile, black generation and soft proofing",
        "Guide link accessibility from a signed-out device and QR print scan test",
        "Rights and permission for commercial artwork and associated branding",
    ]
    return report
