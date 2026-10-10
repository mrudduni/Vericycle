"""Photo evidence: SHA-256, EXIF time and GPS, a 64-bit difference hash, and a deterministic light class for R5.

Pillow only (no numpy/scipy), so it fits a small arm64 Lambda layer. The light classifier is a conservative
heuristic, never a verdict: anything ambiguous returns UNCLEAR, which R5 turns into INCONCLUSIVE.
Camera EXIF is trivially editable; R5 catches careless edits, not careful ones (SOLUTION.md section 14.4).
"""

from __future__ import annotations

import hashlib
import io
from datetime import datetime, timedelta, timezone
from typing import Any

from PIL import Image, ImageOps

IST = timezone(timedelta(hours=5, minutes=30))
LIGHT_CLASSES = ("DIRECT_SUN_HARD_SHADOWS", "BRIGHT_DIFFUSE_DAYLIGHT", "TWILIGHT", "NIGHT_ARTIFICIAL", "INDOOR", "UNCLEAR")

_EXIF_IFD, _GPS_IFD = 0x8769, 0x8825
_DATETIME_ORIGINAL, _OFFSET_TIME_ORIGINAL = 0x9003, 0x9011


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def dhash_hex(img: Image.Image) -> str:
    """64-bit difference hash as 16 hex chars; survives re-encoding and mild resizing."""
    g = ImageOps.exif_transpose(img).convert("L").resize((9, 8), Image.LANCZOS)
    px = list(g.tobytes())
    bits = 0
    for row in range(8):
        for col in range(8):
            bits = (bits << 1) | (1 if px[row * 9 + col] > px[row * 9 + col + 1] else 0)
    return f"{bits:016x}"


def _rational(v) -> float:
    return float(v[0]) / float(v[1]) if isinstance(v, tuple) else float(v)


def _gps_to_deg(vals, ref) -> float | None:
    try:
        d = _rational(vals[0]) + _rational(vals[1]) / 60 + _rational(vals[2]) / 3600
    except (TypeError, IndexError, ZeroDivisionError):
        return None
    return -d if ref in ("S", "W") else d


def read_exif(img: Image.Image) -> dict[str, Any]:
    """{DateTimeOriginal (ISO, with offset when the file has one), OffsetTimeOriginal, gps_lat, gps_lon}; {} if absent."""
    out: dict[str, Any] = {}
    exif = img.getexif()
    if not exif:
        return out
    ifd = exif.get_ifd(_EXIF_IFD)
    raw = ifd.get(_DATETIME_ORIGINAL) or exif.get(0x0132)
    if raw:
        try:
            dt = datetime.strptime(str(raw), "%Y:%m:%d %H:%M:%S")
            off = ifd.get(_OFFSET_TIME_ORIGINAL)
            if off:
                sign = -1 if str(off).startswith("-") else 1
                hh, mm = str(off).lstrip("+-").split(":")
                dt = dt.replace(tzinfo=timezone(sign * timedelta(hours=int(hh), minutes=int(mm))))
                out["OffsetTimeOriginal"] = str(off)
            out["DateTimeOriginal"] = dt.isoformat()
        except ValueError:
            pass
    gps = exif.get_ifd(_GPS_IFD)
    if gps:
        lat = _gps_to_deg(gps.get(2), gps.get(1))
        lon = _gps_to_deg(gps.get(4), gps.get(3))
        if lat is not None and lon is not None:
            out["gps_lat"], out["gps_lon"] = lat, lon
    return out


def classify_light(img: Image.Image) -> tuple[str, dict[str, float]]:
    """Deterministic light class from the sky region's brightness and the sharpness of dark/bright edges.

    Signals: mean luminance of the top third (sky), fraction of strong horizontal gradients (hard shadow edges),
    and overall contrast. Thresholds are demo-calibrated on synthetic scenes and must be recalibrated on real
    photos before anyone relies on them; the result only ever feeds R5, which flags only impossible combinations.
    """
    g = ImageOps.exif_transpose(img).convert("L")
    g.thumbnail((256, 256))
    w, h = g.size
    px = g.load()
    sky = [px[x, y] for y in range(0, max(1, h // 3)) for x in range(w)]
    sky_mean = sum(sky) / len(sky)
    allv = [px[x, y] for y in range(h) for x in range(w)]
    mean = sum(allv) / len(allv)
    strong = total = 0
    for y in range(h):
        for x in range(w - 1):
            total += 1
            if abs(px[x, y] - px[x + 1, y]) > 60:
                strong += 1
    edge = strong / total
    sig = {"sky_mean": round(sky_mean, 1), "mean": round(mean, 1), "hard_edge_fraction": round(edge, 4)}
    if sky_mean < 50 and mean < 90:
        return "NIGHT_ARTIFICIAL", sig
    if sky_mean >= 150:
        return ("DIRECT_SUN_HARD_SHADOWS" if edge >= 0.01 else "BRIGHT_DIFFUSE_DAYLIGHT"), sig
    if 90 <= sky_mean < 150 and edge < 0.01:
        return "TWILIGHT", sig
    return "UNCLEAR", sig


def analyze_photo(data: bytes) -> dict[str, Any]:
    img = Image.open(io.BytesIO(data))
    light, sig = classify_light(img)
    exif = read_exif(img)
    exif["light_class"] = light
    exif["light_signals"] = sig
    return {"sha256": sha256_hex(data), "phash": dhash_hex(img), "exif": exif}
