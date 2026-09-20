"""Shared test fixtures. No test needs AWS or a real Gemini key."""
import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.services import gemini_service, s3_service


def _clear_caches():
    get_settings.cache_clear()
    gemini_service._client.cache_clear()
    s3_service.get_s3_client.cache_clear()


@pytest.fixture(autouse=True)
def local_settings(tmp_path, monkeypatch):
    """Every test: local storage in a temp folder, Gemini disabled unless a test mocks it."""
    monkeypatch.setenv("STORAGE_MODE", "local")
    monkeypatch.setenv("LOCAL_UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("RESULTS_DIR", str(tmp_path / "results"))
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("GOOGLE_API_KEY", "")
    _clear_caches()
    return tmp_path


@pytest.fixture
def client():
    from app.main import app
    with TestClient(app) as test_client:
        yield test_client
