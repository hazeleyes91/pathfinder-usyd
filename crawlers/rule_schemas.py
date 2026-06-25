from typing import List, Literal, Union, Optional
from pydantic import BaseModel, Field

class UnitRequirement(BaseModel):
    type: Literal["unit"] = "unit"
    unit_code: str = Field(description="8-character USYD unit code (4 letters + 4 digits), e.g. COMP2123")

class CreditPointRequirement(BaseModel):
    type: Literal["credit_points"] = "credit_points"
    credit_points: int = Field(description="Number of credit points required, e.g. 12 or 24")
    level: Optional[int] = Field(None, description="Optional level constraint, e.g. 3000 for 3000-level units, or null if none")
    subject: str = Field(description="Subject prefix filter, e.g. 'COMP', 'INFO', or 'ANY'")

class LogicalRequirement(BaseModel):
    type: Literal["logical"] = "logical"
    operator: Literal["AND", "OR"] = Field(description="Logical operator connecting operands")
    operands: List[Union[UnitRequirement, CreditPointRequirement, 'LogicalRequirement']] = Field(
        description="List of sub-requirements connected by the operator"
    )

class RuleParseResult(BaseModel):
    type: Literal["none", "unit", "credit_points", "logical"] = Field(description="Root type of the parsed rule")
    rule: Union[None, UnitRequirement, CreditPointRequirement, LogicalRequirement] = Field(
        description="The parsed rule node, or null if the rule is empty/None"
    )

LogicalRequirement.model_rebuild()
RuleParseResult.model_rebuild()