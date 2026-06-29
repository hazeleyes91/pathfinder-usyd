import time
import json
import requests
import re
import sys
from bs4 import BeautifulSoup
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))
from config import DATA_DIR, RAW_HTML_DIR, RAW_JSON_DIR, DETAIL_URL_TEMPLATE, REQUEST_DELAY_SECONDS, DEFAULT_TARGET_YEAR

def load_target_codes() -> list[str]:
    """Reads data/raw/json/unit_codes.json and returns a list of codes."""
    target_path = RAW_JSON_DIR / "unit_codes.json"
    if not target_path.exists():
        print(f"Warning: {target_path} not found. Returning empty list.")
        return []
    with open(target_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        if isinstance(data, dict):
            return list(data.keys())
        return data

def fetch_and_cache_unit(unit_code: str, target_year: int = DEFAULT_TARGET_YEAR, force_fetch: bool = False, session = None) -> tuple[bool, int | None]:
    """
    Fetches the direct unit page, parses the academic year, and caches the HTML content.
    """
    target_dir = RAW_HTML_DIR / str(target_year)
    target_path = target_dir / f"{unit_code}.html"
    
    if target_path.exists() and not force_fetch:
        # Check if the cached file is a discontinued placeholder
        try:
            with open(target_path, "r", encoding="utf-8") as f:
                content = f.read()
                if "DISCONTINUED" in content:
                    return True, target_year
                soup = BeautifulSoup(content, "html.parser")
                year_element = soup.find(string=re.compile(r"\d{4} unit information"))
                if year_element:
                    match = re.search(r"(\d{4})", year_element)
                    if match:
                        return True, int(match.group(1))
        except Exception:
            pass
        return True, target_year

    url = DETAIL_URL_TEMPLATE.format(unit_code=unit_code)
    print(f"Fetching {unit_code} from {url}...")
    
    try:
        if session:
            response = session.get(url, allow_redirects=True, timeout=15)
        else:
            response = requests.get(url, allow_redirects=True, timeout=15)
        
        # Validate soft 404 redirection / missing text content
        is_soft_404 = (
            response.status_code != 200 or 
            "/errors/404.html" in response.url or
            "not available" in response.text.lower() or
            "under development" in response.text.lower()
        )
        if is_soft_404:
            print(f"Error: Unit code {unit_code} not found (Soft 404). Saving discontinued placeholder.")
            target_dir = RAW_HTML_DIR / str(target_year)
            target_dir.mkdir(parents=True, exist_ok=True)
            target_path = target_dir / f"{unit_code}.html"
            with open(target_path, "w", encoding="utf-8") as f:
                f.write('<html><body><div id="status">DISCONTINUED</div></body></html>')
            return True, target_year

        soup = BeautifulSoup(response.text, "html.parser")
        year_element = soup.find(string=re.compile(r"\d{4} unit information"))

        resolved_year = target_year  # Establish default fallback
        if year_element:
            # Extract the 4-digit year string from the text node
            match = re.search(r"(\d{4})", year_element)
            if match:
                resolved_year = int(match.group(1))
                
        target_dir = RAW_HTML_DIR / str(target_year)
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"{unit_code}.html"

        with open(target_path, "w", encoding="utf-8") as f:
            f.write(response.text)
            
        print(f"Cached outline to: {target_path} (resolved: {resolved_year})")
        return True, resolved_year
    except Exception as e:
        print(f"Network or parsing exception for {unit_code}: {e}")
        return False, None

def discover_and_crawl_dependencies(target_year: int = DEFAULT_TARGET_YEAR, force_fetch: bool = False, session = None, max_iterations: int = 5, log_callback = print) -> int:
    """
    Scans data/raw/json/parsed_units_{year}.json for any referenced unit codes in rule texts.
    If those units are not cached in data/raw/html/{year}/, fetches them on demand.
    Repeats recursively up to max_iterations.
    Returns total number of new units fetched.
    """
    from parsers.base import parse_all_cached_units
    
    total_fetched = 0
    parsed_json_path = DATA_DIR / "raw" / "json" / f"parsed_units_{target_year}.json"
    html_dir = RAW_HTML_DIR / str(target_year)
    code_pattern = re.compile(r"\b[A-Z]{4}\d{4}\b")
    
    for iteration in range(1, max_iterations + 1):
        if not parsed_json_path.exists():
            log_callback(f"Parsed units file not found at {parsed_json_path}. Skipping dependency check.")
            break
            
        with open(parsed_json_path, "r", encoding="utf-8") as f:
            try:
                units = json.load(f)
            except Exception as e:
                log_callback(f"Failed to load parsed units JSON: {e}")
                break
                
        # 1. Gather all currently cached/known units
        cached_codes = set(p.stem for p in html_dir.glob("*.html"))
        
        # 2. Extract referenced codes
        referenced_codes = set()
        for u in units:
            for field in ["prerequisites_text", "corequisites_text", "prohibitions_text", "assumed_knowledge_text"]:
                text = u.get(field, "")
                if text:
                    for match in code_pattern.findall(text):
                        referenced_codes.add(match)
                        
        # 3. Identify missing codes
        missing_codes = sorted(list(referenced_codes - cached_codes))
        if not missing_codes:
            log_callback(f"No missing unit dependencies found (iteration {iteration}).")
            break
            
        log_callback(f"Iteration {iteration}: Found {len(missing_codes)} missing referenced unit dependencies: {', '.join(missing_codes[:10])}...")
        
        iteration_fetched = 0
        for code in missing_codes:
            # Check cache again just in case
            if (html_dir / f"{code}.html").exists() and not force_fetch:
                continue
            success, _ = fetch_and_cache_unit(code, target_year, force_fetch=force_fetch, session=session)
            if success:
                iteration_fetched += 1
                total_fetched += 1
                
            # Rate limiting delay
            time.sleep(0.5)
            
        log_callback(f"Iteration {iteration} complete: Fetched {iteration_fetched} new units.")
        
        if iteration_fetched > 0:
            log_callback("Regenerating parsed units index with new dependencies...")
            parse_all_cached_units(target_year, incremental=True)
        else:
            # If no units were successfully fetched, break to avoid infinite loops
            break
            
    return total_fetched

if __name__ == "__main__":
    codes = load_target_codes()
    print(f"Loaded {len(codes)} codes from JSON index.")
    
    # Test subset including the missing index unit COMP2022
    test_subset = ["COMP2123", "COMP2022", "COMP2017", "COMP9123", "COMP4618"]
    
    for code in test_subset:
        success, resolved_year = fetch_and_cache_unit(code)
        time.sleep(REQUEST_DELAY_SECONDS)
