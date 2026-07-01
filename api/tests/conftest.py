import pytest
import sys
from pathlib import Path

# Add parent path to allow importing api
sys.path.append(str(Path(__file__).resolve().parents[2]))

@pytest.fixture(autouse=True)
def mock_databases(monkeypatch):
    import api.validation.engine as engine
    
    # Simple Mock UoS Metadata Database
    mock_metadata = {
        "INFO1110": {"unit_code": "INFO1110", "title": "Introduction to Programming", "credit_points": 6, "level": "Undergraduate"},
        "MATH1021": {"unit_code": "MATH1021", "title": "Calculus", "credit_points": 6, "level": "Undergraduate"},
        "MATH1921": {"unit_code": "MATH1921", "title": "Calculus (Advanced)", "credit_points": 6, "level": "Undergraduate"},
        "COMP2017": {"unit_code": "COMP2017", "title": "Systems Programming", "credit_points": 6, "level": "Undergraduate"},
        "COMP2123": {"unit_code": "COMP2123", "title": "Data Structures and Algorithms", "credit_points": 6, "level": "Undergraduate"},
        "COMP2823": {"unit_code": "COMP2823", "title": "Data Structures (Adv)", "credit_points": 6, "level": "Undergraduate"},
        "COMP3027": {"unit_code": "COMP3027", "title": "Algorithm Design", "credit_points": 6, "level": "Undergraduate"},
        "COMP3888": {"unit_code": "COMP3888", "title": "Computer Science Project", "credit_points": 6, "level": "Undergraduate"},
        "DUMY1001": {"unit_code": "DUMY1001", "title": "Dummy Unit 1", "credit_points": 6, "level": "Undergraduate"},
        "DUMY1002": {"unit_code": "DUMY1002", "title": "Dummy Unit 2", "credit_points": 6, "level": "Undergraduate"},
    }
    
    # Simple Mock Logic Database
    mock_rules = {
        "INFO1110": {
            "unit_code": "INFO1110",
            "prerequisites_expr": {"type": "none", "rule": None},
            "corequisites_expr": {"type": "none", "rule": None},
            "prohibitions_expr": {"type": "none", "rule": None}
        },
        "DUMY1001": {
            "unit_code": "DUMY1001",
            "prerequisites_expr": {"type": "none", "rule": None},
            "corequisites_expr": {"type": "none", "rule": None},
            "prohibitions_expr": {"type": "none", "rule": None}
        },
        "DUMY1002": {
            "unit_code": "DUMY1002",
            "prerequisites_expr": {"type": "none", "rule": None},
            "corequisites_expr": {"type": "none", "rule": None},
            "prohibitions_expr": {"type": "none", "rule": None}
        },
        "COMP2017": {
            "unit_code": "COMP2017",
            "prerequisites_expr": {"type": "none", "rule": None},
            "corequisites_expr": {"type": "none", "rule": None},
            "prohibitions_expr": {"type": "none", "rule": None}
        },
        "COMP2823": {
            "unit_code": "COMP2823",
            "prerequisites_expr": {"type": "none", "rule": None},
            "corequisites_expr": {"type": "none", "rule": None},
            "prohibitions_expr": {"type": "none", "rule": None}
        },
        "MATH1021": {
            "unit_code": "MATH1021",
            "prerequisites_expr": {"type": "none", "rule": None},
            "corequisites_expr": {"type": "none", "rule": None},
            "prohibitions_expr": {"type": "unit", "rule": {"type": "unit", "unit_code": "MATH1921"}}
        },
        "MATH1921": {
            "unit_code": "MATH1921",
            "prerequisites_expr": {"type": "none", "rule": None},
            "corequisites_expr": {"type": "none", "rule": None},
            "prohibitions_expr": {"type": "unit", "rule": {"type": "unit", "unit_code": "MATH1021"}}
        },
        "COMP2123": {
            "unit_code": "COMP2123",
            "prerequisites_expr": {
                "type": "unit_group",
                "rule": {
                    "type": "unit_group",
                    "operator": "OR",
                    "unit_codes": ["INFO1110", "INFO1910"]
                }
            },
            "corequisites_expr": {"type": "none", "rule": None},
            "prohibitions_expr": {"type": "none", "rule": None}
        },
        "COMP3027": {
            "unit_code": "COMP3027",
            "prerequisites_expr": {
                "type": "unit_group",
                "rule": {
                    "type": "unit_group",
                    "operator": "AND",
                    "unit_codes": ["COMP2123", "COMP2823"]
                }
            },
            "corequisites_expr": {"type": "none", "rule": None},
            "prohibitions_expr": {"type": "none", "rule": None}
        },
        "COMP3888": {
            "unit_code": "COMP3888",
            "prerequisites_expr": {
                "type": "credit_points",
                "rule": {
                    "type": "credit_points",
                    "credit_points": 24,
                    "level": 2000,
                    "subjects": ["COMP", "INFO"]
                }
            },
            "corequisites_expr": {
                "type": "unit",
                "rule": {
                    "type": "unit",
                    "unit_code": "COMP3027"
                }
            },
            "prohibitions_expr": {"type": "none", "rule": None}
        }
    }
    
    # Mock get_availability to return preset values in tests
    mock_avail = {
        "INFO1110": ["sem1", "sem2"],
        "MATH1021": ["sem1", "sem2"],
        "MATH1921": ["sem1"],
        "COMP2017": ["sem1", "sem2"],
        "COMP2123": ["sem1", "sem2"],
        "COMP2823": ["sem1", "sem2"],
        "COMP3027": ["sem1"],
        "COMP3888": ["sem1", "sem2"],
        "DUMY1001": ["sem1", "sem2"],
        "DUMY1002": ["sem1", "sem2"]
    }
    
    monkeypatch.setattr(engine, "UOS_METADATA", mock_metadata)
    monkeypatch.setattr(engine, "RULES_DB", mock_rules)
    monkeypatch.setattr(engine, "get_availability", lambda code: mock_avail.get(code, ["sem1", "sem2"]))
