# tests/test_curation_api.py
import unittest
import json
import sqlite3
from fastapi.testclient import TestClient

# Import app to trigger fastAPI initialization
from admin.portal import app
import admin.portal

class TestCurationAPI(unittest.TestCase):
    
    def setUp(self):
        # Create a shared in-memory SQLite database to keep it alive during test
        self.conn = sqlite3.connect("file:memdb_curation?mode=memory&cache=shared", uri=True, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        
        # Override the database connection helper in the portal module to return new connections to the shared DB
        def mock_get_db_connection():
            conn = sqlite3.connect("file:memdb_curation?mode=memory&cache=shared", uri=True, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            return conn
        admin.portal.get_db_connection = mock_get_db_connection
        
        # Create schema tables matching the specs
        cursor = self.conn.cursor()
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
            resolved_year INTEGER
        );
        """)
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
            flagged INTEGER NOT NULL DEFAULT 0
        );
        """)
        self.conn.commit()
        self.client = TestClient(app)
        
    def tearDown(self):
        self.conn.close()
        
    def test_get_rules(self):
        cursor = self.conn.cursor()
        cursor.execute("""
        INSERT INTO units (unit_code, title, credit_points, level, is_active)
        VALUES ('COMP2123', 'Data Structures and Algorithms', 6, 2000, 1)
        """)
        cursor.execute("""
        INSERT INTO unit_rules (
            unit_code, prerequisites_text, corequisites_text, prohibitions_text,
            prerequisites_expr, corequisites_expr, prohibitions_expr, needs_curation, flagged
        ) VALUES (
            'COMP2123', 'None', 'None', 'None',
            '{"type": "none", "rule": null, "warnings": null, "curation_validity": "valid_for_planning"}',
            '{"type": "none", "rule": null, "warnings": null, "curation_validity": "valid_for_planning"}',
            '{"type": "none", "rule": null, "warnings": null, "curation_validity": "valid_for_planning"}',
            0, 0
        )
        """)
        self.conn.commit()
        
        response = self.client.get("/api/rules")
        self.assertEqual(response.status_code, 200)
        
        expected_data = {
            "COMP2123": {
                "unit_code": "COMP2123",
                "title": "Data Structures and Algorithms",
                "prerequisites_expr": {"type": "none", "rule": None, "warnings": None, "curation_validity": "valid_for_planning"},
                "corequisites_expr": {"type": "none", "rule": None, "warnings": None, "curation_validity": "valid_for_planning"},
                "prohibitions_expr": {"type": "none", "rule": None, "warnings": None, "curation_validity": "valid_for_planning"},
                "needs_curation": False,
                "flagged": False,
                "raw_rules": {
                    "prerequisites": "None",
                    "corequisites": "None",
                    "prohibitions": "None"
                }
            }
        }
        self.assertEqual(response.json(), expected_data)
        
    def test_post_rules_valid(self):
        cursor = self.conn.cursor()
        cursor.execute("""
        INSERT INTO units (unit_code, title, credit_points, level, is_active)
        VALUES ('COMP2123', 'Data Structures and Algorithms', 6, 2000, 1)
        """)
        cursor.execute("""
        INSERT INTO unit_rules (
            unit_code, prerequisites_text, corequisites_text, prohibitions_text,
            prerequisites_expr, corequisites_expr, prohibitions_expr, needs_curation, flagged
        ) VALUES (
            'COMP2123', 'None', 'None', 'None',
            '{"type": "none", "rule": null}', '{"type": "none", "rule": null}', '{"type": "none", "rule": null}',
            1, 0
        )
        """)
        self.conn.commit()
        
        payload = {
            "prerequisites_expr": {"type": "none", "rule": None},
            "corequisites_expr": {"type": "none", "rule": None},
            "prohibitions_expr": {"type": "none", "rule": None},
            "needs_curation": False,
            "flagged": False
        }
        
        response = self.client.post("/api/rules/COMP2123", json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")
        
        # Verify SQLite values actually updated
        cursor.execute("SELECT needs_curation, flagged FROM unit_rules WHERE unit_code = 'COMP2123'")
        row = cursor.fetchone()
        self.assertEqual(row["needs_curation"], 0)
        self.assertEqual(row["flagged"], 0)

    def test_post_rules_flagged(self):
        cursor = self.conn.cursor()
        cursor.execute("""
        INSERT INTO units (unit_code, title, credit_points, level, is_active)
        VALUES ('COMP2123', 'Data Structures and Algorithms', 6, 2000, 1)
        """)
        cursor.execute("""
        INSERT INTO unit_rules (
            unit_code, prerequisites_text, corequisites_text, prohibitions_text,
            prerequisites_expr, corequisites_expr, prohibitions_expr, needs_curation, flagged
        ) VALUES (
            'COMP2123', 'None', 'None', 'None',
            '{"type": "none", "rule": null}', '{"type": "none", "rule": null}', '{"type": "none", "rule": null}',
            1, 0
        )
        """)
        self.conn.commit()
        
        payload = {
            "prerequisites_expr": {"type": "none", "rule": None},
            "corequisites_expr": {"type": "none", "rule": None},
            "prohibitions_expr": {"type": "none", "rule": None},
            "needs_curation": True,
            "flagged": True
        }
        
        response = self.client.post("/api/rules/COMP2123", json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")
        
        # Verify flagged updated to 1
        cursor.execute("SELECT needs_curation, flagged FROM unit_rules WHERE unit_code = 'COMP2123'")
        row = cursor.fetchone()
        self.assertEqual(row["needs_curation"], 1)
        self.assertEqual(row["flagged"], 1)

    def test_post_rules_invalid_schema(self):
        cursor = self.conn.cursor()
        cursor.execute("""
        INSERT INTO units (unit_code, title, credit_points, level, is_active)
        VALUES ('COMP2123', 'Data Structures and Algorithms', 6, 2000, 1)
        """)
        cursor.execute("""
        INSERT INTO unit_rules (
            unit_code, prerequisites_text, corequisites_text, prohibitions_text,
            prerequisites_expr, corequisites_expr, prohibitions_expr, needs_curation, flagged
        ) VALUES (
            'COMP2123', 'None', 'None', 'None',
            '{"type": "none", "rule": null}', '{"type": "none", "rule": null}', '{"type": "none", "rule": null}',
            1, 0
        )
        """)
        self.conn.commit()
        
        # Invalid payload: type='invalid_type' violates Literal constraints in RuleParseResult
        payload = {
            "prerequisites_expr": {"type": "invalid_type", "rule": None},
            "corequisites_expr": {"type": "none", "rule": None},
            "prohibitions_expr": {"type": "none", "rule": None},
            "needs_curation": False,
            "flagged": False
        }
        
        response = self.client.post("/api/rules/COMP2123", json=payload)
        self.assertEqual(response.status_code, 422)
        self.assertIn("validation failure", response.json()["detail"].lower())

    def test_get_stats(self):
        cursor = self.conn.cursor()
        cursor.execute("""
        INSERT INTO units (unit_code, title, credit_points, level, is_active)
        VALUES ('COMP2123', 'Data Structures and Algorithms', 6, 2000, 1)
        """)
        cursor.execute("""
        INSERT INTO unit_rules (
            unit_code, prerequisites_text, corequisites_text, prohibitions_text,
            prerequisites_expr, corequisites_expr, prohibitions_expr, needs_curation, flagged
        ) VALUES (
            'COMP2123', 'COMP2017', 'None', 'None',
            '{"type": "unit", "rule": {"type": "unit", "unit_code": "COMP2017"}, "warnings": ["logic_simplified"], "curation_validity": "valid_for_planning"}',
            '{"type": "none", "rule": null, "warnings": null, "curation_validity": "valid_for_planning"}',
            '{"type": "none", "rule": null, "warnings": null, "curation_validity": "valid_for_planning"}',
            0, 1
        )
        """)
        self.conn.commit()
        
        response = self.client.get("/api/stats")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total_units"], 1)
        self.assertEqual(data["curated_units"], 1)
        self.assertEqual(data["needs_curation_units"], 0)
        self.assertEqual(data["flagged_units"], 1)
        self.assertEqual(data["warning_counts"]["logic_simplified"], 1)
        self.assertEqual(data["validity_counts"]["valid_for_planning"], 3)
        self.assertTrue(len(data["top_subject_stats"]) > 0)
        self.assertEqual(data["top_subject_stats"][0]["subject"], "COMP")

if __name__ == '__main__':
    unittest.main()
