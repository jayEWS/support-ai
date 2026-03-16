#!/bin/bash
set -e

# Default to port 7860 if not set (standard for HF Spaces)
PORT=${PORT:-7860}

echo "🚀 Starting Support Portal..."

# Check if we are using SQLite (default for free tier)
if [[ -z "$DATABASE_URL" ]] || [[ "$DATABASE_URL" == *"sqlite"* ]]; then
    echo "💡 Using SQLite database (Free/Local mode)."
    # Ensure directory exists
    mkdir -p data/db_storage
    export DATABASE_URL="sqlite:///data/db_storage/app.db"
    
    # Run migrations for SQLite
    # Note: Alembic might have issues with SQLite if not configured for batch mode, 
    # but app/core/database.py has a fallback to create_all() for SQLite.
    # We'll try to run migrations, but if it fails, we assume create_all() in code will handle it.
    echo "🔄 Running DB Setup..."
    python -c "from app.core.database import DatabaseManager; DatabaseManager()"
else
    echo "🔌 Connecting to External Database..."
    # Only try to run migrations if we have a connection
    echo "🔄 Running Alembic migrations..."
    alembic upgrade head
fi

# Start the FastAPI application
echo "🔥 Starting Uvicorn on port $PORT..."
exec uvicorn main:app --host 0.0.0.0 --port $PORT --proxy-headers
