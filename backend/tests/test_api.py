import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings

client = TestClient(app)

def test_root():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "version" in data
    assert data["docs_url"] == "/docs"

def test_health():
    response = client.get(f"{settings.API_PREFIX}/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"

def test_list_languages():
    response = client.get(f"{settings.API_PREFIX}/languages")
    assert response.status_code == 200
    langs = response.json()
    codes = [l["code"] for l in langs]
    assert "hi" in codes
    assert "te" in codes

def test_list_voices():
    response = client.get(f"{settings.API_PREFIX}/voices?language=te")
    assert response.status_code == 200
    voices = response.json()
    assert len(voices) >= 2
    voice_ids = [v["voice_id"] for v in voices]
    assert "te-IN-MohanNeural" in voice_ids

def test_get_nonexistent_job():
    response = client.get(f"{settings.API_PREFIX}/jobs/nonexistent123")
    assert response.status_code == 404

def test_delete_job():
    # Non-existent job
    res_404 = client.delete(f"{settings.API_PREFIX}/jobs/nonexistent_del_job")
    assert res_404.status_code == 404

    # Existing job
    from pathlib import Path
    from app.storage.job_store import job_store
    from app.models.schemas import JobSettings

    job_store.create_job(
        job_id="test_delete_id_999",
        original_filename="sample.mp4",
        original_video_path=Path("sample.mp4"),
        job_settings=JobSettings(source_language="hi", target_language="te"),
    )
    assert job_store.get_job("test_delete_id_999") is not None

    res_del = client.delete(f"{settings.API_PREFIX}/jobs/test_delete_id_999")
    assert res_del.status_code == 200
    assert "deleted successfully" in res_del.json()["message"]
    assert job_store.get_job("test_delete_id_999") is None

