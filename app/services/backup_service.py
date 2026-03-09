import shutil
import os
import asyncio
from datetime import datetime
from app.core.config import settings
from app.core.logging import logger

class BackupService:
    @staticmethod
    async def run_backup():
        """
        Automated Database Backup (P0 Fix 5).
        Supports SQLite and SQL Server.
        """
        url = settings.DATABASE_URL.lower()
        
        # 1. Handle SQLite
        if "sqlite" in url:
            db_path = settings.DATABASE_URL.replace("sqlite:///", "")
            if not os.path.exists(db_path):
                logger.error(f"[Backup] SQLite DB file not found at {db_path}")
                return

            backup_dir = os.path.join(os.path.dirname(db_path), "backups")
            os.makedirs(backup_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.normpath(os.path.join(backup_dir, f"db_backup_{timestamp}.db"))

            try:
                shutil.copy2(db_path, backup_path)
                logger.info(f"[Backup] Successfully backed up SQLite database to {backup_path}")
                BackupService._purge_old_backups(backup_dir, "db_backup_", ".db")
            except Exception as e:
                logger.error(f"[Backup] SQLite backup failed: {e}")

        # 2. Handle SQL Server (MSSQL)
        elif "mssql" in url:
            try:
                from app.core.database import db_manager
                from sqlalchemy import text
                
                # Get DB name from URL safely
                # format: mssql+pyodbc://sa:1@localhost/supportportal?...
                # We extract the part between the last '/' and the first '?'
                db_name = settings.DATABASE_URL.split("/")[-1].split("?")[0]
                
                # P0 Fix: Security validation of DB name to prevent injection in raw statement
                import re
                if not re.match(r"^[a-zA-Z0-9_\-]+$", db_name):
                    logger.error(f"[Backup] Invalid database name for backup: {db_name}")
                    return

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_filename = f"{db_name}_full_{timestamp}.bak"
                
                logger.info(f"[Backup] Initiating SQL Server Full Backup for '{db_name}'...")
                
                with db_manager.engine.connect() as conn:
                    # Identifier is quoted with [] for MSSQL safety
                    stmt = text(f"BACKUP DATABASE [{db_name}] TO DISK = :path WITH FORMAT")
                    conn.execute(stmt, {"path": backup_filename})
                    conn.commit()
                
                logger.info(f"[Backup] SQL Server backup successful: {backup_filename}")
            except Exception as e:
                logger.error(f"[Backup] SQL Server backup failed: {e}. Ensure SQL service account has write permissions.")

    @staticmethod
    def _purge_old_backups(directory: str, prefix: str, suffix: str):
        """Retention: keep last 7 local backups."""
        try:
            backups = sorted([f for f in os.listdir(directory) if f.startswith(prefix) and f.endswith(suffix)])
            if len(backups) > 7:
                for old_backup in backups[:-7]:
                    os.remove(os.path.join(directory, old_backup))
                    logger.info(f"[Backup] Purged old backup: {old_backup}")
        except Exception as e:
            logger.warning(f"[Backup] Error during retention cleanup: {e}")

    @classmethod
    async def schedule(cls):
        """Run backup every 24 hours."""
        logger.info("[Backup] Automated backup worker started (24h interval)")
        while True:
            await cls.run_backup()
            await asyncio.sleep(86400) # Every 24 hours

backup_service = BackupService()
