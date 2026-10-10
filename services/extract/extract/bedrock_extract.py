"""Bedrock Converse with a forced tool whose input schema is the extraction schema.

The model never has the last word: every numeric field is read back to the collector, and
fields where the model and the deterministic number reader disagree are marked uncertain.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import hindi_numbers

HERE = Path(__file__).resolve().parent
SCHEMA = json.loads((HERE / "schema.json").read_text())
SYSTEM = (HERE / "prompts" / "system.txt").read_text()
TOOL = "record_handover"
MAX_NOTE_CHARS = 2000

ENUMS = {k: set(v["enum"]) for k, v in SCHEMA["properties"].items() if "enum" in v}


def wrap_note(text: str) -> str:
    """Quote the transcript as data. Delimiters inside the note are neutralised."""
    clean = text.replace("<note>", "‹note›").replace("</note>", "‹/note›")[:MAX_NOTE_CHARS]
    return f"Extract the handover from this note.\n<note>\n{clean}\n</note>"


def tool_config() -> dict:
    return {
        "tools": [{"toolSpec": {"name": TOOL, "description": "Record one handover from the dealer's note.",
                                "inputSchema": {"json": SCHEMA}}}],
        "toolChoice": {"tool": {"name": TOOL}},
    }


def coerce(raw: dict) -> dict:
    """Validate the tool input against the schema; anything off becomes null/UNKNOWN and uncertain."""
    out: dict[str, Any] = {}
    uncertain = set(x for x in raw.get("uncertain_fields") or [] if isinstance(x, str))
    def enum(name, default):
        v = raw.get(name)
        if v in ENUMS[name]:
            return v
        if v is not None:
            uncertain.add(name)
        return default
    out["material"] = enum("material", "UNKNOWN")
    out["weight_basis"] = enum("weight_basis", "STATED")
    out["source_category"] = enum("source_category", "UNKNOWN")
    out["language"] = enum("language", "mixed")
    gas = raw.get("gas_type")
    out["gas_type"] = gas if gas in ENUMS["gas_type"] else None
    for name, kind in (("count", int), ("weight_kg", float), ("charge_kg", float)):
        v = raw.get(name)
        if isinstance(v, bool) or v is None:
            out[name] = None
            continue
        try:
            num = float(v)
        except (TypeError, ValueError):
            out[name] = None
            uncertain.add(name)
            continue
        if num <= 0 or (kind is int and num != int(num)):
            out[name] = None
            uncertain.add(name)
        else:
            out[name] = int(num) if kind is int else num
    if out["material"] != "AC_REFRIGERANT":
        out["gas_type"] = out["charge_kg"] = None
    out["uncertain_fields"] = sorted(uncertain & set(SCHEMA["properties"]))
    return out


def cross_check(text: str, result: dict) -> dict:
    """Mark count/weight uncertain when the deterministic reader disagrees with the model."""
    det = hindi_numbers.parse(text)
    unc = set(result["uncertain_fields"])
    for f in ("count", "weight_kg"):
        if det[f] is not None and result[f] is not None and abs(float(det[f]) - float(result[f])) > 1e-6:
            unc.add(f)
        if result[f] is None and det[f] is not None:
            result[f] = det[f] if f == "weight_kg" else int(det[f])
            unc.add(f)
    result["uncertain_fields"] = sorted(unc)
    return result


def extract_offline(text: str) -> dict:
    """No model: keyword material + deterministic numbers. Everything is marked uncertain."""
    t = text.lower()
    material = ("AC_REFRIGERANT" if any(w in t for w in (" ac ", "एसी", "air condition", "split ac", "window ac")) or t.startswith("ac ")
                else "EWASTE_PHONE" if any(w in t for w in ("phone", "mobile", "फ़ोन", "फोन", "मोबाइल", "handset"))
                else "BATTERY_LEAD_ACID" if any(w in t for w in ("battery", "baitri", "betri", "bettery", "बैटरी"))
                else "UNKNOWN")
    src = ("DRIVER" if any(w in t for w in ("driver", "rickshaw wal", "ड्राइवर")) else
           "TECHNICIAN" if any(w in t for w in ("mistri", "mechanic", "technician")) else
           "RETAIL_EXCHANGE" if "exchange" in t else
           "HOUSEHOLD" if any(w in t for w in ("ghar", "household", "घर")) else "UNKNOWN")
    nums = hindi_numbers.parse(text)
    gas = next((g for g in ("R-410A", "R-32", "R-22") if g.lower().replace("-", "") in t.replace("-", "").replace(" ", "")), None)
    return coerce({"material": material, "count": nums["count"], "weight_kg": nums["weight_kg"],
                   "weight_basis": "WEIGHED" if any(w in t for w in ("taula", "tola", "weigh", "kaanta", "kanta")) else "STATED",
                   "source_category": src, "gas_type": gas if material == "AC_REFRIGERANT" else None, "charge_kg": None,
                   "language": "mixed", "uncertain_fields": ["material", "count", "weight_kg", "source_category"]})


def extract(text: str, model_id: str, client=None) -> dict:
    """Run Bedrock Converse with the forced tool. ``client`` is a bedrock-runtime client."""
    if client is None:
        import boto3  # noqa: PLC0415
        client = boto3.client("bedrock-runtime", region_name="ap-south-1")
    resp = client.converse(
        modelId=model_id,
        system=[{"text": SYSTEM}],
        messages=[{"role": "user", "content": [{"text": wrap_note(text)}]}],
        toolConfig=tool_config(),
        inferenceConfig={"maxTokens": 400, "temperature": 0},
    )
    for block in resp["output"]["message"]["content"]:
        if "toolUse" in block and block["toolUse"]["name"] == TOOL:
            return cross_check(text, coerce(block["toolUse"]["input"]))
    raise RuntimeError("model did not call the extraction tool")
