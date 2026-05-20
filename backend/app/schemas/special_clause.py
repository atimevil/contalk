from typing import List, Literal
from pydantic import Field

from app.schemas.common import CamelModel, DISCLAIMER

SpecialClauseCategory = Literal[
    "renewal", "repair", "deposit", "entry", "termination", "facility", "other"
]
RelatedRisk = Literal["high", "medium", "caution"]


class SpecialClause(CamelModel):
    id: str
    related_risk_clause_id: str
    related_risk: RelatedRisk
    title: str
    text: str
    category: SpecialClauseCategory
    is_editable: bool = True


class SpecialClausesResponse(CamelModel):
    report_id: str
    clauses: List[SpecialClause]
    disclaimer: str = DISCLAIMER


class UpdateSpecialClauseRequest(CamelModel):
    text: str = Field(..., max_length=2000)


class UpdateSpecialClauseResponse(CamelModel):
    id: str
    text: str
    updated_at: str  # ISO 8601
    disclaimer: str = DISCLAIMER
