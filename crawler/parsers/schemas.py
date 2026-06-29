from typing import List, Literal, Union, Optional, Set
from pydantic import BaseModel, Field

class UnitRequirement(BaseModel):
    type: Literal["unit"] = "unit"
    unit_code: str = Field(description="8-character USYD unit code (4 letters + 4 digits), e.g. COMP2123")
    soft_warning: Optional[str] = Field(None, description="Soft warning message for bypassed/ignored requirements")

class CreditPointRequirement(BaseModel):
    type: Literal["credit_points"] = "credit_points"
    credit_points: int = Field(description="Number of credit points required, e.g. 12 or 24")
    level: Optional[int] = Field(None, description="Optional level constraint, e.g. 3000 for 3000-level units, or null if none")
    unit_codes: Optional[Set[str]] = Field(None, description="Eligible pool of unit codes to draw credit points from, e.g. {'AGRO3004', 'BIOL2X31'}. Null means any unit.")
    subjects: Optional[Set[str]] = Field(None, description="Allowlist of subject prefixes, e.g. {'ANAT', 'BIOL'}. Null means any subject.")
    soft_warning: Optional[str] = Field(None, description="Soft warning message for bypassed/ignored requirements")

class UnitGroupRequirement(BaseModel):
    type: Literal["unit_group"] = "unit_group"
    operator: Literal["AND", "OR"] = Field(description="Logical operator connecting the unit group")
    unit_codes: Set[str] = Field(description="Set of unit codes to evaluate")
    soft_warning: Optional[str] = Field(None, description="Soft warning message for bypassed/ignored requirements")

class LogicalRequirement(BaseModel):
    type: Literal["logical"] = "logical"
    operator: Literal["AND", "OR"] = Field(description="Logical operator connecting operands")
    operands: List[Union[UnitRequirement, CreditPointRequirement, UnitGroupRequirement, 'LogicalRequirement']] = Field(
        description="List of sub-requirements connected by the operator"
    )
    soft_warning: Optional[str] = Field(None, description="Soft warning message for bypassed/ignored requirements")

class RuleParseResult(BaseModel):
    type: Literal["none", "unit", "credit_points", "unit_group", "logical"] = Field(description="Root type of the parsed rule")
    rule: Union[None, UnitRequirement, CreditPointRequirement, UnitGroupRequirement, LogicalRequirement] = Field(
        description="The parsed rule node, or null if the rule is empty/None"
    )
    soft_warning: Optional[str] = Field(None, description="Soft warning message for bypassed/ignored requirements")

LogicalRequirement.model_rebuild()
RuleParseResult.model_rebuild()
