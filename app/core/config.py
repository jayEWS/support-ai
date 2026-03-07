from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
import os

class Settings(BaseSettings):
    # AI Config
    OPENAI_API_KEY: str = ""
    MODEL_NAME: str = "gpt-4o-mini"
    AI_BASE_URL: Optional[str] = None
    TEMPERATURE: float = 0.1
    
    # Google Gemini Config
    GOOGLE_GEMINI_API_KEY: str = ""  # from https://aistudio.google.com/
    GEMINI_MODEL_NAME: str = "gemini-2.5-flash"  # or gemini-2.5-pro, gemini-2.0-flash-001
    LLM_PROVIDER: str = "groq"  # vertex | gemini | groq | openai | ollama
    
    # Google Cloud Storage Config
    GCS_BUCKET_NAME: str = ""  # e.g. support-edgeworks-knowledge
    GCS_ENABLED: bool = False  # Enable GCS sync for knowledge files
    GOOGLE_APPLICATION_CREDENTIALS: str = ""  # Path to service account JSON
    GCP_PROJECT_ID: str = ""  # GCP project ID
    
    # Vertex AI Config
    VERTEX_AI_LOCATION: str = "asia-southeast1"  # GCP region for Vertex AI
    VERTEX_AI_MODEL: str = "gemini-2.5-flash"  # Vertex AI model name
    VERTEX_AI_EMBEDDINGS_MODEL: str = "text-embedding-005"  # Vertex AI embeddings model
    
    # Embeddings Config
    EMBEDDINGS_TYPE: str = "local"  # local | openai | vertex
    EMBEDDINGS_MODEL_NAME: str = "all-MiniLM-L6-v2"
    EMBEDDINGS_BASE_URL: Optional[str] = None
    
    # WhatsApp / Meta Cloud API Settings
    WHATSAPP_API_TOKEN: str = os.getenv("WHATSAPP_API_TOKEN", "")
    WHATSAPP_PHONE_NUMBER_ID: str = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
    WHATSAPP_BUSINESS_ACCOUNT_ID: str = os.getenv("WHATSAPP_BUSINESS_ACCOUNT_ID", "")
    WHATSAPP_VERIFY_TOKEN: str = os.getenv("WHATSAPP_VERIFY_TOKEN", "edgeworks_wa_verify_2024")
    WHATSAPP_APP_SECRET: str = os.getenv("WHATSAPP_APP_SECRET", "")
    WHATSAPP_TEST_MODE: bool = os.getenv("WHATSAPP_TEST_MODE", "True").lower() == "true"
    
    # Email / Mailgun Settings
    MAILGUN_API_KEY: str = ""  # Set via environment variable
    MAILGUN_DOMAIN: str = ""  # Set via environment variable
    
    # Email / Gmail Settings
    GMAIL_EMAIL: str = ""  # Gmail address
    GMAIL_PASSWORD: str = ""  # Gmail app password (not regular password)
    EMAIL_FROM_ADDRESS: str = ""  # Sender email address
    EMAIL_PROVIDER: str = "gmail"  # Options: gmail, sendgrid, mock
    
    # Security
    API_SECRET_KEY: str = ""  # Set via environment variable - MUST be changed in production
    AUTH_SECRET_KEY: str = ""  # Set via environment variable - MUST be changed in production
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    MFA_ENABLED: bool = True
    MFA_REQUIRED_FOR_ALL: bool = True
    MFA_CODE_EXPIRE_MINUTES: int = 5
    MFA_CODE_LENGTH: int = 6
    MFA_MAX_ATTEMPTS: int = 5
    MFA_RESEND_COOLDOWN_SECONDS: int = 45
    MFA_DEV_RETURN_CODE: bool = False  # SECURITY: Set to False in production
    COOKIE_SECURE: bool = True  # SECURITY: Set to False only for local development
    COOKIE_SAMESITE: str = "strict"  # SECURITY: Use 'strict' in production
    ALLOWED_ORIGINS: list = []  # SECURITY: Specify exact origins in .env for production
    
    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/auth/google/callback"
    
    # Magic Link
    MAGIC_LINK_EXPIRE_MINUTES: int = 15
    BASE_URL: str = "http://localhost:8000"
    
    # Database Config (PostgreSQL / SQL Server / SQLite)
    DATABASE_URL: str = ""  # Set via environment variable - MUST be configured for production
    # PostgreSQL (Neon): postgresql://user:pass@ep-xxx.region.aws.neon.tech/dbname?sslmode=require
    # SQL Server:        mssql+pyodbc://user:pass@host:1433/db?driver=ODBC+Driver+18+for+SQL+Server
    # SQLite:            sqlite:///data/db_storage/app.db
    
    # Paths
    KNOWLEDGE_DIR: str = "data/knowledge"
    DB_DIR: str = "data/db_storage"
    
    # ── SaaS Multi-Tenant Config ──
    MULTI_TENANT_ENABLED: bool = False  # Set True to enforce tenant isolation
    DEFAULT_TENANT_ID: str = "default"  # Fallback tenant during migration
    TENANT_RESOLUTION: str = "header"  # header | subdomain | jwt
    
    # ── Plan Enforcement ──
    PLAN_ENFORCEMENT_ENABLED: bool = False  # Set True to enforce plan limits
    
    # ── AI Observability ──
    AI_OBSERVABILITY_ENABLED: bool = True  # Track AI interactions
    AI_COST_TRACKING_ENABLED: bool = True  # Estimate and track AI costs
    
    # Billing (Stripe)
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""

    DEBUG: bool = False  # Defaults to False (Production) if not set

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._validate_production_settings()

    def _validate_production_settings(self):
        """Ensure critical secrets are set in production."""
        if not self.DEBUG:
            if self.SECRET_KEY in ["", "changethis", "secret"]:
                raise ValueError("CRITICAL: SECRET_KEY is weak or missing in PRODUCTION mode!")
            
            if not self.DATABASE_URL:
                 raise ValueError("CRITICAL: DATABASE_URL is missing in PRODUCTION mode!")

settings = Settings()
