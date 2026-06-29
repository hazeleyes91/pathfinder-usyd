import argparse
from config import DEFAULT_TARGET_YEAR
from crawlers.indexer import rebuild_unit_index
from crawlers.runner import crawl_detail_pages, crawl_dependencies
from parsers.base import parse_all_cached_units

def run_orchestrator(limit: int = None, force_fetch: bool = False, target_year: int = DEFAULT_TARGET_YEAR, rebuild_index: bool = False, search_queries: str = None):
    """
    Orchestrates the crawling pipeline:
    1. Optionally rebuilds index by combining search results and static handbook tables.
    2. Fetches and caches detail pages, respecting rate limits.
    3. Parses raw HTML to generate the final serialized JSON database.
    4. Crawls dynamic dependencies.
    """
    if rebuild_index:
        rebuild_unit_index(search_queries=search_queries)
        
    crawl_detail_pages(limit=limit, force_fetch=force_fetch, target_year=target_year)
    
    print("\n=== Phase 3: Parsing and Serialization ===")
    parse_all_cached_units(target_year, incremental=True)
    
    crawl_dependencies(force_fetch=force_fetch, target_year=target_year)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="USYD Course Planner Master Crawl Orchestrator")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of units to process")
    parser.add_argument("--force", action="store_true", help="Force fetch from web even if locally cached")
    parser.add_argument("--year", type=int, default=DEFAULT_TARGET_YEAR, help="Target academic year")
    parser.add_argument("--rebuild-index", action="store_true", help="Re-crawl search pages and handbook tables to rebuild unit_codes.json")
    parser.add_argument("--search-queries", type=str, default=None, help="Comma-separated query prefixes for the search crawler")
    
    args = parser.parse_args()
    
    run_orchestrator(
        limit=args.limit, 
        force_fetch=args.force, 
        target_year=args.year, 
        rebuild_index=args.rebuild_index, 
        search_queries=args.search_queries
    )
