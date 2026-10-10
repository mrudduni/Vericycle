"""Event validation driven by materials.yaml (SHAURYA.md 3.5)."""
from __future__ import annotations

import functools
import math
from pathlib import Path
from typing import Any, Mapping

import yaml

from .errors import unprocessable

CONFIG_PATH = Path(__file__).resolve().parent.parent / "materials.yaml"
ROLES = {"HANDLER", "COLLECTOR", "AGGREGATOR", "RECYCLER", "AUDITOR", "PRODUCER"}
BASES = {"STATED", "WEIGHED", "OCR", "COMPUTED"}
CHANNELS = {"OWN_DEVICE_WHATSAPP", "OWN_DEVICE_SMS", "OWN_DEVICE_LINK", "SAME_DEVICE", "NONE"}


@functools.lru_cache(maxsize=1)
def config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def materials() -> dict:
    return config()["materials"]


def material(name: str) -> dict:
    m = materials().get(name)
    if not m:
        raise unprocessable("UNKNOWN_MATERIAL", f"Unknown material {name!r}.")
    return m


def field_spec(name: str) -> dict:
    return config()["fields"][name]


def expected_fields(event_type: str, material_name: str) -> tuple[list[str], list[str]]:
    if event_type == "HANDOVER":
        h = material(material_name)["handover"]
        return h["required"], h.get("optional", [])
    t = config()["event_types"].get(event_type)
    if t is None:
        raise unprocessable("UNKNOWN_EVENT_TYPE", f"Unknown event type {event_type!r}.")
    return t["required"], t.get("optional", [])


def check_value(name: str, value: Any) -> Any:
    spec = field_spec(name)
    t = spec["type"]
    def fail(msg):
        raise unprocessable("INVALID_FIELD", f"{name}: {msg}")
    if t == "int":
        if isinstance(value, bool) or not isinstance(value, int):
            if isinstance(value, float) and value.is_integer():
                value = int(value)
            else:
                fail("must be a whole number")
    if t in ("int", "number"):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            fail("must be a number")
        if not (spec.get("min", -math.inf) <= value <= spec.get("max", math.inf)):
            fail(f"must be between {spec.get('min')} and {spec.get('max')}")
    elif t == "enum":
        if value not in spec["values"]:
            fail(f"must be one of {', '.join(spec['values'])}")
    elif t == "string":
        if not isinstance(value, str) or not value.strip() or len(value) > spec.get("max_len", 200):
            fail("must be a short text")
    elif t == "map_number":
        if not isinstance(value, dict) or not value:
            fail("must be a non-empty map")
        for k, v in value.items():
            if isinstance(v, bool) or not isinstance(v, (int, float)) or v <= 0:
                fail(f"weight for {k} must be a positive number")
    return value


def field_value(name: str, value: Any, role: str, basis: str = "STATED") -> dict:
    """A FieldValue (CONTRACT §5) as asserted by ``role``; never confirmed at creation."""
    if basis not in BASES:
        raise unprocessable("INVALID_BASIS", f"basis must be one of {sorted(BASES)}")
    return {
        "value": check_value(name, value),
        "unit": field_spec(name).get("unit"),
        "asserted_by_role": role,
        "confirmed_by_roles": [],
        "confirmation_channel": "NONE",
        "basis": basis,
    }


def check_fields(event_type: str, material_name: str, fields: Mapping[str, Any]) -> None:
    required, optional = expected_fields(event_type, material_name)
    missing = [f for f in required if f not in fields]
    extra = [f for f in fields if f not in required and f not in optional]
    if missing:
        raise unprocessable("MISSING_FIELD", f"{event_type} needs: {', '.join(missing)}.")
    if extra:
        raise unprocessable("UNEXPECTED_FIELD", f"{event_type} does not take: {', '.join(extra)}.")
    weighed = config()["event_types"].get(event_type, {}).get("weighed", [])
    if event_type == "INTAKE":
        for f in weighed:
            if fields[f].get("basis") not in ("WEIGHED", "OCR"):
                raise unprocessable("INVALID_BASIS", "INTAKE weight must be WEIGHED or OCR.")
