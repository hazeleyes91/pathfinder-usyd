import time
import json
import requests
import re
from bs4 import BeautifulSoup
from pathlib import Path
from config import DATA_DIR, RAW_HTML_DIR, RAW_JSON_DIR, DETAIL_URL_TEMPLATE, REQUEST_DELAY_SECONDS

def load_target_codes() -> list[str]:
    """Reads data/raw/json/unit_codes.json and returns a list of codes."""
    target_path = RAW_JSON_DIR / "unit_codes.json"
    if not target_path.exists():
        print(f"Warning: {target_path} not found. Returning empty list.")
        return []
    with open(target_path, "r", encoding="utf-8") as f:
        return json.load(f)

def fetch_and_cache_unit(unit_code: str) -> tuple[bool, int | None]:
    """
    Fetches the direct unit page, parses the academic year, and caches the HTML content.
    """
    url = DETAIL_URL_TEMPLATE.format(unit_code=unit_code)
    print(f"Fetching {unit_code} from {url}...")
    
    try:
        response = requests.get(url, allow_redirects=True, timeout=15)
        
        # Validate soft 404 redirection
        if response.status_code != 200 or "/errors/404.html" in response.url:
            print(f"Error: Unit code {unit_code} not found (Soft 404).")
            return False, None

        soup = BeautifulSoup(response.text, "html.parser")
        year_element = soup.find(string=re.compile(r"\d{4} unit information"))

        resolved_year = 2026  # Establish default fallback
        if year_element:
            # Extract the 4-digit year string from the text node
            match = re.search(r"(\d{4})", year_element)
            if match:
                resolved_year = int(match.group(1))
                
        target_dir = RAW_HTML_DIR / str(resolved_year)
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"{unit_code}.html"

        with open(target_path, "w", encoding="utf-8") as f:
            f.write(response.text)
            
        print(f"Cached outline to: {target_path}")
        return True, resolved_year
    except Exception as e:
        print(f"Network or parsing exception for {unit_code}: {e}")
        return False, None

if __name__ == "__main__":
    codes = load_target_codes()
    print(f"Loaded {len(codes)} codes from JSON index.")
    
    # Test subset including the missing index unit COMP2022
    test_subset = ["COMP2123", "COMP2022", "COMP2017", "COMP9123", "COMP4618"]
    
    for code in test_subset:
        success, resolved_year = fetch_and_cache_unit(code)
        time.sleep(REQUEST_DELAY_SECONDS)
