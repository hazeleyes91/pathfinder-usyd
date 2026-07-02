import pytest
from fastapi.testclient import TestClient
import sqlite3
from api.main import app
import api.main

client = TestClient(app)

def test_get_units_default_pagination():
    response = client.get("/api/units")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # The DB has many units, default page size is 50
    assert len(data) <= 50

def test_get_units_with_query_search():
    # 'intro' should match several units in their titles
    response = client.get("/api/units?query=intro&page_size=5")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) <= 5
    if data:
        for unit in data:
            title_lower = unit["title"].lower()
            code_lower = unit["code"].lower()
            assert "intro" in title_lower or "intro" in code_lower

def test_get_units_with_table_filter():
    response = client.get("/api/units?table=Engineering&page_size=10")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if data:
        for unit in data:
            assert any("Engineering" in t for t in unit["tables"])

def test_get_units_bulk():
    response = client.get("/api/units/bulk?codes=INFO1110,COMP2123,INVALIDCODE")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2
    codes = [u["code"] for u in data]
    assert "INFO1110" in codes
    assert "COMP2123" in codes
    assert "INVALIDCODE" not in codes

def test_get_unit_detail_success():
    response = client.get("/api/units/COMP2017")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == "COMP2017"

def test_get_unit_detail_not_found():
    response = client.get("/api/units/NONEXISTENT")
    assert response.status_code == 404

def test_serve_planner_root():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert b"Pathfinder USYD" in response.content


def test_get_units_prioritizes_unit_code(monkeypatch):
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE units (
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
        resolved_year INTEGER
    )
    """)
    cursor.execute("""
    CREATE TABLE unit_rules (
        unit_code TEXT PRIMARY KEY,
        prerequisites_text TEXT,
        corequisites_text TEXT,
        prohibitions_text TEXT,
        assumed_knowledge_text TEXT,
        prerequisites_expr TEXT,
        corequisites_expr TEXT,
        prohibitions_expr TEXT,
        needs_curation INTEGER NOT NULL DEFAULT 0,
        flagged INTEGER NOT NULL DEFAULT 0
    )
    """)
    cursor.execute("""
    CREATE TABLE unit_availabilities (
        unit_code TEXT,
        session_code TEXT,
        session_text TEXT,
        modes TEXT,
        locations TEXT,
        PRIMARY KEY (unit_code, session_code)
    )
    """)
    cursor.execute("""
    CREATE TABLE unit_tables (
        unit_code TEXT,
        table_name TEXT,
        PRIMARY KEY (unit_code, table_name)
    )
    """)

    units = [
        ("COMP1234", "Zebra Studies", 6, 1000, "Science", "https://example.com/comp1234", 1),
        ("ABCD1000", "Computer Thinking", 6, 1000, "Science", "https://example.com/abcd1000", 1),
    ]
    cursor.executemany(
        "INSERT INTO units (unit_code, title, credit_points, level, faculty, handbook_url, is_active) VALUES (?, ?, ?, ?, ?, ?, ?)",
        units,
    )
    cursor.executemany(
        "INSERT INTO unit_availabilities (unit_code, session_code, session_text, modes, locations) VALUES (?, ?, ?, ?, ?)",
        [
            ("COMP1234", "s1", "Semester 1", "", ""),
            ("ABCD1000", "s1", "Semester 1", "", ""),
        ],
    )
    cursor.executemany(
        "INSERT INTO unit_tables (unit_code, table_name) VALUES (?, ?)",
        [
            ("COMP1234", "Table A - Science"),
            ("ABCD1000", "Table A - Science"),
        ],
    )
    conn.commit()

    def mock_get_db_connection():
        return conn

    monkeypatch.setattr(api.main, "get_db_connection", mock_get_db_connection)

    response = client.get("/api/units?query=comp&page_size=10")
    assert response.status_code == 200
    data = response.json()
    assert [unit["code"] for unit in data[:2]] == ["COMP1234", "ABCD1000"]
