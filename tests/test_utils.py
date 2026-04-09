"""
test_utils.py — Unit tests for RAG utility functions in utils.py.

All external Azure calls are mocked — no real credentials needed.
"""

import sys
import os
import pytest
from unittest.mock import MagicMock, patch

# Make src/backend importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "backend"))

# Provide minimal env so config.py / utils.py can import
os.environ.setdefault("AZURE_OPENAI_API_KEY", "test-key")
os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
os.environ.setdefault("AZURE_SEARCH_ENDPOINT", "https://test.search.windows.net")
os.environ.setdefault("AZURE_SEARCH_INDEX", "test-index")
os.environ.setdefault("AZURE_SEARCH_API_KEY", "test-search-key")

import utils


# ── Session memory ────────────────────────────────────────────────────────────
class TestSessionMemory:
    def setup_method(self):
        """Isolate each test by using a unique session ID."""
        self.sid = "test-session-memory"
        utils.clear_session_history(self.sid)

    def test_empty_session_returns_empty_list(self):
        assert utils.get_session_history(self.sid) == []

    def test_update_and_retrieve_history(self):
        utils.update_session_history(self.sid, "Hello", "Hi there!")
        history = utils.get_session_history(self.sid)
        assert len(history) == 2
        assert history[0] == {"role": "user", "content": "Hello"}
        assert history[1] == {"role": "assistant", "content": "Hi there!"}

    def test_history_max_10_pairs(self):
        """Deque must never exceed MAX_HISTORY * 2 messages."""
        for i in range(15):  # 15 pairs → 30 msgs, should cap at 20
            utils.update_session_history(self.sid, f"Q{i}", f"A{i}")
        history = utils.get_session_history(self.sid)
        assert len(history) <= utils.MAX_HISTORY * 2

    def test_clear_session_history(self):
        utils.update_session_history(self.sid, "Test", "Response")
        utils.clear_session_history(self.sid)
        assert utils.get_session_history(self.sid) == []


# ── Prompt builder ────────────────────────────────────────────────────────────
class TestBuildSystemPrompt:
    def test_no_docs_returns_fallback(self):
        prompt = utils.build_system_prompt([])
        assert "No relevant documents" in prompt

    def test_docs_appear_in_prompt(self):
        docs = [{"content": "Paris is the capital of France.", "title": "France", "source": "wiki"}]
        prompt = utils.build_system_prompt(docs)
        assert "Paris is the capital of France." in prompt
        assert "France" in prompt

    def test_multiple_docs_numbered(self):
        docs = [
            {"content": "Doc A content.", "title": "A", "source": ""},
            {"content": "Doc B content.", "title": "B", "source": ""},
        ]
        prompt = utils.build_system_prompt(docs)
        assert "[1]" in prompt
        assert "[2]" in prompt


class TestBuildMessages:
    def test_structure(self):
        system = "You are helpful."
        history = [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello!"},
        ]
        messages = utils.build_messages(system, history, "How are you?")
        assert messages[0] == {"role": "system", "content": system}
        assert messages[1] == {"role": "user", "content": "Hi"}
        assert messages[-1] == {"role": "user", "content": "How are you?"}
        assert len(messages) == 4

    def test_empty_history(self):
        messages = utils.build_messages("sys", [], "question?")
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"


# ── Embedding (mocked) ────────────────────────────────────────────────────────
class TestGetEmbedding:
    def test_returns_list_of_floats(self):
        fake_vec = [0.1, 0.2, 0.3]
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=fake_vec)]

        with patch("utils.get_openai_client") as mock_client:
            mock_client.return_value.embeddings.create.return_value = mock_response
            result = utils.get_embedding("test text")

        assert result == fake_vec

    def test_newlines_stripped(self):
        """Text with newlines should be cleaned before embedding."""
        fake_vec = [0.5]
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=fake_vec)]

        with patch("utils.get_openai_client") as mock_client:
            instance = mock_client.return_value
            instance.embeddings.create.return_value = mock_response
            utils.get_embedding("line1\nline2\nline3")
            called_input = instance.embeddings.create.call_args[1]["input"]
            assert "\n" not in called_input[0]


# ── RAG pipeline (integration mock) ──────────────────────────────────────────
class TestRagPipeline:
    def test_pipeline_returns_answer_and_docs(self):
        session = "rag-pipeline-test"
        utils.clear_session_history(session)

        fake_embedding = [0.0] * 1536
        fake_docs = [{"content": "Azure is a cloud.", "title": "Azure", "source": "ms", "score": 0.9}]
        fake_answer = "Azure is Microsoft's cloud platform."

        with patch("utils.get_embedding", return_value=fake_embedding), \
             patch("utils.search_documents", return_value=fake_docs), \
             patch("utils.chat_completion", return_value=fake_answer):

            answer, docs = utils.rag_pipeline(session, "What is Azure?")

        assert answer == fake_answer
        assert docs == fake_docs

        # Memory should be updated
        history = utils.get_session_history(session)
        assert len(history) == 2
        assert history[0]["content"] == "What is Azure?"
        assert history[1]["content"] == fake_answer
