import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import RAW_HTML_DIR, DETAIL_REQUEST_DELAY_SECONDS, DEFAULT_TARGET_YEAR
from crawlers.unit_detail import load_target_codes, fetch_and_cache_unit, discover_and_crawl_dependencies
from crawlers.indexer import SEED_OVERRIDE_CODES

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
        from parsers.base import parse_all_cached_units
        parse_all_cached_units(target_year)
    return success

def crawl_detail_pages(limit: int = None, force_fetch: bool = False, target_year: int = DEFAULT_TARGET_YEAR, log_func=print):
    """
    Loads compiled codes from raw JSON index, unions them with seed codes, 
    and fetches detail pages, respecting rate limits.
    """
    log_func("=== Phase 2: Aggregating Unit Queue & Crawling ===")
    discovered_codes = load_target_codes()
    log_func(f"Loaded {len(discovered_codes)} discovered codes from search index.")
    
    # Merge lists using a set to deduplicate
    master_queue = sorted(list(set(discovered_codes + SEED_OVERRIDE_CODES)))
    log_func(f"Total unique unit codes in crawler queue: {len(master_queue)} (including {len(SEED_OVERRIDE_CODES)} manual seeds).")
    
    if limit:
        master_queue = master_queue[:limit]
        log_func(f"Applying limit constraint: Crawl queue truncated to first {limit} units.")
        
    log_func("\n--- Crawling Detail Pages ---")
    skipped = 0
    fetched = 0
    failed = 0
    
    max_workers = 5
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=max_workers, pool_maxsize=max_workers)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    
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
                    log_func(f"[{total_done}/{len(master_queue)}] Skipped {code} (already cached).")
                    skipped += 1
                elif status == "fetched":
                    log_func(f"[{total_done}/{len(master_queue)}] Successfully fetched {code}.")
                    fetched += 1
                else:
                    log_func(f"[{total_done}/{len(master_queue)}] Failed to fetch {code}.")
                    failed += 1
            except Exception as e:
                log_func(f"Exception fetching {code}: {e}")
                failed += 1
        
    log_func(f"\nCrawling complete. Stats: Total={len(master_queue)}, Skipped={skipped}, Fetched={fetched}, Failed={failed}")
    
def crawl_dependencies(force_fetch: bool = False, target_year: int = DEFAULT_TARGET_YEAR, log_func=print):
    """
    Crawls dynamic dependencies.
    """
    log_func("\n=== Phase 4: Dynamic Dependency Crawling ===")
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=5, pool_maxsize=5)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    discover_and_crawl_dependencies(target_year=target_year, force_fetch=force_fetch, session=session, log_callback=log_func)
