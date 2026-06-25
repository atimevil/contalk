"""
FastAPI 엔드포인트 통합 테스트

테스트 범위:
    - GET  /health                    — 헬스체크
    - GET  /api/v1/health             — API 헬스체크
    - POST /api/v1/analysis/upload    — 파일 업로드 (인증 필요)
    - GET  /api/v1/analysis/{job_id}/status  — 분석 상태 조회
    - GET  /api/v1/analysis/{report_id}/result — 분석 결과 조회
    - GET  /api/v1/analysis/history   — 이력 조회

주의: dependency_overrides는 FastAPI 앱이 사용하는 것과 같은 함수 객체를 키로 써야 한다.
      sys.path에 backend/ 디렉토리가 등록되어 있으므로 'app.*' 로 직접 임포트한다.
"""
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from datetime import datetime, timezone

# conftest.py에서 sys.path 설정됨 (root + backend 추가)
# 'app.*' 임포트는 backend/ 디렉토리에서 해석됨
from app.core.dependencies import get_current_user
from app.core.database import get_db
from app.main import app


# ─── 공통 픽스처 ───────────────────────────────────────────────────────────────

@pytest.fixture
def mock_user():
    user = MagicMock()
    user.id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    user.email = "test@example.com"
    user.nickname = "테스트유저"
    user.terms_agreed = True
    user.privacy_agreed = True
    return user


@pytest.fixture
def mock_contract(mock_user):
    contract = MagicMock()
    contract.id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    contract.job_id = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    contract.report_id = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
    contract.user_id = mock_user.id
    contract.s3_key = "contracts/test/test.pdf"
    contract.contract_type = "jeonse"
    contract.status = "completed"
    contract.progress = 100
    contract.current_step = "clause"
    contract.completed_steps = ["upload", "ocr", "analyze", "clause"]
    contract.error_code = None
    contract.error_message = None
    contract.ocr_text = "계약서 전문"
    contract.created_at = datetime(2026, 5, 1, tzinfo=timezone.utc)
    contract.completed_at = datetime(2026, 5, 1, 0, 1, tzinfo=timezone.utc)
    contract.result = {
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
                "recommendation": "협의 필요",
            },
        ],
        "special_clauses": [],
        "disclaimer": "법률 조언 아님",
        "ocr_method": "plain_text",
        "ocr_confidence": 1.0,
    }
    return contract


@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer test-token-does-not-matter"}


# ─── dependency override 헬퍼 ─────────────────────────────────────────────────

def make_db_override():
    async def _override():
        db = AsyncMock()
        # 결과 엔드포인트는 무료 유저 판별을 위해
        #   user_quota = (await db.execute(...)).scalar_one_or_none()
        # 를 호출한다(커밋 46bace3, 무료 3개 제한). mock이 이를 반영하지 않으면
        # scalar_one_or_none() 이 코루틴을 반환해 .quota_type 접근에서 깨진다.
        # → execute 는 await 가능(AsyncMock)하게, 그 결과의 scalar_one_or_none 은
        #   동기로 None(=quota 없음, 무료 유저)을 반환하도록 구성한다.
        quota_result = MagicMock()
        quota_result.scalar_one_or_none = MagicMock(return_value=None)
        db.execute = AsyncMock(return_value=quota_result)
        yield db
    return _override


# ─── 헬스체크 ─────────────────────────────────────────────────────────────────

class TestHealthCheck:

    @pytest.mark.anyio
    async def test_health_returns_ok(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    @pytest.mark.anyio
    async def test_health_includes_version(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
        data = response.json()
        assert "version" in data

    @pytest.mark.anyio
    async def test_api_v1_health_returns_ok(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/health")
        assert response.status_code == 200


# ─── 인증 없는 요청 → 401 ──────────────────────────────────────────────────────

class TestAuthRequired:

    @pytest.mark.anyio
    async def test_upload_without_auth_returns_401(self):
        from io import BytesIO
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/analysis/upload",
                files={"file": ("test.pdf", BytesIO(b"pdf content"), "application/pdf")},
                data={"contract_type": "jeonse"},
            )
        assert response.status_code == 401

    @pytest.mark.anyio
    async def test_quota_without_auth_returns_401(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/user/quota")
        assert response.status_code == 401

    @pytest.mark.anyio
    async def test_history_without_auth_returns_401(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/analysis/history")
        assert response.status_code == 401


# ─── 업로드 엔드포인트 ────────────────────────────────────────────────────────

class TestUploadEndpoint:

    @pytest.mark.anyio
    async def test_upload_returns_202_with_job_id(self, mock_user, mock_contract):
        from io import BytesIO

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = make_db_override()

        try:
            with patch("app.services.contract_service.check_and_consume_quota", new_callable=AsyncMock):
                with patch("app.services.s3_service.upload_contract_file", new_callable=AsyncMock,
                           return_value="contracts/test/test.pdf"):
                    with patch("app.services.contract_service.create_contract",
                               new_callable=AsyncMock, return_value=mock_contract):
                        with patch("app.tasks.analysis.run_analysis_task") as mock_task:
                            mock_task.delay = MagicMock()
                            async with AsyncClient(
                                transport=ASGITransport(app=app), base_url="http://test"
                            ) as client:
                                response = await client.post(
                                    "/api/v1/analysis/upload",
                                    files={"file": ("contract.pdf", BytesIO(b"pdf bytes"), "application/pdf")},
                                    data={"contract_type": "jeonse"},
                                )
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 202
        data = response.json()["data"]  # success wrapper 언래핑
        assert "jobId" in data  # camelCase alias

    @pytest.mark.anyio
    async def test_upload_invalid_file_type_returns_400(self, mock_user):
        from io import BytesIO

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = make_db_override()

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v1/analysis/upload",
                    files={"file": ("contract.txt", BytesIO(b"text content"), "text/plain")},
                    data={"contract_type": "jeonse"},
                )
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error"]["code"] == "FILE_TYPE_INVALID"

    @pytest.mark.anyio
    async def test_upload_quota_exceeded_returns_402(self, mock_user):
        from io import BytesIO

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = make_db_override()

        try:
            with patch("app.services.s3_service.upload_contract_file", new_callable=AsyncMock,
                       return_value="contracts/test/test.pdf"):
                with patch("app.services.contract_service.check_and_consume_quota",
                           new_callable=AsyncMock, side_effect=ValueError("QUOTA_EXCEEDED")):
                    async with AsyncClient(
                        transport=ASGITransport(app=app), base_url="http://test"
                    ) as client:
                        response = await client.post(
                            "/api/v1/analysis/upload",
                            files={"file": ("contract.pdf", BytesIO(b"pdf bytes"), "application/pdf")},
                            data={"contract_type": "jeonse"},
                        )
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 402


# ─── 상태 조회 엔드포인트 ─────────────────────────────────────────────────────

class TestStatusEndpoint:

    @pytest.mark.anyio
    async def test_status_returns_contract_info(self, mock_user, mock_contract):
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = make_db_override()

        try:
            with patch(
                "app.services.contract_service.get_contract_by_job_id",
                new_callable=AsyncMock, return_value=mock_contract
            ):
                job_id = str(mock_contract.job_id)
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get(f"/api/v1/analysis/{job_id}/status")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()["data"]  # success wrapper 언래핑
        assert data["jobId"] == str(mock_contract.job_id)
        assert data["status"] == "completed"

    @pytest.mark.anyio
    async def test_status_invalid_uuid_returns_404(self, mock_user):
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = make_db_override()

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/api/v1/analysis/not-a-uuid/status")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 404

    @pytest.mark.anyio
    async def test_status_not_found_returns_404(self, mock_user):
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = make_db_override()

        try:
            with patch(
                "app.services.contract_service.get_contract_by_job_id",
                new_callable=AsyncMock, return_value=None
            ):
                job_id = str(uuid.uuid4())
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get(f"/api/v1/analysis/{job_id}/status")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 404

    @pytest.mark.anyio
    async def test_status_other_user_contract_returns_403(self, mock_user, mock_contract):
        # 다른 사용자 소유의 contract
        mock_contract.user_id = uuid.UUID("99999999-9999-9999-9999-999999999999")

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = make_db_override()

        try:
            with patch(
                "app.services.contract_service.get_contract_by_job_id",
                new_callable=AsyncMock, return_value=mock_contract
            ):
                job_id = str(mock_contract.job_id)
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get(f"/api/v1/analysis/{job_id}/status")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 403


# ─── 결과 조회 엔드포인트 ─────────────────────────────────────────────────────

class TestResultEndpoint:

    @pytest.mark.anyio
    async def test_result_returns_analysis_data(self, mock_user, mock_contract):
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = make_db_override()

        try:
            with patch(
                "app.services.contract_service.get_contract_by_report_id",
                new_callable=AsyncMock, return_value=mock_contract
            ):
                report_id = str(mock_contract.report_id)
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get(f"/api/v1/analysis/{report_id}/result")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()["data"]  # success wrapper 언래핑
        assert "reportId" in data     # camelCase alias
        assert "clauses" in data
        assert "summary" in data
        assert "riskScore" in data
        assert "riskLevel" in data

    @pytest.mark.anyio
    async def test_result_risk_level_is_valid(self, mock_user, mock_contract):
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = make_db_override()

        try:
            with patch(
                "app.services.contract_service.get_contract_by_report_id",
                new_callable=AsyncMock, return_value=mock_contract
            ):
                report_id = str(mock_contract.report_id)
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get(f"/api/v1/analysis/{report_id}/result")
        finally:
            app.dependency_overrides.clear()

        data = response.json()["data"]  # success wrapper 언래핑
        assert data["riskLevel"] in ("high", "medium", "caution", "safe")

    @pytest.mark.anyio
    async def test_result_not_found_returns_404(self, mock_user):
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = make_db_override()

        try:
            with patch(
                "app.services.contract_service.get_contract_by_report_id",
                new_callable=AsyncMock, return_value=None
            ):
                report_id = str(uuid.uuid4())
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get(f"/api/v1/analysis/{report_id}/result")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 404

    @pytest.mark.anyio
    async def test_result_other_user_returns_403(self, mock_user, mock_contract):
        mock_contract.user_id = uuid.UUID("99999999-9999-9999-9999-999999999999")

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = make_db_override()

        try:
            with patch(
                "app.services.contract_service.get_contract_by_report_id",
                new_callable=AsyncMock, return_value=mock_contract
            ):
                report_id = str(mock_contract.report_id)
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get(f"/api/v1/analysis/{report_id}/result")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 403
