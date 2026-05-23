"""
S3 서비스 로컬 폴백 테스트

테스트 범위:
    - _is_local_mode: 환경변수로 모드 판별
    - upload_contract_file: 로컬/S3 분기
    - get_presigned_url: 로컬 모드 None 반환
    - get_file_content: 로컬 읽기 및 파일 없음 에러
    - _local_upload / _local_read 경로 구성
"""
import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# sys.path는 conftest.py에서 설정
from backend.app.services.s3_service import (
    _is_local_mode,
    _get_local_upload_dir,
    _local_upload,
    _local_read,
    upload_contract_file,
    get_presigned_url,
    get_file_content,
)


# ─── _is_local_mode ───────────────────────────────────────────────────────────

class TestIsLocalMode:

    def test_local_mode_when_no_key(self):
        with patch.dict(os.environ, {"AWS_ACCESS_KEY_ID": ""}):
            assert _is_local_mode() is True

    def test_local_mode_when_key_whitespace(self):
        with patch.dict(os.environ, {"AWS_ACCESS_KEY_ID": "   "}):
            assert _is_local_mode() is True

    def test_not_local_mode_when_key_set(self):
        with patch.dict(os.environ, {"AWS_ACCESS_KEY_ID": "AKIAIOSFODNN7EXAMPLE"}):
            assert _is_local_mode() is False

    def test_local_mode_when_key_env_absent(self):
        env = {k: v for k, v in os.environ.items() if k != "AWS_ACCESS_KEY_ID"}
        with patch.dict(os.environ, env, clear=True):
            assert _is_local_mode() is True


# ─── _get_local_upload_dir ────────────────────────────────────────────────────

class TestGetLocalUploadDir:

    def test_creates_directory(self, tmp_path):
        custom_dir = str(tmp_path / "contalktok_test")
        with patch.dict(os.environ, {"LOCAL_UPLOAD_DIR": custom_dir}):
            result = _get_local_upload_dir()
            assert result == Path(custom_dir)
            assert result.exists()

    def test_returns_path_object(self, tmp_path):
        with patch.dict(os.environ, {"LOCAL_UPLOAD_DIR": str(tmp_path)}):
            result = _get_local_upload_dir()
            assert isinstance(result, Path)


# ─── _local_upload / _local_read ──────────────────────────────────────────────

class TestLocalUploadRead:

    def test_local_upload_creates_file(self, tmp_path):
        content = b"test contract content"
        with patch.dict(os.environ, {"LOCAL_UPLOAD_DIR": str(tmp_path)}):
            path_str = _local_upload(content, "user-123", "test.pdf")
            assert Path(path_str).exists()
            assert Path(path_str).read_bytes() == content

    def test_local_upload_returns_absolute_path(self, tmp_path):
        with patch.dict(os.environ, {"LOCAL_UPLOAD_DIR": str(tmp_path)}):
            path_str = _local_upload(b"data", "user-123", "file.pdf")
            assert Path(path_str).is_absolute()

    def test_local_upload_uses_user_subdirectory(self, tmp_path):
        with patch.dict(os.environ, {"LOCAL_UPLOAD_DIR": str(tmp_path)}):
            path_str = _local_upload(b"data", "user-abc", "file.pdf")
            assert "user-abc" in path_str

    def test_local_read_returns_bytes(self, tmp_path):
        content = b"hello world"
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(content)
        result = _local_read(str(test_file))
        assert result == content

    def test_local_read_raises_file_not_found(self, tmp_path):
        missing_path = str(tmp_path / "nonexistent.pdf")
        with pytest.raises(FileNotFoundError):
            _local_read(missing_path)


# ─── upload_contract_file (비동기) ────────────────────────────────────────────

class TestUploadContractFile:

    @pytest.mark.anyio
    async def test_local_mode_upload_returns_path(self, tmp_path):
        with patch.dict(os.environ, {
            "AWS_ACCESS_KEY_ID": "",
            "LOCAL_UPLOAD_DIR": str(tmp_path),
        }):
            result = await upload_contract_file(
                file_content=b"contract pdf bytes",
                original_filename="contract.pdf",
                user_id="user-001",
            )
            assert result.endswith(".pdf")
            assert Path(result).exists()

    @pytest.mark.anyio
    async def test_local_mode_pdf_extension_preserved(self, tmp_path):
        with patch.dict(os.environ, {
            "AWS_ACCESS_KEY_ID": "",
            "LOCAL_UPLOAD_DIR": str(tmp_path),
        }):
            result = await upload_contract_file(
                file_content=b"bytes",
                original_filename="lease.pdf",
                user_id="user-001",
            )
            assert result.endswith(".pdf")

    @pytest.mark.anyio
    async def test_local_mode_png_extension_preserved(self, tmp_path):
        with patch.dict(os.environ, {
            "AWS_ACCESS_KEY_ID": "",
            "LOCAL_UPLOAD_DIR": str(tmp_path),
        }):
            result = await upload_contract_file(
                file_content=b"bytes",
                original_filename="contract_photo.png",
                user_id="user-001",
            )
            assert result.endswith(".png")

    @pytest.mark.anyio
    async def test_s3_mode_calls_s3_upload(self):
        with patch.dict(os.environ, {"AWS_ACCESS_KEY_ID": "AKIAIOSFODNN7EXAMPLE"}):
            with patch("backend.app.services.s3_service._s3_upload") as mock_s3:
                mock_s3.return_value = "contracts/user-001/test.pdf"
                result = await upload_contract_file(
                    file_content=b"bytes",
                    original_filename="test.pdf",
                    user_id="user-001",
                )
                mock_s3.assert_called_once()
                assert result == "contracts/user-001/test.pdf"


# ─── get_presigned_url ────────────────────────────────────────────────────────

class TestGetPresignedUrl:

    def test_local_mode_returns_none(self):
        with patch.dict(os.environ, {"AWS_ACCESS_KEY_ID": ""}):
            result = get_presigned_url("contracts/user/test.pdf")
            assert result is None

    def test_s3_mode_returns_url(self):
        with patch.dict(os.environ, {"AWS_ACCESS_KEY_ID": "AKIAIOSFODNN7EXAMPLE"}):
            mock_client = MagicMock()
            mock_client.generate_presigned_url.return_value = "https://s3.example.com/signed-url"
            with patch("backend.app.services.s3_service._get_client", return_value=mock_client):
                result = get_presigned_url("contracts/user/test.pdf")
                assert result == "https://s3.example.com/signed-url"


# ─── get_file_content ─────────────────────────────────────────────────────────

class TestGetFileContent:

    def test_local_mode_reads_existing_file(self, tmp_path):
        content = b"local file content"
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(content)
        with patch.dict(os.environ, {"AWS_ACCESS_KEY_ID": ""}):
            result = get_file_content(str(test_file))
            assert result == content

    def test_local_mode_raises_file_not_found(self, tmp_path):
        missing_path = str(tmp_path / "missing.pdf")
        with patch.dict(os.environ, {"AWS_ACCESS_KEY_ID": ""}):
            with pytest.raises(FileNotFoundError):
                get_file_content(missing_path)

    def test_s3_mode_calls_s3_download(self):
        with patch.dict(os.environ, {"AWS_ACCESS_KEY_ID": "AKIAIOSFODNN7EXAMPLE"}):
            with patch("backend.app.services.s3_service._s3_download") as mock_dl:
                mock_dl.return_value = b"s3 file content"
                result = get_file_content("contracts/user/test.pdf")
                mock_dl.assert_called_once_with("contracts/user/test.pdf")
                assert result == b"s3 file content"
