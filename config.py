import os
from pathlib import Path

# --- Directory Structures ---
# We use pathlib for cross-platform compatibility (Windows vs Unix path separators)
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RAW_HTML_DIR = DATA_DIR / "raw" / "html"
RAW_JSON_DIR = DATA_DIR / "raw" / "json"

# --- Target Crawling Years ---
from datetime import datetime
_now = datetime.now()
# Default to next year if running in Q4 (Oct-Dec) to align with handbook release schedules
DEFAULT_TARGET_YEAR = _now.year + (1 if _now.month >= 10 else 0)
# Fallback sequence goes back 3 years from target
CRAWL_YEARS = [DEFAULT_TARGET_YEAR - i for i in range(4)]

# --- Target URL Endpoints ---
# Public URL for checking units of study
BASE_URL = "https://www.sydney.edu.au"
SEARCH_URL = f"{BASE_URL}/units"
# Direct unit details endpoint format. E.g., https://www.sydney.edu.au/units/COMP2123
DETAIL_URL_TEMPLATE = f"{BASE_URL}/units/{{unit_code}}"

# --- Static Handbook Pages for Direct Index Seeding ---
HANDBOOK_URLS = [
    f"{BASE_URL}/handbooks/arts/coursework/arts-arts-advanced-studies/unit-of-study-table.html",
    f"{BASE_URL}/handbooks/arts/coursework/arts-extended/foundation-studies-unit-of-study-table.html",
    f"{BASE_URL}/handbooks/arts/coursework/honours-advanced-studies-media-communications/unit-of-study-table.html",
    f"{BASE_URL}/handbooks/arts/coursework/arts-laws/media-studies-unit-of-study-table.html",
    f"{BASE_URL}/handbooks/arts/coursework/arts-medicine/unit-of-study-table.html",
    f"{BASE_URL}/handbooks/arts/coursework/arts-social-work/unit-of-study-table.html",
    f"{BASE_URL}/handbooks/arts/coursework/commerce-arts/arts-unit-of-study-table.html",
    f"{BASE_URL}/handbooks/arts/coursework/commerce-arts/commerce-unit-of-study-table.html",
    f"{BASE_URL}/handbooks/arts/coursework/economics-economics-advanced-studies/economics-program-unit-of-study-tables.html",
    f"{BASE_URL}/handbooks/arts/coursework/economics-economics-advanced-studies/advanced-economics-program-unit-of-study-tables.html",
    f"{BASE_URL}/handbooks/arts/coursework/economics-economics-advanced-studies/advanced-coursework-unit-of-study-table.html",
    f"{BASE_URL}/handbooks/arts/coursework/b-economics-b-arts/economics-unit-of-study-table.html",
    f"{BASE_URL}/handbooks/arts/coursework/b-economics-b-arts/arts-unit-of-study-table.html",
    f"{BASE_URL}/handbooks/arts/coursework/education-early-childhood/unit-of-study-table.html",
    f"{BASE_URL}/handbooks/arts/coursework/education-health-physical-education/unit-of-study-table.html",
    f"{BASE_URL}/handbooks/arts/coursework/education-primary/unit-of-study-table.html",
    f"{BASE_URL}/handbooks/arts/coursework/education-secondary-advanced/unit-of-study-table.html",
    f"{BASE_URL}/handbooks/arts/coursework/education-secondary-advanced/advanced-coursework-unit-of-study-table.html",
    f"{BASE_URL}/handbooks/arts/coursework/b-international-studies/unit-of-study-table.html",
    f"{BASE_URL}/handbooks/arts/coursework/hons-b-international-studies/unit-of-study-table.html",
    f"{BASE_URL}/handbooks/arts/coursework/b-languages/unit-of-study-table.html",
    f"{BASE_URL}/handbooks/arts/coursework/b-languages-hons/unit-of-study-table.html",
    f"{BASE_URL}/handbooks/arts/coursework/b-media-communications/unit-of-study-table.html",
    f"{BASE_URL}/handbooks/arts/coursework/b-media-communications-hons/unit-of-study-table.html",
    f"{BASE_URL}/handbooks/arts/coursework/b-politics-philosophy-economics/unit-of-study-table.html",
    f"{BASE_URL}/handbooks/arts/coursework/politics-philosophy-economics-honours/unit-of-study-table-honours-international-relations.html",
    f"{BASE_URL}/handbooks/arts/coursework/politics-philosophy-economics-honours/unit-of-study-table-philosophy-honours.html",
    f"{BASE_URL}/handbooks/arts/coursework/politics-philosophy-economics-honours/unit-of-study-table-honours-economics.html",
    f"{BASE_URL}/handbooks/arts/coursework/politics-philosophy-economics-honours/unit-of-study-table-honours-political-economy.html",
    f"{BASE_URL}/handbooks/arts/coursework/science-arts/science-unit-of-study-table.html",
    f"{BASE_URL}/handbooks/arts/coursework/science-arts/arts-unit-of-study-table.html",
    f"{BASE_URL}/handbooks/arts/coursework/social-work/unit-of-study-table.html",
    f"{BASE_URL}/handbooks/arts/coursework/visual-arts-visual-arts-advanced-studies/unit-of-study-table.html",
    f"{BASE_URL}/handbooks/arts/coursework/visual-arts-visual-arts-advanced-studies/advanced-coursework-unit-of-study-table.html",
    f"{BASE_URL}/handbooks/arts/coursework/visual-arts-honours/unit-of-study-table.html",
    f"{BASE_URL}/handbooks/arts/coursework/diploma-language-studies/unit-of-study-table.html"
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
