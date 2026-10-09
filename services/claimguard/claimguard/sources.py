"""Loads data/sources.yaml and nothing else may hold a cited constant.

Principle P3 in SOLUTION.md: "No source, no rule." Every limit a rule uses
comes from here. A rule that cannot find its source's `value` returns
INSUFFICIENT_EVIDENCE (the rule decides that, not this module) and a source
marked status: DEMO_VALUE makes the rule mark its result demo_value=True.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_SOURCES_PATH = Path(__file__).resolve().parents[3] / "data" / "sources.yaml"


@dataclass(frozen=True)
class Source:
    id: str
    title: str
    status: str  # "CITED" or "DEMO_VALUE"
    value: Any = None
    date: str | None = None
    locator: str | None = None
    url: str | None = None
    note: str | None = None

    @property
    def is_demo_value(self) -> bool:
        return self.status == "DEMO_VALUE"

    @property
    def has_value(self) -> bool:
        return self.value is not None


class SourcesRegistry:
    """In-memory lookup of every source entry, by id."""

    def __init__(self, entries: dict[str, Source]):
        self._entries = entries

    @classmethod
    def load(cls, path: Path | str | None = None) -> "SourcesRegistry":
        p = Path(path) if path else DEFAULT_SOURCES_PATH
        raw = yaml.safe_load(p.read_text(encoding="utf-8")) or []
        entries: dict[str, Source] = {}
        for item in raw:
            source = Source(
                id=item["id"],
                title=item.get("title", item["id"]),
                status=item.get("status", "DEMO_VALUE"),
                value=item.get("value"),
                date=item.get("date"),
                locator=item.get("locator"),
                url=item.get("url"),
                note=item.get("note"),
            )
            if source.id in entries:
                raise ValueError(f"duplicate source id in {p}: {source.id}")
            entries[source.id] = source
        return cls(entries)

    def get(self, source_id: str) -> Source | None:
        return self._entries.get(source_id)

    def require_value(self, source_id: str) -> tuple[Any, bool]:
        """Returns (value, is_demo_value) or raises KeyError if no entry at all.

        A rule calls this and catches KeyError or a None value the same way
        it would any other missing input: outcome INSUFFICIENT_EVIDENCE.
        """
        source = self._entries.get(source_id)
        if source is None:
            raise KeyError(source_id)
        return source.value, source.is_demo_value

    def all_ids(self) -> frozenset[str]:
        return frozenset(self._entries.keys())
