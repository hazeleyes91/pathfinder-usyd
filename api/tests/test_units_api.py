import pytest
from fastapi.testclient import TestClient
from api.main import app

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
    assert b"USYD Course Planner" in response.content
