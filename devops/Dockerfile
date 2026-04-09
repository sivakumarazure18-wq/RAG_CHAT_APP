# =============================================================
# Dockerfile — Multi-stage, lightweight Python 3.11 image
# Supports both backend (FastAPI) and frontend (Streamlit)
# via the SERVICE build argument.
# =============================================================

# ── Stage 1: dependency builder ───────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# System deps for compilation (cryptography, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
 && pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: runtime ─────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Non-root user for security
RUN useradd --create-home appuser
USER appuser
WORKDIR /home/appuser/app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy project source
COPY --chown=appuser:appuser src/       ./src/
COPY --chown=appuser:appuser config/    ./config/

# ── Backend target ────────────────────────────────────────────
FROM runtime AS backend
WORKDIR /home/appuser/app/src/backend
EXPOSE 50505
CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "50505"]

# ── Frontend target ───────────────────────────────────────────
FROM runtime AS frontend
WORKDIR /home/appuser/app/src/frontend
EXPOSE 8501
CMD ["python", "-m", "streamlit", "run", "streamlit_app.py", \
     "--server.port=8501", "--server.address=0.0.0.0", \
     "--server.headless=true", "--browser.gatherUsageStats=false"]
