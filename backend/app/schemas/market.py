"""
시세 조회 관련 Pydantic 스키마

GET /market/districts   — 시도·시군구 코드 목록
GET /market/apt-trade   — 아파트 매매 실거래가 통계
GET /market/apt-rent    — 아파트 전세 실거래가 통계
"""
from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, Field


class DistrictItem(BaseModel):
    """시군구 하나"""
    name: str = Field(..., description="시군구 명칭 (예: 강남구)")
    code: str = Field(..., description="법정동코드 5자리 (예: 11680)")


class SidoItem(BaseModel):
    """시도 + 하위 시군구 목록"""
    name: str = Field(..., description="시도 명칭 (예: 서울특별시)")
    code: str = Field(..., description="시도코드 2자리 (예: 11)")
    districts: List[DistrictItem] = Field(..., alias="시군구", description="시군구 목록")

    model_config = {"populate_by_name": True}


class DistrictsResponse(BaseModel):
    """GET /market/districts 응답"""
    items: List[SidoItem]


# ─── 매매 실거래가 ─────────────────────────────────────────────────────────────

class AptTradeItem(BaseModel):
    """아파트 매매 단건 데이터"""
    apartment: str = Field(..., description="아파트 명칭")
    area: float = Field(..., description="전용면적 (㎡)")
    price_krw: int = Field(..., description="거래금액 (원)")
    floor: Optional[str] = Field(None, description="층")
    deal_date: str = Field(..., description="계약일 (YYYY-MM-DD)")


class AptTradeStat(BaseModel):
    """지역·면적대별 매매가 통계"""
    district_code: str
    district_name: Optional[str] = None
    deal_ym: str = Field(..., description="조회 기준 최근 연월 (YYYYMM)")
    period_from: Optional[str] = Field(None, description="집계 시작 연월 (YYYYMM), 다중 월 조회 시 포함")
    period_to: Optional[str] = Field(None, description="집계 종료 연월 (YYYYMM), 다중 월 조회 시 포함")
    count: int = Field(..., description="거래 건수")
    avg_price_krw: int = Field(..., description="평균 매매가 (원)")
    min_price_krw: int = Field(..., description="최저 매매가 (원)")
    max_price_krw: int = Field(..., description="최고 매매가 (원)")
    items: List[AptTradeItem] = Field(default_factory=list, description="원본 건별 데이터")


# ─── 전세 실거래가 ─────────────────────────────────────────────────────────────

class AptRentItem(BaseModel):
    """아파트 전세 단건 데이터"""
    apartment: str = Field(..., description="아파트 명칭")
    area: float = Field(..., description="전용면적 (㎡)")
    deposit_krw: int = Field(..., description="보증금 (원)")
    monthly_rent_krw: int = Field(0, description="월세 (원, 0이면 전세)")
    is_jeonse: bool = Field(..., description="전세 여부 (월세=false)")
    floor: Optional[str] = Field(None, description="층")
    deal_date: str = Field(..., description="계약일 (YYYY-MM)")


class AptRentStat(BaseModel):
    """지역·면적대별 전세/월세 통계"""
    district_code: str
    district_name: Optional[str] = None
    deal_ym: str = Field(..., description="조회 기준 최근 연월 (YYYYMM)")
    period_from: Optional[str] = Field(None, description="집계 시작 연월 (YYYYMM), 다중 월 조회 시 포함")
    period_to: Optional[str] = Field(None, description="집계 종료 연월 (YYYYMM), 다중 월 조회 시 포함")
    rent_type: str = Field("jeonse", description="집계 유형: 'jeonse'=전세, 'monthly'=월세")
    count: int = Field(..., description="거래 건수")
    avg_deposit_krw: int = Field(..., description="평균 보증금 (원)")
    min_deposit_krw: int = Field(..., description="최저 보증금 (원)")
    max_deposit_krw: int = Field(..., description="최고 보증금 (원)")
    avg_monthly_rent_krw: Optional[int] = Field(None, description="평균 월세 (원, 월세 집계 시만 포함)")
    min_monthly_rent_krw: Optional[int] = Field(None, description="최저 월세 (원)")
    max_monthly_rent_krw: Optional[int] = Field(None, description="최고 월세 (원)")
    items: List[AptRentItem] = Field(default_factory=list, description="원본 건별 데이터")
