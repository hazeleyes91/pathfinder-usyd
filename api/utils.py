import re
from typing import Set

def matches_pattern(pattern: str, code: str) -> bool:
    """Checks if a concrete unit code matches a pattern (which might contain wildcards)."""
    if not ("X" in pattern or "x" in pattern):
        return pattern.upper() == code.upper()
    regex_pattern = f"^{pattern.replace('X', '.').replace('x', '.')}$"
    return bool(re.match(regex_pattern, code, re.IGNORECASE))

def match_wildcard(pattern: str, completed_units: Set[str]) -> bool:
    """Checks if any completed unit matches a pattern (with subject-prefix pruning optimization)."""
    if not ("X" in pattern or "x" in pattern):
        return pattern in completed_units
    subject_prefix = pattern[:4].upper()
    # Prune search space to matching subject prefix
    relevant_completed = {u for u in completed_units if u.startswith(subject_prefix)}
    regex_pattern = f"^{pattern.replace('X', '.').replace('x', '.')}$"
    return any(re.match(regex_pattern, u, re.IGNORECASE) for u in relevant_completed)
