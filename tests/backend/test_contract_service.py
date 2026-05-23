"""
계약서 서비스 순수 함수 테스트

테스트 범위:
    - _compute_risk_score: 위험도 점수 계산 (0-100)
    - _compute_risk_level: 점수 → 레벨 변환
    - contract_to_status_response: Contract 모델 → AnalysisStatusResponse
    - contract_to_result_response: Contract 모델 → AnalysisResultResponse (BUG-004 포함)
    - check_and_consume_quota: 쿼터 소비 로직
"""
import uuid
import pytest
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime, timezone

# sys.path는 conftest.py에서 설정
from backend.app.services.contract_service import (
    _compute_risk_score,
    _compute_risk_level,
    contract_to_status_response,
    contract_to_result_response,
    check_and_consume_quota,
)


# ─── _compute_risk_score ──────────────────────────────────────────────────────

class TestComputeRiskScore:

    def test_all_safe_returns_zero(self):
        summary = {"high": 0, "medium": 0, "caution": 0, "safe": 5}
        assert _compute_risk_score(summary) == 0

    def test_all_high_returns_100(self):
        summary = {"high": 3, "medium": 0, "caution": 0, "safe": 0}
        assert _compute_risk_score(summary) == 100

    def test_all_medium_returns_expected(self):
        # medium * 2 / (total * 3) = 3*2 / (3*3) = 6/9 = 0.666... → 66
        summary = {"high": 0, "medium": 3, "caution": 0, "safe": 0}
        score = _compute_risk_score(summary)
        assert 60 <= score <= 70

    def test_empty_summary_returns_zero(self):
        assert _compute_risk_score({}) == 0

    def test_mixed_summary_in_range(self):
        summary = {"high": 1, "medium": 2, "caution": 2, "safe": 5}
        score = _compute_risk_score(summary)
        assert 0 <= score <= 100

    def test_returns_integer(self):
        summary = {"high": 0, "medium": 1, "caution": 1, "safe": 1}
        assert isinstance(_compute_risk_score(summary), int)

    def test_score_capped_at_100(self):
        summary = {"high": 100, "medium": 100, "caution": 100, "safe": 0}
        score = _compute_risk_score(summary)
        assert score <= 100


# ─── _compute_risk_level ──────────────────────────────────────────────────────

class TestComputeRiskLevel:

    def test_score_70_plus_is_high(self):
        assert _compute_risk_level(70) == "high"
        assert _compute_risk_level(100) == "high"

    def test_score_40_to_69_is_medium(self):
        assert _compute_risk_level(40) == "medium"
        assert _compute_risk_level(69) == "medium"

    def test_score_20_to_39_is_caution(self):
        assert _compute_risk_level(20) == "caution"
        assert _compute_risk_level(39) == "caution"

    def test_score_0_to_19_is_safe(self):
        assert _compute_risk_level(0) == "safe"
        assert _compute_risk_level(19) == "safe"


# ─── contract_to_status_response ─────────────────────────────────────────────

class TestContractToStatusResponse:

    def _make_contract(self, **kwargs):
        contract = MagicMock()
        contract.job_id = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
        contract.status = kwargs.get("status", "analyzing")
        contract.progress = kwargs.get("progress", 50)
        contract.current_step = kwargs.get("current_step", "analyze")
        contract.completed_steps = kwargs.get("completed_steps", ["upload", "ocr"])
        contract.report_id = kwargs.get("report_id", None)
        contract.error_code = kwargs.get("error_code", None)
        contract.error_message = kwargs.get("error_message", None)
        return contract

    def test_job_id_preserved(self):
        contract = self._make_contract()
        response = contract_to_status_response(contract)
        assert response.job_id == "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

    def test_status_preserved(self):
        contract = self._make_contract(status="completed")
        response = contract_to_status_response(contract)
        assert response.status == "completed"

    def test_progress_preserved(self):
        contract = self._make_contract(progress=80)
        response = contract_to_status_response(contract)
        assert response.progress == 80

    def test_completed_steps_preserved(self):
        steps = ["upload", "ocr", "analyze"]
        contract = self._make_contract(completed_steps=steps)
        response = contract_to_status_response(contract)
        assert response.completed_steps == steps

    def test_no_report_id_is_none(self):
        contract = self._make_contract(report_id=None)
        response = contract_to_status_response(contract)
        assert response.report_id is None

    def test_report_id_converted_to_string(self):
        report_uuid = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
        contract = self._make_contract(report_id=report_uuid)
        response = contract_to_status_response(contract)
        assert response.report_id == "cccccccc-cccc-cccc-cccc-cccccccccccc"

    def test_error_fields_preserved(self):
        contract = self._make_contract(
            error_code="ANALYSIS_TIMEOUT",
            error_message="분석 시간이 초과되었습니다."
        )
        response = contract_to_status_response(contract)
        assert response.error_code == "ANALYSIS_TIMEOUT"
        assert response.error_message == "분석 시간이 초과되었습니다."

    def test_disclaimer_is_included(self):
        contract = self._make_contract()
        response = contract_to_status_response(contract)
        assert response.disclaimer is not None
        assert len(response.disclaimer) > 0


# ─── contract_to_result_response ─────────────────────────────────────────────

class TestContractToResultResponse:

    def _make_contract(self, result_data: dict):
        contract = MagicMock()
        contract.report_id = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
        contract.job_id = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
        contract.created_at = datetime(2026, 5, 1, tzinfo=timezone.utc)
        contract.contract_type = "jeonse"
        contract.result = result_data
        contract.ocr_text = "임대차 계약서 전문"
        return contract

    def _make_result(self, **override):
        result = {
            "summary": {"high": 0, "medium": 1, "caution": 1, "safe": 1},
            "clauses": [
                {
                    "id": str(uuid.uuid4()),
                    "risk": "medium",
                    "clause_number": "제4조",
                    "original_text": "수선 책임은 임차인이 부담한다.",
                    "explanation": "불리한 조항",
                    "law_reference": {
                        "law_name": "주택임대차보호법",
                        "article": "제11조",
                        "summary": "임차물 보존 의무",
                        "url": None,
                    },
                    "recommendation": "수선비 협의 필요",
                },
            ],
            "special_clauses": [],
            "disclaimer": "법률 조언 아님",
            "ocr_method": "plain_text",
            "ocr_confidence": 1.0,
            "elapsed_seconds": 5.0,
        }
        result.update(override)
        return result

    def test_report_id_preserved(self):
        contract = self._make_contract(self._make_result())
        response = contract_to_result_response(contract)
        assert response.report_id == "cccccccc-cccc-cccc-cccc-cccccccccccc"

    def test_risk_score_is_computed(self):
        contract = self._make_contract(self._make_result())
        response = contract_to_result_response(contract)
        assert 0 <= response.risk_score <= 100

    def test_risk_level_is_valid(self):
        contract = self._make_contract(self._make_result())
        response = contract_to_result_response(contract)
        assert response.risk_level in ("high", "medium", "caution", "safe")

    def test_clauses_count_matches(self):
        contract = self._make_contract(self._make_result())
        response = contract_to_result_response(contract)
        assert len(response.clauses) == 1

    def test_clause_risk_preserved(self):
        contract = self._make_contract(self._make_result())
        response = contract_to_result_response(contract)
        assert response.clauses[0].risk == "medium"

    def test_law_reference_built_correctly(self):
        contract = self._make_contract(self._make_result())
        response = contract_to_result_response(contract)
        lr = response.clauses[0].law_reference
        assert lr is not None
        assert lr.law_name == "주택임대차보호법"
        assert lr.article == "제11조"

    def test_ocr_text_preserved(self):
        contract = self._make_contract(self._make_result())
        response = contract_to_result_response(contract)
        assert response.ocr_text == "임대차 계약서 전문"

    # BUG-004: "normal" 키를 "safe"로 정규화
    def test_bug004_normal_key_normalized_to_safe(self):
        """pipeline이 'normal' 키를 사용할 경우 'safe'로 통합된다."""
        result = self._make_result(
            summary={"high": 0, "medium": 1, "caution": 0, "normal": 3, "safe": 0}
        )
        contract = self._make_contract(result)
        response = contract_to_result_response(contract)
        assert response.summary.safe == 3  # normal=3이 safe로 합산됨

    def test_bug004_safe_and_normal_summed(self):
        """pipeline이 'safe'와 'normal' 키를 모두 가질 경우 합산된다."""
        result = self._make_result(
            summary={"high": 0, "medium": 0, "caution": 0, "normal": 2, "safe": 1}
        )
        contract = self._make_contract(result)
        response = contract_to_result_response(contract)
        assert response.summary.safe == 3  # 2 + 1

    def test_all_safe_summary_gives_low_risk(self):
        result = self._make_result(
            summary={"high": 0, "medium": 0, "caution": 0, "safe": 5},
            clauses=[],
        )
        contract = self._make_contract(result)
        response = contract_to_result_response(contract)
        assert response.risk_score == 0
        assert response.risk_level == "safe"

    def test_empty_result_handled_gracefully(self):
        contract = self._make_contract({})
        response = contract_to_result_response(contract)
        assert response.clauses == []
        assert response.risk_score == 0


# ─── check_and_consume_quota ──────────────────────────────────────────────────

class TestCheckAndConsumeQuota:

    def _make_quota(self, quota_type="single", remaining=1, pass_expires_at=None):
        quota = MagicMock()
        quota.quota_type = quota_type
        quota.remaining = remaining
        quota.pass_expires_at = pass_expires_at
        return quota

    @pytest.mark.anyio
    async def test_no_quota_record_raises(self, mock_db):
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        with pytest.raises(ValueError, match="QUOTA_EXCEEDED"):
            await check_and_consume_quota(mock_db, uuid.uuid4())

    @pytest.mark.anyio
    async def test_quota_type_none_raises(self, mock_db):
        quota = self._make_quota(quota_type="none", remaining=0)
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=quota)))
        with pytest.raises(ValueError, match="QUOTA_EXCEEDED"):
            await check_and_consume_quota(mock_db, uuid.uuid4())

    @pytest.mark.anyio
    async def test_remaining_zero_raises(self, mock_db):
        quota = self._make_quota(quota_type="single", remaining=0)
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=quota)))
        with pytest.raises(ValueError, match="QUOTA_EXCEEDED"):
            await check_and_consume_quota(mock_db, uuid.uuid4())

    @pytest.mark.anyio
    async def test_single_quota_decrements(self, mock_db):
        quota = self._make_quota(quota_type="single", remaining=3)
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=quota)))
        await check_and_consume_quota(mock_db, uuid.uuid4())
        assert quota.remaining == 2

    @pytest.mark.anyio
    async def test_unlimited_quota_not_decremented(self, mock_db):
        quota = self._make_quota(quota_type="pass_3month", remaining=-1)
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=quota)))
        await check_and_consume_quota(mock_db, uuid.uuid4())
        assert quota.remaining == -1  # 변경 없음

    @pytest.mark.anyio
    async def test_expired_pass_raises(self, mock_db):
        from datetime import datetime, timezone, timedelta
        past = datetime.now(timezone.utc) - timedelta(days=1)
        quota = self._make_quota(quota_type="pass_3month", remaining=-1, pass_expires_at=past)
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=quota)))
        with pytest.raises(ValueError, match="QUOTA_EXCEEDED"):
            await check_and_consume_quota(mock_db, uuid.uuid4())
