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
