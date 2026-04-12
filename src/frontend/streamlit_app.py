import os
import uuid
import time
import requests
import streamlit as st
from dotenv import load_dotenv

# -- Load ENV --
_env_path = os.path.join(os.path.dirname(__file__), "..", "..", "config", ".env")
load_dotenv(dotenv_path=_env_path)

API_HOST = os.getenv("API_ADVERTISED_HOST", "localhost")
API_PORT = os.getenv("API_PORT", "50505")
API_BASE = f"http://{API_HOST}:{API_PORT}"

CHAT_URL = f"{API_BASE}/chat"
HEALTH_URL = f"{API_BASE}/health"
DELETE_SESSION_URL = f"{API_BASE}/session"

# -- Page Config --
st.set_page_config(
    page_title="RAG Chat Assistant",
    page_icon="🤖",
    layout="wide", # Wider layout feels more modern
)

# -- Premium Custom Styling --
st.markdown("""
    <style>
    /* Remove default padding */
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    
    /* Custom Sidebar Gradient */
    [data-testid="stSidebar"] {
        background-image: linear-gradient(#ffffff, #f1f5f9);
        border-right: 1px solid #e2e8f0;
    }

    /* Clean Button Styling */
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        border: 1px solid #e2e8f0;
        background-color: white;
        transition: all 0.3s;
    }
    .stButton>button:hover {
        border-color: #2563eb;
        color: #2563eb;
        background-color: #eff6ff;
    }

    /* Status Indicator */
    .status-dot {
        height: 10px; width: 10px;
        border-radius: 50%;
        display: inline-block;
        margin-right: 5px;
    }
    </style>
""", unsafe_allow_html=True)

# -- Session State Management --
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []
if "show_sources" not in st.session_state:
    st.session_state.show_sources = True

# -- Helper Functions --
def check_backend():
    try:
        return requests.get(HEALTH_URL, timeout=2).status_code == 200
    except:
        return False

def clear_session():
    try:
        requests.delete(f"{DELETE_SESSION_URL}/{st.session_state.session_id}")
    except:
        pass
    st.session_state.messages = []
    st.session_state.session_id = str(uuid.uuid4())

# -- Sidebar UI --
with st.sidebar:
    st.title("⚙️ Settings")
    
    # Connection Status
    is_online = check_backend()
    status_color = "#10b981" if is_online else "#ef4444"
    status_text = "Backend Online" if is_online else "Backend Offline"
    st.markdown(f'<p><span class="status-dot" style="background-color: {status_color};"></span>{status_text}</p>', unsafe_allow_html=True)
    
    st.divider()
    
    st.session_state.show_sources = st.toggle("Show citations", value=True)
    
    st.info(f"**Session ID:** \n`{st.session_state.session_id[:13]}...`")
    
    if st.button("🗑️ Reset Conversation"):
        clear_session()
        st.rerun()

# -- Main Chat Interface --
st.title("💬 RAG Chat Assistant")
st.caption("RAG | Azure OpenAI | FastAPI Backend")

# Display Chat History
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        
        # Display sources if they exist and toggle is on
        if st.session_state.show_sources and message.get("sources"):
            with st.expander("View Reference Sources"):
                for idx, source in enumerate(message["sources"]):
                    st.markdown(f"**{idx+1}. {source.get('title', 'Unknown Source')}**")
                    st.caption(f"Relevance Score: {source.get('score', 'N/A')}")

# Chat Input
if prompt := st.chat_input("Ask a question about your documents..."):
    
    # 1. Add User Message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 2. Call API & Handle Response
    with st.chat_message("assistant"):
        if not is_online:
            error_msg = "I'm sorry, I cannot connect to the knowledge base right now."
            st.error(error_msg)
            st.session_state.messages.append({"role": "assistant", "content": error_msg})
        else:
            response_placeholder = st.empty()
            full_response = ""
            
            with st.spinner("Searching knowledge base..."):
                try:
                    res = requests.post(
                        CHAT_URL,
                        json={"query": prompt, "session_id": st.session_state.session_id},
                        timeout=60
                    ).json()
                    
                    answer = res.get("answer", "No response from AI.")
                    sources = res.get("sources", [])
                    
                    # Simulated Typing Effect
                    for chunk in answer.split(" "):
                        full_response += chunk + " "
                        time.sleep(0.02)
                        response_placeholder.markdown(full_response + "▌")
                    
                    response_placeholder.markdown(full_response)

                    # Add Sources to the UI after typing
                    if st.session_state.show_sources and sources:
                        with st.expander("View Reference Sources"):
                            for idx, s in enumerate(sources):
                                st.markdown(f"**{idx+1}. {s.get('title', 'Source')}**")
                    
                    # Save to History
                    st.session_state.messages.append({
                        "role": "assistant", 
                        "content": full_response,
                        "sources": sources
                    })
                    
                except Exception as e:
                    st.error(f"Error: {str(e)}")
