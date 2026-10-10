"""Live provider for R9: Sentinel-2 L2A over the Earth Search STAC API (AWS Open Data), windowed reads from the COGs.

Reads three pixels around the plant and a ring median from band B12 (SWIR 2.2 um, 20 m) only for scenes whose
scene-level cloud cover is under 30%, and drops any scene whose scene-classification (SCL) pixel at the site is cloud, shadow
or snow. Network and rasterio are needed; the rule itself (claimguard.rules.r9_satellite) is pure and tested offline.
"""

from __future__ import annotations

import json
import urllib.request
from datetime import date
from typing import Any

STAC = "https://earth-search.aws.element84.com/v1/search"
BAD_SCL = {0, 1, 3, 8, 9, 10, 11}  # no data, saturated, cloud shadow, cloud medium/high, thin cirrus, snow


def search_scenes(lat: float, lon: float, start: date, end: date, max_cloud: float = 30.0, limit: int = 12) -> list[dict]:
    body = {"collections": ["sentinel-2-l2a"], "intersects": {"type": "Point", "coordinates": [lon, lat]},
            "datetime": f"{start}T00:00:00Z/{end}T23:59:59Z", "limit": limit,
            "query": {"eo:cloud_cover": {"lt": max_cloud}}, "sortby": [{"field": "properties.datetime", "direction": "desc"}]}
    req = urllib.request.Request(STAC, data=json.dumps(body).encode(), headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["features"]


def _read(href: str, lat: float, lon: float, half: int) -> Any:
    import numpy as np  # noqa: PLC0415
    import rasterio  # noqa: PLC0415
    from rasterio.warp import transform  # noqa: PLC0415
    from rasterio.windows import Window  # noqa: PLC0415

    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", AWS_NO_SIGN_REQUEST="YES"):
        with rasterio.open(href) as ds:
            xs, ys = transform("EPSG:4326", ds.crs, [lon], [lat])
            row, col = ds.index(xs[0], ys[0])
            if not (half <= row < ds.height - half and half <= col < ds.width - half):
                return None
            return ds.read(1, window=Window(col - half, row - half, 2 * half + 1, 2 * half + 1)).astype("float64"), np


def observation(feature: dict, lat: float, lon: float) -> dict | None:
    a = feature["assets"]
    scl = _read(a["scl"]["href"], lat, lon, 0)
    if scl is None or int(scl[0][0][0]) in BAD_SCL:
        return None
    b12 = _read(a["swir22"]["href"], lat, lon, 20)  # 41x41 px at 20 m = ~820 m square
    if b12 is None:
        return None
    arr, np = b12
    c = 20
    site = float(arr[c - 1:c + 2, c - 1:c + 2].mean())
    ring_mask = np.ones_like(arr, dtype=bool)
    ring_mask[c - 3:c + 4, c - 3:c + 4] = False  # exclude the site and its immediate neighbours
    ring = float(np.median(arr[ring_mask]))
    return {"date": feature["properties"]["datetime"][:10], "cloud": feature["properties"].get("eo:cloud_cover"),
            "site_b12": site, "ring_b12": ring, "scene": feature["id"]}


def sentinel_provider(lat: float, lon: float, start: date, end: date) -> list[dict]:
    out = []
    for f in search_scenes(lat, lon, start, end):
        try:
            o = observation(f, lat, lon)
        except Exception:  # one unreadable scene must not fail the claim run
            o = None
        if o:
            out.append(o)
    return out
