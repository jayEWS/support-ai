import pytest
from httpx import ASGITransport, AsyncClient
from main import app
from unittest.mock import AsyncMock, patch, MagicMock

@pytest.fixture
def mock_db():
    with patch("main.db_manager") as mock:
        # Mock save_message to avoid DB errors
        mock.save_message = MagicMock()
        mock.get_agent = MagicMock(return_value=None)
        yield mock

@pytest.mark.anyio
async def test_chat_directly_with_rag(mock_db):
    # Mock rag_engine.ask
    mock_rag = AsyncMock()
    mock_rag.ask.return_value = "Mocked AI Response"
    
    # Manually set state since Lifespan might not be triggered correctly in this test setup
    app.state.rag_engine = mock_rag
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/chat", data={"message": "hello", "user_id": "test_user"})
            
    assert response.status_code == 200
    assert response.json()["answer"] == "Mocked AI Response"

@pytest.mark.anyio
async def test_health_check_vector_store():
    mock_rag = AsyncMock()
    mock_rag.vector_store = True
    
    app.state.rag_engine = mock_rag
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health")
            
    assert response.status_code == 200
    assert response.json()["vector_store_ready"] is True
