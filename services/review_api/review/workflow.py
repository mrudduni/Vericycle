"""Step Functions task handlers for the ClaimGuard workflow (infra/claimguard: state machine `oae-<stage>-claimguard`).

    Start -> Parallel[ physical | custody | photos | documents ] -> Finalize (scores + store run)

Each branch is the same Lambda with a different `family`; any branch that fails is retried, and the visual execution graph
is the demo artifact. The rule engine itself stays pure (claimguard.engine), these are thin wrappers.
"""

from __future__ import annotations

from typing import Any

from .handler import build_service

_SVC = None


def _svc():
    global _SVC
    _SVC = _SVC or build_service()
    return _SVC


def rules_handler(event: dict, context: Any = None, service=None) -> list[dict]:
    return (service or _svc()).run_rule_family(event["claim_id"], event["family"])


def finalize_handler(event: dict, context: Any = None, service=None) -> dict:
    run = (service or _svc()).finalize_run(event["claim_id"], event["results"])
    return {"claim_id": event["claim_id"], "run_id": run["run_id"],
            "flags": sum(1 for r in run["rule_results"] if r["outcome"] == "FLAG")}
