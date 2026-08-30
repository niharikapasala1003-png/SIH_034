"""
Scoring logic for the Legal Metrology Rule Engine.

Simple, transparent formula (deliberately not "smart" — must be explainable
to judges in one sentence):

    score = (number of passed rules / number of applicable rules) * 100

"Applicable rules" excludes rules whose field came back UNREADABLE, since
we cannot fairly judge a field we could not confidently read.
"""

from __future__ import annotations

from typing import List


def calculate_score(passed_count: int, applicable_count: int) -> int:
    """
    Calculate the compliance score as a whole-number percentage.

    If there are zero applicable rules (e.g. everything was unreadable),
    we return 0 rather than dividing by zero, and let the caller decide
    how to represent that edge case in the final status.
    """
    if applicable_count <= 0:
        return 0

    raw_score = (passed_count / applicable_count) * 100
    return round(raw_score)