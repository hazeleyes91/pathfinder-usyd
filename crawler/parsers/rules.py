# parsers/rules.py
import json
import os
import asyncio
import sys
import re
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from config import DATA_DIR, DEFAULT_TARGET_YEAR
from parsers.rule_regex import parse_rules_with_regex
from parsers.rule_ai import parse_rules_with_ai
from parsers.rule_preprocess import parse_rules_with_preprocess
from parsers.schemas import ParserWarning, CurationValidity

def log_ai_rule_attempt(unit_code: str, field_name: str, text: str, parsed_output: dict):
    log_path = DATA_DIR / "ai_rules_log.json"
    log_data = []
    if log_path.exists():
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                log_data = json.load(f)
        except Exception:
            pass
    log_data.append({
        "unit_code": unit_code,
        "field_name": field_name,
        "raw_text": text,
        "parsed_output": parsed_output
    })
    try:
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(log_data, f, indent=2)
    except Exception as e:
        print(f"Failed to write to AI rules log: {e}")

def wrap_and_detect_warnings(raw_text: str, parsed_node: dict, needs_curation: bool) -> dict:
    warns = []
    text_lower = raw_text.lower() if raw_text else ""
    
    # Check words using regex word boundaries at the start to allow prefixes (e.g. "candidat" matches "candidate") while avoiding middle substring matches (e.g. "BHSC" doesn't match "hsc")
    def has_word_match(words: list[str]) -> bool:
        if not text_lower:
            return False
        pattern = r'\b(' + '|'.join(re.escape(w) for w in words) + r')'
        return bool(re.search(pattern, text_lower))
    
    # 1. Degree/Program Enrollment Restrictions
    if has_word_match(["enroll", "admit", "candidat", "stream", "major", "specialis", "bachelor", "master", "program", "degree"]):
        warns.append(ParserWarning.DEGREE_RESTRICTION)
        
    # 2. Grade/Performance Thresholds
    if has_word_match(["wam", "gpa", "mark", "average", "grade", "%", "percent", "distinction", "credit", "pass", "fail"]):
        warns.append(ParserWarning.GRADE_THRESHOLD)
        
    # 3. Academic Level / Year Constraints
    if has_word_match(["1000", "2000", "3000", "4000", "5000", "intermediate", "senior", "junior", "year"]) or re.search(r'\blevel \d\b', text_lower):
        warns.append(ParserWarning.LOGIC_SIMPLIFIED)
        
    # 4. Departmental / Instructor Permission
    if has_word_match(["permission", "consent", "approval", "head", "instructor", "department", "coordinator"]):
        warns.append(ParserWarning.PERMISSION_REQUIRED)
        
    # 5. Assumed Knowledge / HSC
    if has_word_match(["hsc", "assumed", "knowledge", "recommended"]):
        warns.append(ParserWarning.RECOMMENDED_PREPARATION)
        
    warnings_list = list(set(warns)) if warns else None
    root_type = parsed_node.get("type", "none") if parsed_node else "none"
    rule_content = None if root_type == "none" or not parsed_node else parsed_node
    validity = CurationValidity.NEEDS_MANUAL_REVIEW if needs_curation else CurationValidity.VALID_FOR_PLANNING
    
    return {
        "type": root_type,
        "rule": rule_content,
        "warnings": warnings_list,
        "curation_validity": validity
    }

async def parse_rule_field(text: str, field_name: str, unit_code: str, has_keys: bool, regex_only: bool = False, preproc_regex_only: bool = False) -> tuple[dict, bool]:
    """
    Parses a single rule string. Returns (parsed_dict, needs_curation).
    """
    # 1. Regex 1
    regex_res = parse_rules_with_regex(text)
    if regex_res is not None:
        return wrap_and_detect_warnings(text, regex_res, needs_curation=False), False
        
    if regex_only:
        print(f"[{unit_code}] {field_name} is complex — tagged for curation (regex-only mode).")
        return wrap_and_detect_warnings(text, None, needs_curation=True), True

    # 2. Preprocess Agent (run only if API keys are available)
    if has_keys:
        print(f"[{unit_code}] Preprocessing complex {field_name} rule: '{text}'")
        simplified_text = await parse_rules_with_preprocess(text)
        await asyncio.sleep(1.0)  # inter-call delay
        
        # Check if preprocessor discarded the rule
        if simplified_text.strip().upper() == "[CURATE]":
            print(f"[{unit_code}] {field_name} discarded by preprocess agent — tagged for curation.")
            return wrap_and_detect_warnings(text, None, needs_curation=True), True
            
        # 3. Regex 2
        regex_res2 = parse_rules_with_regex(simplified_text)
        if regex_res2 is not None:
            print(f"[{unit_code}] {field_name} resolved via Regex 2 after preprocessing: '{simplified_text}'")
            return wrap_and_detect_warnings(text, regex_res2, needs_curation=False), False
            
        if preproc_regex_only:
            print(f"[{unit_code}] {field_name} not matching Regex 2 after preprocessing (preproc-regex-only mode) — tagged for curation.")
            return wrap_and_detect_warnings(text, None, needs_curation=True), True
            
        # 4. AI Expert (run on preprocessed text)
        print(f"[{unit_code}] Parsing simplified {field_name} rule using AI Expert: '{simplified_text}'")
        ai_res = await parse_rules_with_ai(simplified_text)
        log_ai_rule_attempt(unit_code, field_name, text, ai_res.model_dump())
        await asyncio.sleep(5.0)  # cooldown sleep
        
        res_dict = ai_res.model_dump()
        # Ensure new schema fields exist
        if "warnings" not in res_dict:
            res_dict["warnings"] = None
        
        if ai_res.type == "none" and simplified_text.strip().lower() not in ["none", "none.", ""]:
            res_dict["curation_validity"] = CurationValidity.NEEDS_MANUAL_REVIEW
            return res_dict, True
            
        res_dict["curation_validity"] = CurationValidity.VALID_FOR_PLANNING
        return res_dict, False
    else:
        # Fall back to AI test model if no keys
        print(f"[{unit_code}] {field_name} requires AI parsing but API keys are missing. Tagging for curation.")
        ai_res = await parse_rules_with_ai(text)
        log_ai_rule_attempt(unit_code, field_name, text, ai_res.model_dump())
        res_dict = ai_res.model_dump()
        if "warnings" not in res_dict:
            res_dict["warnings"] = None
        res_dict["curation_validity"] = CurationValidity.NEEDS_MANUAL_REVIEW
        return res_dict, True

async def parse_all_rules(year: int = DEFAULT_TARGET_YEAR, max_units: int = None, regex_only: bool = True, preproc_regex_only: bool = False):
    input_path = DATA_DIR / "raw" / "json" / f"parsed_units_{year}.json"
    output_path = DATA_DIR / f"parsed_rules_{year}.json"
    
    if not input_path.exists():
        print(f"Input file not found: {input_path}")
        return
        
    with open(input_path, "r", encoding="utf-8") as f:
        units = json.load(f)
        
    # Check if API keys are configured
    has_keys = bool(os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY"))
    if not has_keys:
        print("WARNING: No GEMINI_API_KEY or OPENAI_API_KEY found. Complex rules will be flagged for manual curation.")
        
    # Load existing parsed database if it exists
    existing_db = {}
    if output_path.exists():
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                existing_db = json.load(f)
            print(f"Loaded {len(existing_db)} existing parsed rules for incremental parsing.")
        except Exception as e:
            print(f"Could not load existing parsed rules: {e}")

    parsed_rules_db = {}
    curation_needed_list = []
    
    # Run sequentially to ensure stable execution
    units_to_process = units
    if max_units is not None:
        units_to_process = units[:max_units]
        print(f"Applying unit limit: processing first {max_units} of {len(units)} units.")
    
    for unit in units_to_process:
        code = unit["unit_code"]
        
        prereqs_text = unit.get("prerequisites_text", "None")
        coreqs_text = unit.get("corequisites_text", "None")
        prohibitions_text = unit.get("prohibitions_text", "None")
        
        # Check if we can reuse the existing parsed entry to avoid API limits
        # We only reuse if the entry contains the new schema keys 'curation_validity'
        if code in existing_db:
            entry = existing_db[code]
            raw = entry.get("raw_rules", {})
            if (raw.get("prerequisites") == prereqs_text and
                raw.get("corequisites") == coreqs_text and
                raw.get("prohibitions") == prohibitions_text and
                "curation_validity" in entry.get("prerequisites_expr", {}) and
                (not entry.get("needs_curation") or not has_keys)):
                
                parsed_rules_db[code] = entry
                if entry.get("needs_curation"):
                    curation_needed_list.append({
                        "unit_code": code,
                        "prerequisites": prereqs_text,
                        "corequisites": coreqs_text,
                        "prohibitions": prohibitions_text
                    })
                print(f"Skipping {code} (reusing cached parsed rules).")
                continue

        print(f"Processing rules for {code}...")
        
        p_expr, p_curate = await parse_rule_field(prereqs_text, "Prerequisites", code, has_keys, regex_only, preproc_regex_only)
        if not regex_only:
            await asyncio.sleep(1.0)
        c_expr, c_curate = await parse_rule_field(coreqs_text, "Corequisites", code, has_keys, regex_only, preproc_regex_only)
        if not regex_only:
            await asyncio.sleep(1.0)
        n_expr, n_curate = await parse_rule_field(prohibitions_text, "Prohibitions", code, has_keys, regex_only, preproc_regex_only)
        
        needs_curation = p_curate or c_curate or n_curate
        flagged = existing_db.get(code, {}).get("flagged", False)
        
        rule_entry = {
            "unit_code": code,
            "title": unit["title"],
            "prerequisites_expr": p_expr,
            "corequisites_expr": c_expr,
            "prohibitions_expr": n_expr,
            "needs_curation": needs_curation,
            "flagged": flagged,
            "raw_rules": {
                "prerequisites": prereqs_text,
                "corequisites": coreqs_text,
                "prohibitions": prohibitions_text
            }
        }
        
        parsed_rules_db[code] = rule_entry
        if needs_curation:
            curation_needed_list.append({
                "unit_code": code,
                "prerequisites": prereqs_text,
                "corequisites": coreqs_text,
                "prohibitions": prohibitions_text
            })
            
    # Serialize results
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(parsed_rules_db, f, indent=2)
    print(f"Successfully wrote parsed rules to {output_path}")
    
    # Write curation file
    curation_path = DATA_DIR / f"rules_needing_curation_{year}.json"
    with open(curation_path, "w", encoding="utf-8") as f:
        json.dump(curation_needed_list, f, indent=2)
    print(f"Wrote {len(curation_needed_list)} rules needing curation to {curation_path}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Parse prerequisite/corequisite/prohibition rules for all units")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of units to parse (default: all)")
    parser.add_argument("--year", type=int, default=DEFAULT_TARGET_YEAR, help="Target academic year (default: dynamic)")
    parser.add_argument("--use-ai", action="store_true", help="Enable AI parsing agent fallback for complex rules")
    parser.add_argument("--preproc-regex-only", action="store_true", help="Bypass AI Expert, check only if Regex 2 parses preprocessed output")
    args = parser.parse_args()
    asyncio.run(parse_all_rules(
        year=args.year, 
        max_units=args.limit, 
        regex_only=not args.use_ai, 
        preproc_regex_only=args.preproc_regex_only
    ))
