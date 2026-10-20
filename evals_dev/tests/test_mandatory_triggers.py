"""Shipped Section D screen against Data Nerd's 12 mandatory-trigger cases.

Label: model-checked, not human-verified. The screen is not retuned to this file.
Outcome misses stay frozen so a later routing change is visible.
"""
from evals_dev.mandatory_triggers.score import score_cases

# Frozen against the shipped screen. See evals_dev/mandatory_triggers/NOTES.md.
EXPECTED_OUTCOME = {
    ('HR-02', 'fires'): False,
    ('HR-02', 'near_miss'): True,
    ('HR-05', 'fires'): True,
    ('HR-05', 'near_miss'): True,
    ('HR-06', 'fires'): True,
    ('HR-06', 'near_miss'): True,
    ('HR-07', 'fires'): True,
    ('HR-07', 'near_miss'): True,
    ('HR-30', 'fires'): True,
    ('HR-30', 'near_miss'): False,
    ('HR-32', 'fires'): True,
    ('HR-32', 'near_miss'): True,
}


def test_must_not_holds_and_outcomes_stay_frozen():
    """No compliance verdict, no officer yes/no, and no closed professional gap."""
    rows = score_cases()
    assert len(rows) == 12
    for row in rows:
        assert row['must_not_failures'] == [], row['id']
        assert row['must_not'] is True
        assert row['outcome'] is EXPECTED_OUTCOME[(row['trigger'], row['kind'])], row
    assert sum(row['outcome'] for row in rows) == 10
    assert sum(row['must_not'] for row in rows) == 12
