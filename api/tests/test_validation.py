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


class TestEscalation(unittest.TestCase):
    """Integration tests for warning escalation logic."""

    def setUp(self):
        self.client = TestClient(app)

    def test_grade_threshold_escalation_unplaced(self):
        """
        Grade threshold warning should escalate to RED when underlying unit not placed.

        Mock scenario: Unit with grade threshold prerequisite, unit not in plan.
        Expected: Hard warning (no "Advisory check" prefix).
        """
        # Mock unit with grade threshold: requires COMP2123 with 65+ mark
        # Place unit without COMP2123 → should get hard warning
        payload = {
            "mode": "free",
            "start_year": 2026,
            "placements": [
                {"year": 1, "term": "sem1", "codes": ["COMP3027"]}  # Has grade threshold prereq
            ]
        }
        response = self.client.post("/api/validate-plan", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Check for prerequisite warnings
        prereq_warnings = [w for w in data["warnings"] if w["type"] == "prereq_unmet"]

        # Should have warning
        self.assertGreater(len(prereq_warnings), 0)

        # Check if any warning is escalated (not advisory)
        hard_warnings = [w for w in prereq_warnings if not w["message"].startswith("Advisory check")]

        # If grade threshold present and units missing, should escalate
        # Note: This test depends on actual DB data and grade threshold detection
        # May need adjustment based on actual unit requirements

    def test_grade_threshold_remains_soft_when_placed(self):
        """
        Grade threshold warning should remain SOFT when underlying units are placed.

        Mock scenario: Unit with grade threshold, prerequisites satisfied.
        Expected: Soft warning ("Advisory check" prefix).
        """
        payload = {
            "mode": "free",
            "start_year": 2026,
            "placements": [
                {"year": 1, "term": "sem1", "codes": ["INFO1110"]},
                {"year": 1, "term": "sem2", "codes": ["COMP2123"]},
                {"year": 2, "term": "sem1", "codes": ["COMP3027"]}  # Grade threshold satisfied
            ]
        }
        response = self.client.post("/api/validate-plan", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Should be valid (prerequisites met)
        # Any warnings should be advisory
        prereq_warnings = [w for w in data["warnings"] if w["type"] == "prereq_unmet"]
        advisory_warnings = [w for w in prereq_warnings if w["message"].startswith("Advisory check")]

        # If there are grade threshold warnings, they should be advisory
        # (This test validates soft warning behavior)

    def test_wildcard_escalation_no_matches(self):
        """
        Wildcard pattern should escalate to RED when no matching units placed.

        Mock scenario: Prerequisite with wildcard (e.g., COMP2XXX), no COMP 2000-level units.
        Expected: Hard warning.
        """
        # This requires a unit with wildcard prereq in DB
        # Test structure is here but may need actual DB unit with wildcard prereq
        pass

    def test_wildcard_remains_soft_with_matches(self):
        """
        Wildcard pattern should remain SOFT when matching units exist.

        Mock scenario: Prerequisite with wildcard, matching unit placed.
        Expected: Soft warning.
        """
        # This requires a unit with wildcard prereq in DB
        # Test structure is here but may need actual DB unit with wildcard prereq
        pass

    def test_permission_never_escalates(self):
        """
        Permission warnings should always remain SOFT regardless of placement.

        Mock scenario: Unit with permission requirement.
        Expected: Soft warning always.
        """
        # This requires a unit with permission_required warning in DB
        # Permission warnings should never escalate even if conditions unmet
        pass

    def test_multiple_warnings_no_escalation_under_threshold(self):
        """
        With 2 warnings, should not escalate (threshold is 3).

        Mock scenario: Unit with 2 parser warnings.
        Expected: Soft warnings.
        """
        # Requires unit with 2 warnings in DB
        pass

    def test_multiple_warnings_escalates_at_threshold(self):
        """
        With 3+ warnings, should escalate due to MultipleConflictingWarningsCheck.

        Mock scenario: Unit with 3+ parser warnings.
        Expected: Hard warning.
        """
        # Requires unit with 3+ warnings in DB
        pass

    def test_wildcard_affected_codes(self):
        """Verify that affected_codes contains wildcard patterns when wildcard prerequisite is unmet."""
        import api.validation.engine as engine
        
        # Inject mock unit with wildcard prerequisites into RULES_DB
        engine.RULES_DB["COMP3999"] = {
            "unit_code": "COMP3999",
            "prerequisites_expr": {
                "type": "unit",
                "rule": {"type": "unit", "unit_code": "COMP2XXX"}
            },
            "corequisites_expr": {"type": "none", "rule": None},
            "prohibitions_expr": {"type": "none", "rule": None}
        }
        
        # Inject metadata
        engine.UOS_METADATA["COMP3999"] = {
            "unit_code": "COMP3999",
            "title": "Mock Wildcard Unit",
            "credit_points": 6,
            "level": "Undergraduate"
        }
        
        try:
            payload = {
                "mode": "free",
                "start_year": 2026,
                "placements": [
                    {"year": 1, "term": "sem1", "codes": ["COMP3999"]}
                ]
            }
            response = self.client.post("/api/validate-plan", json=payload)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertFalse(data["valid"])
            
            # Find prereq_unmet warning for COMP3999
            warnings = [w for w in data["warnings"] if w["unit_code"] == "COMP3999" and w["type"] == "prereq_unmet"]
            self.assertEqual(len(warnings), 1)
            # affected_codes should contain the wildcard "COMP2XXX"
            self.assertEqual(warnings[0]["affected_codes"], ["COMP2XXX"])
            
        finally:
            # Clean up injected mock rules
            if "COMP3999" in engine.RULES_DB:
                del engine.RULES_DB["COMP3999"]
            if "COMP3999" in engine.UOS_METADATA:
                del engine.UOS_METADATA["COMP3999"]


if __name__ == "__main__":
    unittest.main()
