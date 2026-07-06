"""
Unit tests for the escalation engine.
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from api.validation.escalation import (
    EscalationContext,
    UnitDependencyCheck,
    WildcardDependencyCheck,
    MultipleConflictingWarningsCheck,
    should_escalate,
)


class TestUnitDependencyCheck:
    """Tests for UnitDependencyCheck primitive."""

    def test_escalates_when_concrete_unit_missing(self):
        """Should escalate if required concrete unit not in completed_units."""
        context = EscalationContext(
            completed_units={"INFO1110", "COMP1001"},
            rule_node={"type": "unit", "unit_code": "COMP2123"},
            rule_satisfied=True,
            attached_warnings=["grade_threshold"],
        )
        assert UnitDependencyCheck.check(context) is True

    def test_stays_soft_when_concrete_unit_placed(self):
        """Should not escalate if required unit is placed."""
        context = EscalationContext(
            completed_units={"INFO1110", "COMP2123"},
            rule_node={"type": "unit", "unit_code": "COMP2123"},
            rule_satisfied=True,
            attached_warnings=["grade_threshold"],
        )
        assert UnitDependencyCheck.check(context) is False

    def test_handles_unit_group_with_missing_units(self):
        """Should escalate if any unit in group is missing."""
        context = EscalationContext(
            completed_units={"COMP2123"},
            rule_node={"type": "unit_group", "operator": "AND", "unit_codes": ["COMP2123", "INFO1110"]},
            rule_satisfied=True,
            attached_warnings=["grade_threshold"],
        )
        assert UnitDependencyCheck.check(context) is True

    def test_handles_unit_group_all_placed(self):
        """Should not escalate if all units in group are placed."""
        context = EscalationContext(
            completed_units={"COMP2123", "INFO1110"},
            rule_node={"type": "unit_group", "operator": "AND", "unit_codes": ["COMP2123", "INFO1110"]},
            rule_satisfied=True,
            attached_warnings=["grade_threshold"],
        )
        assert UnitDependencyCheck.check(context) is False

    def test_ignores_wildcards(self):
        """Should not check wildcards (handled by WildcardDependencyCheck)."""
        context = EscalationContext(
            completed_units=set(),
            rule_node={"type": "unit", "unit_code": "COMP2XXX"},
            rule_satisfied=True,
            attached_warnings=["grade_threshold"],
        )
        # Should return False because wildcards are filtered out
        assert UnitDependencyCheck.check(context) is False

    def test_handles_empty_rule_node(self):
        """Should handle None or empty rule nodes gracefully."""
        context = EscalationContext(
            completed_units={"COMP2123"},
            rule_node=None,
            rule_satisfied=True,
            attached_warnings=["grade_threshold"],
        )
        assert UnitDependencyCheck.check(context) is False


class TestWildcardDependencyCheck:
    """Tests for WildcardDependencyCheck primitive."""

    def test_escalates_when_no_wildcard_matches(self):
        """Should escalate if wildcard pattern has no matches."""
        context = EscalationContext(
            completed_units={"INFO1110", "BIOL2001"},
            rule_node={"type": "unit", "unit_code": "COMP2XXX"},
            rule_satisfied=True,
            attached_warnings=["grade_threshold"],
        )
        assert WildcardDependencyCheck.check(context) is True

    def test_stays_soft_when_wildcard_has_match(self):
        """Should not escalate if at least one unit matches wildcard."""
        context = EscalationContext(
            completed_units={"COMP2101", "INFO1110"},
            rule_node={"type": "unit", "unit_code": "COMP2XXX"},
            rule_satisfied=True,
            attached_warnings=["grade_threshold"],
        )
        assert WildcardDependencyCheck.check(context) is False

    def test_handles_multiple_wildcards_or_logic(self):
        """Should stay soft if at least one wildcard matches (OR semantics)."""
        context = EscalationContext(
            completed_units={"COMP2101"},  # Matches COMP2XXX but not INFO3XXX
            rule_node={
                "type": "unit_group",
                "operator": "OR",
                "unit_codes": ["COMP2XXX", "INFO3XXX"],
            },
            rule_satisfied=True,
            attached_warnings=["grade_threshold"],
        )
        # For OR logic, at least one match means stay soft
        assert WildcardDependencyCheck.check(context) is False

    def test_multiple_wildcards_all_match(self):
        """Should not escalate if any wildcard matches."""
        context = EscalationContext(
            completed_units={"COMP2101", "INFO3001"},
            rule_node={
                "type": "unit_group",
                "operator": "OR",
                "unit_codes": ["COMP2XXX", "INFO3XXX"],
            },
            rule_satisfied=True,
            attached_warnings=["grade_threshold"],
        )
        assert WildcardDependencyCheck.check(context) is False

    def test_multiple_wildcards_none_match(self):
        """Should escalate if none of the wildcards match."""
        context = EscalationContext(
            completed_units={"BIOL2001"},
            rule_node={
                "type": "unit_group",
                "operator": "OR",
                "unit_codes": ["COMP2XXX", "INFO3XXX"],
            },
            rule_satisfied=True,
            attached_warnings=["grade_threshold"],
        )
        assert WildcardDependencyCheck.check(context) is True

    def test_ignores_concrete_units(self):
        """Should only check wildcards (concrete handled by UnitDependencyCheck)."""
        context = EscalationContext(
            completed_units=set(),
            rule_node={"type": "unit", "unit_code": "COMP2123"},
            rule_satisfied=True,
            attached_warnings=["grade_threshold"],
        )
        # Should return False because no wildcards present
        assert WildcardDependencyCheck.check(context) is False


class TestMultipleConflictingWarningsCheck:
    """Tests for MultipleConflictingWarningsCheck primitive."""

    def test_escalates_with_3_warnings(self):
        """Should escalate with exactly 3 warnings."""
        context = EscalationContext(
            completed_units={"COMP2123"},
            rule_node={"type": "unit", "unit_code": "COMP2123"},
            rule_satisfied=True,
            attached_warnings=["grade_threshold", "permission_required", "degree_restriction"],
        )
        assert MultipleConflictingWarningsCheck.check(context) is True

    def test_escalates_with_more_than_3_warnings(self):
        """Should escalate with 4+ warnings."""
        context = EscalationContext(
            completed_units={"COMP2123"},
            rule_node={"type": "unit", "unit_code": "COMP2123"},
            rule_satisfied=True,
            attached_warnings=[
                "grade_threshold",
                "permission_required",
                "degree_restriction",
                "logic_simplified",
            ],
        )
        assert MultipleConflictingWarningsCheck.check(context) is True

    def test_stays_soft_with_2_warnings(self):
        """Should not escalate with only 2 warnings."""
        context = EscalationContext(
            completed_units={"COMP2123"},
            rule_node={"type": "unit", "unit_code": "COMP2123"},
            rule_satisfied=True,
            attached_warnings=["grade_threshold", "permission_required"],
        )
        assert MultipleConflictingWarningsCheck.check(context) is False

    def test_stays_soft_with_1_warning(self):
        """Should not escalate with single warning."""
        context = EscalationContext(
            completed_units={"COMP2123"},
            rule_node={"type": "unit", "unit_code": "COMP2123"},
            rule_satisfied=True,
            attached_warnings=["grade_threshold"],
        )
        assert MultipleConflictingWarningsCheck.check(context) is False


class TestShouldEscalate:
    """Integration tests for should_escalate orchestrator."""

    def test_grade_threshold_escalates_when_unit_missing(self):
        """Grade threshold should escalate if underlying unit not placed."""
        context = EscalationContext(
            completed_units={"INFO1110"},
            rule_node={"type": "unit", "unit_code": "COMP2123"},
            rule_satisfied=True,
            attached_warnings=["grade_threshold"],
        )
        assert should_escalate(context, ["grade_threshold"]) is True

    def test_grade_threshold_stays_soft_when_unit_placed(self):
        """Grade threshold should stay soft if underlying unit is placed."""
        context = EscalationContext(
            completed_units={"COMP2123"},
            rule_node={"type": "unit", "unit_code": "COMP2123"},
            rule_satisfied=True,
            attached_warnings=["grade_threshold"],
        )
        assert should_escalate(context, ["grade_threshold"]) is False

    def test_permission_never_escalates(self):
        """Permission warnings should never escalate."""
        context = EscalationContext(
            completed_units=set(),
            rule_node={"type": "unit", "unit_code": "COMP2123"},
            rule_satisfied=True,
            attached_warnings=["permission_required"],
        )
        assert should_escalate(context, ["permission_required"]) is False

    def test_recommended_preparation_never_escalates(self):
        """Recommended preparation warnings should never escalate."""
        context = EscalationContext(
            completed_units=set(),
            rule_node={"type": "unit", "unit_code": "COMP2123"},
            rule_satisfied=True,
            attached_warnings=["recommended_preparation"],
        )
        assert should_escalate(context, ["recommended_preparation"]) is False

    def test_degree_restriction_never_escalates(self):
        """Degree restriction warnings should never escalate."""
        context = EscalationContext(
            completed_units=set(),
            rule_node={"type": "unit", "unit_code": "COMP2123"},
            rule_satisfied=True,
            attached_warnings=["degree_restriction"],
        )
        assert should_escalate(context, ["degree_restriction"]) is False

    def test_logic_simplified_deferred(self):
        """Logic simplified has no checks (deferred)."""
        context = EscalationContext(
            completed_units=set(),
            rule_node={"type": "unit", "unit_code": "COMP2123"},
            rule_satisfied=False,
            attached_warnings=["logic_simplified"],
        )
        assert should_escalate(context, ["logic_simplified"]) is False

    def test_multiple_warnings_trigger_escalation(self):
        """3+ warnings should trigger MultipleConflictingWarningsCheck."""
        context = EscalationContext(
            completed_units={"COMP2123"},
            rule_node={"type": "unit", "unit_code": "COMP2123"},
            rule_satisfied=True,
            attached_warnings=["grade_threshold", "permission_required", "degree_restriction"],
        )
        assert should_escalate(context, ["grade_threshold", "permission_required", "degree_restriction"]) is True

    def test_wildcard_escalates_when_no_matches(self):
        """Wildcard in grade threshold should escalate if no matching units."""
        context = EscalationContext(
            completed_units={"INFO1110"},
            rule_node={"type": "unit", "unit_code": "COMP2XXX"},
            rule_satisfied=True,
            attached_warnings=["grade_threshold"],
        )
        assert should_escalate(context, ["grade_threshold"]) is True

    def test_wildcard_stays_soft_with_matches(self):
        """Wildcard in grade threshold should stay soft if matching units exist."""
        context = EscalationContext(
            completed_units={"COMP2101", "INFO1110"},
            rule_node={"type": "unit", "unit_code": "COMP2XXX"},
            rule_satisfied=True,
            attached_warnings=["grade_threshold"],
        )
        assert should_escalate(context, ["grade_threshold"]) is False
