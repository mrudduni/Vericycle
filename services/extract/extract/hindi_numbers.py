"""Deterministic reader for spoken numbers (Hindi, Hinglish, English, digits).

Used as a cross-check on the model: if both disagree on count, the field is marked uncertain.
Also an offline fallback when Bedrock is unavailable.
"""
from __future__ import annotations

import re

UNITS = {
    "ek": 1, "one": 1, "do": 2, "two": 2, "teen": 3, "three": 3, "chaar": 4, "char": 4, "chār": 4, "four": 4,
    "paanch": 5, "panch": 5, "five": 5, "chhe": 6, "chhah": 6, "che": 6, "chheh": 6, "six": 6, "saat": 7, "seven": 7,
    "aath": 8, "aat": 8, "eight": 8, "nau": 9, "nine": 9, "das": 10, "dus": 10, "ten": 10, "gyarah": 11, "eleven": 11,
    "barah": 12, "baarah": 12, "twelve": 12, "terah": 13, "chaudah": 14, "pandrah": 15,
    "fifteen": 15, "solah": 16, "satrah": 17, "atharah": 18, "unnees": 19, "bees": 20, "twenty": 20, "pachchees": 25,
    "pachees": 25, "tees": 30, "thirty": 30, "chaalees": 40, "chalees": 40, "chalis": 40, "forty": 40,
    "pachaas": 50, "pachas": 50, "fifty": 50, "saath": 60, "sixty": 60, "sattar": 70, "seventy": 70,
    "assi": 80, "assee": 80, "eighty": 80, "nabbe": 90, "ninety": 90,
    # Devanagari
    "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पांच": 5, "पाँच": 5, "छह": 6, "छः": 6, "सात": 7, "आठ": 8, "नौ": 9,
    "दस": 10, "बारह": 12, "पंद्रह": 15, "बीस": 20, "पच्चीस": 25, "तीस": 30, "चालीस": 40, "पचास": 50, "साठ": 60,
    "सत्तर": 70, "अस्सी": 80, "नब्बे": 90,
}
MULT = {"darjan": 12, "dozen": 12, "sau": 100, "hundred": 100, "सौ": 100, "hazaar": 1000, "hazar": 1000, "thousand": 1000, "हज़ार": 1000, "हजार": 1000}
FRACT = {"dedh": 1.5, "डेढ़": 1.5, "dhai": 2.5, "dhaai": 2.5, "ढाई": 2.5, "sava": 1.25}
WEIGHT_WORDS = {"kilo", "kg", "kgs", "kilogram", "kilograms", "किलो"}
QUINTAL = {"quintal", "kuintal", "क्विंटल"}
ITEM_WORDS = {"battery", "batteries", "baitri", "bettery", "betri", "बैटरी", "phone", "phones", "mobile", "mobiles",
              "फ़ोन", "फोन", "मोबाइल", "ac", "एसी", "handset", "handsets", "piece", "pieces", "nag", "पीस"}

_TOKEN = re.compile(r"\d+(?:\.\d+)?|[^\s\d.,;:!?।()\[\]\"'/-]+", re.UNICODE)
ADJECTIVES = {"e", "rickshaw", "purane", "purani", "purana", "old", "inverter", "car", "bike", "split", "window",
              "mobile", "dead", "kharab", "used", "lead", "acid", "पुरानी", "पुराने", "ई", "रिक्शा"}


def tokens(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN.findall(text)]


def _number_at(toks: list[str], i: int) -> tuple[float | None, int]:
    """Parse a number starting at toks[i]; return (value, tokens consumed)."""
    t = toks[i]
    if re.fullmatch(r"\d+(?:\.\d+)?", t):
        v, n = float(t), 1
    elif t in FRACT and i + 1 < len(toks) and toks[i + 1] in MULT:
        return FRACT[t] * MULT[toks[i + 1]], 2
    elif t in UNITS:
        v, n = float(UNITS[t]), 1
    elif t in MULT:
        v, n = float(MULT[t]), 1
    else:
        return None, 0
    if i + n < len(toks) and toks[i + n] in MULT:
        v *= MULT[toks[i + n]]
        n += 1
        # "ek sau assi" = 180, "dedh sau" handled above
        if i + n < len(toks) and toks[i + n] in UNITS and UNITS[toks[i + n]] < v:
            v += UNITS[toks[i + n]]
            n += 1
    return v, n


def numbers_with_context(text: str) -> list[tuple[float, str | None]]:
    toks = tokens(text)
    out, i = [], 0
    while i < len(toks):
        v, n = _number_at(toks, i)
        if v is None:
            i += 1
            continue
        nxt = toks[i + n:i + n + 3]
        out.append((v, " ".join(nxt)))
        i += n
    return out


def parse(text: str) -> dict:
    """Best-effort count and weight. Returns {'count': int|None, 'weight_kg': float|None}."""
    count = weight = None
    for v, ctx in numbers_with_context(text):
        words = (ctx or "").split()
        head = words[0] if words else ""
        if head in WEIGHT_WORDS and weight is None:
            weight = v
        elif head in QUINTAL and weight is None:
            weight = v * 100
        elif count is None and _names_items(words):
            count = int(v) if v == int(v) else None
    return {"count": count, "weight_kg": weight}


def _names_items(words: list[str]) -> bool:
    """The number is directly followed by an item word, allowing up to two adjectives in between."""
    for w in words[:3]:
        if w in ITEM_WORDS:
            return True
        if w not in ADJECTIVES:
            return False
    return False
