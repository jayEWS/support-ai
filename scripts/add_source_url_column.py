"""Add SourceURL column to KnowledgeMetadata table"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.config import settings
from sqlalchemy import create_engine, text

engine = create_engine(settings.DATABASE_URL)

with engine.connect() as conn:
    # Check if column exists
    result = conn.execute(text("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_schema = 'app' AND table_name = 'KnowledgeMetadata' AND column_name = 'SourceURL'
    """))
    if result.fetchone():
        print("✅ SourceURL column already exists")
    else:
        conn.execute(text('ALTER TABLE app."KnowledgeMetadata" ADD COLUMN "SourceURL" VARCHAR(1024)'))
        conn.commit()
        print("✅ Added SourceURL column to KnowledgeMetadata")
