import time
import argparse
import asyncio
from pathlib import Path
from crawlers.config import DATA_DIR, RAW_HTML_DIR, REQUEST_DELAY_SECONDS
from crawlers.unit_detail_crawler import load_target_codes, fetch_and_cache_unit
from crawlers.parser_base import parse_all_cached_units

# Expanded seed list of known computing units that might be missing from search indexes
SEED_OVERRIDE_CODES = ["COMP2022", "COMP2922", "MATH1064"]

def ensure_unit_cached(unit_code: str, target_year: int = 2026) -> bool:
    """
    Checks if a unit code is cached locally in our database.
    If missing, fetches it on demand and triggers re-serialization.
    """
    cache_path = RAW_HTML_DIR / str(target_year) / f"{unit_code}.html"
    is_cached = cache_path.exists()
    
    if not is_cached:
        for year in [2025, 2024, 2023]:
            if (RAW_HTML_DIR / str(year) / f"{unit_code}.html").exists():
                is_cached = True
                break
                
    if is_cached:
        return True
        
    print(f"Dynamic discovery triggered: Unit {unit_code} is missing from cache. Fetching...")
    success = fetch_and_cache_unit(unit_code)
    if success:
        parse_all_cached_units(target_year)
    return success

def run_orchestrator(limit: int = None, force_fetch: bool = False, target_year: int = 2026, rebuild_index: bool = False):
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
        from crawlers.search_crawler import crawl_unit_codes, save_unit_codes
        from crawlers.handbook_crawler import crawl_handbook_unit_codes
        
        # 1. Fetch active search index
        print("Crawling search pages (Playwright)...")
        search_codes = asyncio.run(crawl_unit_codes("COMP"))
        
        # 2. Fetch static handbook tables
        print("Crawling static handbook tables...")
        handbook_codes = crawl_handbook_unit_codes()
        
        # 3. Merge, deduplicate, and write
        unified_codes = sorted(list(set(search_codes + handbook_codes)))
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
    
    for idx, code in enumerate(master_queue):
        cache_path_2026 = RAW_HTML_DIR / str(target_year) / f"{code}.html"
        is_cached = cache_path_2026.exists()
        
        if not is_cached:
            for fallback_year in [2025, 2024, 2023]:
                if (RAW_HTML_DIR / str(fallback_year) / f"{code}.html").exists():
                    is_cached = True
                    break
        
        if is_cached and not force_fetch:
            print(f"[{idx + 1}/{len(master_queue)}] Skipped {code} (already cached).")
            skipped += 1
            continue
            
        success = fetch_and_cache_unit(code)
        if success:
            fetched += 1
        else:
            failed += 1
            
        time.sleep(REQUEST_DELAY_SECONDS)
        
    print(f"\nCrawling complete. Stats: Total={len(master_queue)}, Skipped={skipped}, Fetched={fetched}, Failed={failed}")
    
    print("\n=== Phase 3: Parsing and Serialization ===")
    parse_all_cached_units(target_year)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="USYD Course Planner Master Crawl Orchestrator")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of units to process")
    parser.add_argument("--force", action="store_true", help="Force fetch from web even if locally cached")
    parser.add_argument("--year", type=int, default=2026, help="Target academic year")
    parser.add_argument("--rebuild-index", action="store_true", help="Re-crawl search pages and handbook tables to rebuild unit_codes.json")
    
    args = parser.parse_args()
    
    run_orchestrator(limit=args.limit, force_fetch=args.force, target_year=args.year, rebuild_index=args.rebuild_index)
