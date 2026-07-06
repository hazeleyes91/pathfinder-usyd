import re
from typing import Set, Dict

# Global regex compilation cache
REGEX_CACHE: Dict[str, re.Pattern] = {}


def matches_pattern(pattern: str, code: str) -> bool:
    """Checks if a concrete unit code matches a pattern (which might contain wildcards)."""
    if not ("X" in pattern or "x" in pattern):
        return pattern.upper() == code.upper()

    # Check cache for compiled regex
    if pattern not in REGEX_CACHE:
        regex_pattern = f"^{pattern.replace('X', '.').replace('x', '.')}$"
        REGEX_CACHE[pattern] = re.compile(regex_pattern, re.IGNORECASE)

    return bool(REGEX_CACHE[pattern].match(code))


def match_wildcard(pattern: str, completed_units: Set[str]) -> bool:
    """Checks if any completed unit matches a pattern (with subject-prefix pruning optimization)."""
    if not ("X" in pattern or "x" in pattern):
        return pattern in completed_units

    subject_prefix = pattern[:4].upper()
    # Prune search space to matching subject prefix
    relevant_completed = {u for u in completed_units if u.startswith(subject_prefix)}

    # Check cache for compiled regex
    if pattern not in REGEX_CACHE:
        regex_pattern = f"^{pattern.replace('X', '.').replace('x', '.')}$"
        REGEX_CACHE[pattern] = re.compile(regex_pattern, re.IGNORECASE)

    return any(REGEX_CACHE[pattern].match(u) for u in relevant_completed)
