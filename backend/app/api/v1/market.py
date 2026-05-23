"""
시세 조회 API 엔드포인트

GET /market/districts                — 시도·시군구 코드 목록 (인증 불필요)
GET /market/apt-trade                — 아파트 매매 실거래가 통계 (인증 불필요)
GET /market/apt-rent                 — 아파트 전세 실거래가 통계 (인증 불필요)
GET /market/summary                  — 매매+전세 통합 (전세가율 계산용)

주의: MOLIT_API_KEY가 미설정이면 503 반환.
"""
from __future__ import annotations

from typing import Optional
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, status

from app.core.config import settings
from app.services import market_service
from app.schemas.market import (
    DistrictsResponse,
    AptTradeStat,
    AptRentStat,
    SidoItem,
)
from app.schemas.common import DISCLAIMER

router = APIRouter(prefix="/market", tags=["market"])


def _get_api_key() -> str:
    """MOLIT API 키 반환. 미설정 시 503."""
    key = getattr(settings, "MOLIT_API_KEY", "")
    if not key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": {
                    "code": "MOLIT_API_KEY_NOT_SET",
                    "message": "시세 조회 서비스가 아직 설정되지 않았습니다.",
                },
                "disclaimer": DISCLAIMER,
            },
        )
    return key


def _validate_district_code(district_code: str) -> None:
    """법정동코드 5자리 형식 검증."""
    if not district_code.isdigit() or len(district_code) != 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "district_code는 5자리 숫자여야 합니다. (예: 11680)",
                },
                "disclaimer": DISCLAIMER,
            },
        )


def _validate_deal_ym(deal_ym: str) -> None:
    """계약연월 YYYYMM 형식 검증."""
    if not deal_ym.isdigit() or len(deal_ym) != 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "deal_ym은 YYYYMM 형식의 6자리 숫자여야 합니다. (예: 202504)",
                },
                "disclaimer": DISCLAIMER,
            },
        )


def _default_deal_ym() -> str:
    """기본 조회 연월: 직전 달."""
    try:
        from dateutil.relativedelta import relativedelta  # type: ignore
        past = datetime.now(timezone.utc) - relativedelta(months=1)
        return past.strftime("%Y%m")
    except ImportError:
        now = datetime.now(timezone.utc)
        return now.strftime("%Y%m")


# ─── 엔드포인트 ──────────────────────────────────────────────────────────────

@router.get(
    "/districts",
    response_model=DistrictsResponse,
    summary="시도·시군구 코드 목록",
    description="전국 시도와 시군구의 법정동코드를 반환합니다. MOLIT API 지역 선택 시 사용하세요.",
)
async def get_districts():
    """시도·시군구 코드 목록 반환 (정적 데이터, 인증 불필요)."""
    items: list[SidoItem] = market_service.load_districts()
    return DistrictsResponse(items=items)


@router.get(
    "/apt-trade",
    response_model=AptTradeStat,
    summary="아파트 매매 실거래가 통계",
    description=(
        "국토교통부 실거래가 API를 통해 특정 시군구의 아파트 매매 거래 통계를 반환합니다. "
        "전세가율 계산 시 매매가 기준으로 사용하세요."
    ),
)
async def get_apt_trade(
    district_code: str = Query(..., description="법정동코드 5자리 (예: 11680 = 서울 강남구)"),
    deal_ym: Optional[str] = Query(None, description="조회 연월 YYYYMM (미지정 시 직전 달)"),
    area_min: Optional[float] = Query(None, description="최소 전용면적 필터 (㎡)"),
    area_max: Optional[float] = Query(None, description="최대 전용면적 필터 (㎡)"),
):
    api_key = _get_api_key()
    _validate_district_code(district_code)
    ym = deal_ym or _default_deal_ym()
    _validate_deal_ym(ym)

    try:
        result = market_service.fetch_apt_trade(
            api_key=api_key,
            district_code=district_code,
            deal_ym=ym,
            area_min=area_min,
            area_max=area_max,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": {
                    "code": "MOLIT_API_ERROR",
                    "message": f"국토교통부 API 오류: {exc}",
                },
                "disclaimer": DISCLAIMER,
            },
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": {
                    "code": "MARKET_SERVICE_UNAVAILABLE",
                    "message": "시세 조회 서비스를 일시적으로 사용할 수 없습니다.",
                },
                "disclaimer": DISCLAIMER,
            },
        ) from exc

    return result


@router.get(
    "/apt-rent",
    response_model=AptRentStat,
    summary="아파트 전세 실거래가 통계",
    description=(
        "국토교통부 실거래가 API를 통해 특정 시군구의 아파트 전세 거래 통계를 반환합니다. "
        "내 보증금이 시세 대비 적정한지 확인하세요."
    ),
)
async def get_apt_rent(
    district_code: str = Query(..., description="법정동코드 5자리"),
    deal_ym: Optional[str] = Query(None, description="조회 연월 YYYYMM"),
    area_min: Optional[float] = Query(None, description="최소 전용면적 필터 (㎡)"),
    area_max: Optional[float] = Query(None, description="최대 전용면적 필터 (㎡)"),
):
    api_key = _get_api_key()
    _validate_district_code(district_code)
    ym = deal_ym or _default_deal_ym()
    _validate_deal_ym(ym)

    try:
        result = market_service.fetch_apt_rent(
            api_key=api_key,
            district_code=district_code,
            deal_ym=ym,
            area_min=area_min,
            area_max=area_max,
            jeonse_only=True,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": {
                    "code": "MOLIT_API_ERROR",
                    "message": f"국토교통부 API 오류: {exc}",
                },
                "disclaimer": DISCLAIMER,
            },
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": {
                    "code": "MARKET_SERVICE_UNAVAILABLE",
                    "message": "시세 조회 서비스를 일시적으로 사용할 수 없습니다.",
                },
                "disclaimer": DISCLAIMER,
            },
        ) from exc

    return result


@router.get(
    "/summary",
    summary="전세가율 계산용 매매+전세 통합 조회",
    description=(
        "매매 평균가와 전세 평균 보증금을 함께 조회합니다. "
        "응답에 전세가율(jeonse_ratio_pct)이 포함됩니다."
    ),
)
async def get_market_summary(
    district_code: str = Query(..., description="법정동코드 5자리"),
    deal_ym: Optional[str] = Query(None, description="조회 연월 YYYYMM"),
    area_min: Optional[float] = Query(None, description="최소 전용면적 필터 (㎡)"),
    area_max: Optional[float] = Query(None, description="최대 전용면적 필터 (㎡)"),
):
    api_key = _get_api_key()
    _validate_district_code(district_code)
    ym = deal_ym or _default_deal_ym()
    _validate_deal_ym(ym)

    try:
        trade, rent = market_service.fetch_market_summary(
            api_key=api_key,
            district_code=district_code,
            deal_ym=ym,
            area_min=area_min,
            area_max=area_max,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": {
                    "code": "MOLIT_API_ERROR",
                    "message": f"국토교통부 API 오류: {exc}",
                },
                "disclaimer": DISCLAIMER,
            },
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": {
                    "code": "MARKET_SERVICE_UNAVAILABLE",
                    "message": "시세 조회 서비스를 일시적으로 사용할 수 없습니다.",
                },
                "disclaimer": DISCLAIMER,
            },
        ) from exc

    # 전세가율 계산 (전세 API가 승인되면 자동 계산, 아니면 null)
    jeonse_ratio_pct: Optional[float] = None
    rent_summary = None
    if rent is not None:
        jeonse_ratio_pct = (
            round(rent.avg_deposit_krw / trade.avg_price_krw * 100, 1)
            if trade.avg_price_krw > 0 and rent.avg_deposit_krw > 0
            else None
        )
        rent_summary = {
            "count": rent.count,
            "avg_deposit_krw": rent.avg_deposit_krw,
            "min_deposit_krw": rent.min_deposit_krw,
            "max_deposit_krw": rent.max_deposit_krw,
        }

    return {
        "district_code": district_code,
        "district_name": trade.district_name,
        "deal_ym": ym,
        "trade": {
            "count": trade.count,
            "avg_price_krw": trade.avg_price_krw,
            "min_price_krw": trade.min_price_krw,
            "max_price_krw": trade.max_price_krw,
        },
        "rent": rent_summary,          # 전세 API 미승인 시 null
        "jeonse_ratio_pct": jeonse_ratio_pct,
        "disclaimer": DISCLAIMER,
    }
