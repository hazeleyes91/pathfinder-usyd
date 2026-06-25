import json
import re
from pathlib import Path
from bs4 import BeautifulSoup
from crawlers.config import DATA_DIR, RAW_HTML_DIR

def get_table_value(soup: BeautifulSoup, label_pattern: str) -> str:
    """
    Locates a <th> tag matching the pattern and returns its sibling <td> text.
    """
    for th in soup.find_all("th"):
        if re.search(label_pattern, th.text, re.IGNORECASE):
            td = th.find_next_sibling("td")
            if td:
                return td.text.strip()
    return "None"

def parse_unit_html(file_path: Path) -> dict:
    """
    Parses a single cached HTML file and extracts unit data.
    """
    unit_code = file_path.stem  # Stem extracts filename without extension (e.g. 'COMP2123')
    
    with open(file_path, "r", encoding="utf-8") as f:
        html = f.read()
        
    soup = BeautifulSoup(html, "html.parser")
    
    # 1. Extract and clean Title
    title_div = soup.find(id="page-title-container")
    title = "Unknown Title"
    if title_div:
        title_text = title_div.text.strip()
        if ":" in title_text:
            title = title_text.split(":", 1)[1].strip()
        else:
            title = title_text

    # 2. Extract and cast Credit Points
    cp_text = get_table_value(soup, "Credit points")
    try:
        # Extract digits in case it says "6 cp" or similar
        cp_match = re.search(r"(\d+)", cp_text)
        credit_points = int(cp_match.group(1)) if cp_match else 6
    except Exception:
        credit_points = 6
        
    # 3. Extract Metadata and Rules
    study_level = get_table_value(soup, "Study level")
    academic_unit = get_table_value(soup, "Academic unit")
    prereqs = get_table_value(soup, "Prerequisites")
    coreqs = get_table_value(soup, "Corequisites")
    prohibitions = get_table_value(soup, "Prohibitions")
    assumed_knowledge = get_table_value(soup, "Assumed knowledge")
    
    # 4. Construct response dictionary matching uos_spec.md
    return {
        "unit_code": unit_code,
        "title": title,
        "credit_points": credit_points,
        "level": study_level,
        "academic_unit": academic_unit,
        "prerequisites_text": prereqs,
        "corequisites_text": coreqs,
        "prohibitions_text": prohibitions,
        "assumed_knowledge_text": assumed_knowledge,
        "status": "ACTIVE"
    }

def parse_all_cached_units(year: int = 2026):
    """
    Iterates through all raw HTML files for the year, parses them,
    and saves the collected list to a JSON file.
    """
    html_dir = RAW_HTML_DIR / str(year)
    if not html_dir.exists():
        print(f"Directory {html_dir} does not exist.")
        return
        
    parsed_units = []
    # Loop over all .html files in the directory
    for html_file in html_dir.glob("*.html"):
        print(f"Parsing {html_file.name}...")
        try:
            unit_data = parse_unit_html(html_file)
            parsed_units.append(unit_data)
        except Exception as e:
            print(f"Failed to parse {html_file.name}: {e}")
            
    # Define target path: data/raw/json/parsed_units_{year}.json
    out_dir = DATA_DIR / "raw" / "json"
    out_dir.mkdir(parents=True, exist_ok=True)
    target_path = out_dir / f"parsed_units_{year}.json"
    
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(parsed_units, f, indent=2)
        
    print(f"Successfully serialized {len(parsed_units)} units to {target_path}")

if __name__ == "__main__":
    parse_all_cached_units(2026)
