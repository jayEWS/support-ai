import os
import sqlalchemy
from sqlalchemy import text

# Use DATABASE_URL if set so the same script works with SQLite/demo setups.
db_url = os.environ.get(
    "DATABASE_URL",
    'mssql+pyodbc://sa:1@localhost:1433/tCareEWS?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=no&TrustServerCertificate=yes'
)
engine = sqlalchemy.create_engine(db_url)

# If the project is using SQLite there's no point running the SQL Server
# ALTER statements; the schema will already be correct when tables are
# created via SQLAlchemy metadata.  Skip with a message instead of failing.
if "sqlite" in db_url.lower():
    print("[update_kb_schema] SQLite detected; manual schema tweaks are not needed.")
    exit(0)

def update_kb_schema():
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        print("Updating KnowledgeMetadata table...")
        
        # 1. Add UploadedBy column
        try:
            conn.execute(text("ALTER TABLE app.KnowledgeMetadata ADD UploadedBy NVARCHAR(100)"))
            conn.execute(text("ALTER TABLE app.KnowledgeMetadata ADD CONSTRAINT FK_Knowledge_UploadedBy FOREIGN KEY (UploadedBy) REFERENCES app.Agents(Username)"))
            print("Added UploadedBy to KnowledgeMetadata.")
        except Exception as e:
            print(f"Note: UploadedBy might already exist: {e}")

        # 2. Add Status column
        try:
            conn.execute(text("ALTER TABLE app.KnowledgeMetadata ADD Status NVARCHAR(50) DEFAULT 'Processing'"))
            print("Added Status to KnowledgeMetadata.")
        except Exception as e:
            print(f"Note: Status might already exist: {e}")

        print("Schema update complete.")

if __name__ == "__main__":
    update_kb_schema()
