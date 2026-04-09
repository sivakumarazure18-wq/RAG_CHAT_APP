"""
app.py — FastAPI application entry point.

Endpoints:
  POST   /chat             — RAG chat (evaltools compatible)
  GET    /health           — Health check
  DELETE /session/{id}     — Clear session memory
"""

import logging
import uuid
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from config import settings
from utils import (
    clear_session_history,
    get_session_history,
    rag_pipeline,
)

# ── Logger ────────────────────────────────────────────────────────────────────
logger = logging.getLogger(__name__)

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Azure RAG Chat API",
    description="Production-ready RAG backend using Azure OpenAI + Azure AI Search.",
    version="1.1.0",
    debug=settings.debug,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # 🔒 Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Schemas ───────────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    query: Optional[str] = None
    question: Optional[str] = None   # 👈 for evaltools
    session_id: Optional[str] = None


class SourceDoc(BaseModel):
    title: str
    content: str
    score: float


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    sources: List[SourceDoc]
    history_length: int

    # ✅ Evaltools fields
    message: Dict[str, Any]
    context: Dict[str, Any]


# ── Global Exception Handler ──────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s %s", request.method, request.url)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Please try again."},
    )


# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/health", tags=["Ops"])
async def health_check() -> Dict[str, Any]:
    return {
        "status": "ok",
        "version": "1.1.0",
        "search_index": settings.azure_search_index,
        "chat_deployment": settings.azure_openai_chat_deployment,
    }


@app.post("/chat", tags=["RAG"])
async def chat(payload: ChatRequest) -> Dict[str, Any]:
    # ✅ Accept both query and question
    user_query = payload.query or payload.question

    if not user_query:
        raise HTTPException(status_code=400, detail="Either 'query' or 'question' is required.")

    session_id = payload.session_id or str(uuid.uuid4())

    logger.info(
        "POST /chat | session='%s' | query='%s'",
        session_id,
        user_query[:80],
    )

    try:
        answer, docs = rag_pipeline(session_id, user_query)

    except EnvironmentError as exc:
        logger.error("Configuration error: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc))

    except Exception as exc:
        logger.exception("RAG pipeline failed | session='%s'", session_id)
        raise HTTPException(status_code=500, detail="RAG processing failed.") from exc

    # ── Build response ────────────────────────────────────────────────────────
    history = get_session_history(session_id)

    sources = [
        {
            "title": d.get("title") or "Untitled",
            "content": d.get("content", "")[:500],
            "score": round(float(d.get("score", 0.0)), 4),
        }
        for d in docs
    ]

    # ✅ Extract text chunks for evaltools
    retrieved_chunks = [
        d.get("content", "")
        for d in docs
        if d.get("content")
    ]

    # ✅ FINAL RESPONSE (BOTH formats)
    return {
        # ── Your original response (unchanged)
        "session_id": session_id,
        "answer": answer,
        "sources": sources,
        "history_length": len(history),

        # ── Evaltools REQUIRED format
        "message": {
            "content": answer
        },
        "context": {
            "data_points": {
                "text": retrieved_chunks
            }
        }
    }


@app.delete("/session/{session_id}", tags=["Session"])
async def delete_session(session_id: str) -> Dict[str, str]:
    clear_session_history(session_id)
    logger.info("Session '%s' cleared.", session_id)
    return {"message": f"Session '{session_id}' cleared."}


# ── Entrypoint ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host=settings.api_bind_host,
        port=settings.api_port,
        reload=settings.api_reload,
        log_level=settings.log_level.lower(),
    )