import re
import time
import requests
from bs4 import BeautifulSoup
from crawlers.config import HANDBOOK_URLS, REQUEST_DELAY_SECONDS

def crawl_handbook_unit_codes() -> list[str]:
    """
    Crawls the defined list of static USYD handbook pages and
    extracts all unique unit codes referenced in the text.
    """
    all_codes = []
    
    for url in HANDBOOK_URLS:
        print(f"Crawling handbook page: {url}")
        try:
            r = requests.get(url, timeout=15)
            if r.status_code == 200 and "/errors/404.html" not in r.url:
                soup = BeautifulSoup(r.text, "html.parser")
                body_text = soup.get_text()
                
                # Extract all occurrences of unit codes (4 uppercase letters + 4 digits)
                codes = re.findall(r"\b([A-Z]{4}\d{4})\b", body_text)
                print(f"  Extracted {len(codes)} instances ({len(set(codes))} unique) from page.")
                all_codes.extend(codes)
            else:
                print(f"  Error: Received code {r.status_code} or redirect to 404.")
        except Exception as e:
            print(f"  Exception crawling handbook page {url}: {e}")
            
        # Obey rate limiting politeness delay
        time.sleep(REQUEST_DELAY_SECONDS)
        
    unique_codes = sorted(list(set(all_codes)))
    print(f"Handbook crawling completed. Found {len(unique_codes)} unique unit codes in total.")
    return unique_codes

if __name__ == "__main__":
    codes = crawl_handbook_unit_codes()
    print(f"Sample of extracted codes: {codes[:20]}")
