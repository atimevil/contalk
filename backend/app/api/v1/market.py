"""
시세 조회 API 엔드포인트

GET /market/districts                — 시도·시군구 코드 목록 (인증 불필요)
GET /market/dongs                    — 법정동 목록 (인증 불필요, 24시간 캐시)
GET /market/apt-trade                — 아파트 매매 실거래가 통계 (인증 불필요)
GET /market/apt-rent                 — 아파트 전세 실거래가 통계 (인증 불필요)
GET /market/summary                  — 매매+전세 통합 (인증 필요, 무료 3회 쿼터)

MOLIT API 승인 현황:
  - 매매 실거래가: 2026-05-06 ~ 2028-05-06 승인 완료
  - 전월세 실거래가: 2026-05-23 ~ 2028-05-23 승인 완료

주의: MOLIT_API_KEY가 미설정이면 503 반환.
"""
from __future__ import annotations

import asyncio
from typing import Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.services import market_service
from app.schemas.market import (
    DistrictsResponse,
    AptTradeStat,
    AptRentStat,
    SidoItem,
)
from app.schemas.common import DISCLAIMER

router = APIRouter(prefix="/market", tags=["market"])

# 무료 시세 조회 허용 횟수
MARKET_QUERY_LIMIT = 3


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
        year, month = now.year, now.month - 1
        if month == 0:
            month = 12
            year -= 1
        return f"{year}{month:02d}"


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
    "/dongs",
    summary="시군구 내 법정동 목록",
    description="선택한 시군구에 존재하는 법정동 목록을 반환합니다. 결과는 24시간 캐시됩니다.",
)
async def get_dongs(
    district_code: str = Query(..., description="법정동코드 5자리"),
    deal_ym: Optional[str] = Query(None, description="조회 연월 YYYYMM (미지정 시 직전 달)"),
):
    api_key = _get_api_key()
    _validate_district_code(district_code)
    ym = deal_ym or _default_deal_ym()
    _validate_deal_ym(ym)
    dongs = market_service.fetch_dongs(api_key, district_code, ym)
    return {"district_code": district_code, "deal_ym": ym, "dongs": dongs}


@router.get(
    "/apt-trade",
    response_model=AptTradeStat,
    summary="아파트 매매 실거래가 통계",
    description=(
        "국토교통부 실거래가 API를 통해 특정 시군구의 아파트 매매 거래 통계를 반환합니다. "
        "deal_ym 미지정 시 최근 months개월 데이터를 병렬 수집해 합산 평균을 반환합니다."
    ),
)
async def get_apt_trade(
    district_code: str = Query(..., description="법정동코드 5자리 (예: 11680 = 서울 강남구)"),
    deal_ym: Optional[str] = Query(None, description="단일 조회 연월 YYYYMM (지정 시 해당 월만 조회)"),
    months: int = Query(6, ge=1, le=24, description="집계 개월 수 (기본 6개월, deal_ym 미지정 시 적용)"),
    area_min: Optional[float] = Query(None, description="최소 전용면적 필터 (㎡)"),
    area_max: Optional[float] = Query(None, description="최대 전용면적 필터 (㎡)"),
):
    api_key = _get_api_key()
    _validate_district_code(district_code)

    try:
        if deal_ym:
            _validate_deal_ym(deal_ym)
            result = market_service.fetch_apt_trade(
                api_key=api_key,
                district_code=district_code,
                deal_ym=deal_ym,
                area_min=area_min,
                area_max=area_max,
            )
        else:
            result = await asyncio.to_thread(
                market_service.fetch_apt_trade_range,
                api_key, district_code, months, area_min, area_max,
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
        "deal_ym 미지정 시 최근 months개월 데이터를 병렬 수집해 합산 평균을 반환합니다."
    ),
)
async def get_apt_rent(
    district_code: str = Query(..., description="법정동코드 5자리"),
    deal_ym: Optional[str] = Query(None, description="단일 조회 연월 YYYYMM (지정 시 해당 월만 조회)"),
    months: int = Query(6, ge=1, le=24, description="집계 개월 수 (기본 6개월, deal_ym 미지정 시 적용)"),
    area_min: Optional[float] = Query(None, description="최소 전용면적 필터 (㎡)"),
    area_max: Optional[float] = Query(None, description="최대 전용면적 필터 (㎡)"),
    rent_type: str = Query("jeonse", description="임대차 유형: 'jeonse'=전세, 'monthly'=월세"),
):
    api_key = _get_api_key()
    _validate_district_code(district_code)
    jeonse_only = (rent_type != "monthly")

    try:
        if deal_ym:
            _validate_deal_ym(deal_ym)
            result = market_service.fetch_apt_rent(
                api_key=api_key,
                district_code=district_code,
                deal_ym=deal_ym,
                area_min=area_min,
                area_max=area_max,
                jeonse_only=jeonse_only,
            )
        else:
            result = await asyncio.to_thread(
                market_service.fetch_apt_rent_range,
                api_key, district_code, months, area_min, area_max, jeonse_only,
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
    summary="전세가율 계산용 매매+전세 통합 조회 (인증 필요, 무료 3회)",
    description=(
        "최근 N개월 매매·전세 실거래가를 병렬 수집해 합산 평균과 전세가율을 반환합니다. "
        "deal_ym 지정 시 해당 월만 단일 조회합니다. "
        "로그인 필수, 무료 3회 제공 후 이용권 구매 필요."
    ),
)
async def get_market_summary(
    district_code: str = Query(..., description="법정동코드 5자리"),
    deal_ym: Optional[str] = Query(None, description="단일 조회 연월 YYYYMM (지정 시 해당 월만 조회)"),
    months: int = Query(6, ge=1, le=24, description="집계 개월 수 (기본 6개월, deal_ym 미지정 시 적용)"),
    area_min: Optional[float] = Query(None, description="최소 전용면적 필터 (㎡)"),
    area_max: Optional[float] = Query(None, description="최대 전용면적 필터 (㎡)"),
    dong: Optional[str] = Query(None, description="법정동 이름 필터 (예: 역삼동). 미지정 시 시군구 전체 평균"),
    rent_type: str = Query("jeonse", description="임대차 유형: 'jeonse'=전세, 'monthly'=월세"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    api_key = _get_api_key()
    _validate_district_code(district_code)
    if rent_type not in ("jeonse", "monthly"):
        rent_type = "jeonse"
    if deal_ym:
        _validate_deal_ym(deal_ym)

    # ── 쿼터 확인 (개발 환경에서는 무제한) ──────────────────────────────────────
    is_dev = getattr(settings, "APP_ENV", "production") == "development"
    used = current_user.market_queries_used
    remaining_before = max(0, MARKET_QUERY_LIMIT - used)

    if not is_dev and remaining_before <= 0:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": {
                    "code": "MARKET_QUOTA_EXCEEDED",
                    "message": (
                        f"무료 시세 조회 {MARKET_QUERY_LIMIT}회를 모두 사용했습니다. "
                        "이용권 구매 후 계속 이용할 수 있습니다."
                    ),
                    "remaining": 0,
                    "limit": MARKET_QUERY_LIMIT,
                },
                "disclaimer": DISCLAIMER,
            },
        )

    # ── MOLIT API 호출 ─────────────────────────────────────────────────────────
    try:
        trade, rent = await asyncio.to_thread(
            market_service.fetch_market_summary,
            api_key, district_code, deal_ym, area_min, area_max, dong, months, rent_type,
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

    # jeonse 모드에서 rent API 실패 시 쿼터 소진 없이 오류 반환
    if rent_type == "jeonse" and rent is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": {
                    "code": "MOLIT_API_ERROR",
                    "message": "전세 실거래가 API 조회에 실패했습니다. 잠시 후 다시 시도해 주세요.",
                },
                "disclaimer": DISCLAIMER,
            },
        )

    # ── 쿼터 소비 (API 호출 성공 시, 개발 환경에서는 차감 안 함) ──────────────────
    if not is_dev:
        current_user.market_queries_used = used + 1
        await db.commit()
        remaining_after = remaining_before - 1
    else:
        remaining_after = -1  # 개발 환경: 무제한 표시

    # ── 전세가율 계산 (전세 모드에서만 유효) ────────────────────────────────────
    jeonse_ratio_pct: Optional[float] = None
    rent_summary = None
    if rent is not None:
        # 월세 모드에서는 전세가율 계산 생략
        if rent_type == "jeonse" and trade.avg_price_krw > 0 and rent.avg_deposit_krw > 0:
            jeonse_ratio_pct = round(rent.avg_deposit_krw / trade.avg_price_krw * 100, 1)

        rent_summary = {
            "count": rent.count,
            "rent_type": rent.rent_type,
            "avg_deposit_krw": rent.avg_deposit_krw,
            "min_deposit_krw": rent.min_deposit_krw,
            "max_deposit_krw": rent.max_deposit_krw,
            "avg_monthly_rent_krw": rent.avg_monthly_rent_krw,
            "min_monthly_rent_krw": rent.min_monthly_rent_krw,
            "max_monthly_rent_krw": rent.max_monthly_rent_krw,
        }

    district_label = (
        f"{trade.district_name} {dong}"
        if dong and trade.district_name
        else (trade.district_name or district_code)
    )

    return {
        "district_code": district_code,
        "district_name": district_label,
        "deal_ym": trade.deal_ym,
        "period_from": trade.period_from,
        "period_to": trade.period_to,
        "trade": {
            "count": trade.count,
            "avg_price_krw": trade.avg_price_krw,
            "min_price_krw": trade.min_price_krw,
            "max_price_krw": trade.max_price_krw,
        },
        "rent": rent_summary,
        "jeonse_ratio_pct": jeonse_ratio_pct,
        "market_queries_remaining": remaining_after,
        "market_queries_limit": MARKET_QUERY_LIMIT,
        "disclaimer": DISCLAIMER,
    }
