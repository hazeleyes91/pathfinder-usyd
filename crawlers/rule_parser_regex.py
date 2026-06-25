# crawlers/rule_parser_regex.py
import re

def parse_rules_with_regex(rule_text: str) -> dict | None:
    """
    Tries to parse raw prerequisite text into structured logic using Regex.
    Returns a dictionary if successfully parsed, or None if too complex (requires AI).
    """
    clean_text = rule_text.strip().rstrip(".")
    
    # 1. Check for "None"
    if clean_text.lower() in ["none", "none.", "none (including advanced versions)", ""]:
        return {"type": "none"}
        
    # 2. Check for a single unit code (e.g. COMP2123)
    if re.match(r"^[A-Z]{4}\d{4}$", clean_text, re.IGNORECASE):
        return {
            "type": "unit",
            "unit_code": clean_text.upper()
        }
        
    # 3. Check for a pure "OR" sequence (e.g. INFO1110 or INFO1910)
    or_tokens = [t.strip() for t in re.split(r"\s+or\s+", clean_text, flags=re.IGNORECASE)]
    if len(or_tokens) > 1 and all(re.match(r"^[A-Z]{4}\d{4}$", t) for t in or_tokens):
        return {
            "type": "logical",
            "operator": "OR",
            "operands": [{"type": "unit", "unit_code": t.upper()} for t in or_tokens]
        }
        
    # 4. Check for a pure "AND" sequence (e.g. COMP2123 and MATH1064)
    and_tokens = [t.strip() for t in re.split(r"\s+and\s+", clean_text, flags=re.IGNORECASE)]
    if len(and_tokens) > 1 and all(re.match(r"^[A-Z]{4}\d{4}$", t) for t in and_tokens):
        return {
            "type": "logical",
            "operator": "AND",
            "operands": [{"type": "unit", "unit_code": t.upper()} for t in and_tokens]
        }
        
    # Too complex for simple regex
    return None

if __name__ == "__main__":
    # Sample Test run
    test_cases = [
        "None",
        "COMP2123",
        "INFO1110 or INFO1910 or INFO1113",
        "COMP2123 and MATH1064",
        "(COMP2123 or COMP2823) and 12cp of 3000-level COMP"
    ]
    for case in test_cases:
        res = parse_rules_with_regex(case)
        print(f"Text: '{case}' -> Result: {res}")
