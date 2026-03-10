import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock, patch
from main import app
from app.core.config import settings

client = TestClient(app)

def test_read_main():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

@patch('app.routes.portal_routes.getattr')
def test_api_chat_no_message(mock_getattr):
    # Mock the getattr call to return our mock chat service
    mock_chat_service = Mock()
    mock_chat_service.process_portal_message = AsyncMock(return_value=({"error": "Message required"}, 400))
    mock_getattr.return_value = mock_chat_service

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

@patch('app.routes.portal_routes.portal_manager.send_to_admins', new_callable=AsyncMock)
@patch('app.routes.portal_routes.run_sync', new_callable=AsyncMock)
@patch('app.routes.portal_routes.getattr')
def test_portal_chat_god_mode_human_resolver(mock_getattr, mock_run_sync, mock_send_to_admins):
    mock_getattr.return_value = Mock()  # chat_service existence check

    async def fake_run_sync(func, *args, **kwargs):
        if getattr(func, '__name__', '') == 'get_setting':
            return "1"  # God Mode ON
        return None

    mock_run_sync.side_effect = fake_run_sync

    response = client.post("/api/portal/chat", data={"message": "Need help now", "user_id": "cust_test_1"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["god_mode"] is True
    assert payload["resolver"] == "human"
    assert "human resolver" in payload["answer"].lower()
