from sqlalchemy import create_engine, text
from app.core.config import settings

def migrate():
    engine = create_engine(settings.DATABASE_URL)
    with engine.connect() as conn:
        print("Checking for GoogleID column in app.Agents...")
        try:
            # Check for column existence and add if missing
            conn.execute(text("""
                IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('[app].[Agents]') AND name = 'GoogleID')
                ALTER TABLE [app].[Agents] ADD GoogleID NVARCHAR(100);
            """))
            conn.commit()
            print("GoogleID column ensured.")
        except Exception as e:
            print(f"Error adding GoogleID: {e}")

        print("Checking for AuthMagicLinks table...")
        try:
            conn.execute(text("""
                IF NOT EXISTS (SELECT * FROM sys.tables WHERE object_id = OBJECT_ID('[app].[AuthMagicLinks]'))
                CREATE TABLE [app].[AuthMagicLinks] (
                    LinkID INT PRIMARY KEY IDENTITY(1,1),
                    Username NVARCHAR(100),
                    TokenHash NVARCHAR(128) UNIQUE,
                    ExpiresAt DATETIME,
                    CreatedAt DATETIME DEFAULT GETDATE()
                );
            """))
            conn.commit()
            print("AuthMagicLinks table ensured.")
        except Exception as e:
            print(f"Error creating table: {e}")

if __name__ == "__main__":
    migrate()
