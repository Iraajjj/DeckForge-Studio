"""Simple JSON project configuration and safe path utilities."""
from __future__ import annotations

import json
from pathlib import Path

from .catalog import expected_cards


def default_config(name: str = "My Tarot Deck", extension: str = "png", *, guide_url: str = "") -> dict:
    return {
        "schema_version": 1,
        "deck_name": name,
        "card_width_mm": 70.0,
        "card_height_mm": 120.0,
        "min_dpi": 300,
        "ratio_tolerance": 0.025,
        "safe_area_mm": 4.0,
        "bleed_required_mm": 3.0,
        "source_bleed_mm": 0.0,  # 0=trim-only; positive ONLY when source art really contains extra perimeter art
        "reversibility_tolerance": 0.04,
        "guide_url": guide_url,
        "back_file": "back.png" if extension == "png" else f"back.{extension}",
        "cards": expected_cards(extension),
    }


def write_config(project_dir: Path, config: dict, *, overwrite: bool = False) -> Path:
    project_dir.mkdir(parents=True, exist_ok=True)
    path = project_dir / "deckforge.json"
    if path.exists() and not overwrite:
        raise FileExistsError(f"Project already exists: {path}")
    path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for item in config["cards"]:
        (project_dir / Path(item["file"]).parent).mkdir(parents=True, exist_ok=True)
    return path


def read_config(project_dir: Path) -> dict:
    path = project_dir / "deckforge.json"
    if not path.is_file():
        raise FileNotFoundError(f"Missing deckforge.json inside {project_dir}; run `deckforge init` or `deckforge demo`.")
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("Config should be a JSON object")
    needed = {"deck_name", "card_width_mm", "card_height_mm", "min_dpi", "cards"}
    if missing := needed - obj.keys():
        raise ValueError(f"Config is missing fields: {', '.join(sorted(missing))}")
    if not isinstance(obj["cards"], list):
        raise ValueError("'cards' must be a list")
    for key in ("card_width_mm", "card_height_mm", "min_dpi"):
        if not isinstance(obj[key], (int, float)) or isinstance(obj[key], bool) or obj[key] <= 0:
            raise ValueError(f"{key} must be a positive number")
    tol = obj.get("ratio_tolerance", 0.025)
    if not isinstance(tol, (int, float)) or not 0 < tol <= 0.25:
        raise ValueError("ratio_tolerance must be between 0 and 0.25")
    for key, maximum in (("safe_area_mm", 20), ("bleed_required_mm", 10), ("source_bleed_mm", 15)):
        if key in obj and (not isinstance(obj[key], (int, float)) or isinstance(obj[key], bool) or not 0 <= obj[key] <= maximum):
            raise ValueError(f"{key} must be a number between 0 and {maximum}")
    if obj.get("safe_area_mm", 4) * 2 >= min(obj["card_width_mm"], obj["card_height_mm"]):
        raise ValueError("safe area must leave room for artwork")
    symmetry = obj.get("reversibility_tolerance", 0.04)
    if not isinstance(symmetry, (int,float)) or not 0 < symmetry <= 1:
        raise ValueError("reversibility_tolerance must be between 0 and 1")
    return obj


def safe_relative_file(project_dir: Path, raw: str) -> tuple[Path, str]:
    """Resolve only inside project; block absolute paths, ../ and symlink escapes."""
    if not isinstance(raw, str) or not raw:
        raise ValueError("file path must be a nonempty string")
    rel = Path(raw)
    if rel.is_absolute() or any(part in {"..", "."} for part in rel.parts):
        raise ValueError("Only simple project-relative file paths are allowed")
    root = project_dir.resolve()
    path = (project_dir / rel).resolve()
    if not path.is_relative_to(root):
        raise ValueError("File escapes the project folder")
    return path, rel.as_posix()
