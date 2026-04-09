"""
test_app.py — Integration-style tests for the FastAPI backend.

Uses httpx's AsyncClient + pytest-asyncio so no real Azure calls are made
(core Azure calls are mocked via unittest.mock).
"""

import sys
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Make src/backend importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "backend"))

# Patch settings BEFORE importing the app so it doesn't call load_settings() with real env
os.environ.setdefault("AZURE_OPENAI_API_KEY", "test-key")
os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
os.environ.setdefault("AZURE_SEARCH_ENDPOINT", "https://test.search.windows.net")
os.environ.setdefault("AZURE_SEARCH_INDEX", "test-index")
os.environ.setdefault("AZURE_SEARCH_API_KEY", "test-search-key")

from httpx import AsyncClient, ASGITransport
from app import app


@pytest.mark.asyncio
async def test_health_endpoint():
    """GET /health should return status 200 and 'ok' status."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "version" in body


@pytest.mark.asyncio
async def test_chat_endpoint_success():
    """POST /chat should return 200 with answer and session_id."""
    fake_answer = "The capital of France is Paris."
    fake_docs = [
        {"content": "Paris is the capital.", "title": "France Facts", "source": "wiki", "score": 0.95}
    ]

    with patch("app.rag_pipeline", return_value=(fake_answer, fake_docs)) as mock_pipeline, \
         patch("app.get_session_history", return_value=[]):

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/chat",
                json={"query": "What is the capital of France?", "session_id": "test-session-1"},
            )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == fake_answer
    assert body["session_id"] == "test-session-1"
    assert isinstance(body["sources"], list)
    mock_pipeline.assert_called_once_with("test-session-1", "What is the capital of France?")


@pytest.mark.asyncio
async def test_chat_endpoint_generates_session_id():
    """POST /chat without session_id should generate one."""
    with patch("app.rag_pipeline", return_value=("Hello!", [])), \
         patch("app.get_session_history", return_value=[]):

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/chat", json={"query": "Hello"})

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"]   # must be a non-empty string
    assert len(body["session_id"]) == 36  # UUID4 format


@pytest.mark.asyncio
async def test_chat_endpoint_empty_query_rejected():
    """POST /chat with an empty query should be rejected (422)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/chat", json={"query": ""})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_delete_session():
    """DELETE /session/{id} should return 200 and a confirmation message."""
    with patch("app.clear_session_history") as mock_clear:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.delete("/session/my-session-42")

    assert response.status_code == 200
    assert "my-session-42" in response.json()["message"]
    mock_clear.assert_called_once_with("my-session-42")
