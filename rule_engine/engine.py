"""
Rule Engine — main orchestrator.

Pipeline:
    OCR JSON -> validate each field -> classify PASS/FAIL/UNREADABLE
             -> build violations / passed_rules / unreadable_fields
             -> compute score
             -> return ComplianceResult

Design decision (documented so it can be explained to judges):
    A field that comes back UNREADABLE (OCR confidence below threshold) is
    EXCLUDED from the scoring denominator and does NOT generate a violation.
    We only score rules we could actually and confidently check. This avoids
    penalizing a manufacturer for a blurry photo, which would be legally
    unfair. unreadable_fields is always reported separately so the
    inspector/user knows a field needs to be re-scanned.

Status logic:
    NON_COMPLIANT   -> one or more verified rule violations (a confidently
                       read field failed a check). Takes priority over
                       unreadable fields.
    REVIEW_REQUIRED -> zero violations, but one or more required fields were
                       UNREADABLE (OCR confidence below threshold). We cannot
                       certify compliance on data we couldn't confidently
                       read, so this is neither a PASS nor a FAIL — it needs
                       a re-scan or human review. unreadable_fields lists
                       exactly which fields need attention.
    COMPLIANT       -> zero violations and zero unreadable fields; every
                       applicable required check passed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Union

from models import OCRField, OCRInput, ComplianceResult, Violation
from validator import validate_presence_field, PASS, FAIL, UNREADABLE
from scorer import calculate_score

RULES_PATH = Path(__file__).parent / "rules.json"


def load_rules(rules_path: Path = RULES_PATH) -> List[Dict[str, Any]]:
    """Load rule definitions from rules.json. Returns [] if file is missing/invalid."""
    try:
        with open(rules_path, "r", encoding="utf-8") as f:
            rules = json.load(f)
        if not isinstance(rules, list):
            return []
        return rules
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _coerce_ocr_input(ocr_data: Union[OCRInput, Dict[str, Any], None]) -> OCRInput:
    """
    Safely turn whatever the caller passed into an OCRInput.

    Handles:
    - Already an OCRInput instance
    - A raw dict matching the {"fields": {...}} contract
    - None / malformed input -> empty OCRInput (fail-safe, never crashes)
    """
    if isinstance(ocr_data, OCRInput):
        return ocr_data

    if isinstance(ocr_data, dict):
        try:
            return OCRInput(**ocr_data)
        except Exception:
            return OCRInput(fields={})

    return OCRInput(fields={})


def run_rule_engine(
    ocr_data: Union[OCRInput, Dict[str, Any], None],
    rules_path: Path = RULES_PATH,
) -> ComplianceResult:
    """
    Run the full Rule Engine pipeline on OCR output and return a ComplianceResult.

    This function never raises on malformed input — it degrades gracefully
    (missing/empty fields become FAIL or UNREADABLE as appropriate).
    """
    ocr_input = _coerce_ocr_input(ocr_data)
    rules = load_rules(rules_path)

    violations: List[Violation] = []
    passed_rules: List[str] = []
    unreadable_fields: List[str] = []

    applicable_count = 0
    passed_count = 0

    for rule in rules:
        rule_id = rule.get("id", "UNKNOWN_RULE")
        field_name = rule.get("field", "")
        severity = rule.get("severity", "MEDIUM")
        message = rule.get("message", f"{field_name} declaration is missing.")

        ocr_field: OCRField = ocr_input.fields.get(field_name)

        outcome = validate_presence_field(field_name, ocr_field)

        if outcome == UNREADABLE:
            unreadable_fields.append(field_name)
            continue  # excluded from scoring denominator, no violation

        applicable_count += 1

        if outcome == PASS:
            passed_count += 1
            passed_rules.append(rule_id)
        else:  # FAIL
            detected_value = ocr_field.value if ocr_field else ""
            violations.append(
                Violation(
                    rule_id=rule_id,
                    field=field_name,
                    detected_value=detected_value,
                    severity=severity,
                    reason=message,
                )
            )

    score = calculate_score(passed_count, applicable_count)

    if violations:
        # A confidently-read field failed a rule -> genuine non-compliance.
        status = "NON_COMPLIANT"
    elif unreadable_fields:
        # No verified violations, but at least one required field could not
        # be confidently read. We cannot certify compliance on unread data,
        # so this needs a human/re-scan review rather than a PASS or FAIL.
        status = "REVIEW_REQUIRED"
    else:
        # All applicable required checks passed, nothing unreadable.
        status = "COMPLIANT"

    return ComplianceResult(
        status=status,
        score=score,
        violations=violations,
        passed_rules=passed_rules,
        unreadable_fields=unreadable_fields,
    )