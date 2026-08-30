"""
Field-level validation for the Legal Metrology Rule Engine.

Responsibilities:
- Detect missing / empty OCR values
- Check OCR confidence against the UNREADABLE threshold
- Return one of three outcomes per field: "PASS", "FAIL", "UNREADABLE"

Design note:
Low-confidence OCR must NEVER be silently treated as a legal violation.
If we are not confident about what the OCR actually read, the correct
result is UNREADABLE, not FAIL. This protects against false compliance
accusations caused by poor image quality.
"""

from __future__ import annotations

from typing import Optional
from models import OCRField

# Below this confidence, we cannot trust the OCR reading enough to judge it.
CONFIDENCE_THRESHOLD = 0.60

PASS = "PASS"
FAIL = "FAIL"
UNREADABLE = "UNREADABLE"


def validate_presence_field(field_name: str, ocr_field: Optional[OCRField]) -> str:
    """
    Validate a single field for a "presence" type rule.

    Rules:
    1. If the field was not extracted by OCR at all -> FAIL
       (OCR ran and found nothing for this field; not a confidence issue.)
    2. If the field exists but confidence is below the threshold -> UNREADABLE
       (We can't trust the value enough to judge it either way.)
    3. If the field exists, confidence is sufficient, but the value is
       empty/blank -> FAIL
    4. Otherwise -> PASS
    """
    if ocr_field is None:
        return FAIL

    if ocr_field.confidence < CONFIDENCE_THRESHOLD:
        return UNREADABLE

    value = (ocr_field.value or "").strip()
    if value == "":
        return FAIL

    return PASS