import os
from pathlib import Path

# --- Directory Structures ---
# We use pathlib for cross-platform compatibility (Windows vs Unix path separators)
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RAW_HTML_DIR = DATA_DIR / "raw" / "html"
RAW_JSON_DIR = DATA_DIR / "raw" / "json"

# --- Target Crawling Years ---
# Current target year is 2026. Fallback sequence goes back 3 years.
CRAWL_YEARS = [2026, 2025, 2024, 2023]

# --- Target URL Endpoints ---
# Public URL for checking units of study
BASE_URL = "https://www.sydney.edu.au"
SEARCH_URL = f"{BASE_URL}/units"
# Direct unit details endpoint format. E.g., https://www.sydney.edu.au/units/COMP2123
DETAIL_URL_TEMPLATE = f"{BASE_URL}/units/{{unit_code}}"

# --- Static Handbook Pages for Direct Index Seeding ---
HANDBOOK_URLS = [
    f"{BASE_URL}/handbooks/science/table-a/subject-areas/computer-science/unit-of-study-table.html",
    f"{BASE_URL}/handbooks/science/table-a/subject-areas/data-science/unit-of-study-table.html",
    f"{BASE_URL}/handbooks/science/table-a/subject-areas/mathematics/unit-of-study-table.html"
]

# --- Crawling & Request Politeness Settings ---
# To prevent trigger IP blocking or server overload, we introduce a delay between requests
REQUEST_DELAY_SECONDS = 1.5
# Request timeout in milliseconds (used for Playwright and HTTP requests)
TIMEOUT_MS = 30000
# Run Playwright in headless mode (no visual browser window) to save resources
PLAYWRIGHT_HEADLESS = True

def init_directories():
    """
    Bootstraps the raw data directories if they do not already exist.
    """
    for year in CRAWL_YEARS:
        year_html_dir = RAW_HTML_DIR / str(year)
        year_html_dir.mkdir(parents=True, exist_ok=True)
    
    RAW_JSON_DIR.mkdir(parents=True, exist_ok=True)
    print("Directory bootstrap complete.")
    print(f"Data root: {DATA_DIR}")
    print(f"HTML cache directory: {RAW_HTML_DIR}")

def get_ai_model():
    """
    Determines and returns the AI model to use based on environment keys.
    """
    gemini_key = os.getenv("GEMINI_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    if gemini_key:
        os.environ["GOOGLE_API_KEY"] = gemini_key
        return "google:gemini-3.1-flash-lite"
    elif openai_key:
        return "openai:gpt-4o-mini"
    else:
        from pydantic_ai.models.test import TestModel
        return TestModel()

if __name__ == "__main__":
    init_directories()
