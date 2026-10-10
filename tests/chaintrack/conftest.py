import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for sub in ("services/ledger", "services/capture_api", "services/extract", "services/ingest", "scripts/chaintrack"):
    p = ROOT / sub
    if p.exists() and str(p) not in sys.path:
        sys.path.insert(0, str(p))
