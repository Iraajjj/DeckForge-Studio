"""Create a fully original, non-franchise sample deck for reproducible testing."""
from __future__ import annotations

from math import cos, sin, pi
from colorsys import hsv_to_rgb
from pathlib import Path
import random

from PIL import Image, ImageDraw, ImageFont

from .project import default_config, write_config
from .printer import default_printer_profile,write_printer_profile
from .costing import example

W, H = 840, 1440
PALETTES = (
    ((52, 42, 98), (172, 129, 197), (255, 222, 179)),
    ((30, 79, 115), (130, 168, 196), (252, 217, 164)),
    ((66, 62, 119), (171, 152, 201), (246, 223, 185)),
    ((44, 85, 79), (134, 180, 156), (253, 231, 194)),
    ((91, 52, 97), (188, 142, 182), (249, 220, 196)),
)


def font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = (["DejaVuSans-Bold.ttf"] if bold else ["DejaVuSerif.ttf", "DejaVuSans.ttf"])
    for filename in candidates:
        try:
            return ImageFont.truetype(filename, size)
        except OSError:
            continue
    return ImageFont.load_default()


def bg_gradient(im: Image.Image, top: tuple[int, int, int], bottom: tuple[int, int, int]):
    d = ImageDraw.Draw(im)
    for y in range(H):
        t = y / (H - 1)
        col = tuple(int(a + (b - a) * t) for a, b in zip(top, bottom))
        d.line((0, y, W, y), fill=col, width=1)


def star(draw: ImageDraw.ImageDraw, x: float, y: float, r: float, color: tuple[int, int, int], points: int = 8):
    outer=[]
    for k in range(points * 2):
        phi=-pi/2 + k*pi/points
        rr=r if k%2 == 0 else r*.32
        outer.append((x+cos(phi)*rr, y+sin(phi)*rr))
    draw.polygon(outer, fill=color)


def card_art(title: str, card_id: str, index: int, out: Path) -> None:
    """Original decorative art for QA demonstrations only; no third-party characters."""
    rng = random.Random(index * 5917 + 56)
    top, middle, bottom = PALETTES[index % len(PALETTES)]
    # V2: every card has a unique focal palette and emblem, not just a new caption.
    # This makes the public demo a meaningful test for near-duplicate detection.
    hue = (index * 0.47871 + 0.13) % 1.0
    accent = tuple(round(ch*255) for ch in hsv_to_rgb(hue, .50, .69))
    top = tuple(round(.68*a + .32*b) for a,b in zip(top, accent))
    middle = tuple(round(.64*a + .36*b) for a,b in zip(middle, accent))
    im = Image.new("RGB", (W, H))
    bg_gradient(im, top, middle)
    draw = ImageDraw.Draw(im)
    # Original celestial landscape, selected so every card differs visibly.
    for j in range(13):
        x = rng.randrange(65, W-65)
        y = rng.randrange(180, 830)
        star(draw, x, y, rng.randrange(8, 27), (255, 234, 166), 4 if j%3 else 8)
    draw.ellipse((150, 220, 690, 760), fill=tuple(min(255, c+22) for c in middle), outline=(255,221,156), width=10)
    # A large, card-specific coloured central medallion creates visible differences
    # even among cards sharing the same ornate frame and suit vocabulary.
    accent_soft = tuple(round(.85*a+.15*b) for a,b in zip(accent, (255,230,220)))
    draw.ellipse((220, 290, 620, 690), fill=accent_soft, outline=(255,245,214), width=8)
    # A different radial constellation/petalled geometry on every card. The
    # generated compositions intentionally share a border, NOT the whole scene.
    constellation = random.Random(77771 + index * 7919)
    for k in range(8):
        angle = -pi/2 + 2*pi*k/8 + constellation.random()*.8
        radius = constellation.randrange(60, 245)
        cx = int(420 + cos(angle)*radius)
        cy = int(555 + sin(angle)*radius)
        rr = constellation.randrange(28, 105)
        col = tuple(int(160+95*constellation.random()) for _ in range(3))
        draw.ellipse((cx-rr,cy-rr,cx+rr,cy+rr),fill=col,outline=(255,232,178),width=6)
    if index % 4 == 0:
        star(draw, 420, 530, 164, (251,213,115), points=6+(index%5))
    elif index % 4 == 1:
        for rr in (170,122,75):
            draw.ellipse((420-rr,530-rr,420+rr,530+rr),outline=(255,232,186),width=13)
    elif index % 4 == 2:
        draw.polygon([(225,660),(390,320),(575,660)],fill=(251,222,146),outline=(255,245,214),width=9)
    else:
        for k in range(5):
            star(draw, 255+k*83, 420+(-1)**k*82, 60, (254,221,157), points=5)
    star(draw, 420, 530, 68, (255, 243, 201), points=8)
    draw.ellipse((85, 785, 760, 1060), fill=tuple(min(255,c+30) for c in middle))
    draw.ellipse((200, 870, 640, 1120), fill=bottom)
    draw.rounded_rectangle((25,25,W-25,H-25), radius=65, outline=(255,226,154), width=15)
    draw.rounded_rectangle((48,48,W-48,H-48), radius=48, outline=(255,247,231), width=5)
    for x in (95, W-95):
        for y in (105,H-105):
            star(draw,x,y,28,(255,239,184))
    draw.rounded_rectangle((91, 1150, W-91, 1335), radius=44, fill=(247,232,242), outline=(232,190,112), width=8)
    draw.text((W//2, 1185), title, font=font(46 if len(title)<24 else 35, True),
              anchor="mt", fill=(72, 43, 97), stroke_width=0)
    draw.text((W//2, 1280), f"{card_id}  •  DECKFORGE SAMPLE", font=font(23),
              anchor="mt", fill=(72, 43, 97))
    im.save(out, format="JPEG", quality=86, subsampling=0)


def back_art(out: Path) -> None:
    im = Image.new("RGB", (W,H), (95,76,139))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((24,24,W-24,H-24), radius=66, outline=(255,226,154), width=16)
    d.rounded_rectangle((48,48,W-48,H-48), radius=48, outline=(250,231,244), width=6)
    # Deliberately 180-degree rotationally symmetric: a reversed card is not revealed.
    for x,y in [(110,175),(230,350),(130,520),(650,240),(560,460)]:
        for X,Y in [(x,y),(W-x,H-y)]:
            star(d,X,Y,28,(255,237,173))
    for y in (210, H-210):
        d.ellipse((W/2-110,y-110,W/2+110,y+110),fill=(220,166,202),outline=(255,227,161),width=9)
        star(d,W/2,y,70,(255,230,145))
    d.ellipse((205, H/2-215, 635,H/2+215),fill=(246,227,239),outline=(255,219,149),width=18)
    star(d,W/2,H/2,176,(241,183,116))
    d.ellipse((W/2-81,H/2-81,W/2+81,H/2+81),fill=(111,76,148),outline=(255,239,190),width=9)
    star(d,W/2,H/2,65,(255,222,156))
    im.save(out, format="JPEG", quality=90, subsampling=0)


def create_demo(project_dir: Path, *, overwrite: bool = False) -> Path:
    """Make 78 source-free sample fronts + symmetric back, ready for `build`."""
    if (project_dir/"deckforge.json").exists() and not overwrite:
        raise FileExistsError(f"Demo project already exists: {project_dir}")
    config = default_config("DeckForge Celestial Demo (Original Art)", "jpg",
                            guide_url="https://example.org/deckforge-demo-guide")
    write_config(project_dir, config, overwrite=overwrite)
    for index, entry in enumerate(config["cards"]):
        out = project_dir / entry["file"]
        out.parent.mkdir(parents=True,exist_ok=True)
        card_art(entry["title"], entry["id"], index, out)
    back_art(project_dir/"back.jpg")
    if not (project_dir/'printer_profile.json').exists():
        write_printer_profile(project_dir,default_printer_profile())
    (project_dir/'pricing_scenarios.json').write_text(__import__('json').dumps(example(),indent=2)+'\n',encoding='utf-8')
    return project_dir
