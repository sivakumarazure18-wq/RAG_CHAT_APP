@echo off
REM =============================================================
REM start.bat — Launch the RAG Chat app locally on Windows
REM =============================================================

SETLOCAL

SET ROOT=%~dp0..
SET BACKEND_DIR=%ROOT%\src\backend
SET FRONTEND_DIR=%ROOT%\src\frontend

echo [1/3] Installing dependencies...
pip install -r "%ROOT%\requirements.txt" --quiet
IF ERRORLEVEL 1 (
    echo ERROR: pip install failed.
    EXIT /B 1
)

echo [2/3] Starting FastAPI backend on port 50505...
START "RAG Backend" cmd /k "cd /d %BACKEND_DIR% && python -m uvicorn app:app --host 0.0.0.0 --port 50505 --reload"

REM Give backend a moment to initialise
timeout /t 3 /nobreak >nul

echo [3/3] Starting Streamlit frontend on port 8501...
START "RAG Frontend" cmd /k "cd /d %FRONTEND_DIR% && python -m streamlit run streamlit_app.py --server.port 8501"

echo.
echo ============================================================
echo  Backend  : http://localhost:50505
echo  Frontend : http://localhost:8501
echo  API Docs : http://localhost:50505/docs
echo ============================================================
ENDLOCAL
