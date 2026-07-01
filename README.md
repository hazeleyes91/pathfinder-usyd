# Pathfinder USYD

An independent, visual degree planner and prerequisite validation engine for students. 
This tool provides a drag-and-drop interface for mapping out university degree structures while automatically validating credit point limits, semester availabilities, and complex prerequisite/corequisite dependencies against a compiled unit database.

## Architecture

- **Frontend:** Vanilla JS / HTML / CSS (Serverless static deployment)
- **Backend:** Python FastAPI (Serverless API functions)
- **Database:** Bundled read-only SQLite (`data/handbook.db`)
- **CI/CD:** Automated testing via GitHub Actions and deployment on Vercel

## Local Development

1. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
2. **Run Local Server:**
   ```bash
   python -m api.main
   ```
3. **Run Tests:**
   ```bash
   python -m pytest api/tests/
   ```
## Disclaimer

**Pathfinder Sydney is an independent, open-source student project.** It is not affiliated with, endorsed by, or associated with the University of Sydney. Handbook data is provided for planning purposes only and may contain inaccuracies. Always consult the official university handbook for finalizing your official degree requirements.
