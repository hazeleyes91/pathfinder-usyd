import unittest
from fastapi.testclient import TestClient
import sys
from pathlib import Path

# Add parent path to allow importing api
sys.path.append(str(Path(__file__).resolve().parents[2]))
from api.main import app

class TestValidationAPI(unittest.TestCase):
    
    def setUp(self):
        self.client = TestClient(app)
        
    def test_empty_plan(self):
        payload = {
            "mode": "free",
            "start_year": 2026,
            "placements": []
        }
        response = self.client.post("/api/validate-plan", json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["valid"])
        self.assertEqual(len(response.json()["warnings"]), 0)
        
    def test_prerequisite_satisfied(self):
        payload = {
            "mode": "free",
            "start_year": 2026,
            "placements": [
                {"year": 1, "term": "sem1", "codes": ["INFO1110"]},
                {"year": 1, "term": "sem2", "codes": ["COMP2123"]}
            ]
        }
        response = self.client.post("/api/validate-plan", json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["valid"])
        self.assertEqual(len(response.json()["warnings"]), 0)
        
    def test_prerequisite_unmet(self):
        payload = {
            "mode": "free",
            "start_year": 2026,
            "placements": [
                {"year": 1, "term": "sem1", "codes": ["COMP2123"]}
            ]
        }
        response = self.client.post("/api/validate-plan", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data["valid"])
        warnings = [w for w in data["warnings"] if w["type"] == "prereq_unmet"]
        self.assertEqual(len(warnings), 1)
        self.assertIn("Prerequisite unmet", warnings[0]["message"])
        
    def test_prerequisite_taken_concurrently(self):
        # Taking prereq in same semester is invalid
        payload = {
            "mode": "free",
            "start_year": 2026,
            "placements": [
                {"year": 1, "term": "sem1", "codes": ["INFO1110", "COMP2123"]}
            ]
        }
        response = self.client.post("/api/validate-plan", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data["valid"])
        warnings = [w for w in data["warnings"] if w["type"] == "prereq_unmet"]
        self.assertEqual(len(warnings), 1)
        
    def test_corequisite_concurrent(self):
        payload = {
            "mode": "free",
            "start_year": 2026,
            "placements": [
                {"year": 1, "term": "sem1", "codes": ["INFO1110"]},
                {"year": 1, "term": "sem2", "codes": ["COMP2123", "COMP2823", "COMP3027"]},
                {"year": 2, "term": "sem1", "codes": ["COMP3888"]}
            ]
        }
        # Note: COMP3888 requires 24 CP of COMP/INFO 2000-level units as prerequisite.
        # Completed units pool before Y2 Sem1: COMP2123, COMP2823 (12 CP).
        # So COMP3888 prereq is still unmet (needs 24 CP), but corequisite COMP3027 is met.
        response = self.client.post("/api/validate-plan", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        coreq_warnings = [w for w in data["warnings"] if w["type"] == "coreq_unmet"]
        self.assertEqual(len(coreq_warnings), 0)
        
    def test_corequisite_unmet(self):
        # COMP3888 requires coreq COMP3027. COMP3027 is missing.
        payload = {
            "mode": "free",
            "start_year": 2026,
            "placements": [
                {"year": 1, "term": "sem1", "codes": ["COMP3888"]}
            ]
        }
        response = self.client.post("/api/validate-plan", json=payload)
        data = response.json()
        coreq_warnings = [w for w in data["warnings"] if w["type"] == "coreq_unmet"]
        self.assertEqual(len(coreq_warnings), 1)
        
    def test_prohibitions_conflict(self):
        # MATH1021 and MATH1921 are prohibited
        payload = {
            "mode": "free",
            "start_year": 2026,
            "placements": [
                {"year": 1, "term": "sem1", "codes": ["MATH1021", "MATH1921"]}
            ]
        }
        response = self.client.post("/api/validate-plan", json=payload)
        data = response.json()
        self.assertFalse(data["valid"])
        prohib_warnings = [w for w in data["warnings"] if w["type"] == "prohibited"]
        self.assertEqual(len(prohib_warnings), 2)
        
    def test_session_mismatch(self):
        # COMP3027 is offered in sem1. Placed in sem2.
        # Satisfying its prerequisites: INFO1110 (Y1S1) -> COMP2123, COMP2823 (Y1S2)
        payload = {
            "mode": "free",
            "start_year": 2026,
            "placements": [
                {"year": 1, "term": "sem1", "codes": ["INFO1110"]},
                {"year": 1, "term": "sem2", "codes": ["COMP2123", "COMP2823"]},
                {"year": 2, "term": "sem2", "codes": ["COMP3027"]}
            ]
        }
        response = self.client.post("/api/validate-plan", json=payload)
        data = response.json()
        # Session mismatch is a yellow alert, shouldn't block validation!
        # Requisites are all satisfied.
        self.assertTrue(data["valid"])
        mismatch_warnings = [w for w in data["warnings"] if w["type"] == "session_mismatch"]
        self.assertEqual(len(mismatch_warnings), 1)
        
    def test_semester_overload(self):
        # 5 units of 6 CP in sem1 (Total 30 CP), all are prereq-free.
        payload = {
            "mode": "free",
            "start_year": 2026,
            "placements": [
                {"year": 1, "term": "sem1", "codes": ["INFO1110", "MATH1021", "COMP2017", "DUMY1001", "DUMY1002"]}
            ]
        }
        response = self.client.post("/api/validate-plan", json=payload)
        data = response.json()
        # Overload is yellow alert, shouldn't block validation
        self.assertTrue(data["valid"])
        overload_warnings = [w for w in data["warnings"] if w["type"] == "overload"]
        self.assertEqual(len(overload_warnings), 1)
        self.assertIn("exceeds standard 24 CP", overload_warnings[0]["message"])

if __name__ == "__main__":
    unittest.main()
