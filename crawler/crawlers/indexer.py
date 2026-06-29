import asyncio
from crawlers.search import crawl_unit_codes, save_unit_codes
from crawlers.handbook import crawl_handbook_unit_codes
from config import SEARCH_PREFIXES

# Expanded seed list of known computing units that might be missing from search indexes
SEED_OVERRIDE_CODES = ["COMP2022", "COMP2922", "MATH1064"]

def rebuild_unit_index(search_queries: str = None, log_func=print):
    """
    Rebuilds the unit index by combining search results and static handbook tables.
    """
    log_func("=== Phase 1: Rebuilding unit index cache ===")
    
    # 1. Fetch active search index
    log_func("Crawling search pages (Playwright)...")
    if search_queries:
        queries = [q.strip() for q in search_queries.split(",") if q.strip()]
    else:
        queries = SEARCH_PREFIXES
        
    search_codes = {}
    for query in queries:
        log_func(f"Crawling search index for query prefix: '{query}'...")
        res = asyncio.run(crawl_unit_codes(query))
        for code, urls in res.items():
            search_codes.setdefault(code, []).extend(urls)
    
    # 2. Fetch static handbook tables
    log_func("Crawling static handbook tables...")
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
    log_func(f"Rebuild completed successfully. Found {len(unified_codes)} unit codes.")
