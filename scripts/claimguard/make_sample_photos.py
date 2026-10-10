"""Render synthetic weighbridge-yard photos (four lighting styles) with real EXIF into data/evidence/photos/.

    services/claimguard/.venv/Scripts/python.exe scripts/claimguard/make_sample_photos.py

Synthetic stand-ins for the photos the team shoots for the demo (MRUDDUNI.md 3.2). Deterministic. Upload them to the
claim-evidence bucket as ``evidence/<claim_id>/PHOTO/<file>`` to see the real pipeline classify them and R5 decide.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

import piexif
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "evidence" / "photos"
W, H = 640, 480


def _gps(lat: float, lon: float) -> dict:
    def dms(v):
        v = abs(v)
        d = int(v)
        m = int((v - d) * 60)
        s = round(((v - d) * 60 - m) * 60 * 100)
        return ((d, 1), (m, 1), (s, 100))
    return {piexif.GPSIFD.GPSLatitudeRef: b"N" if lat >= 0 else b"S", piexif.GPSIFD.GPSLatitude: dms(lat),
            piexif.GPSIFD.GPSLongitudeRef: b"E" if lon >= 0 else b"W", piexif.GPSIFD.GPSLongitude: dms(lon)}


def scene(style: str, seed: int = 0) -> Image.Image:
    rnd = random.Random(seed)
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    sky = {"sun": 225, "diffuse": 215, "twilight": 120, "night": 18}[style]
    for y in range(H):
        t = y / H
        v = int(sky - 25 * t) if style != "night" else int(sky + 10 * t)
        d.line([(0, y), (W, y)], fill=(v, v, min(255, v + 12)))
    ground = {"sun": 150, "diffuse": 130, "twilight": 70, "night": 25}[style]
    d.rectangle([0, int(H * 0.62), W, H], fill=(ground, ground - 8, ground - 15))
    d.rectangle([60, int(H * 0.5), 200, int(H * 0.66)], fill=(110, 95, 85))  # weighbridge cabin
    d.rectangle([300, int(H * 0.56), 420, int(H * 0.64)], fill=(70, 80, 95))  # scale platform
    for _ in range(5):  # clutter that differs per photo: pallets, bins, parked vehicles
        x, y = rnd.randint(0, W - 120), rnd.randint(int(H * 0.45), H - 60)
        tone = rnd.randint(40, 200)
        d.rectangle([x, y, x + rnd.randint(30, 110), y + rnd.randint(15, 50)], fill=(tone, tone - 5, tone - 10))
    if style == "sun":  # fence posts casting sharp shadow bars
        for i in range(9):
            x = 40 + i * 62 + rnd.randint(-3, 3)
            d.rectangle([x, int(H * 0.62), x + 14, H - 20], fill=(25, 25, 28))
    if style == "night":
        d.ellipse([260, 40, 380, 120], fill=(250, 245, 200))  # floodlight
    img = img.filter(ImageFilter.GaussianBlur(0.4 if style == "sun" else 2.2))
    return img


def save(name: str, style: str, dt: str | None, offset: str | None, lat=None, lon=None, seed=0, quality=92):
    img = scene(style, seed)
    kwargs = {}
    if dt:
        exif = {"0th": {}, "Exif": {piexif.ExifIFD.DateTimeOriginal: dt.encode()}, "GPS": {}}
        if offset:
            exif["Exif"][piexif.ExifIFD.OffsetTimeOriginal] = offset.encode()
        if lat is not None:
            exif["GPS"] = _gps(lat, lon)
        kwargs["exif"] = piexif.dump(exif)
    OUT.mkdir(parents=True, exist_ok=True)
    img.save(OUT / name, "JPEG", quality=quality, **kwargs)
    return OUT / name


def main() -> None:
    hapur = (28.73, 77.78)
    made = [
        save("c101_daytime_sun.jpg", "sun", "2026:10:06 11:00:00", "+05:30", 28.60, 77.20, seed=1),
        save("c105_hard_sun_after_dusk.jpg", "sun", "2025:06:16 20:22:00", "+05:30", *hapur, seed=2),
        save("c105b_bright_twilight.jpg", "diffuse", "2025:06:16 19:48:00", "+05:30", *hapur, seed=3),
        save("night_yard.jpg", "night", "2026:10:06 22:30:00", "+05:30", 28.60, 77.20, seed=4),
        save("c108_no_exif.jpg", "diffuse", None, None, seed=5),
        save("dup_original.jpg", "diffuse", "2026:07:18 09:00:00", "+05:30", 28.65, 77.30, seed=6, quality=92),
        save("dup_reencoded.jpg", "diffuse", "2026:08:14 09:00:00", "+05:30", 28.65, 77.30, seed=6, quality=60),
    ]
    print("wrote", *[p.name for p in made])


if __name__ == "__main__":
    sys.exit(main())
