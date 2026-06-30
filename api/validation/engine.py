import sys
import os
import json
from pathlib import Path
from typing import List, Dict, Set, Any
from pydantic import TypeAdapter

# Sibling/Parent imports
sys.path.append(str(Path(__file__).resolve().parents[2]))
from api.models import ValidationRequest, WarningDetail, ValidationResponse
from api.validation.rules import evaluate_rule
from api.utils import match_wildcard, matches_pattern
from crawler.config import DATA_DIR, DEFAULT_TARGET_YEAR

# Load the database target year
TARGET_YEAR = int(os.getenv("PORTAL_YEAR", DEFAULT_TARGET_YEAR))

# Load DBs
RULES_DB: Dict[str, Any] = {}
UOS_METADATA: Dict[str, Any] = {}

rules_db_path = DATA_DIR / f"parsed_rules_{TARGET_YEAR}.json"
if rules_db_path.exists():
    with open(rules_db_path, "r", encoding="utf-8") as f:
        RULES_DB = json.load(f)

parsed_units_path = DATA_DIR / "raw" / "json" / f"parsed_units_{TARGET_YEAR}.json"
if parsed_units_path.exists():
    with open(parsed_units_path, "r", encoding="utf-8") as f:
        for u in json.load(f):
            UOS_METADATA[u["unit_code"]] = u

# Cache the availability list to avoid re-parsing HTML repeatedly
AVAILABILITY_CACHE: Dict[str, List[str]] = {}

def get_availability(unit_code: str) -> List[str]:
    if unit_code in AVAILABILITY_CACHE:
        return AVAILABILITY_CACHE[unit_code]
        
    # Check if we have it in HTML
    html_path = DATA_DIR / "raw" / "html" / str(TARGET_YEAR) / f"{unit_code}.html"
    from bs4 import BeautifulSoup
    
    if not html_path.exists():
        # Fallback to metadata if any, or default
        avail = UOS_METADATA.get(unit_code, {}).get("avail", ["sem1", "sem2"])
        AVAILABILITY_CACHE[unit_code] = avail
        return avail
        
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f.read(), "html.parser")
            
        status_div = soup.find(id="status")
        if status_div and status_div.text.strip() == "DISCONTINUED":
            AVAILABILITY_CACHE[unit_code] = []
            return []
            
        sessions = set()
        for table in soup.find_all("table"):
            headers = [th.text.strip().lower() for th in table.find_all(["th", "td"])]
            if not headers or "session" not in headers[0]:
                continue
                
            for tr in table.find_all("tr")[1:]:
                cells = [td.text.strip() for td in tr.find_all(["td", "th"])]
                if not cells:
                    continue
                session_text = cells[0]
                if str(TARGET_YEAR) in session_text:
                    s_lower = session_text.lower()
                    if "semester 1" in s_lower or "s1" in s_lower or "january" in s_lower or "february" in s_lower or "march" in s_lower or "april" in s_lower or "may" in s_lower:
                        if "january" in s_lower or "february" in s_lower or "summer" in s_lower:
                            sessions.add("summ")
                        else:
                            sessions.add("sem1")
                    elif "semester 2" in s_lower or "s2" in s_lower or "july" in s_lower or "august" in s_lower or "september" in s_lower or "october" in s_lower or "november" in s_lower or "december" in s_lower:
                        if "july" in s_lower or "winter" in s_lower:
                            sessions.add("wint")
                        else:
                            sessions.add("sem2")
                    elif "winter" in s_lower or "june" in s_lower:
                        sessions.add("wint")
                    elif "summer" in s_lower:
                        sessions.add("summ")
                        
        if not sessions:
            avail = ["sem1", "sem2"]
        else:
            avail = sorted(list(sessions))
            
        AVAILABILITY_CACHE[unit_code] = avail
        return avail
    except Exception:
        AVAILABILITY_CACHE[unit_code] = ["sem1", "sem2"]
        return ["sem1", "sem2"]

def run_validation(request: ValidationRequest) -> ValidationResponse:
    warnings = []
    
    # 1. Chronological Sorting of Placements
    term_order = {"summ": 0, "sem1": 1, "wint": 2, "sem2": 3}
    
    sorted_placements = sorted(
        request.placements,
        key=lambda p: p.year * 10 + term_order.get(p.term, 0)
    )
    
    # Build complete plan pool of UoS codes
    all_planned_units = set()
    for placement in request.placements:
        all_planned_units.update(placement.codes)
        
    completed_units = set()
    
    for placement in sorted_placements:
        year = placement.year
        term = placement.term
        codes = placement.codes
        
        # Check A: Term CP Overload
        term_cp = 0
        for code in codes:
            cp = UOS_METADATA.get(code, {}).get("credit_points", 6)
            term_cp += cp
            
        overload_limit = 12 if term in ["summ", "wint"] else 24
        if term_cp > overload_limit:
            warnings.append(WarningDetail(
                type="overload",
                year=year,
                term=term,
                message=f"Semester overload: Year {year} {term} load of {term_cp} CP exceeds standard {overload_limit} CP limit."
            ))
            
        # Check individual UoS rules in the current term block
        for code in codes:
            unit_rule = RULES_DB.get(code, {})
            
            # Check B: Session Availability Mismatch
            avail = get_availability(code)
            if term not in avail:
                warnings.append(WarningDetail(
                    type="session_mismatch",
                    unit_code=code,
                    year=year,
                    term=term,
                    message=f"Availability mismatch: {code} is not offered in {term}."
                ))
                
            # Check C: Prohibitions
            prohib_expr = unit_rule.get("prohibitions_expr")
            if prohib_expr and prohib_expr.get("type") != "none":
                prohibited_satisfied, prohib_warnings = evaluate_rule(prohib_expr, all_planned_units, UOS_METADATA)
                if prohibited_satisfied:
                    warnings.append(WarningDetail(
                        type="prohibited",
                        unit_code=code,
                        year=year,
                        term=term,
                        message=f"Prohibition conflict: {code} cannot be taken alongside prohibited units in this plan."
                    ))
            
            # Check D: Corequisites
            coreq_expr = unit_rule.get("corequisites_expr")
            raw_coreq = unit_rule.get("raw_rules", {}).get("corequisites") if unit_rule else None
            is_coreq_unparsed = coreq_expr and (coreq_expr.get("curation_validity") == "needs_manual_review" or coreq_expr.get("type") == "none") and raw_coreq and raw_coreq.strip().lower() not in ["", "none", "none."]
            
            if coreq_expr and coreq_expr.get("type") != "none":
                current_and_completed = completed_units.union(set(codes))
                satisfied, coreq_warnings = evaluate_rule(coreq_expr, current_and_completed, UOS_METADATA)
                
                soft_msg = None
                if coreq_warnings:
                    soft_msg = f"Soft warning(s): {', '.join(coreq_warnings)}"
                    
                if not satisfied:
                    warnings.append(WarningDetail(
                        type="coreq_unmet",
                        unit_code=code,
                        year=year,
                        term=term,
                        message=f"Corequisite unmet for {code}: Requires concurrent enrolment in corequisite UoS.",
                        soft_warning=soft_msg
                    ))
                elif soft_msg:
                    warnings.append(WarningDetail(
                        type="coreq_unmet",
                        unit_code=code,
                        year=year,
                        term=term,
                        message=f"Advisory check for {code}: {soft_msg}",
                        soft_warning=soft_msg
                    ))
            elif is_coreq_unparsed:
                soft_msg = f"Advisory check for {code}: Corequisite requires manual review: {raw_coreq}"
                warnings.append(WarningDetail(
                    type="coreq_unmet",
                    unit_code=code,
                    year=year,
                    term=term,
                    message=soft_msg,
                    soft_warning=soft_msg
                ))
                    
            # Check E: Prerequisites
            prereq_expr = unit_rule.get("prerequisites_expr")
            raw_prereq = unit_rule.get("raw_rules", {}).get("prerequisites") if unit_rule else None
            is_unparsed = prereq_expr and (prereq_expr.get("curation_validity") == "needs_manual_review" or prereq_expr.get("type") == "none") and raw_prereq and raw_prereq.strip().lower() not in ["", "none", "none."]
            
            if prereq_expr and prereq_expr.get("type") != "none":
                satisfied, prereq_warnings = evaluate_rule(prereq_expr, completed_units, UOS_METADATA)
                
                soft_msg = None
                if prereq_warnings:
                    soft_msg = f"Soft warning(s): {', '.join(prereq_warnings)}"
                    
                if not satisfied:
                    warnings.append(WarningDetail(
                        type="prereq_unmet",
                        unit_code=code,
                        year=year,
                        term=term,
                        message=f"Prerequisite unmet for {code}: Requires completing preceding units first.",
                        soft_warning=soft_msg
                    ))
                elif soft_msg:
                    warnings.append(WarningDetail(
                        type="prereq_unmet",
                        unit_code=code,
                        year=year,
                        term=term,
                        message=f"Advisory check for {code}: {soft_msg}",
                        soft_warning=soft_msg
                    ))
            elif is_unparsed:
                soft_msg = f"Advisory check for {code}: Prerequisite requires manual review: {raw_prereq}"
                warnings.append(WarningDetail(
                    type="prereq_unmet",
                    unit_code=code,
                    year=year,
                    term=term,
                    message=soft_msg,
                    soft_warning=soft_msg
                ))
                    
        # Update completed pool for next term blocks
        completed_units.update(codes)
        
    # valid is False if there are any requisite failures that are not soft warnings (Advisory checks)
    valid = not any(
        w.type in ["prereq_unmet", "coreq_unmet", "prohibited"] and not w.message.startswith("Advisory check")
        for w in warnings
    )
    
    return ValidationResponse(
        valid=valid,
        warnings=warnings
    )
