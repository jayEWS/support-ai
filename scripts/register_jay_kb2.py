"""Register JAY DB KB docs with a valid agent username."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import db_manager
from sqlalchemy import text

KB_DIR = '/home/j33ca/support-portal-edgeworks/data/knowledge'

# Find admin agent
with db_manager.engine.connect() as c:
    r = c.execute(text("SELECT TOP 1 Username FROM app.Agents ORDER BY AgentID"))
    row = r.fetchone()
    if row:
        admin_user = row[0]
        print(f"Using agent: {admin_user}")
    else:
        print("No agent found!")
        sys.exit(1)

# First delete any existing entries for these files
files = [
    "JAY_DB_Tables_Schema.txt",
    "JAY_DB_Stored_Procedures.txt",
    "JAY_DB_Functions.txt",
    "JAY_DB_Views.txt",
    "JAY_DB_Triggers.txt",
    "JAY_DB_Indexes.txt",
]

with db_manager.engine.connect() as c:
    for fname in files:
        c.execute(text("DELETE FROM app.KnowledgeMetadata WHERE Filename = :f"), {"f": fname})
    c.commit()
    print("Cleaned old entries")

# Re-register with valid agent
for fname in files:
    fpath = os.path.join(KB_DIR, fname)
    if not os.path.exists(fpath):
        print(f"  SKIP {fname}")
        continue
    size_kb = os.path.getsize(fpath) / 1024
    try:
        db_manager.save_knowledge_metadata(
            filename=fname,
            file_path=fpath,
            uploaded_by=admin_user,
            status="Indexed"
        )
        print(f"  OK {fname} ({size_kb:.1f} KB)")
    except Exception as e:
        print(f"  ERR {fname}: {e}")

print("\nDone! Now click Train AI in admin panel.")
