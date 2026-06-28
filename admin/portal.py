# admin/portal.py
import os
import json
from pathlib import Path
from typing import Literal, Union, Optional, Any, Dict
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, TypeAdapter
from config import DATA_DIR, DEFAULT_TARGET_YEAR
from parsers.schemas import RuleParseResult, UnitRequirement, CreditPointRequirement, LogicalRequirement

app = FastAPI(title="USYD Course Planner - Curation Admin Portal")

# Define path references
PORTAL_YEAR = int(os.getenv("PORTAL_YEAR", DEFAULT_TARGET_YEAR))
DB_PATH = DATA_DIR / f"parsed_rules_{PORTAL_YEAR}.json"
STATIC_DIR = Path(__file__).resolve().parent / "static"

RuleExpression = RuleParseResult

# Payload validation model
class RuleUpdatePayload(BaseModel):
    prerequisites_expr: Dict[str, Any] = Field(description="JSON logic expression for prerequisites")
    corequisites_expr: Dict[str, Any] = Field(description="JSON logic expression for corequisites")
    prohibitions_expr: Dict[str, Any] = Field(description="JSON logic expression for prohibitions")
    needs_curation: bool = Field(description="Indicates if manual curation is still required")
    flagged: bool = Field(default=False, description="Flagged for later manual fix")

def load_rules_db() -> Dict[str, Any]:
    """Reads parsed rules database from disk."""
    if not DB_PATH.exists():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Parsed rules database file not found at {DB_PATH}. Please run parse_rules pipeline first."
        )
    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read parsed rules database: {e}"
        )

def save_rules_db(db: Dict[str, Any]):
    """Writes updated rules database to disk."""
    try:
        with open(DB_PATH, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=2)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to serialize rules database back to disk: {e}"
        )

# API Endpoints
@app.get("/api/rules")
async def get_rules():
    """Retrieve full database of parsed rules."""
    return load_rules_db()

@app.post("/api/rules/{unit_code}")
async def update_unit_rules(unit_code: str, payload: RuleUpdatePayload):
    """
    Validates updated logic expressions against rule schemas, 
    persists edits back to the parsed rules database, and clears curation flags.
    """
    db = load_rules_db()
    
    if unit_code not in db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unit code {unit_code} not found in rules database."
        )

    # 1. Enforce Pydantic validation schemas on input expressions
    ta = TypeAdapter(RuleExpression)
    try:
        ta.validate_python(payload.prerequisites_expr)
        ta.validate_python(payload.corequisites_expr)
        ta.validate_python(payload.prohibitions_expr)
    except Exception as validation_err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Rule schema validation failure: {validation_err}"
        )

    # 2. Update record values
    db[unit_code]["prerequisites_expr"] = payload.prerequisites_expr
    db[unit_code]["corequisites_expr"] = payload.corequisites_expr
    db[unit_code]["prohibitions_expr"] = payload.prohibitions_expr
    db[unit_code]["needs_curation"] = payload.needs_curation
    db[unit_code]["flagged"] = payload.flagged

    # 3. Serialize back to disk
    save_rules_db(db)
    print(f"[{unit_code}] Successfully curated and saved to disk.")
    
    return {"status": "success", "message": f"Successfully updated rules for {unit_code}."}

# Mount static web files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
async def serve_root():
    """Serves the primary layout index file."""
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portal index.html template file not found."
        )
    return FileResponse(index_file)

@app.get("/{filename}")
async def serve_static_files(filename: str):
    """Serves styles and scripts directly from static sub-directory."""
    file_path = STATIC_DIR / filename
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")

if __name__ == "__main__":
    import uvicorn
    # Start web server automatically
    print(f"Starting Curation Admin Portal...")
    print(f"Static directory: {STATIC_DIR}")
    uvicorn.run("admin.portal:app", host="127.0.0.1", port=8000, reload=True)
