from typing import List, Literal, Optional, Dict
from pydantic import BaseModel, Field

class PlacementGroup(BaseModel):
    year: int = Field(description="Year number, e.g. 1, 2, 3")
    term: Literal["summ", "sem1", "wint", "sem2"] = Field(description="Teaching period code")
    codes: List[str] = Field(description="List of unit codes placed in this teaching period")

class ValidationRequest(BaseModel):
    mode: Literal["free", "struct"] = Field(default="free", description="Planning mode")
    award_code: Optional[str] = Field(default=None, description="Degree award code (ignored for now)")
    start_year: int = Field(default=2026, description="Commencement calendar year")
    placements: List[PlacementGroup] = Field(description="List of chronological term placements")

class WarningDetail(BaseModel):
    type: Literal["overload", "session_mismatch", "prereq_unmet", "coreq_unmet", "prohibited"]
    unit_code: Optional[str] = None
    year: Optional[int] = None
    term: Optional[str] = None
    message: str
    soft_warning: Optional[str] = None

class ValidationResponse(BaseModel):
    valid: bool
    warnings: List[WarningDetail]
    progress: Optional[Dict] = None
