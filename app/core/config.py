from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
import os

class Settings(BaseSettings):
    # AI Config
    OPENAI_API_KEY: str = ""
    MODEL_NAME: str = "llama-3.3-70b-versatile"  # Groq default; override in .env
    AI_BASE_URL: Optional[str] = None
    TEMPERATURE: float = 0.1
    
    # Google Gemini Config
    GOOGLE_GEMINI_API_KEY: str = ""  # from https://aistudio.google.com/
    GEMINI_MODEL_NAME: str = "gemini-2.0-flash"  # or gemini-2.5-pro, gemini-2.0-flash-001
    LLM_PROVIDER: str = "groq"  # vertex | gemini | groq | openai | ollama
    
    # Groq Config
    GROQ_API_KEY: str = "" # from https://console.groq.com/
    
    # Ollama Config (100% Free Local LLM)
    OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")  # Primary local model
    OLLAMA_FALLBACK_MODEL: str = os.getenv("OLLAMA_FALLBACK_MODEL", "qwen2.5:7b")  # Fast fallback
    OLLAMA_TIMEOUT: int = int(os.getenv("OLLAMA_TIMEOUT", "60"))  # Seconds
    OLLAMA_NUM_CTX: int = int(os.getenv("OLLAMA_NUM_CTX", "4096"))  # Context window
    
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
    EMBEDDINGS_TYPE: str = "local"  # local | openai | vertex | qdrant
    EMBEDDINGS_MODEL_NAME: str = os.getenv("EMBEDDINGS_MODEL_NAME", "sentence-transformers/multi-qa-mpnet-base-dot-v1")  # Upgraded from all-MiniLM-L6-v2
    EMBEDDINGS_BASE_URL: Optional[str] = None
    
    # Reranker Config
    CROSS_ENCODER_MODEL: str = os.getenv("CROSS_ENCODER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")  # or BAAI/bge-reranker-v2-m3

    # Qdrant Vector Storage
    QDRANT_HOST: Optional[str] = os.getenv("QDRANT_HOST", "qdrant")
    QDRANT_PORT: int = int(os.getenv("QDRANT_PORT", "6333"))
    QDRANT_API_KEY: Optional[str] = os.getenv("QDRANT_API_KEY", "")
    QDRANT_URL: Optional[str] = os.getenv("QDRANT_URL", None) # Full URL for Cloud (e.g. https://xxx.qdrant.tech)
    
    # Prometheus Metrics
    PROMETHEUS_ENABLED: bool = os.getenv("PROMETHEUS_ENABLED", "False").lower() == "true"

    # WhatsApp / Meta Cloud API Settings
    WHATSAPP_API_TOKEN: str = os.getenv("WHATSAPP_API_TOKEN", "")
    WHATSAPP_PHONE_NUMBER_ID: str = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
    WHATSAPP_BUSINESS_ACCOUNT_ID: str = os.getenv("WHATSAPP_BUSINESS_ACCOUNT_ID", "")
    # P0 FIX: Removed hardcoded default verify token — MUST be set via env var
    WHATSAPP_VERIFY_TOKEN: str = os.getenv("WHATSAPP_VERIFY_TOKEN", "")
    WHATSAPP_APP_SECRET: str = os.getenv("WHATSAPP_APP_SECRET", "")
    # P0 FIX: Default to False (fail-closed) — set True only for local development
    WHATSAPP_TEST_MODE: bool = os.getenv("WHATSAPP_TEST_MODE", "False").lower() == "true"
    
    # Email / Mailgun Settings
    MAILGUN_API_KEY: str = ""  # Set via environment variable
    MAILGUN_DOMAIN: str = ""  # Set via environment variable
    
    # Email / Gmail Settings
    GMAIL_EMAIL: str = ""  # Gmail address
    GMAIL_PASSWORD: str = ""  # Gmail app password (not regular password)
    EMAIL_FROM_ADDRESS: str = ""  # Sender email address
    EMAIL_PROVIDER: str = "gmail"  # Options: gmail, sendgrid, mock
    SENDGRID_API_KEY: str = ""  # SendGrid API key (if EMAIL_PROVIDER=sendgrid)
    
    # Security
    API_SECRET_KEY: str = os.getenv("API_SECRET_KEY", "")  # MUST be set via environment variable
    AUTH_SECRET_KEY: str = ""  # Set via environment variable - MUST be changed in production
    ALGORITHM: str = "HS256"
    # Security Fix M2: Reduce default access token lifetime from 1440 (24h) to 60 minutes
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    MFA_ENABLED: bool = True
    MFA_REQUIRED_FOR_ALL: bool = True
    MFA_CODE_EXPIRE_MINUTES: int = 5
    MFA_CODE_LENGTH: int = 6
    MFA_MAX_ATTEMPTS: int = 5
    MFA_RESEND_COOLDOWN_SECONDS: int = 45
    MFA_DEV_RETURN_CODE: bool = False  # SECURITY: Set to False in production
    COOKIE_SECURE: bool = True  # SECURITY: Set to False only for local development
    COOKIE_SAMESITE: str = "strict"  # SECURITY: Use 'strict' in production
    ALLOWED_ORIGINS: str = ""  # SECURITY: Comma-separated origins in .env for production
    
    @property
    def parsed_origins(self) -> list:
        """Parse comma-separated ALLOWED_ORIGINS string into a list."""
        if not self.ALLOWED_ORIGINS:
            return []
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(',') if o.strip()]
    
    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8001/api/auth/google/callback")
    
    # Magic Link
    MAGIC_LINK_EXPIRE_MINUTES: int = 15
    BASE_URL: str = "http://localhost:8001"
    
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

    # Redis Config (Distributed State)
    REDIS_URL: str = os.getenv("REDIS_URL", "")
    REDIS_ENABLED: bool = os.getenv("REDIS_ENABLED", "False").lower() == "true"

    DEBUG: bool = False  # Defaults to False (Production) if not set

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._validate_production_settings()

    def _validate_production_settings(self):
        """Ensure critical secrets are set in production."""
        if not self.DEBUG:
            # Security Fix C8: Check the ACTUAL JWT signing key, not just SECRET_KEY
            weak_values = [
                "", "changethis", "secret", "your-secret-key",
                "super-secret-production-key-for-testing",
                "another-secret-key", "please-change-me",
            ]
            
            if self.API_SECRET_KEY.lower().strip() in weak_values:
                import secrets
                self.API_SECRET_KEY = secrets.token_urlsafe(32)
                print("WARNING: API_SECRET_KEY was weak/missing. Generated a temporary one for this session.")
            
            if self.AUTH_SECRET_KEY.lower().strip() in weak_values or len(self.AUTH_SECRET_KEY) < 32:
                # P0 FIX: Persist auto-generated key to file so restarts don't
                # invalidate all active sessions (multi-worker safe)
                import secrets
                key_file = os.path.join(self.DB_DIR, ".auth_secret_key")
                try:
                    os.makedirs(self.DB_DIR, exist_ok=True)
                    if os.path.exists(key_file):
                        with open(key_file, "r") as f:
                            saved_key = f.read().strip()
                        if len(saved_key) >= 32:
                            self.AUTH_SECRET_KEY = saved_key
                            print("INFO: AUTH_SECRET_KEY loaded from persisted file.")
                        else:
                            raise ValueError("Saved key too short")
                    else:
                        generated = secrets.token_urlsafe(64)
                        with open(key_file, "w") as f:
                            f.write(generated)
                        self.AUTH_SECRET_KEY = generated
                        print("WARNING: AUTH_SECRET_KEY was weak/missing. Generated and PERSISTED a new one.")
                        print(f"  → Saved to: {key_file}")
                        print("  → For production, set AUTH_SECRET_KEY in your .env file instead.")
                except Exception as e:
                    self.AUTH_SECRET_KEY = secrets.token_urlsafe(64)
                    print(f"WARNING: AUTH_SECRET_KEY auto-generated (could not persist: {e}).")
            
            if not self.DATABASE_URL:
                 print("WARNING: DATABASE_URL is missing. Defaulting to SQLite for Free/Demo mode.")
                 self.DATABASE_URL = "sqlite:///data/db_storage/app.db"
                 
            # Auto-configure local Qdrant if no external URL provided
            if not self.QDRANT_URL and self.QDRANT_HOST == "qdrant":
                 print("WARNING: QDRANT_URL missing. Defaulting to local file-based Qdrant.")
                 self.QDRANT_HOST = "local"
            
            # P1 FIX: Warn about missing CORS configuration
            if not self.ALLOWED_ORIGINS:
                print("WARNING: ALLOWED_ORIGINS is not set. CORS will allow all origins — unsafe for production.")

settings = Settings()
