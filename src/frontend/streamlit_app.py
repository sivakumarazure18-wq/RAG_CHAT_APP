"""
streamlit.py — Premium Light UI RAG Chat Frontend

Run:
    streamlit run streamlit.py
"""

import os
import uuid
import time
import requests
import streamlit as st
from dotenv import load_dotenv

# ── Load ENV ──────────────────────────────────────────────────────────────────
_env_path = os.path.join(os.path.dirname(__file__), "..", "..", "config", ".env")
load_dotenv(dotenv_path=_env_path)

API_HOST = os.getenv("API_ADVERTISED_HOST", "localhost")
API_PORT = os.getenv("API_PORT", "50505")
API_BASE = f"http://{API_HOST}:{API_PORT}"

CHAT_URL = f"{API_BASE}/chat"
HEALTH_URL = f"{API_BASE}/health"
DELETE_SESSION_URL = f"{API_BASE}/session"

# ── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="RAG Chat",
    page_icon="💬",
    layout="centered",
)

# ── PREMIUM LIGHT THEME ───────────────────────────────────────────────────────
st.markdown("""
<style>
/* Global */
body, .stApp {
    background-color: #f9fafb;
    font-family: -apple-system, BlinkMacSystemFont, sans-serif;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background: #ffffff;
    border-right: 1px solid #e5e7eb;
}

/* Title */
.title {
    font-size: 1.8rem;
    font-weight: 600;
    color: #111827;
}
.subtitle {
    font-size: 0.85rem;
    color: #6b7280;
    margin-bottom: 1rem;
}

/* Chat bubbles */
.msg-user {
    display: flex;
    justify-content: flex-end;
    margin: 10px 0;
}
.msg-user .bubble {
    background: #2563eb;
    color: white;
    padding: 10px 14px;
    border-radius: 16px 16px 4px 16px;
    max-width: 70%;
}

.msg-ai {
    display: flex;
    margin: 10px 0;
}
.msg-ai .avatar {
    margin-right: 8px;
}
.msg-ai .bubble {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    padding: 10px 14px;
    border-radius: 4px 16px 16px 16px;
    max-width: 75%;
}

/* Sources */
.source-chip {
    font-size: 0.7rem;
    background: #eef2ff;
    padding: 3px 7px;
    border-radius: 8px;
    margin-right: 5px;
}

/* Input */
.stTextInput input {
    border-radius: 12px !important;
    border: 1px solid #d1d5db !important;
    padding: 10px !important;
}

/* Buttons */
.stButton button {
    background: #2563eb;
    color: white;
    border-radius: 10px;
}
</style>
""", unsafe_allow_html=True)

# ── Session State ─────────────────────────────────────────────────────────────
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []

if "debug" not in st.session_state:
    st.session_state.debug = False

# ── Helpers ───────────────────────────────────────────────────────────────────
def check_backend():
    try:
        return requests.get(HEALTH_URL, timeout=3).status_code == 200
    except:
        return False

def call_chat_api(query):
    response = requests.post(
        CHAT_URL,
        json={"query": query, "session_id": st.session_state.session_id},
        timeout=60
    )
    response.raise_for_status()
    return response.json()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 💬 RAG Chat")

    if check_backend():
        st.success("Backend connected")
    else:
        st.error("Backend not reachable")

    st.markdown(f"**Session:** `{st.session_state.session_id[:8]}`")
    st.markdown(f"Messages: {len(st.session_state.messages)}")

    if st.button("🗑 Clear Chat"):
        try:
            requests.delete(f"{DELETE_SESSION_URL}/{st.session_state.session_id}")
        except:
            pass
        st.session_state.messages = []
        st.session_state.session_id = str(uuid.uuid4())
        st.rerun()

    st.session_state.debug = st.toggle("Show sources", value=st.session_state.debug)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown('<div class="title">💬 RAG Chat</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Azure OpenAI + AI Search + FastAPI</div>', unsafe_allow_html=True)

# ── Chat Display ──────────────────────────────────────────────────────────────
for msg in st.session_state.messages:
    if msg["role"] == "user":
        st.markdown(
            f'<div class="msg-user"><div class="bubble">{msg["content"]}</div></div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="msg-ai"><div class="avatar">🤖</div><div class="bubble">{msg["content"]}</div></div>',
            unsafe_allow_html=True,
        )

        # Sources
        if st.session_state.debug and msg.get("sources"):
            with st.expander("Sources"):
                for s in msg["sources"]:
                    st.write(f"**{s['title']}** ({s['score']})")

        # Copy block
        st.code(msg["content"], language=None)

# ── Input Row ─────────────────────────────────────────────────────────────────
st.markdown("---")
col1, col2 = st.columns([6, 1])

with col1:
    user_input = st.text_input(
        "Message",
        placeholder="Ask anything about your documents...",
        label_visibility="collapsed",
    )

with col2:
    send = st.button("Send", use_container_width=True)

# ── Send Logic ────────────────────────────────────────────────────────────────
if send and user_input.strip():
    query = user_input.strip()

    st.session_state.messages.append({"role": "user", "content": query})

    if not check_backend():
        st.session_state.messages.append({
            "role": "assistant",
            "content": "⚠️ Backend not reachable.",
            "sources": []
        })
        st.rerun()

    with st.spinner("Thinking..."):
        try:
            res = call_chat_api(query)
            answer = res.get("answer", "No answer")
            sources = res.get("sources", [])
        except Exception as e:
            answer = f"⚠️ Error: {e}"
            sources = []

    # ── Typing Effect ────────────────────────────────────────────────────────
    placeholder = st.empty()
    typed = ""

    for word in answer.split():
        typed += word + " "
        placeholder.markdown(
            f'<div class="msg-ai"><div class="avatar">🤖</div><div class="bubble">{typed}</div></div>',
            unsafe_allow_html=True,
        )
        time.sleep(0.015)

    st.session_state.messages.append({
        "role": "assistant",
        "content": answer,
        "sources": sources
    })

    st.rerun()