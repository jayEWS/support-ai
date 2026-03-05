import os
import sqlalchemy
from sqlalchemy import text

# Read database URL from environment so the script is portable.
db_url = os.environ.get(
    "DATABASE_URL",
    'mssql+pyodbc://sa:1@localhost:1433/tCareEWS?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=no&TrustServerCertificate=yes'
)
engine = sqlalchemy.create_engine(db_url)

if "sqlite" in db_url.lower():
    print("[update_rbac_schema] SQLite detected; no schema update necessary.")
    exit(0)

def update_schema():
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        print("Updating schema for Enterprise RBAC...")
        
        # 1. Update Permissions table (Add Category)
        try:
            conn.execute(text("ALTER TABLE app.Permissions ADD Category NVARCHAR(50) DEFAULT 'General'"))
            print("Added Category to Permissions.")
        except Exception as e:
            print(f"Note: Category column might already exist or error: {e}")

        # 2. Update Roles table (Add IsActive)
        try:
            conn.execute(text("ALTER TABLE app.Roles ADD IsActive BIT DEFAULT 1"))
            print("Added IsActive to Roles.")
        except Exception as e:
            print(f"Note: IsActive column might already exist or error: {e}")

        # 3. Create UserPermissions association table if not exists
        try:
            conn.execute(text("""
                IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'UserPermissions' AND schema_id = SCHEMA_ID('app'))
                BEGIN
                    CREATE TABLE app.UserPermissions (
                        AgentID INT NOT NULL,
                        PermissionID INT NOT NULL,
                        PRIMARY KEY (AgentID, PermissionID),
                        FOREIGN KEY (AgentID) REFERENCES app.Agents(AgentID),
                        FOREIGN KEY (PermissionID) REFERENCES app.Permissions(PermissionID)
                    )
                    PRINT 'Created app.UserPermissions table.'
                END
            """))
        except Exception as e:
            print(f"Error creating UserPermissions: {e}")

        print("Schema update complete.")

if __name__ == "__main__":
    update_schema()
