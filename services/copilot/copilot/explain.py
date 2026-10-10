"""Deterministic, cited explanations of a claim run. No model involved, so they cannot contradict the rule engine.

Every sentence carries `cites`: rule ids ("R1") and source ids. The copilot's generated answers are validated against
the same id sets (agent.validate_answer); this module is also the fallback when the model is unavailable or refuses.
"""

from __future__ import annotations

from typing import Any

OUTCOME_WORDS = {
    "PASS": "is consistent with the available data",
    "FLAG": "is inconsistent with the data",
    "INSUFFICIENT_EVIDENCE": "has not enough evidence to decide",
    "INCONCLUSIVE": "cannot be decided from the data present",
}
DISCLAIMER = "A claim that passes is consistent with the available data. It is not certified as genuine."


def explain_run(claim: dict, run: dict | None, sources: dict[str, dict]) -> list[dict[str, Any]]:
    cid = claim["claim_id"]
    if not run:
        return [{"text": f"ClaimGuard has not been run on {cid} yet.", "cites": []}]
    out: list[dict[str, Any]] = []
    for r in run["rule_results"]:
        rid = r["rule_id"]
        sev = f" ({r['severity'].lower()})" if r["outcome"] == "FLAG" and r["severity"] != "NONE" else ""
        text = f"{rid} {OUTCOME_WORDS[r['outcome']]}{sev}: {r['formula_rendered']}"
        if r.get("demo_value"):
            text += " This uses a DEMO VALUE that is not yet backed by a cited document."
        if r.get("next_action") and r["outcome"] != "PASS":
            text += f" What would resolve this: {r['next_action']}"
        out.append({"text": text, "cites": [rid, *[f"S:{s}" for s in r["source_ids"]]]})
    s = run["scores"]
    cov = f"{s['traceability_coverage']:.0%}"
    out.append({"text": f"Traceability coverage is {cov} ({s['covered_kg']:g} kg of {s['claimed_kg']:g} kg claimed is linked to "
                        f"recorded handovers). Coverage is a metric, not a verdict.", "cites": ["R4"]})
    eq = s["evidence_quality"]
    out.append({"text": f"Handover records: {eq['handler_confirmed']} confirmed by the seller on their own phone, "
                        f"{eq['same_device_confirmed']} confirmed on the buyer's phone (not independent), "
                        f"{eq['buyer_reported']} reported by the buyer only.", "cites": ["R4"]})
    out.append({"text": DISCLAIMER, "cites": []})
    return out


def known_cites(run: dict | None, sources: dict[str, dict]) -> set[str]:
    ids = {r["rule_id"] for r in (run["rule_results"] if run else [])}
    return ids | {f"S:{s}" for s in sources}
