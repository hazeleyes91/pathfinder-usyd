import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Set

from pydantic import TypeAdapter

# Sibling/Parent imports
sys.path.append(str(Path(__file__).resolve().parents[2]))
from api.models import ValidationRequest, ValidationResponse, WarningDetail
from api.utils import match_wildcard, matches_pattern
from api.validation.rules import evaluate_rule


def _extract_failing_recursive(node: dict, completed_units: Set[str]) -> List[str]:
    """
    Walk a rule node and return only the unit codes that are actually required
    but missing, respecting logical structure:
    - AND: collect failing codes from every failing child.
    - OR:  if any child is satisfied the whole OR is met → return [].
             if all children fail → return codes from all failing children.
    """
    from api.validation.rules import evaluate_node

    if not node:
        return []

    node_type = node.get("type")

    if node_type == "unit":
        code = node.get("unit_code", "")
        if not code or "X" in code or "x" in code:
            return []
        return [code] if not match_wildcard(code, completed_units) else []

    elif node_type == "unit_group":
        operator = node.get("operator", "AND")
        codes = [c for c in node.get("unit_codes", []) if "X" not in c and "x" not in c]
        if operator == "AND":
            return [c for c in codes if c not in completed_units]
        else:  # OR
            if any(c in completed_units for c in codes):
                return []  # at least one alternative is satisfied
            return [c for c in codes if c not in completed_units]

    elif node_type == "logical":
        operator = node.get("operator", "AND")
        operands = node.get("operands", [])

        if operator == "AND":
            failing = []
            for operand in operands:
                sat, _ = evaluate_node(operand, completed_units, {})
                if not sat:
                    failing.extend(_extract_failing_recursive(operand, completed_units))
            return failing
        else:  # OR
            # Check each operand
            sats = [evaluate_node(op, completed_units, {})[0] for op in operands]
            if any(sats):
                return []  # OR is satisfied — nothing to highlight
            # All branches failed — collect codes from all failing children
            failing = []
            for operand in operands:
                failing.extend(_extract_failing_recursive(operand, completed_units))
            return failing

    return []


def extract_failing_units(rule_expr: dict, completed_units: Set[str]) -> List[str]:
    """Return unit codes that are actually required but missing, respecting logical OR/AND structure."""
    if not rule_expr:
        return []
    node = rule_expr.get("rule")
    if not node:
        return []
    return list(set(_extract_failing_recursive(node, completed_units)))


def _collect_all_codes(node: dict) -> List[str]:
    """Flat collection of all concrete unit codes in a node tree (for prohibition checks)."""
    if not node:
        return []
    node_type = node.get("type")
    if node_type == "unit":
        code = node.get("unit_code", "")
        return [code] if code and "X" not in code and "x" not in code else []
    elif node_type == "unit_group":
        return [c for c in node.get("unit_codes", []) if "X" not in c and "x" not in c]
    elif node_type == "logical":
        result = []
        for op in node.get("operands", []):
            result.extend(_collect_all_codes(op))
        return result
    return []


def extract_conflicting_units(rule_expr: dict, planned_units: Set[str]) -> List[str]:
    """Return unit codes in a prohibition rule_expr that ARE in planned_units (the conflict)."""
    if not rule_expr:
        return []
    node = rule_expr.get("rule")
    if not node:
        return []
    return [c for c in _collect_all_codes(node) if c in planned_units]


from api.database import get_db_connection
from crawler.config import DATA_DIR, DEFAULT_TARGET_YEAR

# Load the database target year
TARGET_YEAR = int(os.getenv("PORTAL_YEAR", DEFAULT_TARGET_YEAR))

# Load DBs (kept for test mocking capability)
RULES_DB: Dict[str, Any] = {}
UOS_METADATA: Dict[str, Any] = {}

# Cache the availability list to avoid re-parsing HTML repeatedly
AVAILABILITY_CACHE: Dict[str, List[str]] = {}


def get_availability(unit_code: str) -> List[str]:
    if unit_code in AVAILABILITY_CACHE:
        return AVAILABILITY_CACHE[unit_code]

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT session_code, session_text FROM unit_availabilities WHERE unit_code = ?",
            (unit_code,),
        )
        rows = cursor.fetchall()
        if not rows:
            # Fallback to UOS_METADATA mock if present
            mock_avail = UOS_METADATA.get(unit_code, {}).get("avail")
            if mock_avail:
                AVAILABILITY_CACHE[unit_code] = mock_avail
                return mock_avail
            AVAILABILITY_CACHE[unit_code] = ["sem1", "sem2"]
            return ["sem1", "sem2"]

        sessions = set()
        for row in rows:
            sess_code = row["session_code"]
            s_lower = sess_code.lower()
            if s_lower == "s1":
                sessions.add("sem1")
            elif s_lower == "s2":
                sessions.add("sem2")
            elif s_lower == "summer" or s_lower in ("s1cija", "s1cife"):
                sessions.add("summ")
            elif s_lower == "winter" or s_lower in ("s1cijn", "s2cijl"):
                sessions.add("wint")
            elif s_lower in ("s1cima", "s1ciap", "s1cimy"):
                sessions.add("sem1")
            elif s_lower in ("s2ciau", "s2cise", "s2cioc", "s2cinv", "s2cide"):
                sessions.add("sem2")
            else:
                s_text_lower = row["session_text"].lower()
                if "semester 1" in s_text_lower:
                    sessions.add("sem1")
                elif "semester 2" in s_text_lower:
                    sessions.add("sem2")
                elif (
                    "winter" in s_text_lower
                    or "june" in s_text_lower
                    or "july" in s_text_lower
                ):
                    sessions.add("wint")
                elif (
                    "summer" in s_text_lower
                    or "january" in s_text_lower
                    or "february" in s_text_lower
                ):
                    sessions.add("summ")

        avail = sorted(list(sessions)) if sessions else ["sem1", "sem2"]
        AVAILABILITY_CACHE[unit_code] = avail
        return avail
    except Exception:
        return ["sem1", "sem2"]
    finally:
        conn.close()


# Save a reference to the original function for mock-detection
_original_get_availability = get_availability


def run_validation(request: ValidationRequest) -> ValidationResponse:
    warnings = []

    # 1. Chronological Sorting of Placements
    term_order = {"summ": 0, "sem1": 1, "wint": 2, "sem2": 3}

    sorted_placements = sorted(
        request.placements, key=lambda p: p.year * 10 + term_order.get(p.term, 0)
    )

    # Build complete plan pool of UoS codes
    all_planned_units = set()
    for placement in request.placements:
        all_planned_units.update(placement.codes)

    completed_units = set()

    # Pre-fetch details from SQLite in 2 sweeps
    local_uos_metadata = {}
    local_rules_db = {}
    local_availabilities = {}

    # If mocked globally by test fixtures, use the mocks
    if UOS_METADATA:
        for k, v in UOS_METADATA.items():
            local_uos_metadata[k] = v
    if RULES_DB:
        for k, v in RULES_DB.items():
            local_rules_db[k] = v

    # Identify which codes need to be fetched from SQLite
    codes_to_fetch = [
        code
        for code in all_planned_units
        if (code not in local_uos_metadata or code not in local_rules_db)
    ]

    if codes_to_fetch:
        placeholders = ", ".join("?" for _ in codes_to_fetch)
        conn = get_db_connection()
        try:
            # Query Sweep 1: Units + Rules
            query1 = f"""
            SELECT
                u.unit_code, u.title, u.credit_points, u.level, u.faculty, u.handbook_url, u.is_active, u.replaced_by_code,
                r.prerequisites_text, r.corequisites_text, r.prohibitions_text, r.assumed_knowledge_text,
                r.prerequisites_expr, r.corequisites_expr, r.prohibitions_expr, r.needs_curation, r.flagged
            FROM units u
            LEFT JOIN unit_rules r ON u.unit_code = r.unit_code
            WHERE u.unit_code IN ({placeholders})
            """
            cursor = conn.cursor()
            cursor.execute(query1, list(codes_to_fetch))
            rows1 = cursor.fetchall()

            for row in rows1:
                code = row["unit_code"]
                if code not in local_uos_metadata:
                    local_uos_metadata[code] = {
                        "unit_code": code,
                        "title": row["title"],
                        "credit_points": row["credit_points"],
                        "level": "Undergraduate"
                        if row["level"] < 9000
                        else "Postgraduate",
                        "academic_unit": row["faculty"],
                        "prerequisites_text": row["prerequisites_text"] or "None",
                        "corequisites_text": row["corequisites_text"] or "None",
                        "prohibitions_text": row["prohibitions_text"] or "None",
                        "assumed_knowledge_text": row["assumed_knowledge_text"]
                        or "None",
                        "status": "ACTIVE" if row["is_active"] else "INACTIVE",
                    }

                if code not in local_rules_db:
                    prereq_expr = (
                        json.loads(row["prerequisites_expr"])
                        if row["prerequisites_expr"]
                        else {"type": "none", "rule": None}
                    )
                    coreq_expr = (
                        json.loads(row["corequisites_expr"])
                        if row["corequisites_expr"]
                        else {"type": "none", "rule": None}
                    )
                    prohib_expr = (
                        json.loads(row["prohibitions_expr"])
                        if row["prohibitions_expr"]
                        else {"type": "none", "rule": None}
                    )

                    local_rules_db[code] = {
                        "unit_code": code,
                        "title": row["title"],
                        "prerequisites_expr": prereq_expr,
                        "corequisites_expr": coreq_expr,
                        "prohibitions_expr": prohib_expr,
                        "needs_curation": bool(row["needs_curation"]),
                        "flagged": bool(row["flagged"]),
                        "raw_rules": {
                            "prerequisites": row["prerequisites_text"] or "None",
                            "corequisites": row["corequisites_text"] or "None",
                            "prohibitions": row["prohibitions_text"] or "None",
                        },
                    }

            # Query Sweep 2: Availabilities
            query2 = f"""
            SELECT unit_code, session_code, session_text, modes, locations
            FROM unit_availabilities
            WHERE unit_code IN ({placeholders})
            """
            cursor.execute(query2, list(codes_to_fetch))
            rows2 = cursor.fetchall()

            for row in rows2:
                code = row["unit_code"]
                sess_code = row["session_code"]

                term_key = None
                s_lower = sess_code.lower()
                if s_lower == "s1":
                    term_key = "sem1"
                elif s_lower == "s2":
                    term_key = "sem2"
                elif s_lower == "summer" or s_lower in ("s1cija", "s1cife"):
                    term_key = "summ"
                elif s_lower == "winter" or s_lower in ("s1cijn", "s2cijl"):
                    term_key = "wint"
                elif s_lower in ("s1cima", "s1ciap", "s1cimy"):
                    term_key = "sem1"
                elif s_lower in ("s2ciau", "s2cise", "s2cioc", "s2cinv", "s2cide"):
                    term_key = "sem2"
                else:
                    s_text_lower = row["session_text"].lower()
                    if "semester 1" in s_text_lower:
                        term_key = "sem1"
                    elif "semester 2" in s_text_lower:
                        term_key = "sem2"
                    elif (
                        "winter" in s_text_lower
                        or "june" in s_text_lower
                        or "july" in s_text_lower
                    ):
                        term_key = "wint"
                    elif (
                        "summer" in s_text_lower
                        or "january" in s_text_lower
                        or "february" in s_text_lower
                    ):
                        term_key = "summ"
                    else:
                        term_key = "sem1"

                if term_key:
                    local_availabilities.setdefault(code, set()).add(term_key)
        finally:
            conn.close()

    # For any code that still wasn't found in DB, assign standard defaults
    for code in all_planned_units:
        if code not in local_uos_metadata:
            local_uos_metadata[code] = {
                "unit_code": code,
                "title": "Unknown Unit",
                "credit_points": 6,
                "level": "Undergraduate",
                "academic_unit": "Unknown",
                "prerequisites_text": "None",
                "corequisites_text": "None",
                "prohibitions_text": "None",
                "assumed_knowledge_text": "None",
                "status": "ACTIVE",
            }
        if code not in local_rules_db:
            local_rules_db[code] = {
                "unit_code": code,
                "prerequisites_expr": {"type": "none", "rule": None},
                "corequisites_expr": {"type": "none", "rule": None},
                "prohibitions_expr": {"type": "none", "rule": None},
                "needs_curation": False,
                "flagged": False,
                "raw_rules": {
                    "prerequisites": "None",
                    "corequisites": "None",
                    "prohibitions": "None",
                },
            }

    for placement in sorted_placements:
        year = placement.year
        term = placement.term
        codes = placement.codes

        # Check A: Term CP Overload
        term_cp = 0
        for code in codes:
            cp = local_uos_metadata.get(code, {}).get("credit_points", 6)
            term_cp += cp

        overload_limit = 12 if term in ["summ", "wint"] else 24
        if term_cp > overload_limit:
            warnings.append(
                WarningDetail(
                    type="overload",
                    year=year,
                    term=term,
                    message=f"Semester overload: Year {year} {term} load of {term_cp} CP exceeds standard {overload_limit} CP limit.",
                )
            )

        # Check individual UoS rules in the current term block
        for code in codes:
            unit_rule = local_rules_db.get(code, {})

            # Check B: Session Availability Mismatch
            if get_availability is not _original_get_availability:
                avail = get_availability(code)
            else:
                avail = list(local_availabilities.get(code, {"sem1", "sem2"}))

            if term not in avail:
                warnings.append(
                    WarningDetail(
                        type="session_mismatch",
                        unit_code=code,
                        year=year,
                        term=term,
                        message=f"Availability mismatch: {code} is not offered in {term}.",
                    )
                )

            # Check C: Prohibitions
            prohib_expr = unit_rule.get("prohibitions_expr")
            if prohib_expr and prohib_expr.get("type") != "none":
                prohibited_satisfied, prohib_warnings = evaluate_rule(
                    prohib_expr, all_planned_units, local_uos_metadata
                )
                if prohibited_satisfied:
                    conflict_codes = extract_conflicting_units(
                        prohib_expr, all_planned_units
                    )
                    warnings.append(
                        WarningDetail(
                            type="prohibited",
                            unit_code=code,
                            year=year,
                            term=term,
                            message=f"Prohibition conflict: {code} cannot be taken alongside prohibited units in this plan.",
                            affected_codes=conflict_codes or None,
                        )
                    )

            # Check D: Corequisites
            coreq_expr = unit_rule.get("corequisites_expr")
            raw_coreq = (
                unit_rule.get("raw_rules", {}).get("corequisites")
                if unit_rule
                else None
            )
            is_coreq_unparsed = (
                coreq_expr
                and (
                    coreq_expr.get("curation_validity") == "needs_manual_review"
                    or coreq_expr.get("type") == "none"
                )
                and raw_coreq
                and raw_coreq.strip().lower() not in ["", "none", "none."]
            )

            if (
                coreq_expr
                and coreq_expr.get("type") != "none"
                and not is_coreq_unparsed
            ):
                current_and_completed = completed_units.union(set(codes))
                satisfied, coreq_warnings = evaluate_rule(
                    coreq_expr, current_and_completed, local_uos_metadata
                )

                soft_msg = None
                if coreq_warnings:
                    soft_msg = f"Soft warning(s): {', '.join(coreq_warnings)}"

                missing_coreqs = extract_failing_units(
                    coreq_expr, current_and_completed
                )
                if not satisfied:
                    warnings.append(
                        WarningDetail(
                            type="coreq_unmet",
                            unit_code=code,
                            year=year,
                            term=term,
                            message=f"Corequisite unmet for {code}: Requires concurrent enrolment in corequisite UoS.",
                            soft_warning=soft_msg,
                            affected_codes=missing_coreqs or None,
                        )
                    )
                elif soft_msg:
                    # Check if soft warning should escalate to hard
                    from api.validation.escalation import should_escalate, EscalationContext

                    escalation_context = EscalationContext(
                        completed_units=current_and_completed,
                        rule_node=coreq_expr.get("rule"),
                        rule_satisfied=satisfied,
                        attached_warnings=coreq_warnings,
                    )

                    if should_escalate(escalation_context, coreq_warnings):
                        # Escalate to hard warning
                        missing_coreqs = extract_failing_units(coreq_expr, current_and_completed)
                        warnings.append(
                            WarningDetail(
                                type="coreq_unmet",
                                unit_code=code,
                                year=year,
                                term=term,
                                message=f"Corequisite unmet for {code}: {soft_msg}",
                                soft_warning=soft_msg,
                                affected_codes=missing_coreqs or None,
                            )
                        )
                    else:
                        # Keep as soft warning
                        warnings.append(
                            WarningDetail(
                                type="coreq_unmet",
                                unit_code=code,
                                year=year,
                                term=term,
                                message=f"Advisory check for {code}: {soft_msg}",
                                soft_warning=soft_msg,
                            )
                        )
            elif is_coreq_unparsed:
                soft_msg = f"Advisory check for {code}: Corequisite requires manual review: {raw_coreq}"
                warnings.append(
                    WarningDetail(
                        type="coreq_unmet",
                        unit_code=code,
                        year=year,
                        term=term,
                        message=soft_msg,
                        soft_warning=soft_msg,
                    )
                )

            # Check E: Prerequisites
            prereq_expr = unit_rule.get("prerequisites_expr")
            raw_prereq = (
                unit_rule.get("raw_rules", {}).get("prerequisites")
                if unit_rule
                else None
            )
            is_unparsed = (
                prereq_expr
                and (
                    prereq_expr.get("curation_validity") == "needs_manual_review"
                    or prereq_expr.get("type") == "none"
                )
                and raw_prereq
                and raw_prereq.strip().lower() not in ["", "none", "none."]
            )

            if prereq_expr and prereq_expr.get("type") != "none" and not is_unparsed:
                satisfied, prereq_warnings = evaluate_rule(
                    prereq_expr, completed_units, local_uos_metadata
                )

                soft_msg = None
                if prereq_warnings:
                    soft_msg = f"Soft warning(s): {', '.join(prereq_warnings)}"

                missing_prereqs = extract_failing_units(prereq_expr, completed_units)
                if not satisfied:
                    warnings.append(
                        WarningDetail(
                            type="prereq_unmet",
                            unit_code=code,
                            year=year,
                            term=term,
                            message=f"Prerequisite unmet for {code}: Requires completing preceding units first.",
                            soft_warning=soft_msg,
                            affected_codes=missing_prereqs or None,
                        )
                    )
                elif soft_msg:
                    # Check if soft warning should escalate to hard
                    from api.validation.escalation import should_escalate, EscalationContext

                    escalation_context = EscalationContext(
                        completed_units=completed_units,
                        rule_node=prereq_expr.get("rule"),
                        rule_satisfied=satisfied,
                        attached_warnings=prereq_warnings,
                    )

                    if should_escalate(escalation_context, prereq_warnings):
                        # Escalate to hard warning
                        missing_prereqs = extract_failing_units(prereq_expr, completed_units)
                        warnings.append(
                            WarningDetail(
                                type="prereq_unmet",
                                unit_code=code,
                                year=year,
                                term=term,
                                message=f"Prerequisite unmet for {code}: {soft_msg}",
                                soft_warning=soft_msg,
                                affected_codes=missing_prereqs or None,
                            )
                        )
                    else:
                        # Keep as soft warning
                        warnings.append(
                            WarningDetail(
                                type="prereq_unmet",
                                unit_code=code,
                                year=year,
                                term=term,
                                message=f"Advisory check for {code}: {soft_msg}",
                                soft_warning=soft_msg,
                            )
                        )
            elif is_unparsed:
                soft_msg = f"Advisory check for {code}: Prerequisite requires manual review: {raw_prereq}"
                warnings.append(
                    WarningDetail(
                        type="prereq_unmet",
                        unit_code=code,
                        year=year,
                        term=term,
                        message=soft_msg,
                        soft_warning=soft_msg,
                    )
                )

        # Update completed pool for next term blocks
        completed_units.update(codes)

    # valid is False if there are any requisite failures that are not soft warnings (Advisory checks)
    valid = not any(
        w.type in ["prereq_unmet", "coreq_unmet", "prohibited"]
        and not w.message.startswith("Advisory check")
        for w in warnings
    )

    return ValidationResponse(valid=valid, warnings=warnings)
