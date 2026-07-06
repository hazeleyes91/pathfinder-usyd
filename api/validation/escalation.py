"""
Escalation engine for converting soft warnings to hard warnings based on context.

This module implements a scalable warning escalation system using primitive check patterns
that can be applied to any warning type via configuration.
"""

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Set, List, Protocol

# Add parent path to import sibling api modules
sys.path.append(str(Path(__file__).resolve().parents[2]))
from api.validation.rules import extract_required_units, extract_wildcard_patterns


@dataclass
class EscalationContext:
    """Context information for escalation decision."""
    completed_units: Set[str]
    rule_node: dict
    rule_satisfied: bool
    attached_warnings: List[str]


class EscalationCheck(Protocol):
    """Protocol for primitive escalation check patterns."""

    @staticmethod
    def check(context: EscalationContext) -> bool:
        """
        Check if escalation should occur based on context.
        Returns True if warning should escalate to hard, False to stay soft.
        """
        ...


class UnitDependencyCheck:
    """Escalates if concrete unit codes are required but not placed."""

    @staticmethod
    def check(context: EscalationContext) -> bool:
        required_units = extract_required_units(context.rule_node)
        if not required_units:
            return False

        # Escalate if any required concrete units are missing
        missing_units = required_units - context.completed_units
        return len(missing_units) > 0


class WildcardDependencyCheck:
    """Escalates if wildcard patterns exist but no matching units are placed."""

    @staticmethod
    def check(context: EscalationContext) -> bool:
        wildcard_patterns = extract_wildcard_patterns(context.rule_node)
        if not wildcard_patterns:
            return False

        # Check if ANY wildcard pattern has a match
        from api.utils import match_wildcard

        any_match = False
        for pattern in wildcard_patterns:
            has_match = match_wildcard(pattern, context.completed_units)
            if has_match:
                any_match = True
                break

        # Escalate if NONE of the wildcards have matches (likely OR rule)
        # Stay soft if at least one wildcard has a match
        return not any_match


class MultipleConflictingWarningsCheck:
    """Escalates if 3+ warnings present (indicates parsing ambiguity)."""

    @staticmethod
    def check(context: EscalationContext) -> bool:
        return len(context.attached_warnings) >= 3


# Configuration mapping: ParserWarning type → list of applicable checks
ESCALATION_CONFIG = {
    "grade_threshold": [UnitDependencyCheck, WildcardDependencyCheck],
    "permission_required": [],  # Never escalate (human approval)
    "recommended_preparation": [],  # Never escalate (advisory by nature)
    "degree_restriction": [],  # Never escalate (external to planner)
    "logic_simplified": [],  # DEFERRED - placeholder for future
    "other": [],  # PLACEHOLDER - defer until specific cases identified
}


def should_escalate(context: EscalationContext, warning_types: List[str]) -> bool:
    """
    Determine if soft warning should escalate to hard based on context.

    Args:
        context: EscalationContext with validation state
        warning_types: List of ParserWarning strings attached to the rule

    Returns:
        True if warning should escalate to hard, False to remain soft
    """
    # Check MultipleConflictingWarningsCheck first (applies to all)
    if MultipleConflictingWarningsCheck.check(context):
        return True

    # Run applicable checks for each warning type
    for warning_type in warning_types:
        # Normalize to lowercase for config lookup
        warning_key = warning_type.lower()

        # Get applicable checks from config
        checks = ESCALATION_CONFIG.get(warning_key, [])

        # If any check triggers, escalate
        for check_class in checks:
            if check_class.check(context):
                return True

    # No escalation triggers found
    return False
