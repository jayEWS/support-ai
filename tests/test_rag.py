import pytest
from httpx import ASGITransport, AsyncClient
from main import app
from unittest.mock import AsyncMock, patch, MagicMock, Mock

# Set up mock services on app.state
mock_rag = AsyncMock()
mock_rag.ask.return_value = "Mocked AI Response"
mock_rag.vector_store = True

mock_llm = Mock()
mock_chat_service = Mock()
mock_chat_service.process_portal_message = AsyncMock(return_value=({"answer": "Mocked AI Response", "confidence": 0.8}, 200))

app.state.rag_service = mock_rag
app.state.llm_service = mock_llm
app.state.chat_service = mock_chat_service

@pytest.mark.anyio
async def test_chat_directly_with_rag():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/chat", data={"message": "hello", "user_id": "test_user"})

    assert response.status_code == 200
    assert response.json()["answer"] == "Mocked AI Response"

@pytest.mark.anyio
async def test_health_check_vector_store():
    # Mock the AI service for health endpoint
    mock_llm = Mock()
    with patch.object(app.state, 'llm_service', mock_llm):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/health")

        # Health endpoint returns 503 if Redis is not available (common in test env)
        # but should still return valid JSON with service status
        assert response.status_code in [200, 503]
        data = response.json()
        assert "services" in data
        assert data["services"]["database"] == "up"
        assert data["services"]["ai"] == "configured"
