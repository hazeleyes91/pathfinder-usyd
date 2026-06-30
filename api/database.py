import sqlite3
from pathlib import Path
from crawler.config import DATA_DIR

DB_PATH = DATA_DIR / "handbook.db"

def get_db_connection() -> sqlite3.Connection:
    """
    Returns an active connection to the SQLite database with row factory enabled
    and foreign keys turned on.
    """
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    """
    Initializes the SQLite tables for UoS.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Create units table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS units (
        unit_code TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        credit_points INTEGER NOT NULL,
        level INTEGER NOT NULL,
        faculty TEXT,
        handbook_url TEXT,
        is_active INTEGER NOT NULL DEFAULT 1,
        replaced_by_code TEXT,
        is_special_topic INTEGER NOT NULL DEFAULT 0,
        is_zero_cp INTEGER NOT NULL DEFAULT 0,
        is_year_long INTEGER NOT NULL DEFAULT 0,
        is_external_placeholder INTEGER NOT NULL DEFAULT 0,
        resolved_year INTEGER,
        FOREIGN KEY (replaced_by_code) REFERENCES units (unit_code) ON DELETE SET NULL
    );
    """)
    
    # 2. Create unit_rules table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS unit_rules (
        unit_code TEXT PRIMARY KEY,
        prerequisites_text TEXT,
        corequisites_text TEXT,
        prohibitions_text TEXT,
        assumed_knowledge_text TEXT,
        prerequisites_expr TEXT,
        corequisites_expr TEXT,
        prohibitions_expr TEXT,
        needs_curation INTEGER NOT NULL DEFAULT 0,
        flagged INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (unit_code) REFERENCES units (unit_code) ON DELETE CASCADE
    );
    """)
    
    # 3. Create unit_availabilities table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS unit_availabilities (
        unit_code TEXT,
        session_code TEXT,
        session_text TEXT,
        modes TEXT,
        locations TEXT,
        PRIMARY KEY (unit_code, session_code),
        FOREIGN KEY (unit_code) REFERENCES units (unit_code) ON DELETE CASCADE
    );
    """)
    
    # 4. Create unit_tables table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS unit_tables (
        unit_code TEXT,
        table_name TEXT,
        PRIMARY KEY (unit_code, table_name),
        FOREIGN KEY (unit_code) REFERENCES units (unit_code) ON DELETE CASCADE
    );
    """)
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database schema successfully initialized.")
