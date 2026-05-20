from typing import Optional, List, Literal
from pydantic import BaseModel

from app.schemas.common import CamelModel, DISCLAIMER

AnalysisStatus = Literal["queued", "uploading", "ocr", "analyzing", "generating", "completed", "failed"]
AnalysisStepId = Literal["upload", "ocr", "analyze", "clause"]
ContractType = Literal["jeonse", "monthly", "unknown"]
RiskLevel = Literal["high", "medium", "caution", "safe"]


class UploadResponse(CamelModel):
    job_id: str
    estimated_seconds: int = 60
    status: str = "queued"
    disclaimer: str = DISCLAIMER


class AnalysisStatusResponse(CamelModel):
    job_id: str
    status: AnalysisStatus
    progress: int  # 0-100
    current_step: AnalysisStepId
    completed_steps: List[AnalysisStepId]
    report_id: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    disclaimer: str = DISCLAIMER


class LawReference(CamelModel):
    law_name: str
    article: str
    summary: str
    url: Optional[str] = None


class AnalysisClause(CamelModel):
    id: str
    risk: RiskLevel
    clause_number: Optional[str] = None
    original_text: str
    explanation: str
    law_reference: Optional[LawReference] = None
    recommendation: Optional[str] = None


class RiskSummary(CamelModel):
    high: int
    medium: int
    caution: int
    safe: int


class AnalysisResultResponse(CamelModel):
    report_id: str
    job_id: str
    created_at: str
    contract_type: ContractType
    risk_score: int  # 0-100
    risk_level: RiskLevel
    summary: RiskSummary
    clauses: List[AnalysisClause]
    ocr_text: Optional[str] = None
    disclaimer: str = DISCLAIMER


class AnalysisHistoryItem(CamelModel):
    report_id: str
    created_at: str
    contract_type: ContractType
    risk_score: int
    risk_level: RiskLevel
    summary: RiskSummary
    disclaimer: str = DISCLAIMER


# Pydantic models matching role system prompt spec
class RiskClause(CamelModel):
    text: str
    risk: Literal["high", "medium", "caution", "normal"]
    law_ref: str
    explanation: str


class AnalysisResult(CamelModel):
    contract_id: str
    clauses: List[RiskClause]
    summary: dict  # {"high": 2, "medium": 3, "caution": 1}
    special_clauses: List[str]
    disclaimer: str = DISCLAIMER
