"""Run R9 against real Sentinel-2 imagery for a coordinate and period (needs internet + rasterio).

    services/claimguard/.venv/Scripts/python.exe scripts/claimguard/r9_live_demo.py 28.73 77.78 2026-08-01 2026-10-01
"""
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "services" / "claimguard"), str(ROOT / "services" / "evidence")]
from claimguard.context import RuleContext  # noqa: E402
from claimguard.model import Claim, ClaimProduct, Facility  # noqa: E402
from claimguard.rules import r9_satellite  # noqa: E402
from claimguard.sources import SourcesRegistry  # noqa: E402
from evidence.satellite import sentinel_provider  # noqa: E402

lat, lon, a, b = float(sys.argv[1]), float(sys.argv[2]), date.fromisoformat(sys.argv[3]), date.fromisoformat(sys.argv[4])
claim = Claim(claim_id="LIVE", recycler_party_id="X", product=ClaimProduct.BATTERY_LEAD_ACID,
              period_start=datetime.combine(a, datetime.min.time()), period_end=datetime.combine(b, datetime.min.time()), input_t=1, processed_t=1)
ctx = RuleContext(facility=Facility("X", 1, 1, 1, 1, lat, lon), sources=SourcesRegistry.load(), satellite=sentinel_provider)
obs = sentinel_provider(lat, lon, a, b)
for o in obs:
    print(o)
r = r9_satellite.evaluate(claim, ctx)
print(r.outcome.value, "-", r.formula_rendered)
