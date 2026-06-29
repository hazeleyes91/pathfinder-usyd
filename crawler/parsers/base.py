import json
import re
import sys
from pathlib import Path
from bs4 import BeautifulSoup
sys.path.append(str(Path(__file__).resolve().parents[1]))
from config import DATA_DIR, RAW_HTML_DIR, DEFAULT_TARGET_YEAR

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
        
    # Check for discontinued placeholder marker
    if '<div id="status">DISCONTINUED</div>' in html:
        return {
            "unit_code": unit_code,
            "title": "Discontinued Unit",
            "credit_points": 6,
            "level": "Unknown",
            "academic_unit": "Unknown",
            "prerequisites_text": "None",
            "corequisites_text": "None",
            "prohibitions_text": "None",
            "assumed_knowledge_text": "None",
            "status": "INACTIVE",
            "resolved_year": None
        }
        
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
    
    # Parse resolved year from text
    year_element = soup.find(string=re.compile(r"\d{4} unit information"))
    resolved_year = None
    if year_element:
        match = re.search(r"(\d{4})", year_element)
        if match:
            resolved_year = int(match.group(1))
            
    # Check for explicit discontinued text in HTML
    status = "ACTIVE"
    html_lower = html.lower()
    if "this unit of study is discontinued" in html_lower or "discontinued unit" in html_lower:
        status = "INACTIVE"
    
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
        "status": status,
        "resolved_year": resolved_year
    }

def parse_all_cached_units(year: int = DEFAULT_TARGET_YEAR, incremental: bool = False) -> None:
    """
    Iterates through all raw HTML files for the year, parses them,
    and saves the collected list to a JSON file.
    """
    html_dir = RAW_HTML_DIR / str(year)
    if not html_dir.exists():
        print(f"Directory {html_dir} does not exist.")
        return
        
    existing_units = {}
    out_dir = DATA_DIR / "raw" / "json"
    out_dir.mkdir(parents=True, exist_ok=True)
    target_path = out_dir / f"parsed_units_{year}.json"
    
    if incremental and target_path.exists():
        try:
            with open(target_path, "r", encoding="utf-8") as f:
                for u in json.load(f):
                    existing_units[u["unit_code"]] = u
            print(f"Loaded {len(existing_units)} existing parsed units for incremental parsing.")
        except Exception as e:
            print(f"Failed to load existing parsed units for incremental parsing: {e}")
            
    parsed_units = []
    # Loop over all .html files in the directory
    for html_file in html_dir.glob("*.html"):
        unit_code = html_file.stem
        if incremental and unit_code in existing_units:
            parsed_units.append(existing_units[unit_code])
            continue
            
        print(f"Parsing {html_file.name}...")
        try:
            unit_data = parse_unit_html(html_file)
            
            # Compare resolved year against the target year to mark status as INACTIVE if older
            res_yr = unit_data.get("resolved_year")
            if res_yr is not None and res_yr < year:
                unit_data["status"] = "INACTIVE"
                
            parsed_units.append(unit_data)
        except Exception as e:
            print(f"Failed to parse {html_file.name}: {e}")
            
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(parsed_units, f, indent=2)
        
    print(f"Successfully serialized {len(parsed_units)} units to {target_path}")

if __name__ == "__main__":
    parse_all_cached_units(DEFAULT_TARGET_YEAR)
