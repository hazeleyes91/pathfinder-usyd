from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sys
from pathlib import Path

# Parent imports
sys.path.append(str(Path(__file__).resolve().parents[1]))
from api.models import ValidationRequest, ValidationResponse
from api.validation.engine import run_validation

app = FastAPI(title="USYD Course Planner - Validation API")

# Add CORS Middleware to support client-side requests from any origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/validate-plan", response_model=ValidationResponse)
async def validate_plan(request: ValidationRequest):
    """
    Statelessly validates the complete chronological placements of a student's study plan.
    """
    return run_validation(request)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
