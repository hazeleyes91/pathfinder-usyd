import sys
import re
from pathlib import Path
from typing import Set, Dict, Any, Tuple, List

# Add parent path to import sibling api modules
sys.path.append(str(Path(__file__).resolve().parents[2]))
from api.utils import match_wildcard, matches_pattern

def evaluate_rule(rule_expr: dict, completed_units: Set[str], db_units_metadata: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Evaluates a RuleParseResult expression against completed units.
    Returns (is_satisfied, list_of_warning_messages).
    """
    if not rule_expr:
        return True, []
        
    rule_type = rule_expr.get("type", "none")
    rule_node = rule_expr.get("rule")
    
    # Root level warnings
    warnings = set()
    root_warns = rule_expr.get("warnings")
    if root_warns:
        for w in root_warns:
            warnings.add(w)
            
    if rule_type == "none" or not rule_node:
        return True, sorted(list(warnings))
        
    satisfied, node_warnings = evaluate_node(rule_node, completed_units, db_units_metadata)
    warnings.update(node_warnings)
    
    return satisfied, sorted(list(warnings))

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
