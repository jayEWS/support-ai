"""
Register JAY DB knowledge documents in the database and trigger RAG reindex.
Run on the production server after uploading the .txt files to data/knowledge/.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import db_manager

KB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'knowledge')

files = [
    "JAY_DB_Tables_Schema.txt",
    "JAY_DB_Stored_Procedures.txt", 
    "JAY_DB_Functions.txt",
    "JAY_DB_Views.txt",
    "JAY_DB_Triggers.txt",
    "JAY_DB_Indexes.txt",
]

# 1. Check current status
print("=" * 50)
print("Checking existing KB metadata for JAY files...")
print("=" * 50)
existing = db_manager.get_all_knowledge()
jay_existing = [r for r in existing if r['filename'].startswith('JAY_')]
if jay_existing:
    for r in jay_existing:
        print(f"  {r['filename']:<40} status={r.get('status','')}  by={r.get('uploaded_by','')}")
    print(f"\n  Found {len(jay_existing)} registered JAY files.")
else:
    print("  (none registered yet)")

# 2. Get a valid admin agent
from sqlalchemy import text
session = db_manager.get_session()
try:
    result = session.execute(text("SELECT TOP 1 Username FROM app.Agents WHERE Username IS NOT NULL ORDER BY Username"))
    row = result.fetchone()
    agent_name = row[0] if row else 'admin'
finally:
    db_manager.Session.remove()
print(f"\nUsing agent: {agent_name}")

# 3. Register missing files
print("\n" + "=" * 50)
print("Registering files...")
print("=" * 50)
existing_names = {r['filename'] for r in jay_existing} if jay_existing else set()

for fname in files:
    fpath = os.path.join(KB_DIR, fname)
    if not os.path.exists(fpath):
        print(f"  ❌ {fname} - file not found in {KB_DIR}")
        continue
    
    fsize = os.path.getsize(fpath)
    status = "already registered" if fname in existing_names else "registering"
    
    try:
        db_manager.save_knowledge_metadata(
            filename=fname,
            file_path=fpath,
            uploaded_by=agent_name,
            status="Indexed"
        )
        if fname in existing_names:
            print(f"  ✔️  {fname} ({fsize:,} bytes) - updated")
        else:
            print(f"  ✅ {fname} ({fsize:,} bytes) - registered!")
    except Exception as e:
        print(f"  ⚠️  {fname} - {e}")

# 4. Reindex
print("\n" + "=" * 50)
print("Triggering RAG reload_knowledge (reindex)...")
print("=" * 50)
try:
    from app.services.rag_service import RAGService
    rag = RAGService()
    import asyncio
    result = asyncio.run(rag.reload_knowledge())
    print(f"  ✅ Reindex complete: {result}")
except Exception as e:
    print(f"  ❌ Reindex error: {e}")
    print("  → Try clicking 'Train AI' button in admin panel instead.")

print("\nDone!")
