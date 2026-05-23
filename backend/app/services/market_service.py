"""
국토교통부 아파트 실거래가 서비스

공공데이터포털 MOLIT API를 이용해 아파트 매매·전세 실거래가를 조회한다.

End Point:
  매매: https://apis.data.go.kr/1613000/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade
  전월세: https://apis.data.go.kr/1613000/RTMSDataSvcAptRent/getRTMSDataSvcAptRent

응답 XML 태그 (영문, 매매):
  aptNm       — 아파트 명칭
  dealAmount  — 거래금액 (만원 단위, 쉼표 포함 예: '355,000')
  excluUseAr  — 전용면적 (㎡)
  floor       — 층
  dealYear / dealMonth / dealDay — 계약 날짜

응답 XML 태그 (영문, 전월세):
  aptNm       — 아파트 명칭
  deposit     — 보증금 (만원 단위)
  monthlyRent — 월세 (만원 단위, 전세는 0)
  excluUseAr  — 전용면적 (㎡)
  floor       — 층
  dealYear / dealMonth — 계약 년월

단위: API 응답 거래금액은 '만원' 단위 → 서비스에서 '원'으로 변환
승인: 매매 API (2026-05-06 ~), 전월세 API (2026-05-23 ~) 모두 승인 완료
"""
from __future__ import annotations

import json
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

import httpx

from app.schemas.market import (
    AptTradeItem,
    AptTradeStat,
    AptRentStat,
    DistrictItem,
    SidoItem,
)

logger = logging.getLogger(__name__)

# ─── 상수 ────────────────────────────────────────────────────────────────────

_MOLIT_BASE = "https://apis.data.go.kr/1613000"

# 매매 실거래가 (승인됨)
_TRADE_ENDPOINT = f"{_MOLIT_BASE}/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade"

# 전월세 실거래가 (2026-05-23 승인 완료)
_RENT_ENDPOINT = f"{_MOLIT_BASE}/RTMSDataSvcAptRent/getRTMSDataSvcAptRent"

_DISTRICTS_JSON = Path(__file__).parent.parent / "data" / "districts.json"

# 한 번에 가져올 최대 레코드 수
_NUM_OF_ROWS = 100

# HTTP 타임아웃 (초)
_TIMEOUT = 15.0


# ─── 법정동 코드 데이터 ──────────────────────────────────────────────────────

def load_districts() -> List[SidoItem]:
    """districts.json을 읽어 SidoItem 목록으로 반환."""
    raw = json.loads(_DISTRICTS_JSON.read_text(encoding="utf-8"))
    result: List[SidoItem] = []
    for sido in raw["시도"]:
        districts = [
            DistrictItem(name=d["name"], code=d["code"])
            for d in sido["시군구"]
        ]
        result.append(
            SidoItem.model_validate({"name": sido["name"], "code": sido["code"], "시군구": districts})
        )
    return result


def get_district_name(district_code: str) -> Optional[str]:
    """법정동코드로 '시도명 시군구명' 반환. 없으면 None."""
    for sido in load_districts():
        for district in sido.districts:
            if district.code == district_code:
                return f"{sido.name} {district.name}"
    return None


# ─── 유틸 ────────────────────────────────────────────────────────────────────

def _parse_price(text: Optional[str]) -> int:
    """
    '355,000' 형태의 만원 단위 문자열 → 원 단위 정수.
    파싱 실패 시 0 반환.
    """
    if not text:
        return 0
    cleaned = re.sub(r"[^\d]", "", text.strip())
    if not cleaned:
        return 0
    return int(cleaned) * 10_000  # 만원 → 원


def _parse_float(text: Optional[str]) -> float:
    """전용면적 등 소수 파싱. 실패 시 0.0."""
    if not text:
        return 0.0
    try:
        return float(text.strip())
    except ValueError:
        return 0.0


def _build_deal_date(year: str, month: str, day: str = "01") -> str:
    """년/월/일 조합 → 'YYYY-MM-DD'."""
    y = (year or "").strip()
    m = (month or "").strip().zfill(2)
    d = (day or "01").strip().zfill(2)
    return f"{y}-{m}-{d}"


def _current_deal_ym() -> str:
    """현재 연월 YYYYMM."""
    return datetime.now(timezone.utc).strftime("%Y%m")


def _prev_deal_ym(months_ago: int = 1) -> str:
    """몇 달 전 연월 YYYYMM."""
    try:
        from dateutil.relativedelta import relativedelta  # type: ignore
        now = datetime.now(timezone.utc)
        past = now - relativedelta(months=months_ago)
        return past.strftime("%Y%m")
    except ImportError:
        return _current_deal_ym()


def _text(el: ET.Element, tag: str) -> str:
    """XML 요소에서 하위 태그 텍스트 추출. 없으면 빈 문자열."""
    child = el.find(tag)
    return child.text.strip() if child is not None and child.text else ""


# ─── API 호출 ─────────────────────────────────────────────────────────────────

def _call_api(url: str, params: dict) -> ET.Element:
    """
    MOLIT API GET 호출 → XML ElementTree 루트 반환.
    오류 시 HTTPError 또는 ValueError 발생.
    """
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.get(url, params=params)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.error("MOLIT API 호출 실패 [%s]: %s", url, exc)
        raise

    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError as exc:
        logger.error("MOLIT XML 파싱 실패: %s\n응답: %s", exc, resp.text[:500])
        raise ValueError(f"XML 파싱 실패: {exc}") from exc

    # 응답 코드 확인 (공공데이터포털: '000' = OK)
    result_code_el = root.find(".//resultCode")
    if result_code_el is not None and result_code_el.text:
        code = result_code_el.text.strip()
        if code not in ("00", "000"):
            msg_el = root.find(".//resultMsg")
            msg = msg_el.text.strip() if msg_el is not None and msg_el.text else "알 수 없는 오류"
            logger.error("MOLIT API 오류 [코드 %s]: %s", code, msg)
            raise ValueError(f"MOLIT API 오류 코드 {code}: {msg}")

    return root


# ─── 매매 실거래가 ────────────────────────────────────────────────────────────

def fetch_apt_trade(
    api_key: str,
    district_code: str,
    deal_ym: str,
    area_min: Optional[float] = None,
    area_max: Optional[float] = None,
) -> AptTradeStat:
    """
    아파트 매매 실거래가를 조회하고 통계를 반환한다.

    Args:
        api_key:        MOLIT API 서비스 키
        district_code:  법정동코드 5자리 (예: 11680 = 서울 강남구)
        deal_ym:        조회 연월 YYYYMM (예: 202503)
        area_min:       최소 전용면적 필터 (㎡, 선택)
        area_max:       최대 전용면적 필터 (㎡, 선택)
    """
    params = {
        "serviceKey": api_key,
        "LAWD_CD": district_code,
        "DEAL_YMD": deal_ym,
        "numOfRows": str(_NUM_OF_ROWS),
        "pageNo": "1",
    }

    root = _call_api(_TRADE_ENDPOINT, params)
    items: List[AptTradeItem] = []

    for item_el in root.iter("item"):
        try:
            # API 응답 태그는 영문 (aptNm, excluUseAr, dealAmount, floor, dealYear/Month/Day)
            area = _parse_float(_text(item_el, "excluUseAr"))
            if area_min is not None and area < area_min:
                continue
            if area_max is not None and area > area_max:
                continue

            price_krw = _parse_price(_text(item_el, "dealAmount"))
            if price_krw <= 0:
                continue

            items.append(
                AptTradeItem(
                    apartment=_text(item_el, "aptNm") or "알 수 없음",
                    area=area,
                    price_krw=price_krw,
                    floor=_text(item_el, "floor") or None,
                    deal_date=_build_deal_date(
                        _text(item_el, "dealYear"),
                        _text(item_el, "dealMonth"),
                        _text(item_el, "dealDay"),
                    ),
                )
            )
        except Exception as exc:
            logger.warning("매매 항목 파싱 실패: %s", exc)
            continue

    prices = [it.price_krw for it in items]
    district_name = get_district_name(district_code)

    return AptTradeStat(
        district_code=district_code,
        district_name=district_name,
        deal_ym=deal_ym,
        count=len(items),
        avg_price_krw=round(sum(prices) / len(prices)) if prices else 0,
        min_price_krw=min(prices) if prices else 0,
        max_price_krw=max(prices) if prices else 0,
        items=items,
    )


# ─── 전세 실거래가 (별도 신청 필요) ──────────────────────────────────────────

def fetch_apt_rent(
    api_key: str,
    district_code: str,
    deal_ym: str,
    area_min: Optional[float] = None,
    area_max: Optional[float] = None,
    jeonse_only: bool = True,
) -> AptRentStat:
    """
    아파트 전월세 실거래가를 조회한다.

    승인 완료: 2026-05-23 data.go.kr '아파트 전월세 실거래가' 승인.
    응답 태그: deposit(보증금), monthlyRent(월세), excluUseAr(면적), aptNm(아파트명)
    """
    params = {
        "serviceKey": api_key,
        "LAWD_CD": district_code,
        "DEAL_YMD": deal_ym,
        "numOfRows": str(_NUM_OF_ROWS),
        "pageNo": "1",
    }

    root = _call_api(_RENT_ENDPOINT, params)
    items = []

    for item_el in root.iter("item"):
        try:
            area = _parse_float(_text(item_el, "excluUseAr"))
            if area_min is not None and area < area_min:
                continue
            if area_max is not None and area > area_max:
                continue

            # 전월세 API 태그: deposit → 보증금, monthlyRent → 월세
            deposit_krw = _parse_price(_text(item_el, "deposit"))
            monthly_krw = _parse_price(_text(item_el, "monthlyRent"))

            is_jeonse = monthly_krw == 0
            if jeonse_only and not is_jeonse:
                continue
            if deposit_krw <= 0:
                continue

            from app.schemas.market import AptRentItem
            items.append(
                AptRentItem(
                    apartment=_text(item_el, "aptNm") or "알 수 없음",
                    area=area,
                    deposit_krw=deposit_krw,
                    monthly_rent_krw=monthly_krw,
                    is_jeonse=is_jeonse,
                    floor=_text(item_el, "floor") or None,
                    deal_date=_build_deal_date(
                        _text(item_el, "dealYear"),
                        _text(item_el, "dealMonth"),
                    ),
                )
            )
        except Exception as exc:
            logger.warning("전세 항목 파싱 실패: %s", exc)
            continue

    deposits = [it.deposit_krw for it in items]
    district_name = get_district_name(district_code)

    return AptRentStat(
        district_code=district_code,
        district_name=district_name,
        deal_ym=deal_ym,
        count=len(items),
        avg_deposit_krw=round(sum(deposits) / len(deposits)) if deposits else 0,
        min_deposit_krw=min(deposits) if deposits else 0,
        max_deposit_krw=max(deposits) if deposits else 0,
        items=items,
    )


# ─── 복합 조회: 매매가만으로 전세가율 참고치 제공 ──────────────────────────────

def fetch_market_summary(
    api_key: str,
    district_code: str,
    deal_ym: Optional[str] = None,
    area_min: Optional[float] = None,
    area_max: Optional[float] = None,
) -> Tuple[AptTradeStat, Optional[AptRentStat]]:
    """
    매매가 조회 (전세 API는 미승인 시 None 반환).

    deal_ym 미지정 시 직전 달을 사용한다.
    """
    if not deal_ym:
        deal_ym = _prev_deal_ym(1)

    trade = fetch_apt_trade(api_key, district_code, deal_ym, area_min, area_max)

    # 전세 API (2026-05-23 승인) — 실패해도 매매 데이터는 반환
    rent: Optional[AptRentStat] = None
    try:
        rent = fetch_apt_rent(api_key, district_code, deal_ym, area_min, area_max)
    except Exception as exc:
        logger.info("전세 API 조회 실패: %s", exc)

    return trade, rent
