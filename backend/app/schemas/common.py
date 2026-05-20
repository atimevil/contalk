from typing import Any, Generic, Optional, TypeVar
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

T = TypeVar("T")

DISCLAIMER = "본 분석은 법률 조언이 아닌 정보 제공 서비스입니다."


class CamelModel(BaseModel):
    """
    모든 스키마의 베이스 클래스.
    응답 직렬화 시 snake_case 필드를 camelCase alias로 변환하여
    프론트엔드 TypeScript 타입과 자동으로 호환된다.

    FastAPI 라우터에서 반드시 `response_model_by_alias=True` 또는
    전역 설정을 통해 alias 직렬화를 활성화해야 한다.
    """
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,   # snake_case 입력도 허용 (내부 코드 호환)
        from_attributes=True,
    )


class PaginationMeta(CamelModel):
    total: int
    page: int
    per_page: int
    total_pages: int


class SuccessResponse(CamelModel, Generic[T]):
    success: bool = True
    data: T
    meta: Optional[PaginationMeta] = None
    disclaimer: str = DISCLAIMER


class ErrorDetail(CamelModel):
    code: str
    message: str
    details: Optional[Any] = None
    field: Optional[str] = None


class ErrorResponse(CamelModel):
    success: bool = False
    error: ErrorDetail
    request_id: str
    disclaimer: str = DISCLAIMER
