"""
utils.py — Core RAG utilities: embeddings, Azure Search, prompt building, memory.
"""

import logging
import time
from collections import deque
from functools import wraps
from typing import Any, Deque, Dict, List, Optional, Tuple

from openai import AzureOpenAI, APIError, APITimeoutError, RateLimitError
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from azure.core.credentials import AzureKeyCredential

from config import settings

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Azure OpenAI client (singleton) ───────────────────────────────────────────
_openai_client: Optional[AzureOpenAI] = None


def get_openai_client() -> AzureOpenAI:
    """Return (or lazily create) the Azure OpenAI client."""
    global _openai_client
    if _openai_client is None:
        _openai_client = AzureOpenAI(
            api_key=settings.azure_openai_api_key,
            azure_endpoint=settings.azure_openai_endpoint,
            api_version=settings.azure_openai_api_version,
        )
        logger.info("AzureOpenAI client initialised.")
    return _openai_client


# ── Azure Search client (singleton) ──────────────────────────────────────────
_search_client: Optional[SearchClient] = None


def get_search_client() -> SearchClient:
    """Return (or lazily create) the Azure AI Search client."""
    global _search_client
    if _search_client is None:
        _search_client = SearchClient(
            endpoint=settings.azure_search_endpoint,
            index_name=settings.azure_search_index,
            credential=AzureKeyCredential(settings.azure_search_api_key),
        )
        logger.info("Azure SearchClient initialised for index '%s'.", settings.azure_search_index)
    return _search_client


# ── Retry decorator ───────────────────────────────────────────────────────────
def retry(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """Exponential-backoff retry for Azure API calls."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            attempt = 0
            wait = delay
            while attempt < max_attempts:
                try:
                    return fn(*args, **kwargs)
                except (APIError, APITimeoutError, RateLimitError) as exc:
                    attempt += 1
                    if attempt >= max_attempts:
                        logger.error("'%s' failed after %d attempts: %s", fn.__name__, max_attempts, exc)
                        raise
                    logger.warning(
                        "'%s' attempt %d/%d failed (%s). Retrying in %.1fs…",
                        fn.__name__, attempt, max_attempts, exc, wait,
                    )
                    time.sleep(wait)
                    wait *= backoff
        return wrapper
    return decorator


# ── Embeddings ────────────────────────────────────────────────────────────────
@retry(max_attempts=3)
def get_embedding(text: str) -> List[float]:
    """
    Generate a vector embedding for *text* using Azure OpenAI.
    Returns a list of floats (1536-dimensional for ada-002).
    """
    client = get_openai_client()
    cleaned = text.replace("\n", " ").strip()
    response = client.embeddings.create(
        input=[cleaned],
        model=settings.azure_openai_embedding_deployment,
    )
    embedding = response.data[0].embedding
    logger.debug("Embedding generated (dim=%d) for text[:50]='%s'", len(embedding), cleaned[:50])
    return embedding


# ── Azure AI Search ───────────────────────────────────────────────────────────
@retry(max_attempts=3)
def search_documents(query_embedding: List[float], top_k: int = None) -> List[Dict[str, Any]]:
    """
    Perform vector similarity search against Azure AI Search.
    """
    top_k = top_k or settings.azure_search_top_k
    client = get_search_client()

    # ✅ Correct vector field
    vector_query = VectorizedQuery(
        vector=query_embedding,
        k_nearest_neighbors=top_k,
        fields="text_vector",   # ✅ FIXED
    )

    # ✅ Correct fields
    results = client.search(
        search_text=None,
        vector_queries=[vector_query],
        select=["chunk", "title"],   # ✅ FIXED
        top=top_k,
    )

    docs: List[Dict[str, Any]] = []

    for r in results:
        docs.append({
            "content": r.get("chunk", ""),   # ✅ FIXED
            "title": r.get("title", ""),
            "score": r.get("@search.score", 0.0),
        })

    logger.info("Azure Search returned %d documents.", len(docs))
    return docs

# ── Prompt builder ────────────────────────────────────────────────────────────
def build_system_prompt(docs: List[Dict[str, Any]]) -> str:
    """
    Construct a system message that injects retrieved context into the prompt.
    """
    if not docs:
        context_block = "No relevant documents were found."
    else:
        context_parts = []
        for i, doc in enumerate(docs, start=1):
            title = doc.get("title") or f"Document {i}"
            content = doc.get("content", "").strip()
            context_parts.append(f"[{i}] {title}\n{content}")
        context_block = "\n\n".join(context_parts)

    return (
        "You are a helpful AI assistant. Answer the user's question "
        "using ONLY the context provided below. "
        "If the context does not contain enough information, say so honestly. "
        "Be concise, accurate, and professional.\n\n"
        "=== RETRIEVED CONTEXT ===\n"
        f"{context_block}\n"
        "=========================\n"
    )


def build_messages(
    system_prompt: str,
    history: List[Dict[str, str]],
    user_query: str,
) -> List[Dict[str, str]]:
    """
    Assemble the full message list for the chat completion call.

    Format:
      [system] → [history turns] → [current user turn]
    """
    messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_query})
    return messages


# ── LLM chat completion ───────────────────────────────────────────────────────
@retry(max_attempts=3)
def chat_completion(messages: List[Dict[str, str]]) -> str:
    """
    Send a message list to the Azure OpenAI chat deployment and return the
    assistant's reply text.
    """
    client = get_openai_client()
    response = client.chat.completions.create(
        model=settings.azure_openai_chat_deployment,
        messages=messages,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
    )
    reply = response.choices[0].message.content or ""
    logger.info(
        "Chat completion done. tokens_used=%d",
        response.usage.total_tokens if response.usage else -1,
    )
    return reply.strip()


# ── In-memory session store ───────────────────────────────────────────────────
# Maps session_id → deque of {"role": ..., "content": ...} dicts
_session_store: Dict[str, Deque[Dict[str, str]]] = {}
MAX_HISTORY = 10   # keep last 10 turns (each turn = 1 user + 1 assistant msg)


def get_session_history(session_id: str) -> List[Dict[str, str]]:
    """Return the message history for *session_id* as a plain list."""
    return list(_session_store.get(session_id, deque()))


def update_session_history(session_id: str, user_msg: str, assistant_msg: str) -> None:
    """
    Append the latest user/assistant exchange to the session's deque.
    Automatically evicts oldest messages once MAX_HISTORY pairs are reached.
    """
    if session_id not in _session_store:
        _session_store[session_id] = deque(maxlen=MAX_HISTORY * 2)  # *2: user+assistant

    history = _session_store[session_id]
    history.append({"role": "user", "content": user_msg})
    history.append({"role": "assistant", "content": assistant_msg})
    logger.debug("Session '%s' history length: %d msgs.", session_id, len(history))


def clear_session_history(session_id: str) -> None:
    """Remove all stored history for *session_id*."""
    _session_store.pop(session_id, None)
    logger.info("Session '%s' cleared.", session_id)


# ── Full RAG pipeline ─────────────────────────────────────────────────────────
def rag_pipeline(session_id: str, user_query: str) -> Tuple[str, List[Dict[str, Any]]]:
    """
    End-to-end RAG pipeline:
      1. Embed user query
      2. Retrieve relevant documents from Azure Search
      3. Build prompt with context + history
      4. Call Azure OpenAI chat completion
      5. Persist exchange to session memory
      6. Return (answer, source_docs)
    """
    logger.info("RAG pipeline started | session='%s' | query='%s'", session_id, user_query[:80])

    # Step 1 – Embed
    query_embedding = get_embedding(user_query)

    # Step 2 – Retrieve
    docs = search_documents(query_embedding)

    # Step 3 – Build prompt
    system_prompt = build_system_prompt(docs)
    history = get_session_history(session_id)
    messages = build_messages(system_prompt, history, user_query)

    # Step 4 – LLM
    answer = chat_completion(messages)

    # Step 5 – Update memory
    update_session_history(session_id, user_query, answer)

    logger.info("RAG pipeline complete | session='%s'", session_id)
    return answer, docs
