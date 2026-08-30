"""
Pydantic models for the Legal Metrology Rule Engine.

These models define the data contracts between:
- OCR Service -> Rule Engine  (OCRInput)
- Rule Engine -> Backend/Frontend  (ComplianceResult)

Keep these models simple and explicit so they are easy to explain to judges.
"""

from __future__ import annotations

from typing import Dict, List
from pydantic import BaseModel, Field


class OCRField(BaseModel):
    """A single field extracted by OCR, with its recognized text and confidence."""

    value: str = Field(default="", description="Raw text value extracted by OCR")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="OCR confidence score (0-1)")


class OCRInput(BaseModel):
    """
    The structured input the Rule Engine receives from the OCR service.

    Matches the contract:
    {
        "fields": {
            "mrp": {"value": "149", "confidence": 0.96},
            ...
        }
    }
    """

    fields: Dict[str, OCRField] = Field(default_factory=dict)


class Violation(BaseModel):
    """A single rule violation detected during validation."""

    rule_id: str
    field: str
    detected_value: str
    severity: str
    reason: str


class ComplianceResult(BaseModel):
    """Final output of the Rule Engine for one product label."""
    status: str  # "COMPLIANT" | "NON_COMPLIANT" | "REVIEW_REQUIRED"
    score: int
    violations: List[Violation] = Field(default_factory=list)
    passed_rules: List[str] = Field(default_factory=list)
    unreadable_fields: List[str] = Field(default_factory=list)