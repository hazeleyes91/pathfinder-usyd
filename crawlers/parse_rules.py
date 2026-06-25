# crawlers/parse_rules.py
import json
import os
import asyncio
from crawlers.config import DATA_DIR
from crawlers.rule_parser_regex import parse_rules_with_regex
from crawlers.rule_parser_ai import parse_rules_with_ai

async def parse_rule_field(text: str, field_name: str, unit_code: str, has_keys: bool) -> tuple[dict, bool]:
    """
    Parses a single rule string. Returns (parsed_dict, needs_curation).
    """
    # 1. Try regex parser first
    regex_res = parse_rules_with_regex(text)
    if regex_res is not None:
        return regex_res, False
        
    # 2. Fall back to AI if complex
    if not has_keys:
        # If no keys, we cannot perform actual AI parsing
        print(f"[{unit_code}] {field_name} requires AI parsing but API keys are missing. Tagging for curation.")
        # Run through rule_parser_ai (will use TestModel) to ensure execution path succeeds
        ai_res = await parse_rules_with_ai(text)
        return ai_res.model_dump(), True
        
    print(f"[{unit_code}] Parsing complex {field_name} rule using AI: '{text}'")
    ai_res = await parse_rules_with_ai(text)
    
    # Cooldown to respect Free Tier limit (15 requests per minute = 1 request every 4 seconds)
    await asyncio.sleep(4.0)
    
    # Check if AI successfully parsed (we consider 'none' as success for empty/none text,
    # but if it was non-empty and AI returned none or failed, we flag it)
    if ai_res.type == "none" and text.strip().lower() not in ["none", "none.", ""]:
        return ai_res.model_dump(), True
        
    return ai_res.model_dump(), False

async def parse_all_rules(year: int = 2026):
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
    for unit in units:
        code = unit["unit_code"]
        
        prereqs_text = unit.get("prerequisites_text", "None")
        coreqs_text = unit.get("corequisites_text", "None")
        prohibitions_text = unit.get("prohibitions_text", "None")
        
        # Check if we can reuse the existing parsed entry to avoid API limits
        if code in existing_db:
            entry = existing_db[code]
            raw = entry.get("raw_rules", {})
            if (raw.get("prerequisites") == prereqs_text and
                raw.get("corequisites") == coreqs_text and
                raw.get("prohibitions") == prohibitions_text and
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
        
        p_expr, p_curate = await parse_rule_field(prereqs_text, "Prerequisites", code, has_keys)
        c_expr, c_curate = await parse_rule_field(coreqs_text, "Corequisites", code, has_keys)
        n_expr, n_curate = await parse_rule_field(prohibitions_text, "Prohibitions", code, has_keys)
        
        needs_curation = p_curate or c_curate or n_curate
        
        rule_entry = {
            "unit_code": code,
            "title": unit["title"],
            "prerequisites_expr": p_expr,
            "corequisites_expr": c_expr,
            "prohibitions_expr": n_expr,
            "needs_curation": needs_curation,
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
    asyncio.run(parse_all_rules(2026))
