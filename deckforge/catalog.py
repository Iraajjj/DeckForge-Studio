"""Canonical 78-card Rider-Waite-Smith order used to build portable manifests."""
from __future__ import annotations

import re

MAJORS = (
    "The Fool", "The Magician", "The High Priestess", "The Empress",
    "The Emperor", "The Hierophant", "The Lovers", "The Chariot",
    "Strength", "The Hermit", "Wheel of Fortune", "Justice",
    "The Hanged Man", "Death", "Temperance", "The Devil", "The Tower",
    "The Star", "The Moon", "The Sun", "Judgement", "The World",
)
SUITS = ("Wands", "Cups", "Swords", "Pentacles")
RANKS = ("Ace", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight",
         "Nine", "Ten", "Page", "Knight", "Queen", "King")


def slugify(value: str) -> str:
    """Turn a card name into a conservative ASCII file slug."""
    value = value.casefold().replace("’", "'")
    return re.sub(r"[^a-z0-9]+", "_", value).strip("_")


def expected_cards(extension: str = "png") -> list[dict[str, str]]:
    """Card inventory with deterministic IDs and file paths."""
    extension = extension.lower().lstrip(".")
    if extension not in {"png", "jpg", "jpeg", "webp", "tif", "tiff"}:
        raise ValueError("extension must be png, jpg, jpeg, webp, tif or tiff")
    cards = []
    for i, title in enumerate(MAJORS):
        cards.append({"id": f"M{i:02d}", "title": title, "file": f"cards/major_arcana/{i:02d}_{slugify(title)}.{extension}"})
    for suit, letter in zip(SUITS, "WCSP"):
        for i, rank in enumerate(RANKS, start=1):
            title = f"{rank} of {suit}"
            cards.append({"id": f"{letter}{i:02d}", "title": title,
                          "file": f"cards/{suit.lower()}/{i:02d}_{slugify(title)}.{extension}"})
    assert len(cards) == 78
    return cards
