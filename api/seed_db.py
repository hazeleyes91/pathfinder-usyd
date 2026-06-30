import os
import json
import sqlite3
from pathlib import Path
from bs4 import BeautifulSoup

from crawler.config import DATA_DIR, DEFAULT_TARGET_YEAR
from api.database import get_db_connection

PORTAL_YEAR = int(os.getenv("PORTAL_YEAR", DEFAULT_TARGET_YEAR))

SESSION_MAPPING = {
    "semester 1": "S1",
    "semester 2": "S2",
    "intensive january": "S1CIJA",
    "intensive february": "S1CIFE",
    "intensive march": "S1CIMA",
    "intensive april": "S1CIAP",
    "intensive may": "S1CIMY",
    "intensive june": "S1CIJN",
    "intensive july": "S2CIJL",
    "intensive august": "S2CIAU",
    "intensive september": "S2CISE",
    "intensive october": "S2CIOC",
    "intensive november": "S2CINV",
    "intensive december": "S2CIDE",
    "winter": "Winter",
    "summer": "Summer"
}

def map_session_text_to_code(text: str) -> tuple[str, str]:
    text_lower = text.lower()
    for key, code in SESSION_MAPPING.items():
        if key in text_lower:
            return code, key.title()
    # Fallback to capitalizing the words
    return text, text

def get_tables_for_unit(unit_code: str) -> list[str]:
    prefix = unit_code[:4].upper()
    if prefix in ("COMP", "INFO", "DATA", "SOFT", "ISYS"):
        return ["Table A - Engineering", "Table A - Science", "Table S"]
    elif prefix in ("MATH", "STAT"):
        return ["Table A - Science", "Table S"]
    elif prefix in ("OLET", "OLEO", "OLES", "OINF"):
        return ["Table O - Open Learning Environment"]
    elif prefix in ("ELEC", "AERO", "CHNG", "CIVL", "MECH", "MTRX", "BMET", "PMGT", "ENGF", "ENVI", "ENVE"):
        return ["Table A - Engineering", "Table S"]
    elif prefix in ("ACCT", "BUSS", "CLAW", "ECMT", "ECON", "ECOS", "FINC", "IBUS", "MKTG", "QBUS", "WORK"):
        return ["Table A - Business", "Table S"]
    else:
        return ["Table S"]

def seed():
    print(f"Seeding database for target year {PORTAL_YEAR}...")
    
    parsed_units_path = DATA_DIR / "raw" / "json" / f"parsed_units_{PORTAL_YEAR}.json"
    parsed_rules_path = DATA_DIR / f"parsed_rules_{PORTAL_YEAR}.json"
    html_dir = DATA_DIR / "raw" / "html" / str(PORTAL_YEAR)
    
    if not parsed_units_path.exists():
        print(f"Error: {parsed_units_path} does not exist. Run crawler/parsers first.")
        return
    if not parsed_rules_path.exists():
        print(f"Error: {parsed_rules_path} does not exist. Run crawler/parsers first.")
        return
        
    with open(parsed_units_path, "r", encoding="utf-8") as f:
        units_list = json.load(f)
        
    with open(parsed_rules_path, "r", encoding="utf-8") as f:
        rules_map = json.load(f)
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Disable foreign keys temporarily for bulk delete/truncate, or just clear them
    cursor.execute("PRAGMA foreign_keys = OFF;")
    cursor.execute("DELETE FROM unit_tables;")
    cursor.execute("DELETE FROM unit_availabilities;")
    cursor.execute("DELETE FROM unit_rules;")
    cursor.execute("DELETE FROM units;")
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    units_to_insert = []
    rules_to_insert = []
    availabilities_to_insert = []
    tables_to_insert = []
    
    for u in units_list:
        unit_code = u["unit_code"]
        title = u.get("title", "Unknown Title")
        credit_points = int(u.get("credit_points", 6))
        
        # 1. Level mapping
        try:
            level = int(unit_code[4]) * 1000
        except (IndexError, ValueError):
            if u.get("level") == "Postgraduate":
                level = 9000
            else:
                level = 1000
                
        faculty = u.get("academic_unit", None)
        handbook_url = f"https://www.sydney.edu.au/units/{unit_code}"
        is_active = 1 if u.get("status") == "ACTIVE" else 0
        replaced_by_code = None
        is_special_topic = 0
        is_zero_cp = 1 if credit_points == 0 else 0
        is_year_long = 0
        is_external_placeholder = 0
        resolved_year = u.get("resolved_year", PORTAL_YEAR)
        
        units_to_insert.append((
            unit_code, title, credit_points, level, faculty, handbook_url,
            is_active, replaced_by_code, is_special_topic, is_zero_cp,
            is_year_long, is_external_placeholder, resolved_year
        ))
        
        # 2. Rules insertion details
        rule_entry = rules_map.get(unit_code, {})
        prereqs_text = u.get("prerequisites_text", "None")
        coreqs_text = u.get("corequisites_text", "None")
        prohibitions_text = u.get("prohibitions_text", "None")
        assumed_knowledge_text = u.get("assumed_knowledge_text", "None")
        
        prereqs_expr = json.dumps(rule_entry.get("prerequisites_expr")) if rule_entry.get("prerequisites_expr") else None
        coreqs_expr = json.dumps(rule_entry.get("corequisites_expr")) if rule_entry.get("corequisites_expr") else None
        prohibitions_expr = json.dumps(rule_entry.get("prohibitions_expr")) if rule_entry.get("prohibitions_expr") else None
        
        needs_curation = 1 if rule_entry.get("needs_curation") else 0
        flagged = 1 if rule_entry.get("flagged") else 0
        
        rules_to_insert.append((
            unit_code, prereqs_text, coreqs_text, prohibitions_text, assumed_knowledge_text,
            prereqs_expr, coreqs_expr, prohibitions_expr, needs_curation, flagged
        ))
        
        # 3. Availabilities mapping
        html_path = html_dir / f"{unit_code}.html"
        sessions = set()
        
        if html_path.exists():
            try:
                with open(html_path, "r", encoding="utf-8") as hf:
                    soup = BeautifulSoup(hf.read(), "html.parser")
                    
                status_div = soup.find(id="status")
                if status_div and status_div.text.strip() == "DISCONTINUED":
                    pass # Keep sessions empty
                else:
                    for table in soup.find_all("table"):
                        headers_cells = table.find_all(["th", "td"])
                        if not headers_cells:
                            continue
                        headers = [th.text.strip().lower() for th in headers_cells]
                        if not headers or "session" not in headers[0]:
                            continue
                            
                        # Find dynamic column indices
                        moa_idx = -1
                        loc_idx = -1
                        for idx, h in enumerate(headers):
                            if "moa" in h or "mode" in h or "delivery" in h or "attendance" in h:
                                moa_idx = idx
                            elif "location" in h or "campus" in h:
                                loc_idx = idx
                                
                        for tr in table.find_all("tr")[1:]:
                            cells = [td.text.strip() for td in tr.find_all(["td", "th"])]
                            if not cells:
                                continue
                            session_text = cells[0]
                            if str(PORTAL_YEAR) in session_text:
                                session_code, clean_session_text = map_session_text_to_code(session_text)
                                
                                modes = [cells[moa_idx]] if (moa_idx != -1 and moa_idx < len(cells)) else ["Normal day"]
                                locations = [cells[loc_idx]] if (loc_idx != -1 and loc_idx < len(cells)) else ["Camperdown/Darlington, Sydney"]
                                
                                # Use tuple as key to prevent duplicates
                                sessions.add((session_code, clean_session_text, json.dumps(modes), json.dumps(locations)))
            except Exception as e:
                print(f"Warning: Failed to parse HTML for {unit_code}: {e}")
                
        # Fallback to S1/S2 if no session parsed but unit is active
        if not sessions and is_active:
            sessions.add(("S1", "Semester 1", json.dumps(["Normal day"]), json.dumps(["Camperdown/Darlington, Sydney"])))
            sessions.add(("S2", "Semester 2", json.dumps(["Normal day"]), json.dumps(["Camperdown/Darlington, Sydney"])))
            
        for s_code, s_text, s_modes, s_locs in sessions:
            availabilities_to_insert.append((unit_code, s_code, s_text, s_modes, s_locs))
            
        # 4. Tables mapping
        for table_name in get_tables_for_unit(unit_code):
            tables_to_insert.append((unit_code, table_name))
            
    # Bulk insertions
    print(f"Inserting {len(units_to_insert)} units...")
    cursor.executemany("""
    INSERT INTO units (
        unit_code, title, credit_points, level, faculty, handbook_url,
        is_active, replaced_by_code, is_special_topic, is_zero_cp,
        is_year_long, is_external_placeholder, resolved_year
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, units_to_insert)
    
    print(f"Inserting {len(rules_to_insert)} unit rules...")
    cursor.executemany("""
    INSERT INTO unit_rules (
        unit_code, prerequisites_text, corequisites_text, prohibitions_text, assumed_knowledge_text,
        prerequisites_expr, corequisites_expr, prohibitions_expr, needs_curation, flagged
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rules_to_insert)
    
    print(f"Inserting {len(availabilities_to_insert)} unit availabilities...")
    cursor.executemany("""
    INSERT OR IGNORE INTO unit_availabilities (
        unit_code, session_code, session_text, modes, locations
    ) VALUES (?, ?, ?, ?, ?)
    """, availabilities_to_insert)
    
    print(f"Inserting {len(tables_to_insert)} unit tables...")
    cursor.executemany("""
    INSERT OR IGNORE INTO unit_tables (
        unit_code, table_name
    ) VALUES (?, ?)
    """, tables_to_insert)
    
    conn.commit()
    conn.close()
    print("Database seeding completed successfully.")

if __name__ == "__main__":
    seed()
