"""
Alembic Environment Configuration
===================================
Loads the DATABASE_URL from the application's .env file and connects
to both the main app models and SaaS tenant models for auto-detection.
"""

import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# ── Add project root to sys.path so we can import app modules ──
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# ── Load .env before importing app settings ──
from dotenv import load_dotenv
load_dotenv()

from app.core.config import settings
from app.models.models import Base as AppBase

# Try to import tenant models (SaaS layer) if they exist
try:
    from app.models.tenant_models import Base as TenantBase
except ImportError:
    TenantBase = None

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Override sqlalchemy.url with the actual DB URL from .env
# Escape % signs for configparser (it interprets % as interpolation syntax)
_db_url = settings.DATABASE_URL.replace("%", "%%")
config.set_main_option("sqlalchemy.url", _db_url)

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── Target metadata for autogenerate ──
# P0 Fix: Combine both app AND tenant model metadata so Alembic detects all schema changes
from sqlalchemy import MetaData
if TenantBase is not None:
    _combined = MetaData()
    for table in AppBase.metadata.tables.values():
        table.tometadata(_combined)
    for table in TenantBase.metadata.tables.values():
        if table.key not in _combined.tables:
            table.tometadata(_combined)
    target_metadata = _combined
else:
    target_metadata = AppBase.metadata


def include_name(name, type_, parent_names):
    """Filter to include 'app' schema tables and default schema tables."""
    if type_ == "schema":
        return name in (None, "app")
    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        include_name=include_name,
        version_table_schema="app",
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    # Detect dialect for schema configuration
    url = str(connectable.url)
    is_mssql = "mssql" in url
    
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=is_mssql,
            include_name=include_name if is_mssql else None,
            version_table_schema="app" if is_mssql else None,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
