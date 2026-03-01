from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # AI Config
    OPENAI_API_KEY: str = ""
    MODEL_NAME: str = "gpt-4o-mini"
    AI_BASE_URL: Optional[str] = None
    TEMPERATURE: float = 0.3
    
    # Embeddings Config
    EMBEDDINGS_TYPE: str = "local"
    EMBEDDINGS_MODEL_NAME: str = "all-MiniLM-L6-v2"
    EMBEDDINGS_BASE_URL: Optional[str] = None
    
    # WhatsApp / Bird Settings
    BIRD_API_KEY: str = ""
    BIRD_CHANNEL_ID: str = ""
    BIRD_WORKSPACE_ID: str = ""  # Set via environment variable
    BIRD_WEBHOOK_SECRET: str = ""
    
    # Email / Mailgun Settings
    MAILGUN_API_KEY: str = ""  # Set via environment variable
    MAILGUN_DOMAIN: str = ""  # Set via environment variable
    
    # Email / Gmail Settings
    GMAIL_EMAIL: str = ""  # Gmail address
    GMAIL_PASSWORD: str = ""  # Gmail app password (not regular password)
    EMAIL_FROM_ADDRESS: str = ""  # Sender email address
    EMAIL_PROVIDER: str = "gmail"  # Options: gmail, sendgrid, mock
    
    # Asana Integration
    ASANA_ACCESS_TOKEN: str = ""  # Set via environment variable
    ASANA_PROJECT_GID: str = ""  # Set via environment variable
    ASANA_ENABLED: bool = False
    
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
    
    # Database Config (SQL Server 2025)
    DATABASE_URL: str = ""  # Set via environment variable - MUST be configured for production
    
    # Paths
    KNOWLEDGE_DIR: str = "data/knowledge"
    DB_DIR: str = "data/db_storage"
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
