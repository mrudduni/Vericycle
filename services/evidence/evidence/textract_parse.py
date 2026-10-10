"""Turns an Amazon Textract AnalyzeExpense response into the fields R7 reads (CONTRACT §6 `extracted`).

Every value keeps its confidence and source text so the dashboard can show it beside the document. OCR text is data:
it is only ever copied into fields, never interpreted as an instruction (SOLUTION.md section 8).
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

GSTIN_RE = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][A-Z\d]Z[A-Z\d]\b")
NUM_RE = re.compile(r"[-+]?\d[\d,]*\.?\d*")
DATE_FORMATS = ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d.%m.%Y", "%d %b %Y", "%d-%b-%Y")


def _num(s: str) -> float | None:
    m = NUM_RE.search(s or "")
    try:
        return float(m.group(0).replace(",", "")) if m else None
    except ValueError:
        return None


def _date(s: str) -> str | None:
    from datetime import datetime  # noqa: PLC0415

    for f in DATE_FORMATS:
        try:
            return datetime.strptime(s.strip(), f).date().isoformat()
        except ValueError:
            continue
    return None


def parse_expense(resp: dict) -> dict[str, Any]:
    """Returns {invoice_number, date, gstin, total_weight_t, total_weight_kg, fields:{name:{value,confidence,text}}}."""
    out: dict[str, Any] = {"fields": {}}
    docs = resp.get("ExpenseDocuments") or []
    if not docs:
        return out
    doc = docs[0]
    for f in doc.get("SummaryFields", []):
        ftype = (f.get("Type") or {}).get("Text", "")
        label = ((f.get("LabelDetection") or {}).get("Text") or "").lower()
        value = (f.get("ValueDetection") or {}).get("Text", "")
        conf = (f.get("ValueDetection") or {}).get("Confidence")
        rec = {"value": value, "confidence": conf, "text": value}
        if ftype == "INVOICE_RECEIPT_ID" and "invoice_number" not in out:
            out["invoice_number"], out["fields"]["invoice_number"] = value, rec
        elif ftype == "INVOICE_RECEIPT_DATE" and "date" not in out:
            d = _date(value)
            if d:
                out["date"], out["fields"]["date"] = d, rec
        elif ftype in ("VENDOR_GST_NUMBER", "TAX_PAYER_ID") or "gstin" in label:
            m = GSTIN_RE.search(value.upper())
            if m and "gstin" not in out:
                out["gstin"], out["fields"]["gstin"] = m.group(0), rec
    kg = 0.0
    for group in doc.get("LineItemGroups", []):
        for item in group.get("LineItems", []):
            for f in item.get("LineItemExpenseFields", []):
                if (f.get("Type") or {}).get("Text") == "QUANTITY":
                    txt = (f.get("ValueDetection") or {}).get("Text", "")
                    n = _num(txt)
                    if n is not None:
                        low = txt.lower()
                        kg += n * 1000 if re.search(r"\b(t|mt|tonne|tonnes|ton)\b", low) else n
    if kg:
        out["total_weight_kg"], out["total_weight_t"] = kg, kg / 1000.0
    if "gstin" not in out:
        blob = " ".join((f.get("ValueDetection") or {}).get("Text", "") for f in doc.get("SummaryFields", []))
        m = GSTIN_RE.search(blob.upper())
        if m:
            out["gstin"] = m.group(0)
    return out
