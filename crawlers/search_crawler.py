import asyncio
import json
import re
from pathlib import Path
from playwright.async_api import async_playwright
from crawlers.config import SEARCH_URL, PLAYWRIGHT_HEADLESS, DATA_DIR

async def crawl_unit_codes(query: str) -> list[str]:
    """
    Crawls USYD unit search page for a prefix query, extracts unique unit codes,
    and returns them.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=PLAYWRIGHT_HEADLESS)
        page = await browser.new_page()
        
        # Inject query and number of results directly in the URL hash
        rrp = 100
        url = f"{SEARCH_URL}#q={query}&numberOfResults={rrp}"
        await page.goto(url)
        
        # Wait for the Coveo dynamic components to finish loading results
        await page.wait_for_load_state("networkidle")
        
        # Loop and click 'Show more' until all items are loaded
        load_more_selector = 'atomic-load-more-results button[part="load-more-results-button"]'
        load_more_button = page.locator(load_more_selector)
        
        while await load_more_button.is_visible():
            # force=True prevents issues if cookie banner overlay intercepts coordinates
            await load_more_button.click(force=True)
            await page.wait_for_timeout(2000)
            await page.wait_for_load_state("networkidle")

        # Parse links and extract unique 8-character unit codes
        links = await page.locator("a").all()
        unit_codes = []
        for link in links:
            href = await link.get_attribute("href")
            if href:
                match = re.search(r"/units/([A-Z]{4}\d{4})", href)
                if match:
                    unit_codes.append(match.group(1))
                    
        unique_codes = sorted(list(set(unit_codes)))
        return unique_codes

def save_unit_codes(unit_codes: list[str], filename: str = "unit_codes.json"):
    """
    Writes the list of unit codes to DATA_DIR / 'raw' / filename in JSON format.
    """
    out_dir = DATA_DIR / "raw" / "json"
    out_dir.mkdir(parents=True, exist_ok=True)
    target_path = out_dir / filename
    
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(unit_codes, f, indent=2)
    print(f"Saved {len(unit_codes)} unit codes to {target_path}")

if __name__ == "__main__":
    # Test script execution
    codes = asyncio.run(crawl_unit_codes("COMP"))
    save_unit_codes(codes)
    print(f"Extracted {len(codes)} unique unit codes.")

        


