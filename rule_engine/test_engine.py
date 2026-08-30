"""
Automated tests for the Legal Metrology Rule Engine prototype.

Run with:
    pytest rule_engine/test_engine.py -v
"""

from engine import run_rule_engine


def _all_valid_ocr():
    return {
        "fields": {
            "mrp": {"value": "149", "confidence": 0.96},
            "net_quantity": {"value": "500 g", "confidence": 0.94},
            "manufacturer": {"value": "ABC Foods Pvt Ltd", "confidence": 0.91},
            "packing_date": {"value": "08/2026", "confidence": 0.88},
            "consumer_care": {"value": "1800-123-4567", "confidence": 0.83},
        }
    }


def test_all_fields_valid_is_compliant():
    """TEST 1: All five fields valid -> COMPLIANT, score = 100."""
    result = run_rule_engine(_all_valid_ocr())

    assert result.status == "COMPLIANT"
    assert result.score == 100
    assert result.violations == []
    assert set(result.passed_rules) == {"MRP_001", "QTY_001", "MFR_001", "DATE_001", "CARE_001"}
    assert result.unreadable_fields == []


def test_mrp_missing_is_non_compliant():
    """TEST 2: MRP missing -> NON_COMPLIANT with MRP_001 violation."""
    ocr_data = _all_valid_ocr()
    del ocr_data["fields"]["mrp"]

    result = run_rule_engine(ocr_data)

    assert result.status == "NON_COMPLIANT"
    violation_ids = [v.rule_id for v in result.violations]
    assert "MRP_001" in violation_ids
    assert "MRP_001" not in result.passed_rules


def test_multiple_fields_missing_multiple_violations():
    """TEST 3: Multiple fields missing -> multiple violations."""
    ocr_data = _all_valid_ocr()
    del ocr_data["fields"]["mrp"]
    del ocr_data["fields"]["manufacturer"]
    ocr_data["fields"]["net_quantity"]["value"] = ""  # empty value also counts as missing

    result = run_rule_engine(ocr_data)

    assert result.status == "NON_COMPLIANT"
    violation_ids = {v.rule_id for v in result.violations}
    assert violation_ids == {"MRP_001", "MFR_001", "QTY_001"}
    assert len(result.violations) == 3


def test_low_confidence_field_is_unreadable_not_violation():
    """TEST 4: MRP confidence below 0.60 -> unreadable, NOT auto-violation.

    With no verified violations but an unreadable required field, overall
    status must be REVIEW_REQUIRED (not COMPLIANT, not NON_COMPLIANT).
    """
    ocr_data = _all_valid_ocr()
    ocr_data["fields"]["mrp"] = {"value": "1?9", "confidence": 0.31}

    result = run_rule_engine(ocr_data)

    assert "mrp" in result.unreadable_fields
    violation_ids = [v.rule_id for v in result.violations]
    assert "MRP_001" not in violation_ids
    # Remaining 4 fields are valid, so they should still pass and score 100
    # over the 4 applicable rules.
    assert result.score == 100
    assert result.status == "REVIEW_REQUIRED"


def test_single_unreadable_field_no_violations_is_review_required():
    """TEST 6: One unreadable required field, no violations -> REVIEW_REQUIRED."""
    ocr_data = _all_valid_ocr()
    ocr_data["fields"]["consumer_care"] = {"value": "180?-???-4567", "confidence": 0.42}

    result = run_rule_engine(ocr_data)

    assert result.status == "REVIEW_REQUIRED"
    assert result.unreadable_fields == ["consumer_care"]
    assert result.violations == []
    assert "CARE_001" not in result.passed_rules


def test_multiple_unreadable_fields_no_violations_is_review_required():
    """TEST 7: Multiple unreadable required fields, no violations -> REVIEW_REQUIRED."""
    ocr_data = _all_valid_ocr()
    ocr_data["fields"]["mrp"] = {"value": "1?9", "confidence": 0.20}
    ocr_data["fields"]["packing_date"] = {"value": "0?/2026", "confidence": 0.55}

    result = run_rule_engine(ocr_data)

    assert result.status == "REVIEW_REQUIRED"
    assert set(result.unreadable_fields) == {"mrp", "packing_date"}
    assert result.violations == []
    # Score is over the 3 applicable (confidently-read) rules, all passed.
    assert result.score == 100


def test_violation_takes_priority_over_unreadable_for_status():
    """TEST 8: A verified violation alongside an unreadable field ->
    NON_COMPLIANT still wins over REVIEW_REQUIRED (real failure outranks
    an inconclusive read)."""
    ocr_data = _all_valid_ocr()
    del ocr_data["fields"]["manufacturer"]  # verified FAIL
    ocr_data["fields"]["mrp"] = {"value": "1?9", "confidence": 0.31}  # UNREADABLE

    result = run_rule_engine(ocr_data)

    assert result.status == "NON_COMPLIANT"
    violation_ids = [v.rule_id for v in result.violations]
    assert "MFR_001" in violation_ids
    assert "mrp" in result.unreadable_fields


def test_empty_or_malformed_input_handled_safely():
    """TEST 5: Empty or malformed OCR input -> handled safely, no crash."""
    # Completely empty dict
    result_empty = run_rule_engine({})
    assert result_empty.status == "NON_COMPLIANT"
    assert len(result_empty.violations) == 5  # all fields missing -> all FAIL

    # None input
    result_none = run_rule_engine(None)
    assert result_none.status == "NON_COMPLIANT"
    assert len(result_none.violations) == 5

    # Garbage / wrong-shaped input
    result_garbage = run_rule_engine({"unexpected": "shape", "fields": "not_a_dict"})
    assert result_garbage.status == "NON_COMPLIANT"
    assert len(result_garbage.violations) == 5