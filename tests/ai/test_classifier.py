"""
위험도 분류기(classifier.py) 테스트 — rule-based 폴백 기준

테스트 범위:
    - 중위험(medium) 패턴 전체
    - 주의(caution) 패턴 전체
    - 정상(safe) 표준 조항
    - 조항 목록 일괄 분류
    - 엣지케이스 (빈 텍스트, 혼합 패턴)
"""
import pytest
from backend.ai.classifier import _classify_with_rules, classify_risk


# ---------------------------------------------------------------------------
# 중위험(medium) 패턴
# ---------------------------------------------------------------------------

class TestMediumRisk:

    def test_landlord_consent_violation(self):
        assert _classify_with_rules("임대인 동의 없이 목적물을 전대할 수 없다") == "medium"

    def test_landlord_consent_with_spacing(self):
        assert _classify_with_rules("임대인의 동의 없이 임차권을 양도한다") == "medium"

    def test_deposit_refusal(self):
        assert _classify_with_rules("보증금 반환 거절 시 이자를 청구할 수 없다") == "medium"

    def test_deposit_delay(self):
        assert _classify_with_rules("보증금 반환 지연에 대해 임차인은 이의를 제기할 수 없다") == "medium"

    def test_contract_termination_prohibited(self):
        assert _classify_with_rules("임차인은 계약 해지 불가하다") == "medium"

    def test_contract_termination_cannot(self):
        assert _classify_with_rules("임차인은 계약 해지할 수 없다") == "medium"

    def test_landlord_unilateral_termination(self):
        assert _classify_with_rules("임대인이 언제든지 해지할 수 있다") == "medium"

    def test_landlord_one_sided_termination(self):
        assert _classify_with_rules("임대인은 일방적으로 해제할 수 있다") == "medium"

    def test_deposit_deduction_arbitrary(self):
        assert _classify_with_rules("보증금에서 일방적으로 공제한다") == "medium"

    def test_deposit_deduction_unconditional(self):
        assert _classify_with_rules("보증금에서 무조건 공제할 수 있다") == "medium"

    def test_right_of_lease_waiver(self):
        assert _classify_with_rules("임차인은 대항력 포기에 동의한다") == "medium"

    def test_fixed_date_prohibition(self):
        assert _classify_with_rules("확정일자 신청 금지") == "medium"

    def test_lease_registration_prohibition(self):
        assert _classify_with_rules("임차권 등기 신청 금지") == "medium"

    def test_repair_responsibility(self):
        assert _classify_with_rules("수선 책임은 임차인이 부담한다") == "medium"

    def test_repair_cost(self):
        assert _classify_with_rules("수선 비용은 임차인이 전액 부담한다") == "medium"

    def test_restoration(self):
        assert _classify_with_rules("계약 종료 시 원상복구 의무가 있다") == "medium"

    def test_maintenance_fee(self):
        assert _classify_with_rules("관리비 전액 부담은 임차인으로 한다") == "medium"

    def test_deposit_no_interest(self):
        assert _classify_with_rules("보증금 이자 없음을 상호 확인한다") == "medium"

    def test_early_termination_penalty(self):
        assert _classify_with_rules("중도 해지 위약금은 보증금의 10%로 한다") == "medium"

    def test_landlord_entry_anytime(self):
        assert _classify_with_rules("임대인이 언제든지 방문할 수 있다") == "medium"

    def test_landlord_entry_without_notice(self):
        assert _classify_with_rules("임대인은 사전 통보 없이 출입할 수 있다") == "medium"

    def test_high_overdue_interest(self):
        assert _classify_with_rules("연체 이자 연 20%를 부과한다") == "medium"

    def test_monthly_overdue_interest(self):
        assert _classify_with_rules("연체 이율 월 3%를 적용한다") == "medium"


# ---------------------------------------------------------------------------
# 주의(caution) 패턴
# ---------------------------------------------------------------------------

class TestCautionRisk:

    def test_sublease_prohibition(self):
        assert _classify_with_rules("전대 금지로 한다") == "caution"

    def test_sublease_impossible(self):
        assert _classify_with_rules("전대 불가 조항에 동의한다") == "caution"

    def test_pet_prohibition(self):
        assert _classify_with_rules("반려동물 사육을 금지한다") == "caution"

    def test_pet_alt_term(self):
        assert _classify_with_rules("애완동물은 입주 불가하다") == "caution"

    def test_smoking_prohibition(self):
        assert _classify_with_rules("흡연 금지 구역으로 지정한다") == "caution"

    def test_smoking_impossible(self):
        assert _classify_with_rules("흡연 불가") == "caution"

    def test_interior_change_prohibition(self):
        assert _classify_with_rules("인테리어 변경 금지") == "caution"

    def test_facility_alteration_prohibition(self):
        assert _classify_with_rules("시설 개조 금지") == "caution"

    def test_structure_modification_prohibition(self):
        assert _classify_with_rules("구조 공사 금지") == "caution"

    def test_washer_installation_prohibition(self):
        assert _classify_with_rules("세탁기 설치 금지") == "caution"

    def test_ac_installation_prohibition(self):
        assert _classify_with_rules("에어컨 설치 금지") == "caution"

    def test_resident_registration_restriction(self):
        assert _classify_with_rules("전입신고 제한이 있다") == "caution"

    def test_resident_registration_prohibition(self):
        assert _classify_with_rules("전입신고 금지 조항") == "caution"


# ---------------------------------------------------------------------------
# 정상(safe) 조항
# ---------------------------------------------------------------------------

class TestSafeRisk:

    def test_lease_period_standard(self):
        assert _classify_with_rules("임대차 기간은 2024년 3월 1일부터 2026년 2월 28일까지 2년으로 한다") == "safe"

    def test_deposit_payment(self):
        assert _classify_with_rules("보증금은 금 일억원으로 하며 계약 시 계약금을 지불한다") == "safe"

    def test_landlord_obligation_standard(self):
        assert _classify_with_rules("임대인은 임차인이 사용·수익할 수 있도록 목적물을 유지하여야 한다") == "safe"

    def test_purpose_clause(self):
        assert _classify_with_rules("본 계약은 아래 부동산에 대한 임대차 계약을 체결함을 목적으로 한다") == "safe"

    def test_contract_renewal_notice(self):
        assert _classify_with_rules("임차인이 계속 거주를 원하는 경우 만료 2개월 전에 통보하여야 한다") == "safe"

    def test_property_info(self):
        assert _classify_with_rules("소재지: 서울시 강남구 역삼동 123-45, 건물종류: 아파트") == "safe"

    def test_empty_text(self):
        assert _classify_with_rules("") == "safe"

    def test_whitespace_only(self):
        assert _classify_with_rules("   \n\t  ") == "safe"

    def test_unrelated_korean(self):
        assert _classify_with_rules("날씨가 맑고 하늘이 파랗다") == "safe"


# ---------------------------------------------------------------------------
# 혼합 패턴 (가장 높은 우선순위 규칙이 적용되어야 함)
# ---------------------------------------------------------------------------

class TestMixedPatterns:

    def test_medium_takes_priority_over_caution(self):
        # medium + caution 조항 혼합 → medium이 먼저 매칭
        text = "임대인 동의 없이 전대 금지이며 반려동물도 금지한다"
        assert _classify_with_rules(text) == "medium"

    def test_caution_when_no_medium_keywords(self):
        # caution만 있으면 caution
        text = "전대 금지 및 반려동물 사육 금지"
        assert _classify_with_rules(text) == "caution"

    def test_restoration_with_other_content(self):
        # 원상복구가 포함된 긴 조항
        text = "계약 종료 시 임차인은 원상복구 의무를 지며 임대인은 보증금을 반환한다"
        assert _classify_with_rules(text) == "medium"

    def test_whitespace_in_pattern(self):
        # 패턴 내 공백 처리 확인
        assert _classify_with_rules("수선  책임 은 임 차인 부담") == "medium"


# ---------------------------------------------------------------------------
# 조항 목록 일괄 분류 (classify_risk)
# ---------------------------------------------------------------------------

class TestClassifyRisk:

    def test_single_safe_clause(self):
        clauses = [{"number": "제1조", "title": "목적", "text": "임대차 계약을 체결함을 목적으로 한다", "items": []}]
        result = classify_risk(clauses)
        assert len(result) == 1
        assert result[0]["risk"] == "safe"
        assert result[0]["number"] == "제1조"

    def test_multiple_clauses_mixed(self):
        clauses = [
            {"number": "제1조", "title": "목적", "text": "임대차 계약을 목적으로 한다", "items": []},
            {"number": "제2조", "title": "의무", "text": "수선 책임은 임차인이 부담한다", "items": []},
            {"number": "특약", "title": "", "text": "흡연 금지", "items": []},
        ]
        result = classify_risk(clauses)
        assert result[0]["risk"] == "safe"
        assert result[1]["risk"] == "medium"
        assert result[2]["risk"] == "caution"

    def test_original_fields_preserved(self):
        clauses = [{"number": "제5조", "title": "특별조항", "text": "원상복구", "items": ["① 항목1"]}]
        result = classify_risk(clauses)
        assert result[0]["number"] == "제5조"
        assert result[0]["title"] == "특별조항"
        assert result[0]["items"] == ["① 항목1"]

    def test_empty_list(self):
        assert classify_risk([]) == []

    def test_all_safe(self):
        clauses = [
            {"number": "제1조", "title": "", "text": "임대차 기간은 2년으로 한다", "items": []},
            {"number": "제2조", "title": "", "text": "보증금은 일억원으로 한다", "items": []},
        ]
        result = classify_risk(clauses)
        assert all(c["risk"] == "safe" for c in result)

    def test_all_medium(self):
        clauses = [
            {"number": "제1조", "title": "", "text": "보증금 반환 거절 시 이의 없다", "items": []},
            {"number": "제2조", "title": "", "text": "임대인이 언제든지 해지할 수 있다", "items": []},
        ]
        result = classify_risk(clauses)
        assert all(c["risk"] == "medium" for c in result)


class TestCriticalRisk:
    """치명 위험(전세사기/깡통전세) → 규칙 기반 high 승격."""

    def _risk(self, text: str) -> str:
        return classify_risk(
            [{"number": "X", "title": "", "text": text, "items": []}]
        )[0]["risk"]

    def test_trust_without_consent(self):
        assert self._risk("본 주택은 신탁회사 동의 없이 임대를 체결한다") == "high"

    def test_lien_priority_over_tenant(self):
        assert self._risk("해당 근저당은 임차인의 대항력보다 선순위로 간주한다") == "high"

    def test_extra_lien_allowed(self):
        assert self._risk("임대인은 전입신고일 당일 추가 근저당권을 설정할 수 있다") == "high"

    def test_collateral_disclosure_refusal(self):
        assert self._risk("임대인은 근저당권 내역을 임차인에게 별도 고지하지 않는다") == "high"

    def test_priority_repayment_excluded(self):
        assert self._risk("임차인은 선순위 근저당권자에 대해 우선 정산을 주장할 수 없다") == "high"

    def test_deposit_insurance_waiver(self):
        assert self._risk("임차인은 보증금 반환 보증보험 가입 권리를 포기한다") == "high"

    def test_gap_no_price_difference(self):
        assert self._risk("매매가와 전세가의 차액이 없음을 확인한다") == "high"

    def test_move_in_absolute_prohibition(self):
        assert self._risk("임차인은 전입신고를 절대 하지 않기로 확약한다") == "high"

    def test_renewal_right_waiver(self):
        assert self._risk("임차인은 계약갱신요구권을 일체 행사하지 않기로 포기한다") == "high"

    # 과탐 방지 — 일반 조항은 high가 아니어야 함
    def test_ordinary_clause_not_high(self):
        assert self._risk("임대차 기간은 2년으로 한다") == "safe"

    def test_ordinary_repair_not_high(self):
        assert self._risk("수선 책임은 임차인이 부담한다") == "medium"
