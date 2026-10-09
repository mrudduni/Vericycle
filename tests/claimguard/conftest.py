import sys
from pathlib import Path

CLAIMGUARD_SRC = Path(__file__).resolve().parents[2] / "services" / "claimguard"
if str(CLAIMGUARD_SRC) not in sys.path:
    sys.path.insert(0, str(CLAIMGUARD_SRC))
