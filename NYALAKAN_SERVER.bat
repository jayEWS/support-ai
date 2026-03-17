@echo off
TITLE SUPPORT-AI SERVER (PRODUCTION)
echo ==========================================
echo    SUPPORT-AI SERVER STARTING...
echo ==========================================
echo 1. Activating Virtual Environment...
call .venv\Scripts\activate
if %errorlevel% neq 0 (
    echo [ERROR] Virtual environment not found. Please run: python -m venv .venv
    pause
    exit /b
)

echo 2. Running Database Migrations...
python -m alembic upgrade head
if %errorlevel% neq 0 (
    echo [ERROR] Migration failed. Check your DATABASE_URL in .env
    pause
    exit /b
)

echo 3. Launching Fast API Server on Port 8001...
echo Visit: http://localhost:8001
uvicorn main:app --host 0.0.0.0 --port 8001 --workers 4

pause
