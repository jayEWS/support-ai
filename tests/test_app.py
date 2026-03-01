import pytest
from fastapi.testclient import TestClient
from main import app
from app.core.config import settings

client = TestClient(app)

def test_read_main():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

def test_api_chat_no_message():
    response = client.post("/api/chat", json={})
    assert response.status_code == 400
    # The API accepts either a message or a file; current API returns this message
    assert response.json() == {"error": "Message required"}

def test_upload_knowledge_no_api_key():
    # Attempt upload without API key
    files = {'file': ('test.txt', b'hello world')}
    response = client.post("/api/knowledge/upload", files=files)
    assert response.status_code == 401

def test_config_loading():
    assert settings.API_SECRET_KEY is not None
    # MODEL_NAME may be overridden by environment; ensure it's set to a non-empty string
    assert isinstance(settings.MODEL_NAME, str) and len(settings.MODEL_NAME) > 0
