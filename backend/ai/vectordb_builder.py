"""
벡터DB 구축 스크립트 — 임대차보호법 텍스트를 ChromaDB에 색인한다.

실행 방법:
    python -m backend.ai.vectordb_builder
    또는
    python backend/ai/vectordb_builder.py

    # 샘플 데이터로 테스트 (실제 법령 파일 없이도 동작)
    python backend/ai/vectordb_builder.py --sample

    # 공공데이터포털 API로 실제 법령 색인 (권장)
    python backend/ai/vectordb_builder.py --api

    # 실제 법령 PDF 색인
    python backend/ai/vectordb_builder.py --pdf path/to/law.pdf

환경변수:
    OPENAI_API_KEY       — 임베딩 생성에 사용
    LAW_API_KEY          — 공공데이터포털 법제처 API 키 (--api 옵션 사용 시 필요)
    CHROMA_PERSIST_DIR   — ChromaDB 저장 경로 (기본: ./chroma_data)
    CHROMA_HOST          — 원격 ChromaDB 서버 주소 (설정 시 원격 사용)
    CHROMA_PORT          — 원격 ChromaDB 포트 (기본: 8001)
    CHROMA_COLLECTION_NAME — 컬렉션명 (기본: lease_law)
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 주택임대차보호법 샘플 데이터 (실제 법령 색인 전 테스트용)
# ---------------------------------------------------------------------------

SAMPLE_LAW_ARTICLES = [
    # ── 주택임대차보호법 전문 ───────────────────────────────────────────────
    {
        "article": "제1조",
        "title": "목적",
        "text": (
            "제1조(목적) 이 법은 주거용 건물의 임대차(賃貸借)에 관하여 「민법」에 대한 특례를 규정함으로써 "
            "국민 주거생활의 안정을 보장함을 목적으로 한다."
        ),
        "law_name": "주택임대차보호법",
    },
    {
        "article": "제2조",
        "title": "적용 범위",
        "text": (
            "제2조(적용 범위) 이 법은 주거용 건물(이하 \"주택\"이라 한다)의 전부 또는 일부의 임대차에 관하여 "
            "적용한다. 그 임차주택(賃借住宅)의 일부가 주거 외의 목적으로 사용되는 경우에도 또한 같다."
        ),
        "law_name": "주택임대차보호법",
    },
    {
        "article": "제3조",
        "title": "대항력 등",
        "text": (
            "제3조(대항력 등) ① 임대차는 그 등기(登記)가 없는 경우에도 임차인(賃借人)이 주택의 인도(引渡)와 "
            "주민등록을 마친 때에는 그 다음 날부터 제3자에 대하여 효력이 생긴다. "
            "이 경우 전입신고를 한 때에 주민등록이 된 것으로 본다. "
            "② 임차주택의 양수인(讓受人)(그 밖에 임대할 권리를 승계한 자를 포함한다)은 "
            "임대인(賃貸人)의 지위를 승계한 것으로 본다."
        ),
        "law_name": "주택임대차보호법",
    },
    {
        "article": "제3조의2",
        "title": "보증금의 회수",
        "text": (
            "제3조의2(보증금의 회수) ① 임차인은 임차주택에 대하여 「민사집행법」에 따른 경매를 신청하는 경우와 "
            "「국세징수법」에 따른 공매(公賣)를 하는 경우에는 법원에 배당요구를 하여 임차인으로서의 우선순위에 따라 "
            "보증금을 받을 수 있다. "
            "② 제1항에 따라 우선변제를 받을 임차인은 제3조 제1항의 요건을 갖추고 임대차계약증서(臨貸借契約證書)상의 "
            "확정일자(確定日字)를 갖추어야 한다."
        ),
        "law_name": "주택임대차보호법",
    },
    {
        "article": "제3조의3",
        "title": "임차권등기명령",
        "text": (
            "제3조의3(임차권등기명령) ① 임대차가 끝난 후 보증금이 반환되지 아니한 경우 임차인은 임차주택의 소재지를 "
            "관할하는 지방법원, 지방법원지원 또는 시·군 법원에 임차권등기명령을 신청할 수 있다. "
            "② 임차권등기명령의 집행에 따른 임차권등기를 마치면 임차인은 대항력 및 우선변제권을 취득한다. "
            "다만, 임차인이 임차권등기 이전에 이미 대항력 또는 우선변제권을 취득한 경우에는 그 대항력 또는 "
            "우선변제권이 그대로 유지되며, 임차권등기 이후에는 제3조 제1항의 대항요건을 상실하더라도 "
            "이미 취득한 대항력 또는 우선변제권을 잃지 아니한다."
        ),
        "law_name": "주택임대차보호법",
    },
    {
        "article": "제4조",
        "title": "임대차기간 등",
        "text": (
            "제4조(임대차기간 등) ① 기간을 정하지 아니하거나 2년 미만으로 정한 임대차는 그 기간을 2년으로 본다. "
            "다만, 임차인은 2년 미만으로 정한 기간이 유효함을 주장할 수 있다. "
            "② 임대차가 종료한 경우에도 임차인이 보증금을 반환받을 때까지는 임대차 관계가 존속되는 것으로 본다."
        ),
        "law_name": "주택임대차보호법",
    },
    {
        "article": "제5조",
        "title": "임차주택의 양도 등에 따른 임차인의 권리 보호",
        "text": (
            "제5조(임차주택의 양도 등에 따른 임차인의 권리 보호) 임차주택의 양도 등에 따라 임대인의 지위가 "
            "승계되는 경우에도 임차인은 기존 임대인에 대한 임대차보증금반환채권을 포기하지 않는 한 "
            "새로운 임대인에게 보증금의 반환을 청구할 수 있다."
        ),
        "law_name": "주택임대차보호법",
    },
    {
        "article": "제6조",
        "title": "계약의 갱신",
        "text": (
            "제6조(계약의 갱신) ① 임대인이 임대차기간이 끝나기 6개월 전부터 2개월 전까지의 기간에 "
            "임차인에게 갱신거절(更新拒絶)의 통지를 하지 아니하거나 계약조건을 변경하지 아니하면 "
            "갱신하지 아니한다는 뜻의 통지를 하지 아니한 경우에는 그 기간이 끝난 때에 "
            "전 임대차와 동일한 조건으로 다시 임대차한 것으로 본다. "
            "② 제1항의 경우 임대차의 존속기간은 2년으로 본다. "
            "③ 2기(期)의 차임액(借賃額)에 달하도록 차임을 연체하거나 그 밖에 임차인으로서의 의무를 "
            "현저히 위반한 임차인에 대하여는 제1항을 적용하지 아니한다."
        ),
        "law_name": "주택임대차보호법",
    },
    {
        "article": "제6조의2",
        "title": "묵시적 갱신의 경우 계약의 해지",
        "text": (
            "제6조의2(묵시적 갱신의 경우 계약의 해지) ① 제6조 제1항에 따라 계약이 갱신된 경우 같은 조 제2항에도 "
            "불구하고 임차인은 언제든지 임대인에게 계약해지를 통지할 수 있다. "
            "② 제1항에 따른 해지는 임대인이 그 통지를 받은 날부터 3개월이 지나면 그 효력이 발생한다."
        ),
        "law_name": "주택임대차보호법",
    },
    {
        "article": "제6조의3",
        "title": "계약갱신 요구 등",
        "text": (
            "제6조의3(계약갱신 요구 등) ① 제6조에도 불구하고 임차인은 계약기간이 끝나기 6개월 전부터 "
            "2개월 전까지의 기간에 계약갱신을 요구할 수 있다. 이 경우 임대인은 정당한 사유 없이 "
            "거절하지 못한다. "
            "② 임차인은 제1항에 따른 계약갱신요구권을 1회에 한하여 행사할 수 있다. "
            "이 경우 갱신되는 임대차의 존속기간은 2년으로 본다. "
            "③ 갱신되는 임대차는 전 임대차와 동일한 조건으로 다시 계약된 것으로 본다. "
            "다만, 차임과 보증금은 제7조의 범위에서 증감할 수 있다. "
            "④ 제1항에 따라 갱신된 임대차의 해지에 관하여는 제6조의2를 준용한다."
        ),
        "law_name": "주택임대차보호법",
    },
    {
        "article": "제7조",
        "title": "차임 등의 증감청구권",
        "text": (
            "제7조(차임 등의 증감청구권) ① 당사자는 약정한 차임이나 보증금이 임차주택에 관한 조세, 공과금, "
            "그 밖의 부담의 증감이나 경제사정의 변동으로 인하여 적절하지 아니하게 된 때에는 장래에 대하여 "
            "그 증감을 청구할 수 있다. 이 경우 증액청구는 임대차계약 또는 약정한 차임이나 보증금의 증액이 "
            "있은 후 1년 이내에는 하지 못한다. "
            "② 제1항에 따른 증액청구는 약정한 차임이나 보증금의 20분의 1의 금액을 초과하지 못한다. "
            "다만, 특별시·광역시·특별자치시·도 및 특별자치도는 관할 구역 내의 지역별 임대차 시장 여건 등을 "
            "고려하여 본문의 범위에서 증액청구의 상한을 달리 정할 수 있다."
        ),
        "law_name": "주택임대차보호법",
    },
    {
        "article": "제7조의2",
        "title": "월차임 전환 시 산정률의 제한",
        "text": (
            "제7조의2(월차임 전환 시 산정률의 제한) 보증금의 전부 또는 일부를 월 단위의 차임으로 전환하는 경우에는 "
            "그 전환되는 금액에 다음 각 호 중 낮은 비율을 곱한 월차임의 범위를 초과할 수 없다. "
            "1. 은행법에 따른 은행에서 적용하는 대출금리와 해당 지역의 경제 여건 등을 고려하여 대통령령으로 "
            "정하는 비율 2. 한국은행에서 공시한 기준금리에 대통령령으로 정하는 이율을 더한 비율."
        ),
        "law_name": "주택임대차보호법",
    },
    {
        "article": "제8조",
        "title": "보증금 중 일정액의 보호",
        "text": (
            "제8조(보증금 중 일정액의 보호) ① 임차인은 보증금 중 일정액을 다른 담보물권자(擔保物權者)보다 "
            "우선하여 변제받을 권리가 있다. 이 경우 임차인은 주택에 대한 경매신청의 등기 전에 "
            "제3조 제1항의 요건을 갖추어야 한다. "
            "② 제1항에 따라 우선변제를 받을 임차인 및 보증금 중 일정액의 범위와 기준은 "
            "주택 가액(임대차 목적 주택의 경매 또는 공매에 의한 매각 대금에서 저당권 등의 피담보채권과 "
            "임차권등기명령에 의하여 이미 취득한 임차권의 우선변제권 있는 채권 등의 금액을 공제한 잔액을 말한다)의 "
            "2분의 1을 초과할 수 없다."
        ),
        "law_name": "주택임대차보호법",
    },
    {
        "article": "제9조",
        "title": "주택 임차권의 승계",
        "text": (
            "제9조(주택 임차권의 승계) ① 임차인이 상속인 없이 사망한 경우에는 그 주택에서 가정공동생활을 하던 "
            "사실상의 혼인 관계에 있는 자가 임차인의 권리와 의무를 승계한다. "
            "② 임차인이 사망한 때에 사망 당시 상속인이 그 주택에서 가정공동생활을 하고 있지 아니한 경우에는 "
            "그 주택에서 가정공동생활을 하던 사실상의 혼인 관계에 있는 자와 2촌 이내의 친족이 공동으로 "
            "임차인의 권리와 의무를 승계한다."
        ),
        "law_name": "주택임대차보호법",
    },
    {
        "article": "제10조",
        "title": "강행규정",
        "text": (
            "제10조(강행규정) 이 법에 위반된 약정(約定)으로서 임차인에게 불리한 것은 그 효력이 없다."
        ),
        "law_name": "주택임대차보호법",
    },
    {
        "article": "제11조",
        "title": "일시사용을 위한 임대차",
        "text": (
            "제11조(일시사용을 위한 임대차) 이 법은 일시사용하기 위한 임대차임이 명백한 경우에는 적용하지 아니한다."
        ),
        "law_name": "주택임대차보호법",
    },
    {
        "article": "제12조",
        "title": "미등기전세에의 준용",
        "text": (
            "제12조(미등기전세에의 준용) 제3조, 제3조의2, 제3조의3, 제8조의 규정은 주택의 등기를 하지 아니한 "
            "전세계약(傳貰契約)에 관하여 이를 준용한다."
        ),
        "law_name": "주택임대차보호법",
    },
    # ── 상가건물임대차보호법 핵심 조항 ────────────────────────────────────────
    {
        "article": "제1조",
        "title": "목적",
        "text": (
            "상가건물임대차보호법 제1조(목적) 이 법은 상가건물 임대차에 관하여 「민법」에 대한 특례를 규정하여 "
            "국민 경제생활의 안정을 보장함을 목적으로 한다."
        ),
        "law_name": "상가건물임대차보호법",
    },
    {
        "article": "제2조",
        "title": "적용범위",
        "text": (
            "상가건물임대차보호법 제2조(적용범위) ① 이 법은 상가건물(「부가가치세법」 제8조에 따른 사업자등록의 "
            "대상이 되는 건물을 말한다)의 임대차(임대차 목적물의 주된 부분을 영업용으로 사용하는 경우를 포함한다)에 "
            "대하여 적용한다. 다만, 대통령령으로 정하는 보증금액을 초과하는 임대차에 대하여는 "
            "제3조, 제10조 제1항, 제2항, 제3항 본문, 제10조의2부터 제10조의9까지의 규정 및 제19조만 적용한다."
        ),
        "law_name": "상가건물임대차보호법",
    },
    {
        "article": "제10조",
        "title": "계약갱신 요구 등",
        "text": (
            "상가건물임대차보호법 제10조(계약갱신 요구 등) ① 임대인은 임차인이 임대차기간이 만료되기 6개월 전부터 "
            "1개월 전까지 사이에 계약갱신을 요구할 경우 정당한 사유 없이 거절하지 못한다. "
            "② 임차인의 계약갱신요구권은 최초의 임대차기간을 포함한 전체 임대차기간이 10년을 초과하지 아니하는 "
            "범위에서만 행사할 수 있다."
        ),
        "law_name": "상가건물임대차보호법",
    },
    {
        "article": "제10조의4",
        "title": "권리금 회수기회 보호 등",
        "text": (
            "상가건물임대차보호법 제10조의4(권리금 회수기회 보호 등) ① 임대인은 임대차기간이 끝나기 3개월 전부터 "
            "임대차 종료 시까지 다음 각 호의 어느 하나에 해당하는 행위를 함으로써 권리금 계약에 따라 임차인이 "
            "주선한 신규임차인이 되려는 자로부터 권리금을 지급받는 것을 방해하여서는 아니 된다."
        ),
        "law_name": "상가건물임대차보호법",
    },
    {
        "article": "제11조",
        "title": "차임 등의 증감청구권",
        "text": (
            "상가건물임대차보호법 제11조(차임 등의 증감청구권) ① 차임 또는 보증금이 임차건물에 관한 조세, 공과금, "
            "그 밖의 부담의 증감이나 「감정평가 및 감정평가사에 관한 법률」에 따른 감정평가액의 증감 등으로 "
            "인하여 상당하지 아니하게 된 경우에는 당사자는 장래의 차임 또는 보증금에 대하여 증감을 청구할 수 있다. "
            "② 증액청구는 청구 당시의 차임 또는 보증금의 100분의 5의 금액을 초과하지 못한다."
        ),
        "law_name": "상가건물임대차보호법",
    },
    # ── 민법 임대차 관련 조항 ─────────────────────────────────────────────────
    {
        "article": "민법 제618조",
        "title": "임대차의 의의",
        "text": (
            "민법 제618조(임대차의 의의) 임대차는 당사자 일방이 상대방에게 목적물을 사용, 수익하게 할 것을 약정하고 "
            "상대방이 이에 대하여 차임을 지급할 것을 약정함으로써 그 효력이 생긴다."
        ),
        "law_name": "민법",
    },
    {
        "article": "민법 제619조",
        "title": "처분능력, 권한 없는 자의 단기임대차",
        "text": (
            "민법 제619조(처분능력, 권한 없는 자의 단기임대차) 처분의 능력 또는 권한 없는 자가 임대차를 하는 경우에는 "
            "그 임대차는 다음 기간을 넘지 못한다. 1. 식목, 채염 또는 석재, 砂礦, 토사의 채취를 목적으로 한 토지의 "
            "임대차는 10년 2. 기타 토지의 임대차는 5년 3. 건물 기타 공작물의 임대차는 3년 4. 동산의 임대차는 6월."
        ),
        "law_name": "민법",
    },
    {
        "article": "민법 제621조",
        "title": "임대차의 등기",
        "text": (
            "민법 제621조(임대차의 등기) ① 부동산임차인은 당사자간의 반대약정이 없으면 임대인에 대하여 그 임대차 "
            "등기절차에 협력할 것을 청구할 수 있다. "
            "② 부동산임대차를 등기한 때에는 그때부터 제3자에 대하여 효력이 생긴다."
        ),
        "law_name": "민법",
    },
    {
        "article": "민법 제622조",
        "title": "건물등기있는 차지권의 대항력",
        "text": (
            "민법 제622조(건물등기있는 차지권의 대항력) ① 건물의 소유를 목적으로 한 토지임대차는 이를 등기하지 "
            "아니한 경우에도 임차인이 그 지상건물을 등기한 때에는 제3자에 대하여 임대차의 효력이 생긴다. "
            "② 건물이 임대차기간 만료 전에 멸실 또는 후퇴한 때에는 전항의 효력을 잃는다."
        ),
        "law_name": "민법",
    },
    {
        "article": "민법 제623조",
        "title": "임대인의 의무",
        "text": (
            "민법 제623조(임대인의 의무) 임대인은 목적물을 임차인에게 인도하고 계약 존속중 그 사용, "
            "수익에 필요한 상태를 유지하게 할 의무를 부담한다."
        ),
        "law_name": "민법",
    },
    {
        "article": "민법 제624조",
        "title": "임대인의 보존행위, 인용의무",
        "text": (
            "민법 제624조(임대인의 보존행위, 인용의무) 임대인이 임대물의 보존에 필요한 행위를 하는 때에는 "
            "임차인은 이를 거절하지 못한다."
        ),
        "law_name": "민법",
    },
    {
        "article": "민법 제625조",
        "title": "임차인의 의사에 반하는 보존행위와 해지권",
        "text": (
            "민법 제625조(임차인의 의사에 반하는 보존행위와 해지권) 임대인이 임차인의 의사에 반하여 보존행위를 하는 "
            "경우에 임차인이 이로 인하여 임차의 목적을 달성할 수 없는 때에는 계약을 해지할 수 있다."
        ),
        "law_name": "민법",
    },
    {
        "article": "민법 제626조",
        "title": "임차인의 상환청구권",
        "text": (
            "민법 제626조(임차인의 상환청구권) ① 임차인이 임차물의 보존에 관한 필요비를 지출한 때에는 "
            "임대인에 대하여 그 상환을 청구할 수 있다. "
            "② 임차인이 유익비를 지출한 경우에는 임대인은 임대차 종료 시에 그 가액의 증가가 현존한 때에 한하여 "
            "임차인의 지출한 금액이나 그 증가액을 상환하여야 한다. 이 경우에 법원은 임대인의 청구에 의하여 "
            "상당한 상환기간을 허여할 수 있다."
        ),
        "law_name": "민법",
    },
    {
        "article": "민법 제627조",
        "title": "일부멸실 등과 감액청구, 해지권",
        "text": (
            "민법 제627조(일부멸실 등과 감액청구, 해지권) ① 임차물의 일부가 임차인의 과실 없이 멸실 기타 사유로 "
            "인하여 사용, 수익할 수 없는 때에는 임차인은 그 부분의 비율에 의한 차임의 감액을 청구할 수 있다. "
            "② 전항의 경우에 그 잔존부분으로 임차의 목적을 달성할 수 없는 때에는 임차인은 계약을 해지할 수 있다."
        ),
        "law_name": "민법",
    },
    {
        "article": "민법 제628조",
        "title": "차임증감청구권",
        "text": (
            "민법 제628조(차임증감청구권) 임대물에 대한 공과부담의 증감 기타 경제사정의 변동으로 인하여 약정한 "
            "차임이 상당하지 아니하게 된 때에는 당사자는 장래에 대한 차임의 증감을 청구할 수 있다."
        ),
        "law_name": "민법",
    },
    {
        "article": "민법 제629조",
        "title": "임차권의 양도, 전대의 제한",
        "text": (
            "민법 제629조(임차권의 양도, 전대의 제한) ① 임차인은 임대인의 동의 없이 그 권리를 양도하거나 "
            "임차물을 전대하지 못한다. "
            "② 임차인이 전항의 규정에 위반한 때에는 임대인은 계약을 해지할 수 있다."
        ),
        "law_name": "민법",
    },
    {
        "article": "민법 제630조",
        "title": "전대의 효과",
        "text": (
            "민법 제630조(전대의 효과) ① 임차인이 임대인의 동의를 얻어 임차물을 전대한 때에는 전차인은 직접 "
            "임대인에 대하여 의무를 부담한다. 이 경우에 전차인은 전대인에 대한 차임의 지급으로써 임대인에게 "
            "대항하지 못한다. "
            "② 전항의 규정은 임대인의 임차인에 대한 권리 행사에 영향을 미치지 아니한다."
        ),
        "law_name": "민법",
    },
    {
        "article": "민법 제631조",
        "title": "전차인의 권리의 확정",
        "text": (
            "민법 제631조(전차인의 권리의 확정) 임차인이 임대인의 동의를 얻어 전대한 경우에는 임대인과 임차인의 "
            "합의로 계약을 종료한 때에도 전차인의 권리는 소멸하지 아니한다."
        ),
        "law_name": "민법",
    },
    {
        "article": "민법 제632조",
        "title": "임차건물의 전대와 임대인의 동의",
        "text": (
            "민법 제632조(임차건물의 전대와 임대인의 동의) 건물의 임차인이 그 건물의 소부분을 타인에게 사용하게 하는 "
            "경우에는 임대인의 동의가 없어도 된다."
        ),
        "law_name": "민법",
    },
    {
        "article": "민법 제633조",
        "title": "차임지급의 시기",
        "text": (
            "민법 제633조(차임지급의 시기) 차임은 동산, 건물이나 대지에 대하여는 매월 말에, 기타 토지에 대하여는 "
            "매년 말에 지급하여야 한다. 그러나 수확기 있는 것에 대하여는 그 수확 후 지체 없이 지급하여야 한다."
        ),
        "law_name": "민법",
    },
    {
        "article": "민법 제634조",
        "title": "임차인의 통지의무",
        "text": (
            "민법 제634조(임차인의 통지의무) 임차물의 수리를 요하거나 임차물에 대하여 권리를 주장하는 자가 있는 때에는 "
            "임차인은 지체 없이 임대인에게 이를 통지하여야 한다. 그러나 임대인이 이미 이를 안 때에는 그러하지 아니하다."
        ),
        "law_name": "민법",
    },
    {
        "article": "민법 제635조",
        "title": "기간의 약정 없는 임대차의 해지통고",
        "text": (
            "민법 제635조(기간의 약정 없는 임대차의 해지통고) ① 임대차기간의 약정이 없는 때에는 당사자는 언제든지 "
            "계약해지의 통고를 할 수 있다. "
            "② 상대방이 전항의 통고를 받은 날로부터 다음 각 호의 기간이 경과하면 해지의 효력이 생긴다. "
            "1. 토지, 건물 기타 공작물에 대하여는 임대인이 해지를 통고한 경우에는 6월, 임차인이 해지를 통고한 "
            "경우에는 1월 2. 동산에 대하여는 5일."
        ),
        "law_name": "민법",
    },
    {
        "article": "민법 제636조",
        "title": "기간만료후의 임대차",
        "text": (
            "민법 제636조(기간만료후의 임대차) 임대차기간이 만료한 후 임차인이 임차물의 사용, 수익을 계속하는 경우에 "
            "임대인이 상당한 기간 내에 이의를 하지 아니한 때에는 전임대차와 동일한 조건으로 다시 임대차한 것으로 본다. "
            "그러나 당사자는 제635조의 규정에 의하여 해지의 통고를 할 수 있다."
        ),
        "law_name": "민법",
    },
    {
        "article": "민법 제637조",
        "title": "임차인의 파산과 해지통고",
        "text": (
            "민법 제637조(임차인의 파산과 해지통고) ① 임차인이 파산선고를 받은 경우에는 임대차기간의 약정이 있는 때에도 "
            "임대인 또는 파산관재인은 제635조의 규정에 의하여 계약해지의 통고를 할 수 있다."
        ),
        "law_name": "민법",
    },
    {
        "article": "민법 제638조",
        "title": "해지통고의 전차인에 대한 통지",
        "text": (
            "민법 제638조(해지통고의 전차인에 대한 통지) ① 임대차계약이 해지의 통고로 인하여 종료된 경우에 "
            "그 임대물이 전대되어 있는 때에는 임대인은 전차인에게 그 통지를 하지 아니하면 그 해지로써 전차인에게 "
            "대항하지 못한다. "
            "② 전차인이 전항의 통지를 받은 때에는 제635조 제2항의 기간은 그 통지를 받은 날로부터 기산한다."
        ),
        "law_name": "민법",
    },
    {
        "article": "민법 제640조",
        "title": "차임연체와 해지",
        "text": (
            "민법 제640조(차임연체와 해지) 건물 기타 공작물의 임대차에는 임차인의 차임연체액이 2기의 차임액에 달하는 "
            "때에는 임대인은 계약을 해지할 수 있다."
        ),
        "law_name": "민법",
    },
    {
        "article": "민법 제641조",
        "title": "동전",
        "text": (
            "민법 제641조(동전) 건물 기타 공작물의 소유 또는 식목, 채염, 목축을 목적으로 한 토지임대차에는 "
            "임차인의 차임연체액이 2기의 차임액에 달하는 때에는 임대인은 계약을 해지할 수 있다."
        ),
        "law_name": "민법",
    },
    {
        "article": "민법 제643조",
        "title": "임차인의 갱신청구권, 매수청구권",
        "text": (
            "민법 제643조(임차인의 갱신청구권, 매수청구권) 건물 기타 공작물의 소유 또는 식목, 채염, 목축을 목적으로 "
            "한 토지임대차의 기간이 만료한 경우에 건물, 수목 기타 지상시설이 현존한 때에는 제283조의 규정을 준용한다."
        ),
        "law_name": "민법",
    },
    {
        "article": "민법 제645조",
        "title": "임차인의 갱신청구권, 매수청구권의 제한",
        "text": (
            "민법 제645조(임차인의 갱신청구권, 매수청구권의 제한) 제643조의 규정은 임차인이 그 토지를 "
            "적법하게 이용하지 아니한 때에는 이를 적용하지 아니한다."
        ),
        "law_name": "민법",
    },
    {
        "article": "민법 제647조",
        "title": "전차인의 매수청구권",
        "text": (
            "민법 제647조(전차인의 매수청구권) ① 건물 기타 공작물의 소유를 목적으로 한 토지임대차의 전차인이 "
            "그 토지를 적법하게 전차한 경우에 임대차 기간이 만료된 때에는 제643조의 규정을 준용한다. "
            "② 전항의 경우에 전차인의 매수청구는 임차인이 이미 이에 해당하는 건물 기타 공작물의 매수청구를 하지 "
            "아니한 때에 한하여 허용된다."
        ),
        "law_name": "민법",
    },
    {
        "article": "민법 제652조",
        "title": "강행규정",
        "text": (
            "민법 제652조(강행규정) 제627조, 제628조, 제631조, 제635조, 제638조, 제640조, 제641조, 제643조 내지 "
            "제647조의 규정에 위반하는 약정으로 임차인이나 전차인에게 불리한 것은 그 효력이 없다."
        ),
        "law_name": "민법",
    },
    {
        "article": "민법 제654조",
        "title": "준용규정",
        "text": (
            "민법 제654조(준용규정) 제610조 제1항, 제615조 내지 제617조의 규정은 임대차에 준용한다. "
            "임차인은 임대인의 동의 없이 임차권을 양도하거나 임차물을 전대하지 못한다."
        ),
        "law_name": "민법",
    },
]


# ---------------------------------------------------------------------------
# 벡터DB 구축 함수
# ---------------------------------------------------------------------------

def build_vectordb(articles: Optional[List[dict]] = None, use_sample: bool = False) -> int:
    """
    법령 텍스트를 ChromaDB에 색인한다.

    Parameters
    ----------
    articles : List[dict], optional
        색인할 법령 조항 목록. None이면 SAMPLE_LAW_ARTICLES 사용.
    use_sample : bool
        True이면 SAMPLE_LAW_ARTICLES만 사용.

    Returns
    -------
    int
        색인된 문서 수
    """
    if articles is None or use_sample:
        articles = SAMPLE_LAW_ARTICLES
        logger.info("샘플 법령 데이터 사용 (%d개 조항)", len(articles))

    try:
        import chromadb  # type: ignore
    except ImportError:
        logger.error("chromadb 패키지 미설치. pip install chromadb")
        raise

    # ChromaDB 클라이언트 초기화
    chroma_host = os.environ.get("CHROMA_HOST", "")
    chroma_port = int(os.environ.get("CHROMA_PORT", "8001"))
    persist_dir = os.environ.get("CHROMA_PERSIST_DIR", "./chroma_data")
    collection_name = os.environ.get("CHROMA_COLLECTION_NAME", "lease_law")

    if chroma_host:
        client = chromadb.HttpClient(host=chroma_host, port=chroma_port)
        logger.info("ChromaDB 원격 서버: %s:%d", chroma_host, chroma_port)
    else:
        client = chromadb.PersistentClient(path=persist_dir)
        logger.info("ChromaDB 로컬: %s", persist_dir)

    # 컬렉션 생성 또는 재사용
    try:
        collection = client.get_collection(name=collection_name)
        existing_count = collection.count()
        if existing_count > 0:
            logger.info(
                "기존 컬렉션 '%s' 발견 (%d개). 초기화 후 재색인합니다.",
                collection_name,
                existing_count,
            )
            client.delete_collection(name=collection_name)
    except Exception:
        pass  # 컬렉션이 없으면 새로 생성

    # 임베딩 함수 설정 (OpenAI API 키 없으면 stub 사용 — ONNX 다운로드 방지)
    embedding_fn = _get_embedding_function()
    is_openai = os.environ.get("OPENAI_API_KEY", "") != ""

    collection = client.create_collection(
        name=collection_name,
        embedding_function=embedding_fn,
        metadata={"hnsw:space": "cosine"},
    )
    logger.info("%s 임베딩 사용", "OpenAI" if is_openai else "stub (텍스트 검색 전용)")

    # 문서 준비
    ids = []
    documents = []
    metadatas = []

    for i, article in enumerate(articles):
        doc_id = f"article_{i:04d}_{article.get('article', '').replace(' ', '_')}"
        ids.append(doc_id)
        documents.append(article["text"])
        metadatas.append(
            {
                "law_name": article.get("law_name", "주택임대차보호법"),
                "article": article.get("article", ""),
                "title": article.get("title", ""),
            }
        )

    # 배치 삽입 (한 번에 많으면 속도 저하)
    batch_size = 50
    total_indexed = 0
    for start in range(0, len(documents), batch_size):
        end = min(start + batch_size, len(documents))
        collection.add(
            ids=ids[start:end],
            documents=documents[start:end],
            metadatas=metadatas[start:end],
        )
        total_indexed += end - start
        logger.info(
            "색인 중... %d / %d", total_indexed, len(documents)
        )

    final_count = collection.count()
    logger.info(
        "ChromaDB 색인 완료. 컬렉션 '%s': %d개 문서",
        collection_name,
        final_count,
    )
    return final_count


class _StubEmbeddingFunction:
    """
    OpenAI API 키 없을 때 사용하는 최소 임베딩 stub.
    실제 벡터 유사도 검색 없이 ChromaDB peek 기반 검색만 사용.
    정확도가 낮으므로 OPENAI_API_KEY 설정을 권장.
    """

    def name(self) -> str:  # ChromaDB 1.x 필수 메서드
        return "stub"

    def __call__(self, input):  # noqa: A002
        return [[0.0] * 384 for _ in input]


def _get_embedding_function():
    """OpenAI 임베딩 함수를 반환. API 키 없으면 stub 반환."""
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        logger.warning(
            "OPENAI_API_KEY 미설정 — 텍스트 기반 검색으로 동작합니다. "
            "정확도를 높이려면 OPENAI_API_KEY를 설정하세요."
        )
        return _StubEmbeddingFunction()

    try:
        from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction  # type: ignore

        return OpenAIEmbeddingFunction(
            api_key=api_key,
            model_name="text-embedding-3-small",
        )
    except ImportError:
        logger.warning("chromadb OpenAIEmbeddingFunction을 불러올 수 없습니다. stub 사용.")
        return _StubEmbeddingFunction()
    except Exception as exc:
        logger.warning("임베딩 함수 초기화 실패: %s — stub 사용", exc)
        return _StubEmbeddingFunction()


# ---------------------------------------------------------------------------
# 생활법령정보 조회 서비스 SOAP API 색인
# (법제처 easylaw.go.kr — https://www.easylaw.go.kr/OPENAPI/soap/LifeLawInfoService?wsdl)
# ---------------------------------------------------------------------------

# ChromaDB에 색인할 생활법령 영역 (csmSeq: getLifeAreaList → csmAstSeq=3 부동산/임대차)
_EASYLAW_TARGET_AREAS = [
    {"csm_seq": "629", "law_name": "주택임대차"},
    {"csm_seq": "627", "law_name": "상가건물임대차"},
    {"csm_seq": "1972", "law_name": "전세사기피해자지원"},
]

_EASYLAW_ENDPOINT = "https://www.easylaw.go.kr/OPENAPI/soap/LifeLawInfoService"
_SOAP_NS = {
    "soapenv": "http://schemas.xmlsoap.org/soap/envelope/",
    "ns1": "http://openapi.affis.go.kr",
    "head": "http://apache.org/headers",
}


def fetch_articles_from_law_api(api_key: str) -> List[dict]:
    """
    생활법령정보 조회 서비스 SOAP API로 임대차 관련 법령 내용을 가져온다.

    엔드포인트: https://www.easylaw.go.kr/OPENAPI/soap/LifeLawInfoService

    흐름:
        1. getLifeInterrestRuleAreaClassList(csmSeq) → CNPCLS 분류 목록
        2. getLifeInterrestRuleSummaryItem(csmSeq, ccfNo, cciNo, cnpClsNo) → 법령 HTML
        3. HTML 태그 제거 → 텍스트 추출 → ChromaDB article 형식으로 변환

    Parameters
    ----------
    api_key : str
        공공데이터포털에서 발급받은 서비스 키

    Returns
    -------
    List[dict]
        파싱된 법령 조항 목록 (article, title, text, law_name 키)
    """
    import time

    all_articles: List[dict] = []

    for area in _EASYLAW_TARGET_AREAS:
        csm_seq = area["csm_seq"]
        law_name = area["law_name"]
        logger.info("[%s] 분류 체계 조회 중 (csmSeq=%s)...", law_name, csm_seq)

        try:
            class_items = _easylaw_get_area_class_list(api_key, csm_seq)
        except Exception as exc:
            logger.warning("[%s] 분류 조회 실패: %s", law_name, exc)
            continue

        # CNPCLS 리프 노드만 추출 (실제 법령 내용이 있는 항목)
        cnpcls_items = [it for it in class_items if it.get("cls") == "CNPCLS"]
        logger.info("[%s] CNPCLS 항목 %d개 수집", law_name, len(cnpcls_items))

        for idx, item in enumerate(cnpcls_items):
            ccf_no = item.get("ccfNo", "0")
            cci_no = item.get("cciNo", "0")
            cnp_cls_no = item.get("cnpClsNo", "0")
            item_nm = item.get("nm", "")

            try:
                html_content = _easylaw_get_rule_summary(
                    api_key, csm_seq, ccf_no, cci_no, cnp_cls_no
                )
                text = _html_to_text(html_content)

                if len(text.strip()) < 30:
                    continue

                article_id = f"{law_name}_{ccf_no}_{cci_no}_{cnp_cls_no}"
                all_articles.append({
                    "article": article_id,
                    "title": item_nm,
                    "text": text[:1500],
                    "law_name": law_name,
                    "source": "easylaw",
                })

                if (idx + 1) % 10 == 0:
                    logger.info("[%s] %d / %d 완료", law_name, idx + 1, len(cnpcls_items))

                # API 부하 방지 (0.3초 간격)
                time.sleep(0.3)

            except Exception as exc:
                logger.warning(
                    "[%s] 항목 조회 실패 (%s ccf=%s cci=%s cls=%s): %s",
                    law_name, item_nm, ccf_no, cci_no, cnp_cls_no, exc
                )
                continue

        logger.info("[%s] 완료: %d개 항목 수집", law_name, len(all_articles))

    logger.info("생활법령 API 수집 완료: 총 %d개 항목", len(all_articles))
    return all_articles


def _check_soap_error(root) -> None:
    """SOAP 응답 XML에서 공공데이터포털 API 오류가 있는지 검사하고 예외를 던진다."""
    err_msg_el = root.find(".//errMsg")
    return_code_el = root.find(".//returnCode")
    if err_msg_el is not None and err_msg_el.text:
        err_msg = err_msg_el.text.strip()
        return_code = return_code_el.text.strip() if return_code_el is not None else "unknown"
        if return_code != "00" and err_msg:
            raise RuntimeError(f"API Error (code={return_code}): {err_msg}")


def _easylaw_soap_call(api_key: str, req_id: str, body_xml: str) -> str:
    """
    생활법령 SOAP API를 호출하고 응답 XML 문자열을 반환한다.

    SOAP 헤더 구조:
        <head:ComMsgHeader>
          <RequestMsgID>...</RequestMsgID>   ← 네임스페이스 없음
          <ServiceKey>...</ServiceKey>       ← 네임스페이스 없음
        </head:ComMsgHeader>
    """
    import urllib.request

    envelope = f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:ns1="http://openapi.affis.go.kr"
                  xmlns:head="http://apache.org/headers">
  <soapenv:Header>
    <head:ComMsgHeader>
      <RequestMsgID>{req_id}</RequestMsgID>
      <ServiceKey>{api_key}</ServiceKey>
    </head:ComMsgHeader>
  </soapenv:Header>
  <soapenv:Body>
{body_xml}
  </soapenv:Body>
</soapenv:Envelope>"""

    data = envelope.encode("utf-8")
    req = urllib.request.Request(
        _EASYLAW_ENDPOINT,
        data=data,
        headers={
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": "",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def _easylaw_get_area_class_list(api_key: str, csm_seq: str) -> List[dict]:
    """getLifeInterrestRuleAreaClassList → CNPCLS 분류 목록 반환.

    NOTE: 응답 내부 요소(`LifeInterrestRuleAreaClassListItem`, `ccfNo` 등)에는
    XML 네임스페이스가 없으므로 태그명을 그대로 사용한다.
    """
    import xml.etree.ElementTree as ET

    body = f"""    <ns1:getLifeInterrestRuleAreaClassList>
      <LifeInterrestRuleAreaClassListRequest>
        <csmSeq>{csm_seq}</csmSeq>
      </LifeInterrestRuleAreaClassListRequest>
    </ns1:getLifeInterrestRuleAreaClassList>"""

    xml_str = _easylaw_soap_call(api_key, f"CLS_{csm_seq}", body)
    root = ET.fromstring(xml_str)
    _check_soap_error(root)

    items = []
    # 응답 내부 요소는 네임스페이스 없음 → 태그명만 사용
    for item in root.iter("LifeInterrestRuleAreaClassListItem"):
        items.append({
            "cls":      _et_text(item, "cls"),
            "ccfNo":    _et_text(item, "ccfNo"),
            "cciNo":    _et_text(item, "cciNo"),
            "cnpClsNo": _et_text(item, "cnpClsNo"),
            "csmSeq":   _et_text(item, "csmSeq"),
            "nm":       _et_text(item, "nm"),
            "srvYn":    _et_text(item, "srvYn"),
        })
    return items


def _easylaw_get_rule_summary(
    api_key: str, csm_seq: str, ccf_no: str, cci_no: str, cnp_cls_no: str
) -> str:
    """getLifeInterrestRuleSummaryItem → 법령 내용 HTML 반환.

    NOTE: `item` 필드가 네임스페이스 없이 반환되므로 find("//item") 사용.
    """
    import xml.etree.ElementTree as ET

    body = f"""    <ns1:getLifeInterrestRuleSummaryItem>
      <LifeInterrestRuleSummaryItemRequest>
        <csmSeq>{csm_seq}</csmSeq>
        <ccfNo>{ccf_no}</ccfNo>
        <cciNo>{cci_no}</cciNo>
        <cnpClsNo>{cnp_cls_no}</cnpClsNo>
      </LifeInterrestRuleSummaryItemRequest>
    </ns1:getLifeInterrestRuleSummaryItem>"""

    xml_str = _easylaw_soap_call(
        api_key, f"RULE_{csm_seq}_{ccf_no}_{cci_no}_{cnp_cls_no}", body
    )
    root = ET.fromstring(xml_str)
    _check_soap_error(root)

    # `item` 요소 탐색: 네임스페이스 없이 재귀 탐색
    item_el = root.find(".//item")
    if item_el is not None and item_el.text:
        return item_el.text
    return ""


def _et_text(element, tag: str) -> str:
    """XML Element에서 단순 태그 텍스트를 추출한다 (없으면 빈 문자열)."""
    child = element.find(tag)
    return (child.text or "").strip() if child is not None else ""


def _html_to_text(html: str) -> str:
    """HTML을 일반 텍스트로 변환한다 (태그 제거, 공백 정리)."""
    import re
    import html as html_module

    # HTML 엔티티 디코딩 (&#xD; → \r, &amp; → &, etc.)
    text = html_module.unescape(html)
    # script / style 태그 제거
    text = re.sub(r"<(script|style)[^>]*>.*?</(script|style)>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    # 나머지 HTML 태그 제거
    text = re.sub(r"<[^>]+>", " ", text)
    # 연속 공백 및 개행 정리
    text = re.sub(r"[\r\n\t]+", " ", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


# ---------------------------------------------------------------------------
# PDF 법령 텍스트 파싱 (실제 법령 PDF 색인용)
# ---------------------------------------------------------------------------

def load_articles_from_pdf(pdf_path: str) -> List[dict]:
    """
    PDF 법령 파일에서 조항을 파싱한다.

    Parameters
    ----------
    pdf_path : str
        PDF 파일 경로

    Returns
    -------
    List[dict]
        파싱된 법령 조항 목록
    """
    try:
        import pdfplumber  # type: ignore
    except ImportError:
        logger.error("pdfplumber 미설치. pip install pdfplumber")
        raise

    import re

    try:
        pages_text = []
        with pdfplumber.open(pdf_path) as pdf:
            law_name = os.path.splitext(os.path.basename(pdf_path))[0]
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages_text.append(text.strip())

        full_text = "\n\n".join(pages_text)
    except Exception as exc:
        logger.error("PDF 읽기 실패: %s", exc)
        raise

    # 조항 분리 (제N조 패턴)
    article_pattern = re.compile(
        r"(제\s*\d+\s*조(?:\s*의\s*\d+)?(?:\s*[\(\（][^\)\）]{0,40}[\)\）])?)",
        re.MULTILINE,
    )

    matches = list(article_pattern.finditer(full_text))
    articles = []

    for i, match in enumerate(matches):
        article_label = re.sub(r"\s+", "", match.group(1))
        # 괄호 안의 제목 추출
        title_match = re.search(r"[\(\（]([^\)\）]+)[\)\）]", match.group(1))
        title = title_match.group(1).strip() if title_match else ""

        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        text_body = full_text[start:end].strip()

        # 너무 짧은 조항 제외
        if len(text_body) < 20:
            continue

        articles.append(
            {
                "article": article_label,
                "title": title,
                "text": text_body[:1000],  # 최대 1000자 (임베딩 제한)
                "law_name": law_name,
            }
        )

    logger.info("PDF '%s'에서 %d개 조항 파싱 완료", pdf_path, len(articles))
    return articles


# ---------------------------------------------------------------------------
# CLI 진입점
# ---------------------------------------------------------------------------

def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="임대차 법령 텍스트를 ChromaDB에 색인합니다."
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        default=False,
        help="샘플 데이터로 테스트 색인 (실제 PDF·API 없이 동작)",
    )
    parser.add_argument(
        "--api",
        action="store_true",
        default=False,
        help="공공데이터포털 법제처 API로 실제 법령 색인 (LAW_API_KEY 필요)",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default="",
        help="법제처 API 키 (미입력 시 LAW_API_KEY 환경변수 사용)",
    )
    parser.add_argument(
        "--pdf",
        type=str,
        action="append",
        default=[],
        help="법령 PDF 파일 경로 (여러 번 지정 가능)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        default=False,
        help="샘플 + API 법령을 모두 합쳐 색인 (LAW_API_KEY 권장, 없으면 샘플만)",
    )
    parser.add_argument(
        "--persist-dir",
        type=str,
        default="",
        help="ChromaDB 저장 경로 (기본: ./chroma_data)",
    )
    args = parser.parse_args()

    if args.persist_dir:
        os.environ["CHROMA_PERSIST_DIR"] = args.persist_dir

    if args.all:
        # 샘플 + API 합쳐서 최대 데이터 색인
        api_key = args.api_key or os.environ.get("LAW_API_KEY", "")
        combined: List[dict] = list(SAMPLE_LAW_ARTICLES)
        if api_key:
            logger.info("샘플 + 법제처 API 합산 색인 시작")
            try:
                api_articles = fetch_articles_from_law_api(api_key)
            except Exception as e:
                logger.error("법제처 API 호출 실패: %s. 로컬 PDF 폴백을 진행합니다.", e)
                api_articles = []

            # API 수집 실패 시 PDF 폴백
            if not api_articles:
                logger.warning("API 수집 결과가 없으므로 로컬 PDF 파일(raw_data/)을 파싱하여 폴백합니다.")
                pdf_files = ["raw_data/lease_protection_law.pdf", "raw_data/civil_law.pdf"]
                for pdf_path in pdf_files:
                    if os.path.exists(pdf_path):
                        try:
                            logger.info("폴백 PDF 파싱: %s", pdf_path)
                            api_articles.extend(load_articles_from_pdf(pdf_path))
                        except Exception as exc:
                            logger.error("폴백 PDF 파싱 실패 (%s): %s", pdf_path, exc)
                    else:
                        logger.warning("폴백용 PDF 파일이 존재하지 않습니다: %s", pdf_path)

            combined.extend(api_articles)
            logger.info("샘플 %d개 + API/PDF %d개 = 총 %d개 조항", len(SAMPLE_LAW_ARTICLES), len(api_articles), len(combined))
        else:
            logger.warning("LAW_API_KEY 미설정 — 샘플 데이터(%d개)만 색인합니다.", len(combined))
        count = build_vectordb(articles=combined)

    elif args.api:
        # 공공데이터포털 API로 실제 법령 색인 (샘플 포함)
        api_key = args.api_key or os.environ.get("LAW_API_KEY", "")
        if not api_key:
            logger.error(
                "LAW_API_KEY 환경변수 또는 --api-key 인자가 필요합니다.\n"
                "  export LAW_API_KEY='발급받은_API_키'\n"
                "  또는 --api-key '발급받은_API_키'"
            )
            sys.exit(1)
        logger.info("공공데이터포털 법제처 API로 법령 색인 시작")
        try:
            api_articles_only = fetch_articles_from_law_api(api_key)
        except Exception as e:
            logger.error("법제처 API 호출 실패: %s. 로컬 PDF 폴백을 진행합니다.", e)
            api_articles_only = []

        # API 수집 실패 시 PDF 폴백
        if not api_articles_only:
            logger.warning("API 수집 결과가 없으므로 로컬 PDF 파일(raw_data/)을 파싱하여 폴백합니다.")
            pdf_files = ["raw_data/lease_protection_law.pdf", "raw_data/civil_law.pdf"]
            for pdf_path in pdf_files:
                if os.path.exists(pdf_path):
                    try:
                        logger.info("폴백 PDF 파싱: %s", pdf_path)
                        api_articles_only.extend(load_articles_from_pdf(pdf_path))
                    except Exception as exc:
                        logger.error("폴백 PDF 파싱 실패 (%s): %s", pdf_path, exc)
                else:
                    logger.warning("폴백용 PDF 파일이 존재하지 않습니다: %s", pdf_path)

        # API 데이터가 적을 경우 샘플도 포함하여 최소 품질 보장
        all_articles: List[dict] = list(SAMPLE_LAW_ARTICLES) + api_articles_only
        logger.info("샘플 %d개 + API/PDF %d개 = 총 %d개 조항 → ChromaDB 색인 시작",
                    len(SAMPLE_LAW_ARTICLES), len(api_articles_only), len(all_articles))
        count = build_vectordb(articles=all_articles)

    elif args.pdf:
        all_articles = []
        for pdf_path in args.pdf:
            logger.info("PDF 법령 파일 파싱: %s", pdf_path)
            all_articles.extend(load_articles_from_pdf(pdf_path))
        logger.info("총 %d개 조항 수집", len(all_articles))
        count = build_vectordb(articles=all_articles)

    else:
        # 기본: 샘플 데이터 사용
        logger.info("샘플 데이터로 테스트 색인 시작 (--api 옵션으로 실제 법령 색인 권장)")
        count = build_vectordb(use_sample=True)

    print(f"\n색인 완료: {count}개 법령 조항이 ChromaDB에 저장되었습니다.")


if __name__ == "__main__":
    main()
