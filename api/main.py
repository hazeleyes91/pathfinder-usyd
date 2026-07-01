import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse

# Parent imports
sys.path.append(str(Path(__file__).resolve().parents[1]))
from api.database import get_db_connection
from api.models import ValidationRequest, ValidationResponse
from api.validation.engine import get_availability, run_validation

WEB_DIR = Path(__file__).resolve().parents[1] / "web"
DEBUG_LOG = Path(__file__).resolve().parents[1] / "debug-0321a6.log"


def _debug_log(hypothesis_id: str, location: str, message: str, data: dict):
    # #region agent log
    try:
        payload = {
            "sessionId": "0321a6",
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
            "runId": "pre-fix",
        }
        with open(DEBUG_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload) + "\n")
    except Exception:
        pass
    # #endregion

app = FastAPI(title="USYD Course Planner")


@app.post("/api/validate-plan", response_model=ValidationResponse)
async def validate_plan(request: ValidationRequest):
    """
    Statelessly validates the complete chronological placements of a student's study plan.
    """
    return run_validation(request)


def _build_unit_json(cursor, codes: List[str]) -> List[Dict]:
    if not codes:
        return []

    placeholders = ",".join("?" for _ in codes)

    # Get base details and rules
    cursor.execute(f"""
        SELECT u.unit_code, u.title, u.credit_points,
               r.prerequisites_text, r.corequisites_text,
               r.prohibitions_text, r.assumed_knowledge_text,
               u.handbook_url
        FROM units u
        LEFT JOIN unit_rules r ON u.unit_code = r.unit_code
        WHERE u.unit_code IN ({placeholders})
    """, codes)

    base_rows = cursor.fetchall()

    # Get tables
    cursor.execute(f"""
        SELECT unit_code, table_name
        FROM unit_tables
        WHERE unit_code IN ({placeholders})
    """, codes)
    table_rows = cursor.fetchall()

    tables_by_code = {code: [] for code in codes}
    for r in table_rows:
        tables_by_code[r["unit_code"]].append(r["table_name"])

    units_list = []
    for row in base_rows:
        code = row["unit_code"]
        avail = get_availability(code)

        avail_labels = []
        if "sem1" in avail:
            avail_labels.append("Semester 1")
        if "sem2" in avail:
            avail_labels.append("Semester 2")
        if "summ" in avail:
            avail_labels.append("Summer")
        if "wint" in avail:
            avail_labels.append("Winter")
        availText = ", ".join(avail_labels) if avail_labels else "Unknown"

        units_list.append({
            "code": code,
            "title": row["title"],
            "avail": avail,
            "availText": availText,
            "cp": row["credit_points"],
            "tables": tables_by_code.get(code, []),
            "prereq": row["prerequisites_text"],
            "coreq": row["corequisites_text"],
            "prohibit": row["prohibitions_text"],
            "assumed": row["assumed_knowledge_text"],
            "url": row["handbook_url"]
        })

    units_list.sort(key=lambda x: x["code"])
    return units_list


@app.get("/api/units")
async def get_units(
    query: Optional[str] = None,
    table: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100)
):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        sql = "SELECT u.unit_code FROM units u "
        conditions = ["u.is_active = 1"]
        params = []

        if query:
            conditions.append("(u.unit_code LIKE ? OR u.title LIKE ?)")
            params.extend([f"%{query}%", f"%{query}%"])

        if table and table.lower() != "all":
            sql += " JOIN unit_tables ut ON u.unit_code = ut.unit_code "
            conditions.append("ut.table_name LIKE ?")
            if table.lower() == "ole":
                params.append("%open%")
            else:
                params.append(f"%{table}%")

        sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY u.unit_code LIMIT ? OFFSET ?"

        params.extend([page_size, (page - 1) * page_size])

        cursor.execute(sql, params)
        codes = [r["unit_code"] for r in cursor.fetchall()]

        results = _build_unit_json(cursor, codes)
        # #region agent log
        _debug_log("H2", "api/main.py:get_units", "units query result", {
            "query": query,
            "table": table,
            "page": page,
            "codes_found": len(codes),
            "results_built": len(results),
        })
        # #endregion
        return results
    finally:
        conn.close()


@app.get("/api/units/bulk")
async def get_units_bulk(codes: str):
    code_list = [c.strip().upper() for c in codes.split(",") if c.strip()]
    if not code_list:
        return []

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        placeholders = ",".join("?" for _ in code_list)
        cursor.execute(
            f"SELECT unit_code FROM units WHERE unit_code IN ({placeholders})",
            code_list,
        )
        active_codes = [r["unit_code"] for r in cursor.fetchall()]

        results = _build_unit_json(cursor, active_codes)
        return results
    finally:
        conn.close()


@app.get("/api/units/{unit_code}")
async def get_unit(unit_code: str):
    code = unit_code.strip().upper()
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT unit_code FROM units WHERE unit_code = ?",
            (code,),
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Unit not found")

        results = _build_unit_json(cursor, [code])
        if not results:
            raise HTTPException(status_code=404, detail="Unit not found")
        return results[0]
    finally:
        conn.close()


@app.get("/")
async def serve_planner():
    index = WEB_DIR / "index.html"
    if not index.is_file():
        raise HTTPException(status_code=404, detail="Planner UI not found")
    return FileResponse(index)


if __name__ == "__main__":
    import uvicorn

    print("USYD Course Planner running at http://127.0.0.1:8000/")
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
