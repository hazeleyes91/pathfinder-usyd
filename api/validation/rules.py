import sys
import re
import json
from functools import lru_cache
from pathlib import Path
from typing import Set, Dict, Any, Tuple, List

# Add parent path to import sibling api modules
sys.path.append(str(Path(__file__).resolve().parents[2]))
from api.utils import match_wildcard, matches_pattern

@lru_cache(maxsize=256)
def _evaluate_rule_cached(rule_expr_json: str, completed_units_frozen: frozenset, metadata_json: str) -> Tuple[bool, Tuple[str, ...]]:
    """
    Cached implementation of evaluate_rule.
    Uses immutable types for caching: json strings and frozensets.
    """
    rule_expr = json.loads(rule_expr_json)
    completed_units = set(completed_units_frozen)
    db_units_metadata = json.loads(metadata_json)

    if not rule_expr:
        return True, ()

    rule_type = rule_expr.get("type", "none")
    rule_node = rule_expr.get("rule")

    # Root level warnings
    warnings = set()
    root_warns = rule_expr.get("warnings")
    if root_warns:
        for w in root_warns:
            warnings.add(w)

    if rule_type == "none" or not rule_node:
        return True, tuple(sorted(warnings))

    satisfied, node_warnings = evaluate_node(rule_node, completed_units, db_units_metadata)
    warnings.update(node_warnings)

    return satisfied, tuple(sorted(warnings))


def evaluate_rule(rule_expr: dict, completed_units: Set[str], db_units_metadata: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Evaluates a RuleParseResult expression against completed units.
    Returns (is_satisfied, list_of_warning_messages).

    Uses LRU cache for repeated evaluations with same parameters.
    """
    # Convert to immutable types for caching
    rule_expr_json = json.dumps(rule_expr, sort_keys=True)
    completed_units_frozen = frozenset(completed_units)
    metadata_json = json.dumps(db_units_metadata, sort_keys=True)

    # Call cached implementation
    satisfied, warnings_tuple = _evaluate_rule_cached(rule_expr_json, completed_units_frozen, metadata_json)

    return satisfied, list(warnings_tuple)

def evaluate_node(node: dict, completed_units: Set[str], db_units_metadata: Dict[str, Any]) -> Tuple[bool, Set[str]]:
    if not node:
        return True, set()
        
    node_type = node.get("type")
    warnings = set()
    node_warns = node.get("warnings")
    if node_warns:
        for w in node_warns:
            warnings.add(w)
            
    if node_type == "unit":
        unit_code = node.get("unit_code")
        if not unit_code:
            return True, warnings
        satisfied = match_wildcard(unit_code, completed_units)
        return satisfied, warnings
        
    elif node_type == "unit_group":
        operator = node.get("operator", "AND")
        unit_codes = node.get("unit_codes", [])
        if not unit_codes:
            return True, warnings
            
        # Partition into exact and wildcards
        unit_codes_set = set(unit_codes)
        exact_codes = {c for c in unit_codes_set if not ("X" in c or "x" in c)}
        wildcard_codes = {c for c in unit_codes_set if "X" in c or "x" in c}
        
        matches = []
        # Exact matching using set operations (subset/disjoint)
        if exact_codes:
            if operator == "AND":
                matches.append(exact_codes.issubset(completed_units))
            else: # OR
                matches.append(not exact_codes.isdisjoint(completed_units))
                
        # Wildcard matching using subject-pruned regex checks
        for pattern in wildcard_codes:
            matches.append(match_wildcard(pattern, completed_units))
            
        if not matches:
            return True, warnings
            
        if operator == "AND":
            satisfied = all(matches)
        else: # OR
            satisfied = any(matches)
            
        return satisfied, warnings
        
    elif node_type == "credit_points":
        required_cp = node.get("credit_points", 0)
        level_filter = node.get("level") # e.g. 3000
        pool_units = node.get("unit_codes") # Set[str] or list
        subjects_filter = node.get("subjects") # Set[str] or list
        
        pool_units_set = set(pool_units) if pool_units else None
        subjects_set = set(subjects_filter) if subjects_filter else None
        
        total_cp = 0
        for u in completed_units:
            # 1. Level filter check
            if level_filter is not None:
                # Code format typically 4 letters + 4 digits (e.g. COMP2123)
                # First digit represents level (COMP2123 -> level 2 -> 2000 level UoS)
                if len(u) >= 5 and u[4].isdigit():
                    unit_level = int(u[4]) * 1000
                    if unit_level != level_filter:
                        continue
                else:
                    continue
                    
            # 2. Subject filter check
            if subjects_set is not None:
                subject_prefix = u[:4].upper()
                if subject_prefix not in subjects_set:
                    continue
                    
            # 3. Unit codes pool check
            if pool_units_set is not None:
                match_found = False
                for pattern in pool_units_set:
                    if matches_pattern(pattern, u):
                        match_found = True
                        break
                if not match_found:
                    continue
                    
            # Fetch CP from metadata or fallback to 6
            unit_cp = db_units_metadata.get(u, {}).get("credit_points", 6)
            total_cp += unit_cp
            
        satisfied = total_cp >= required_cp
        return satisfied, warnings
        
    elif node_type == "logical":
        operator = node.get("operator", "AND")
        operands = node.get("operands", [])
        if not operands:
            return True, warnings
            
        operand_results = []
        for operand in operands:
            sat, op_warns = evaluate_node(operand, completed_units, db_units_metadata)
            operand_results.append((sat, op_warns))
            
        # Collect warnings
        sats = [r[0] for r in operand_results]
        
        if operator == "AND":
            satisfied = all(sats)
            for r in operand_results:
                warnings.update(r[1])
        else: # OR
            satisfied = any(sats)
            for sat, op_warns in operand_results:
                if sat:
                    warnings.update(op_warns)
            if not satisfied:
                for r in operand_results:
                    warnings.update(r[1])

        return satisfied, warnings

    return True, set()


def extract_required_units(rule_node: dict) -> Set[str]:
    """
    Extract concrete unit codes from a rule node (excludes wildcards).

    Args:
        rule_node: Rule node dictionary from RuleParseResult

    Returns:
        Set of concrete unit codes (no wildcards)
    """
    if not rule_node:
        return set()

    node_type = rule_node.get("type")
    units = set()

    if node_type == "unit":
        unit_code = rule_node.get("unit_code")
        if unit_code and "X" not in unit_code and "x" not in unit_code:
            units.add(unit_code)

    elif node_type == "unit_group":
        unit_codes = rule_node.get("unit_codes", [])
        for code in unit_codes:
            if "X" not in code and "x" not in code:
                units.add(code)

    elif node_type == "logical":
        operands = rule_node.get("operands", [])
        for operand in operands:
            units.update(extract_required_units(operand))

    elif node_type == "credit_points":
        # Credit points may have a unit pool
        pool_units = rule_node.get("unit_codes")
        if pool_units:
            for code in pool_units:
                if "X" not in code and "x" not in code:
                    units.add(code)

    return units


def extract_wildcard_patterns(rule_node: dict) -> Set[str]:
    """
    Extract wildcard patterns from a rule node (only wildcards).

    Args:
        rule_node: Rule node dictionary from RuleParseResult

    Returns:
        Set of wildcard patterns (e.g., COMP2XXX, INFO3X01)
    """
    if not rule_node:
        return set()

    node_type = rule_node.get("type")
    patterns = set()

    if node_type == "unit":
        unit_code = rule_node.get("unit_code")
        if unit_code and ("X" in unit_code or "x" in unit_code):
            patterns.add(unit_code)

    elif node_type == "unit_group":
        unit_codes = rule_node.get("unit_codes", [])
        for code in unit_codes:
            if "X" in code or "x" in code:
                patterns.add(code)

    elif node_type == "logical":
        operands = rule_node.get("operands", [])
        for operand in operands:
            patterns.update(extract_wildcard_patterns(operand))

    elif node_type == "credit_points":
        # Credit points may have wildcard patterns in pool
        pool_units = rule_node.get("unit_codes")
        if pool_units:
            for code in pool_units:
                if "X" in code or "x" in code:
                    patterns.add(code)

    return patterns
