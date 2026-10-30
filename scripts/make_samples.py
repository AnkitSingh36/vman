"""Generate fictional sample images for the POC.

Nameplates for engines and labels for part containers. All names and numbers are invented.
Each image gets a sidecar .json with what a perfect camera would read (used by offline mode only).
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path(__file__).resolve().parent.parent / "samples"
FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")


def font(size: int, bold: bool = False):
    """Try Linux DejaVu, then Windows/macOS Arial, then Pillow's default font."""
    candidates = [str(FONT_DIR / ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf")),
                  "arialbd.ttf" if bold else "arial.ttf",
                  "Arial Bold.ttf" if bold else "Arial.ttf"]
    for c in candidates:
        try:
            return ImageFont.truetype(c, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def nameplate(serial: str, model: str = "ME-450", year: str = "2024") -> Image.Image:
    w, h = 960, 600
    img = Image.new("RGB", (w, h), (70, 74, 80))
    d = ImageDraw.Draw(img)
    rng = random.Random(serial)
    for _ in range(4000):  # brushed metal speckle
        x, y = rng.randrange(w), rng.randrange(h)
        g = rng.randrange(150, 200)
        d.point((x, y), fill=(g, g, g + 5))
    plate = (120, 110, 840, 490)
    d.rounded_rectangle(plate, radius=18, fill=(196, 198, 202), outline=(90, 92, 96), width=6)
    for cx, cy in [(150, 140), (810, 140), (150, 460), (810, 460)]:
        d.ellipse((cx - 12, cy - 12, cx + 12, cy + 12), fill=(120, 122, 126))
    d.text((180, 150), "NORDVIK ENGINE WORKS", font=font(34, True), fill=(30, 30, 34))
    rows = [("MODEL", model), ("SERIAL NO.", serial), ("YEAR", year), ("RATED POWER", "450 kW @ 1800 rpm")]
    for i, (k, v) in enumerate(rows):
        y = 230 + i * 58
        d.text((180, y), k, font=font(24), fill=(60, 60, 64))
        d.text((420, y - 4), v, font=font(32, True), fill=(20, 20, 24))
    img = img.rotate(-3, resample=Image.BICUBIC, fillcolor=(70, 74, 80))
    return img.filter(ImageFilter.GaussianBlur(0.6))


def part_label(part_no: str, desc: str, rev: str, batch: str, container: str, qty: int) -> Image.Image:
    w, h = 960, 620
    img = Image.new("RGB", (w, h), (176, 140, 92))  # cardboard
    d = ImageDraw.Draw(img)
    rng = random.Random(container)
    for _ in range(3000):
        x, y = rng.randrange(w), rng.randrange(h)
        d.point((x, y), fill=(160 + rng.randrange(20), 124 + rng.randrange(20), 80))
    d.rectangle((110, 80, 850, 540), fill=(250, 250, 248), outline=(40, 40, 40), width=3)
    d.text((140, 100), "AURORA COMPONENTS OY", font=font(26, True), fill=(20, 20, 20))
    lines = [("PART NO.", part_no), ("DESCRIPTION", desc), ("REV", rev), ("BATCH", batch),
             ("CONTAINER", container), ("QTY", str(qty))]
    for i, (k, v) in enumerate(lines):
        y = 160 + i * 48
        d.text((140, y), k, font=font(22), fill=(70, 70, 70))
        d.text((380, y - 4), v, font=font(30, True), fill=(10, 10, 10))
    x = 140  # fake barcode
    for _ in range(70):
        bw = rng.choice([2, 3, 5])
        d.rectangle((x, 460, x + bw, 520), fill=(0, 0, 0))
        x += bw + rng.choice([2, 3, 4])
    img = img.rotate(2, resample=Image.BICUBIC, fillcolor=(176, 140, 92))
    return img.filter(ImageFilter.GaussianBlur(0.5))


def drone_plate(drone_id: str) -> Image.Image:
    w, h = 960, 600
    img = Image.new("RGB", (w, h), (34, 40, 48))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((180, 180, 780, 420), radius=60, fill=(220, 222, 226))      # drone body
    for cx, cy in [(130, 130), (830, 130), (130, 470), (830, 470)]:               # rotors
        d.ellipse((cx - 90, cy - 22, cx + 90, cy + 22), outline=(150, 150, 155), width=4)
        d.line((cx, cy, 480, 300), fill=(90, 90, 95), width=10)
    d.rounded_rectangle((300, 250, 660, 350), radius=10, fill=(250, 250, 250), outline=(40, 40, 40), width=3)
    d.text((320, 258), "UAV ID", font=font(20), fill=(70, 70, 70))
    d.text((320, 290), drone_id, font=font(40, True), fill=(10, 10, 10))
    return img.filter(ImageFilter.GaussianBlur(0.5))


def gauge(asset_tag: str, point: str, value: float, vmax: float = 10.0) -> Image.Image:
    import math
    w, h = 960, 640
    img = Image.new("RGB", (w, h), (150, 160, 150))
    d = ImageDraw.Draw(img)
    d.rectangle((0, 420, w, h), fill=(120, 128, 120))                                 # tank wall
    d.rectangle((620, 450, 900, 560), fill=(240, 240, 236), outline=(30, 30, 30), width=3)
    d.text((640, 465), "ASSET", font=font(20), fill=(60, 60, 60))
    d.text((640, 495), asset_tag, font=font(40, True), fill=(10, 10, 10))
    cx, cy, r = 330, 300, 220
    d.ellipse((cx - r - 12, cy - r - 12, cx + r + 12, cy + r + 12), fill=(60, 60, 64))
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(250, 250, 248))
    start, sweep = 225, 270                                                         # degrees, clockwise
    for i in range(0, int(vmax) + 1):
        a = math.radians(start - sweep * i / vmax)
        x1, y1 = cx + (r - 20) * math.cos(a), cy - (r - 20) * math.sin(a)
        x2, y2 = cx + (r - 50) * math.cos(a), cy - (r - 50) * math.sin(a)
        d.line((x1, y1, x2, y2), fill=(20, 20, 20), width=5)
        tx, ty = cx + (r - 80) * math.cos(a), cy - (r - 80) * math.sin(a)
        d.text((tx - 10, ty - 14), str(i), font=font(26, True), fill=(20, 20, 20))
    lo = math.radians(start - sweep * 6.0 / vmax)                                   # red zone above 6 bar
    hi = math.radians(start - sweep)
    d.arc((cx - r + 8, cy - r + 8, cx + r - 8, cy + r - 8), start=-math.degrees(lo), end=-math.degrees(hi),
          fill=(200, 30, 30), width=10)
    d.text((cx - 22, cy + 70), "bar", font=font(28, True), fill=(20, 20, 20))
    d.text((cx - 45, cy + 110), point, font=font(28, True), fill=(20, 20, 20))
    a = math.radians(start - sweep * value / vmax)
    d.line((cx, cy, cx + (r - 40) * math.cos(a), cy - (r - 40) * math.sin(a)), fill=(180, 20, 20), width=8)
    d.ellipse((cx - 14, cy - 14, cx + 14, cy + 14), fill=(30, 30, 30))
    return img.filter(ImageFilter.GaussianBlur(0.6))


def main() -> None:
    OUT.mkdir(exist_ok=True)
    plates = ["ME450-21877", "ME450-19950", "ME450-21878"]  # last one is not in the vault
    for s in plates:
        nameplate(s).save(OUT / f"nameplate_{s}.png")
        (OUT / f"nameplate_{s}.json").write_text(json.dumps({"identifier": s, "model": "ME-450"}, indent=2))
    labels = [
        ("PN-88213", "INJECTOR BRACKET", "A", "B-2026-0915", "CNT-48812", 12),
        ("PN-77102", "SEAL KIT", "C", "B-2026-0912", "CNT-48807", 40),
        ("PN-55410", "HOSE ASSEMBLY", "A", "B-2026-0930", "CNT-48830", 8),
        ("PN-60001", "CLAMP", "F", "B-2026-1002", "CNT-48841", 200),
        ("PN-88213", "INJECTOR BRACKET", "B", "B-2026-1003", "CNT-48850", 12),
    ]
    for pn, desc, rev, batch, cnt, qty in labels:
        part_label(pn, desc, rev, batch, cnt, qty).save(OUT / f"label_{cnt}.png")
        (OUT / f"label_{cnt}.json").write_text(json.dumps(
            {"identifier": cnt, "part_number": pn, "label_revision": rev, "batch_number": batch}, indent=2))
    drone_plate("UAV-D7-0041").save(OUT / "drone_UAV-D7-0041.png")
    (OUT / "drone_UAV-D7-0041.json").write_text(json.dumps({"identifier": "UAV-D7-0041"}, indent=2))
    for tag, point, value in (("TK-102", "PI-102", 7.4), ("TK-101", "PI-101", 3.1)):
        gauge(tag, point, value).save(OUT / f"gauge_{tag}.png")
        (OUT / f"gauge_{tag}.json").write_text(json.dumps(
            {"identifier": tag, "measurement_point": point, "value": value, "unit": "bar"}, indent=2))
    print(f"Wrote {len(plates) + len(labels) + 3} images to {OUT}")


if __name__ == "__main__":
    main()
