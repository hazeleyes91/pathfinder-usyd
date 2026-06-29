import time
import argparse
import asyncio
import requests
from pathlib import Path
from config import DATA_DIR, RAW_HTML_DIR, REQUEST_DELAY_SECONDS, DETAIL_REQUEST_DELAY_SECONDS, CRAWL_YEARS, DEFAULT_TARGET_YEAR
from crawlers.unit_detail import load_target_codes, fetch_and_cache_unit
from parsers.base import parse_all_cached_units

# Expanded seed list of known computing units that might be missing from search indexes
SEED_OVERRIDE_CODES = ["COMP2022", "COMP2922", "MATH1064"]

def _is_unit_cached(unit_code: str, target_year: int) -> bool:
    """Returns True if the unit HTML is cached in the target year directory."""
    return (RAW_HTML_DIR / str(target_year) / f"{unit_code}.html").exists()

def ensure_unit_cached(unit_code: str, target_year: int = DEFAULT_TARGET_YEAR) -> bool:
    """
    Checks if a unit code is cached locally in our database.
    If missing, fetches it on demand and triggers re-serialization.
    """
    is_cached = _is_unit_cached(unit_code, target_year)
                
    if is_cached:
        return True
        
    print(f"Dynamic discovery triggered: Unit {unit_code} is missing from cache. Fetching...")
    success, resolved_year = fetch_and_cache_unit(unit_code, target_year)
    if success and resolved_year:
        parse_all_cached_units(target_year)
    return success

def run_orchestrator(limit: int = None, force_fetch: bool = False, target_year: int = DEFAULT_TARGET_YEAR, rebuild_index: bool = False, search_queries: str = None):
    """
    Orchestrates the crawling pipeline:
    1. Optionally rebuilds index by combining search results and static handbook tables.
    2. Loads compiled codes from raw JSON index.
    3. Unions them with seed codes to guarantee coverage.
    4. Fetches and caches detail pages, respecting rate limits.
    5. Parses raw HTML to generate the final serialized JSON database.
    """
    print("=== Phase 1: Aggregating Unit Queue ===")
    
    if rebuild_index:
        print("Rebuilding unit index cache...")
        from crawlers.search import crawl_unit_codes, save_unit_codes
        from crawlers.handbook import crawl_handbook_unit_codes
        from config import SEARCH_PREFIXES
        
        # 1. Fetch active search index
        print("Crawling search pages (Playwright)...")
        if search_queries:
            queries = [q.strip() for q in search_queries.split(",") if q.strip()]
        else:
            queries = SEARCH_PREFIXES
            
        search_codes = {}
        for query in queries:
            print(f"Crawling search index for query prefix: '{query}'...")
            res = asyncio.run(crawl_unit_codes(query))
            for code, urls in res.items():
                search_codes.setdefault(code, []).extend(urls)
        
        # 2. Fetch static handbook tables
        print("Crawling static handbook tables...")
        handbook_codes = crawl_handbook_unit_codes()
        
        # 3. Merge, deduplicate, and write
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
        
    discovered_codes = load_target_codes()
    print(f"Loaded {len(discovered_codes)} discovered codes from search index.")
    
    # Merge lists using a set to deduplicate
    master_queue = sorted(list(set(discovered_codes + SEED_OVERRIDE_CODES)))
    print(f"Total unique unit codes in crawler queue: {len(master_queue)} (including {len(SEED_OVERRIDE_CODES)} manual seeds).")
    
    if limit:
        master_queue = master_queue[:limit]
        print(f"Applying limit constraint: Crawl queue truncated to first {limit} units.")
        
    print("\n=== Phase 2: Crawling Detail Pages ===")
    skipped = 0
    fetched = 0
    failed = 0
    
    max_workers = 5
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=max_workers, pool_maxsize=max_workers)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    def crawl_worker(code):
        is_cached = _is_unit_cached(code, target_year)
        if is_cached and not force_fetch:
            return code, True, "cached"
        success, _ = fetch_and_cache_unit(code, target_year, force_fetch=force_fetch, session=session)
        time.sleep(DETAIL_REQUEST_DELAY_SECONDS)
        return code, success, "fetched" if success else "failed"

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_code = {executor.submit(crawl_worker, code): code for code in master_queue}
        
        for future in as_completed(future_to_code):
            code = future_to_code[future]
            try:
                code, success, status = future.result()
                total_done = skipped + fetched + failed + 1
                if status == "cached":
                    print(f"[{total_done}/{len(master_queue)}] Skipped {code} (already cached).")
                    skipped += 1
                elif status == "fetched":
                    print(f"[{total_done}/{len(master_queue)}] Successfully fetched {code}.")
                    fetched += 1
                else:
                    print(f"[{total_done}/{len(master_queue)}] Failed to fetch {code}.")
                    failed += 1
            except Exception as e:
                print(f"Exception fetching {code}: {e}")
                failed += 1
        
    print(f"\nCrawling complete. Stats: Total={len(master_queue)}, Skipped={skipped}, Fetched={fetched}, Failed={failed}")
    
    print("\n=== Phase 3: Parsing and Serialization ===")
    parse_all_cached_units(target_year, incremental=True)
    
    print("\n=== Phase 4: Dynamic Dependency Crawling ===")
    from crawlers.unit_detail import discover_and_crawl_dependencies
    discover_and_crawl_dependencies(target_year=target_year, force_fetch=force_fetch, session=session)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="USYD Course Planner Master Crawl Orchestrator")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of units to process")
    parser.add_argument("--force", action="store_true", help="Force fetch from web even if locally cached")
    parser.add_argument("--year", type=int, default=DEFAULT_TARGET_YEAR, help="Target academic year")
    parser.add_argument("--rebuild-index", action="store_true", help="Re-crawl search pages and handbook tables to rebuild unit_codes.json")
    parser.add_argument("--search-queries", type=str, default=None, help="Comma-separated query prefixes for the search crawler")
    
    args = parser.parse_args()
    
    run_orchestrator(limit=args.limit, force_fetch=args.force, target_year=args.year, rebuild_index=args.rebuild_index, search_queries=args.search_queries)
