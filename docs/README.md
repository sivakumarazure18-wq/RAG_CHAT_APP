# 🔷 Azure RAG Chat

A production-ready **Retrieval-Augmented Generation (RAG)** chat application built with:

| Layer | Technology |
|---|---|
| Backend | FastAPI + Uvicorn |
| Frontend | Streamlit |
| Vector Store | Azure AI Search |
| LLM + Embeddings | Azure OpenAI (GPT-4 / ada-002) |
| Memory | In-memory session store (deque, last 10 turns) |
| DevOps | Docker + docker-compose + PowerShell / .bat scripts |

---

## 📁 Project Structure

```
Rag_project/
├── src/
│   ├── backend/
│   │   ├── app.py          # FastAPI app, routes
│   │   ├── utils.py        # RAG pipeline, embeddings, search, memory
│   │   └── config.py       # .env loader, Settings dataclass
│   └── frontend/
│       └── streamlit_app.py
├── docs/
│   └── README.md
├── devops/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── start.bat
│   └── start.ps1
├── config/
│   ├── .env                # ← Fill in your secrets here
│   └── .env.example
├── tests/
│   ├── test_app.py
│   └── test_utils.py
└── requirements.txt
```

---

## ⚙️ Setup

### 1 — Clone & configure

```bash
git clone <repo-url>
cd Rag_project
cp config/.env.example config/.env
# Edit config/.env with your Azure credentials
```

### 2 — Fill in `config/.env`

```dotenv
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com/
AZURE_SEARCH_ENDPOINT=https://<search>.search.windows.net
AZURE_SEARCH_INDEX=<your-index>
AZURE_SEARCH_API_KEY=...
```

> **Azure Search index requirement**: Your index must have a field named `content_vector` (type `Collection(Edm.Single)`, dimensions=1536) for vector search. Also include `content`, `title`, and `source` string fields.

---

## 🚀 Running the app

### Option A — Docker Compose (recommended)

```bash
cd devops
docker-compose up --build
```

- Backend : http://localhost:50505  
- Frontend: http://localhost:8501  
- API Docs: http://localhost:50505/docs

### Option B — PowerShell (local dev)

```powershell
.\devops\start.ps1
```

### Option C — Windows Batch

```bat
devops\start.bat
```

### Option D — Manual

```bash
# Terminal 1 – backend
cd src/backend
pip install -r ../../requirements.txt
uvicorn app:app --host 0.0.0.0 --port 50505 --reload

# Terminal 2 – frontend
cd src/frontend
streamlit run streamlit_app.py --server.port 8501
```

---

## 🧪 Running tests

```bash
pip install -r requirements.txt
pytest tests/ -v
```

---

## 🔁 RAG Pipeline

```
User Query
    │
    ▼
[1] Azure OpenAI Embeddings (ada-002)
    │
    ▼
[2] Azure AI Search — vector similarity search (top_k docs)
    │
    ▼
[3] Build system prompt with retrieved context + session memory
    │
    ▼
[4] Azure OpenAI Chat Completion (eval deployment)
    │
    ▼
[5] Update in-memory session history (last 10 turns)
    │
    ▼
Answer + Source docs → Streamlit UI
```

---

## 🔐 Security Notes

- Never commit `config/.env` to version control — it is `.gitignore`d.
- The CORS policy is set to `allow_origins=["*"]` for development. Restrict this in production.
- Consider Azure Managed Identity instead of API keys for production.

---

## 📡 API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Liveness probe |
| `POST` | `/chat` | RAG chat completion |
| `DELETE` | `/session/{id}` | Clear session memory |

### POST /chat

```json
// Request
{
  "query": "What is Azure Cognitive Search?",
  "session_id": "optional-uuid"
}

// Response
{
  "session_id": "uuid",
  "answer": "Azure Cognitive Search is ...",
  "sources": [
    {"title": "Azure Docs", "source": "https://...", "score": 0.94}
  ],
  "history_length": 4
}
```
