"""NOAA solar position algorithm: deterministic, no AI. Used only by R5.

Implements the standard NOAA solar calculator formulas (equivalent to
Meeus, "Astronomical Algorithms"), returning the sun's geometric elevation
angle above the horizon for a given timezone-aware datetime and location.
`solar_elevation_deg` returns the plain geometric angle with no
atmospheric-refraction correction: R5's decision table (SOLUTION.md
section 6) uses geometric thresholds (-1, -12, +10 degrees), which are
this project's own simplified boundaries, not the refraction-corrected
sunrise/sunset convention.

Published sunset times (what "sunset ~19:19 IST" means on a calendar) are
conventionally the moment the sun's upper limb crosses the horizon, i.e.
geometric elevation of its center reaches about -0.8333 degrees (34
arcminutes of refraction plus a ~16 arcminute solar radius), not 0 degrees.
`STANDARD_SUNSET_ELEVATION_DEG` below is that constant, used only to find
or check against published sunset times in tests; it plays no part in R5's
own decision logic.

SOLUTION.md section 13.1 requires this algorithm to reproduce the sunset
and civil-dusk times for Hapur (28.73N, 77.78E) on 16 June 2025 within 2
minutes of NOAA's published values (sunset ~19:19 IST, civil dusk ~19:46
IST). Section 21's elevation figures at fixed clock times
(sunset + 29 min, sunset + 60 min) are approximate, hand-rounded numbers
from that document, not an exact target this module must hit to the tenth
of a degree; tests/claimguard/test_solar.py checks them to within about
1 degree, which is enough to keep the "about -7, about -12.6" language
honest.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

STANDARD_SUNSET_ELEVATION_DEG = -0.8333


def _julian_day(dt_utc: datetime) -> float:
    """Julian Day for a timezone-aware UTC datetime."""
    y, m = dt_utc.year, dt_utc.month
    d = (
        dt_utc.day
        + dt_utc.hour / 24
        + dt_utc.minute / 1440
        + dt_utc.second / 86400
    )
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + a // 4
    return math.floor(365.25 * (y + 4716)) + math.floor(30.6001 * (m + 1)) + d + b - 1524.5


def solar_elevation_deg(dt_aware: datetime, lat_deg: float, lon_deg: float) -> float:
    """Geometric solar elevation in degrees. Positive above the horizon.

    `dt_aware` must carry a tzinfo (any offset; converted to UTC here).
    `lon_deg` is signed, east positive (matching EXIF GPS convention and
    data/facilities.json), matching India's positive longitudes directly.
    """
    if dt_aware.tzinfo is None:
        raise ValueError("solar_elevation_deg requires a timezone-aware datetime")

    dt_utc = dt_aware.astimezone(timezone.utc)
    jd = _julian_day(dt_utc)
    t = (jd - 2451545.0) / 36525.0  # Julian century

    # Geometric mean longitude and anomaly of the sun (degrees)
    l0 = (280.46646 + t * (36000.76983 + t * 0.0003032)) % 360
    m = 357.52911 + t * (35999.05029 - 0.0001537 * t)
    m_rad = math.radians(m)

    # Eccentricity of earth's orbit
    ecc = 0.016708634 - t * (0.000042037 + 0.0000001267 * t)

    # Sun's equation of center
    c = (
        math.sin(m_rad) * (1.914602 - t * (0.004817 + 0.000014 * t))
        + math.sin(2 * m_rad) * (0.019993 - 0.000101 * t)
        + math.sin(3 * m_rad) * 0.000289
    )

    true_long = l0 + c  # sun's true ecliptic longitude (degrees)

    # Apparent longitude, correcting for nutation and aberration
    omega = 125.04 - 1934.136 * t
    apparent_long = true_long - 0.00569 - 0.00478 * math.sin(math.radians(omega))

    # Mean and corrected obliquity of the ecliptic
    seconds = 21.448 - t * (46.815 + t * (0.00059 - t * 0.001813))
    obliquity0 = 23 + (26 + seconds / 60) / 60
    obliquity = obliquity0 + 0.00256 * math.cos(math.radians(omega))

    # Sun's declination
    decl_rad = math.asin(
        math.sin(math.radians(obliquity)) * math.sin(math.radians(apparent_long))
    )

    # Equation of time, in minutes
    y = math.tan(math.radians(obliquity) / 2) ** 2
    eq_time = 4 * math.degrees(
        y * math.sin(2 * math.radians(l0))
        - 2 * ecc * math.sin(m_rad)
        + 4 * ecc * y * math.sin(m_rad) * math.cos(2 * math.radians(l0))
        - 0.5 * y * y * math.sin(4 * math.radians(l0))
        - 1.25 * ecc * ecc * math.sin(2 * m_rad)
    )

    minutes_of_day = dt_utc.hour * 60 + dt_utc.minute + dt_utc.second / 60
    true_solar_time = (minutes_of_day + eq_time + 4 * lon_deg) % 1440

    hour_angle = true_solar_time / 4 - 180
    if true_solar_time / 4 < 0:
        hour_angle = true_solar_time / 4 + 180

    lat_rad = math.radians(lat_deg)
    ha_rad = math.radians(hour_angle)

    cos_zenith = math.sin(lat_rad) * math.sin(decl_rad) + math.cos(lat_rad) * math.cos(
        decl_rad
    ) * math.cos(ha_rad)
    cos_zenith = max(-1.0, min(1.0, cos_zenith))
    zenith_deg = math.degrees(math.acos(cos_zenith))

    return 90.0 - zenith_deg


def find_elevation_crossing(
    date_local_midnight: datetime,
    lat_deg: float,
    lon_deg: float,
    target_elevation_deg: float,
    *,
    rising: bool = False,
    search_hours: tuple[float, float] = (0.0, 24.0),
) -> datetime | None:
    """Binary-searches the local time the sun crosses `target_elevation_deg`.

    `date_local_midnight` must be timezone-aware, at local midnight. Used in
    tests to compare against published sunset/dusk times, and by the
    clock-skew helper. Returns None if no crossing is found in the window
    (sun does not reach that elevation that day at that latitude).
    """
    start = date_local_midnight + timedelta(hours=search_hours[0])
    end = date_local_midnight + timedelta(hours=search_hours[1])

    def f(dt: datetime) -> float:
        return solar_elevation_deg(dt, lat_deg, lon_deg) - target_elevation_deg

    # Scan in 10-minute steps to find a bracket, then bisect within it.
    step = timedelta(minutes=10)
    prev_t, prev_v = start, f(start)
    t = start + step
    while t <= end:
        v = f(t)
        crosses_down = prev_v > 0 and v <= 0
        crosses_up = prev_v < 0 and v >= 0
        if (not rising and crosses_down) or (rising and crosses_up):
            lo, hi = prev_t, t
            lo_v = prev_v
            for _ in range(40):
                mid = lo + (hi - lo) / 2
                mid_v = f(mid)
                if (mid_v > 0) == (lo_v > 0):
                    lo, lo_v = mid, mid_v
                else:
                    hi = mid
            return lo + (hi - lo) / 2
        prev_t, prev_v = t, v
        t += step
    return None


@dataclass(frozen=True)
class ClockSkewResult:
    device_offset_hours: int | None
    confidence: str  # "LIKELY" | "NONE"


def detect_clock_skew(
    reported_minus_expected_hours: list[float], tolerance_minutes: float = 5.0
) -> ClockSkewResult:
    """CONTRACT/SOLUTION §6 step 4: one device, consistently off by whole hours.

    `reported_minus_expected_hours` is, for each photo from one device, the
    EXIF time minus an independently expected time (for example server
    receipt time minus typical upload delay), in hours. If every value is
    close to the same whole number of hours, report that instead of flagging
    each photo individually.
    """
    if not reported_minus_expected_hours:
        return ClockSkewResult(None, "NONE")
    rounded = [round(h) for h in reported_minus_expected_hours]
    if len(set(rounded)) != 1 or rounded[0] == 0:
        return ClockSkewResult(None, "NONE")
    candidate = rounded[0]
    if all(abs(h - candidate) * 60 <= tolerance_minutes for h in reported_minus_expected_hours):
        return ClockSkewResult(candidate, "LIKELY")
    return ClockSkewResult(None, "NONE")
