"""
국토교통부 전월세 실거래가 API 활성화 확인 및 태그명 검증 스크립트

사용법:
    MOLIT_API_KEY=<발급키> python scripts/check_molit_rent.py
    (또는 .env 로드 후 실행)

활성화 전: 403 출력
활성화 후: XML 태그명 목록 + 실제 데이터 출력 → market_service.py 확인
"""
import os
import sys
import xml.etree.ElementTree as ET
import httpx

API_KEY = os.environ.get("MOLIT_API_KEY")
if not API_KEY:
    print("환경변수 MOLIT_API_KEY가 설정되지 않았습니다.")
    sys.exit(1)
URL = "https://apis.data.go.kr/1613000/RTMSDataSvcAptRent/getRTMSDataSvcAptRent"

params = {
    "serviceKey": API_KEY,
    "LAWD_CD": "11350",   # 서울 노원구 (거래량 많음)
    "DEAL_YMD": "202503",
    "numOfRows": "3",
    "pageNo": "1",
}

resp = httpx.get(URL, params=params, timeout=15)
print(f"Status: {resp.status_code}")

if resp.status_code != 200:
    print("응답:", resp.text[:200])
    exit()

print("\n=== 원시 XML (처음 2000자) ===")
print(resp.text[:2000])

print("\n=== item 태그 목록 ===")
root = ET.fromstring(resp.text)
for i, item in enumerate(root.iter("item")):
    if i >= 1:
        break
    for child in item:
        print(f"  <{child.tag}>: {repr(child.text)}")

print("\n=== 파싱 결과 ===")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
from app.services.market_service import fetch_apt_rent

result = fetch_apt_rent(API_KEY, "11350", "202503")
print(f"전세 건수: {result.count}")
if result.count > 0:
    print(f"평균 보증금: {result.avg_deposit_krw//10000:,}만원")
    print(f"최저/최고: {result.min_deposit_krw//10000:,}만 ~ {result.max_deposit_krw//10000:,}만원")
    for item in result.items[:3]:
        print(f"  {item.apartment} {item.area}㎡ 전세 {item.deposit_krw//10000:,}만원")
else:
    print("⚠ 0건 — 태그명 불일치 가능성 있음")
    print("  XML에서 확인한 태그명으로 market_service.py 수정 필요")
