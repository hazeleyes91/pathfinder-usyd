# admin/portal.py
import os
import json
import time
import threading
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))
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

# --- Crawler Admin State & Endpoints ---
crawler_state = {
    "is_running": False,
    "is_rebuilding": False,
    "total": 0,
    "processed": 0,
    "failed": 0,
    "current_unit": "",
    "errors": [],
    "logs": []
}

def run_crawler_thread(limit: Optional[int] = None, force_fetch: bool = False, target_year: int = PORTAL_YEAR):
    global crawler_state
    try:
        import requests
        from concurrent.futures import ThreadPoolExecutor, as_completed
        from run import SEED_OVERRIDE_CODES, _is_unit_cached
        from crawlers.unit_detail import load_target_codes, fetch_and_cache_unit
        from parsers.base import parse_all_cached_units
        from config import DETAIL_REQUEST_DELAY_SECONDS
        
        crawler_state["logs"].append("Loading target codes...")
        discovered_codes = load_target_codes()
        master_queue = sorted(list(set(discovered_codes + SEED_OVERRIDE_CODES)))
        
        if limit:
            master_queue = master_queue[:limit]
            
        crawler_state["total"] = len(master_queue)
        crawler_state["processed"] = 0
        crawler_state["failed"] = 0
        crawler_state["errors"] = []
        crawler_state["logs"] = []
        
        crawler_state["logs"].append(f"Starting parallel crawl for {len(master_queue)} units...")
        
        max_workers = 5
        session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=max_workers, pool_maxsize=max_workers)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        
        # Helper worker function
        def crawl_worker(code):
            if not crawler_state["is_running"]:
                return code, False, "stopped"
                
            crawler_state["current_unit"] = code
            is_cached = _is_unit_cached(code, target_year)
            
            if is_cached and not force_fetch:
                return code, True, "cached"
                
            success, _ = fetch_and_cache_unit(code, target_year, force_fetch, session=session)
            time.sleep(DETAIL_REQUEST_DELAY_SECONDS)
            return code, success, "fetched" if success else "failed"

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_code = {executor.submit(crawl_worker, code): code for code in master_queue}
            
            for future in as_completed(future_to_code):
                code = future_to_code[future]
                if not crawler_state["is_running"]:
                    break
                try:
                    code, success, status = future.result()
                    
                    total_done = crawler_state["processed"] + crawler_state["failed"] + 1
                    
                    if status == "stopped":
                        break
                    elif status == "cached":
                        crawler_state["logs"].append(f"[{total_done}/{crawler_state['total']}] Skipped {code} (already cached).")
                        crawler_state["processed"] += 1
                    elif status == "fetched":
                        crawler_state["logs"].append(f"[{total_done}/{crawler_state['total']}] Successfully fetched {code}.")
                        crawler_state["processed"] += 1
                    else:
                        crawler_state["failed"] += 1
                        crawler_state["logs"].append(f"[{total_done}/{crawler_state['total']}] Failed to fetch {code}.")
                        crawler_state["errors"].append(f"Failed to fetch {code}")
                except Exception as e:
                    crawler_state["failed"] += 1
                    crawler_state["logs"].append(f"Exception fetching {code}: {e}")
                    crawler_state["errors"].append(f"Exception fetching {code}: {e}")
            
        if crawler_state["is_running"]:
            crawler_state["logs"].append("Starting post-crawl parsing and serialization...")
            parse_all_cached_units(target_year, incremental=True)
            
            crawler_state["logs"].append("Starting dynamic dependency crawling...")
            from crawlers.unit_detail import discover_and_crawl_dependencies
            def portal_log(msg):
                crawler_state["logs"].append(msg)
                print(msg)
                
            discover_and_crawl_dependencies(
                target_year=target_year,
                force_fetch=force_fetch,
                session=session,
                log_callback=portal_log
            )
            crawler_state["logs"].append("Crawl run completed successfully.")
            
    except Exception as e:
        crawler_state["errors"].append(f"Critical error: {e}")
        crawler_state["logs"].append(f"Crawl aborted: {e}")
    finally:
        crawler_state["is_running"] = False

def run_rebuild_thread():
    global crawler_state
    try:
        import asyncio
        import crawlers.handbook
        import crawlers.search
        from crawlers.search import crawl_unit_codes, save_unit_codes
        from crawlers.handbook import crawl_handbook_unit_codes
        from run import SEED_OVERRIDE_CODES
        
        crawler_state["logs"] = []
        crawler_state["errors"] = []
        crawler_state["processed"] = 0
        crawler_state["total"] = 0
        crawler_state["current_unit"] = ""
        
        # Save original print functions to restore them later
        orig_handbook_print = getattr(crawlers.handbook, "print", print)
        orig_search_print = getattr(crawlers.search, "print", print)
        
        def log_to_state(*args, **kwargs):
            msg = " ".join(str(arg) for arg in args)
            crawler_state["logs"].append(msg)
            print(msg)
            
        crawlers.handbook.print = log_to_state
        crawlers.search.print = log_to_state
        
        log_to_state("Starting unit index rebuild...")
        
        # 1. Fetch active search index
        log_to_state("Phase 1: Crawling search pages (Playwright)...")
        from config import SEARCH_PREFIXES
        search_codes = {}
        for query in SEARCH_PREFIXES:
            log_to_state(f"Crawling search index for query prefix: '{query}'...")
            res = asyncio.run(crawl_unit_codes(query))
            for code, urls in res.items():
                search_codes.setdefault(code, []).extend(urls)
        
        # 2. Fetch static handbook tables
        log_to_state("Phase 2: Crawling static handbook tables...")
        handbook_codes = crawl_handbook_unit_codes()
        
        # 3. Merge, deduplicate, and write
        log_to_state("Phase 3: Merging and deduplicating unit codes...")
        unified_codes = {}
        for d in [search_codes, handbook_codes]:
            for code, urls in d.items():
                unified_codes.setdefault(code, []).extend(urls)
                
        # Inject seed overrides
        for code in SEED_OVERRIDE_CODES:
            unified_codes.setdefault(code, []).append("SEED_OVERRIDE")
            
        # Deduplicate parent URLs per code
        for code in unified_codes:
            unified_codes[code] = sorted(list(set(unified_codes[code])))
            
        save_unit_codes(unified_codes)
        log_to_state(f"Rebuild completed successfully. Found {len(unified_codes)} unit codes.")
        
        # Restore print functions
        crawlers.handbook.print = orig_handbook_print
        crawlers.search.print = orig_search_print
        
    except Exception as e:
        crawler_state["errors"].append(f"Critical rebuild error: {e}")
        crawler_state["logs"].append(f"Rebuild aborted: {e}")
    finally:
        crawler_state["is_rebuilding"] = False

@app.get("/api/crawler/status")
async def get_crawler_status():
    return crawler_state

@app.post("/api/crawler/start")
async def start_crawler(limit: Optional[int] = None, force: bool = False):
    global crawler_state
    if crawler_state["is_running"] or crawler_state.get("is_rebuilding"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Crawler or index rebuild is already running."
        )
    crawler_state["is_running"] = True
    thread = threading.Thread(target=run_crawler_thread, args=(limit, force))
    thread.daemon = True
    thread.start()
    return {"status": "started"}

@app.post("/api/crawler/rebuild")
async def rebuild_crawler_index():
    global crawler_state
    if crawler_state["is_running"] or crawler_state.get("is_rebuilding"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Crawler or index rebuild is already running."
        )
    crawler_state["is_rebuilding"] = True
    thread = threading.Thread(target=run_rebuild_thread)
    thread.daemon = True
    thread.start()
    return {"status": "started"}

@app.post("/api/crawler/stop")
async def stop_crawler():
    global crawler_state
    if not crawler_state["is_running"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Crawler is not running."
        )
    crawler_state["is_running"] = False
    return {"status": "stopping"}

@app.get("/crawler")
async def serve_crawler_page():
    """Serves the crawler control page."""
    crawler_file = STATIC_DIR / "crawler.html"
    if not crawler_file.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="crawler.html file not found."
        )
    return FileResponse(crawler_file)

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
