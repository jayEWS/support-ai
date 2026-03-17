"""
Health Check Definitions
=========================
Each health check is a callable that returns a standardized HealthCheckResult.
Checks are designed to be non-destructive, read-only, and fast (<5s each).
"""

import time
import json
import asyncio
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
from enum import Enum

from app.core.logging import logger


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    UNREACHABLE = "unreachable"


@dataclass
class HealthCheckResult:
    """Standardized output from any health check."""
    target: str
    target_type: str
    status: HealthStatus
    latency_ms: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)
    outlet_id: Optional[int] = None
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "target": self.target,
            "target_type": self.target_type,
            "status": self.status.value,
            "latency_ms": round(self.latency_ms, 2),
            "details": self.details,
            "outlet_id": self.outlet_id,
            "checked_at": self.checked_at.isoformat(),
        }


async def check_database() -> HealthCheckResult:
    """Check PostgreSQL/Neon database connectivity and performance."""
    from app.core.database import db_manager
    from sqlalchemy import text

    target = "neon_postgresql"
    start = time.time()

    try:
        if not db_manager:
            return HealthCheckResult(
                target=target, target_type="database",
                status=HealthStatus.UNREACHABLE,
                details={"error": "db_manager not initialized"},
            )

        session = db_manager.get_session()
        try:
            # 1. Basic connectivity
            session.execute(text("SELECT 1"))
            latency = (time.time() - start) * 1000

            # 2. Table count
            from sqlalchemy import inspect
            inspector = inspect(db_manager.engine)
            tables = inspector.get_table_names()

            # 3. Active connections (PostgreSQL specific)
            conn_info = {}
            try:
                result = session.execute(text(
                    "SELECT count(*) as active FROM pg_stat_activity WHERE state = 'active'"
                ))
                row = result.fetchone()
                conn_info["active_connections"] = row[0] if row else 0
            except Exception:
                pass  # Not PostgreSQL or no permission

            # 4. DB size
            try:
                result = session.execute(text(
                    "SELECT pg_database_size(current_database()) as size_bytes"
                ))
                row = result.fetchone()
                if row:
                    conn_info["database_size_mb"] = round(row[0] / 1024 / 1024, 2)
            except Exception:
                pass

            # Determine status based on latency
            if latency > 5000:
                status = HealthStatus.CRITICAL
            elif latency > 2000:
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.HEALTHY

            return HealthCheckResult(
                target=target, target_type="database",
                status=status, latency_ms=latency,
                details={
                    "table_count": len(tables),
                    **conn_info,
                },
            )
        finally:
            db_manager.Session.remove()

    except Exception as e:
        latency = (time.time() - start) * 1000
        logger.error(f"[HealthCheck] Database check failed: {e}")
        return HealthCheckResult(
            target=target, target_type="database",
            status=HealthStatus.UNREACHABLE, latency_ms=latency,
            details={"error": str(e)},
        )


async def check_api_latency() -> HealthCheckResult:
    """Check internal API response time (self-ping)."""
    import httpx
    from app.core.config import settings

    port = getattr(settings, "PORT", 8001) or 8001
    url = f"http://127.0.0.1:{port}/health"
    start = time.time()

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            latency = (time.time() - start) * 1000

            if resp.status_code == 200:
                status = HealthStatus.HEALTHY if latency < 1000 else HealthStatus.DEGRADED
            else:
                status = HealthStatus.DEGRADED

            return HealthCheckResult(
                target="fastapi_server", target_type="api",
                status=status, latency_ms=latency,
                details={"status_code": resp.status_code, "response": resp.json() if resp.status_code == 200 else {}},
            )
    except Exception as e:
        latency = (time.time() - start) * 1000
        return HealthCheckResult(
            target="fastapi_server", target_type="api",
            status=HealthStatus.UNREACHABLE, latency_ms=latency,
            details={"error": str(e)},
        )


async def check_vector_store() -> HealthCheckResult:
    """Check Qdrant vector store health."""
    start = time.time()

    try:
        from app.services.qdrant_store import get_qdrant_store
        store = get_qdrant_store()

        if store is None:
            return HealthCheckResult(
                target="qdrant", target_type="vector_store",
                status=HealthStatus.UNREACHABLE,
                details={"error": "Qdrant store not initialized"},
            )

        latency = (time.time() - start) * 1000

        # Try to get collection info
        details = {"initialized": True}
        try:
            from qdrant_client import QdrantClient
            client = getattr(store, '_client', None) or getattr(store, 'client', None)
            if client and hasattr(client, 'get_collections'):
                collections = client.get_collections()
                details["collections"] = len(collections.collections)
        except Exception:
            pass

        status = HealthStatus.HEALTHY if latency < 2000 else HealthStatus.DEGRADED

        return HealthCheckResult(
            target="qdrant", target_type="vector_store",
            status=status, latency_ms=latency,
            details=details,
        )
    except Exception as e:
        latency = (time.time() - start) * 1000
        return HealthCheckResult(
            target="qdrant", target_type="vector_store",
            status=HealthStatus.UNREACHABLE, latency_ms=latency,
            details={"error": str(e)},
        )


async def check_llm_service() -> HealthCheckResult:
    """Check LLM (Groq) connectivity with a minimal prompt."""
    start = time.time()

    try:
        from app.core.config import settings
        provider = settings.LLM_PROVIDER

        if provider == "groq":
            import httpx
            api_key = settings.GROQ_API_KEY
            if not api_key:
                return HealthCheckResult(
                    target="groq_llm", target_type="llm",
                    status=HealthStatus.UNREACHABLE,
                    details={"error": "GROQ_API_KEY not configured"},
                )

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                latency = (time.time() - start) * 1000

                if resp.status_code == 200:
                    models = resp.json().get("data", [])
                    model_ids = [m["id"] for m in models[:5]]
                    status = HealthStatus.HEALTHY
                elif resp.status_code == 429:
                    status = HealthStatus.DEGRADED
                    model_ids = []
                else:
                    status = HealthStatus.CRITICAL
                    model_ids = []

                return HealthCheckResult(
                    target="groq_llm", target_type="llm",
                    status=status, latency_ms=latency,
                    details={
                        "provider": provider,
                        "model": settings.MODEL_NAME,
                        "available_models": model_ids,
                        "status_code": resp.status_code,
                    },
                )
        else:
            # Non-Groq providers — just verify config exists
            latency = (time.time() - start) * 1000
            return HealthCheckResult(
                target=f"{provider}_llm", target_type="llm",
                status=HealthStatus.HEALTHY, latency_ms=latency,
                details={"provider": provider, "note": "Config check only"},
            )
    except Exception as e:
        latency = (time.time() - start) * 1000
        return HealthCheckResult(
            target="llm_service", target_type="llm",
            status=HealthStatus.UNREACHABLE, latency_ms=latency,
            details={"error": str(e)},
        )


async def check_pos_devices() -> List[HealthCheckResult]:
    """Check POS device health from database records."""
    from app.core.database import db_manager
    from app.models.models import POSDevice, Outlet

    results = []
    try:
        if not db_manager:
            return results

        session = db_manager.get_session()
        try:
            devices = session.query(POSDevice).all()
            now = datetime.now(timezone.utc)

            for device in devices:
                last_seen = device.last_seen
                if last_seen and last_seen.tzinfo is None:
                    last_seen = last_seen.replace(tzinfo=timezone.utc)

                if not last_seen:
                    status = HealthStatus.UNREACHABLE
                    minutes_since = None
                else:
                    minutes_since = (now - last_seen).total_seconds() / 60
                    if minutes_since < 5:
                        status = HealthStatus.HEALTHY
                    elif minutes_since < 15:
                        status = HealthStatus.DEGRADED
                    else:
                        status = HealthStatus.CRITICAL

                results.append(HealthCheckResult(
                    target=device.id,
                    target_type=device.device_type or "pos_device",
                    status=status,
                    outlet_id=device.outlet_id,
                    details={
                        "device_name": device.device_name,
                        "ip_address": device.ip_address,
                        "db_status": device.status,
                        "last_seen": last_seen.isoformat() if last_seen else None,
                        "minutes_since_seen": round(minutes_since, 1) if minutes_since else None,
                    },
                ))
        finally:
            db_manager.Session.remove()
    except Exception as e:
        logger.error(f"[HealthCheck] POS device check failed: {e}")

    return results


async def check_transaction_rate() -> HealthCheckResult:
    """Check transaction rate anomalies (sudden drop may indicate POS failure)."""
    from app.core.database import db_manager
    from app.models.models import POSTransaction
    from sqlalchemy import func as sqlfunc, text

    start = time.time()
    try:
        if not db_manager:
            return HealthCheckResult(
                target="txn_rate", target_type="metric",
                status=HealthStatus.UNREACHABLE,
                details={"error": "db_manager not initialized"},
            )

        session = db_manager.get_session()
        try:
            now = datetime.now(timezone.utc)
            one_hour_ago = now - timedelta(hours=1)
            two_hours_ago = now - timedelta(hours=2)

            # Current hour count
            current_count = session.query(sqlfunc.count(POSTransaction.id)).filter(
                POSTransaction.timestamp >= one_hour_ago
            ).scalar() or 0

            # Previous hour count
            prev_count = session.query(sqlfunc.count(POSTransaction.id)).filter(
                POSTransaction.timestamp >= two_hours_ago,
                POSTransaction.timestamp < one_hour_ago
            ).scalar() or 0

            latency = (time.time() - start) * 1000

            # Anomaly: >50% drop in txn rate
            if prev_count > 10 and current_count < prev_count * 0.5:
                status = HealthStatus.DEGRADED
            elif prev_count > 10 and current_count < prev_count * 0.2:
                status = HealthStatus.CRITICAL
            else:
                status = HealthStatus.HEALTHY

            return HealthCheckResult(
                target="txn_rate", target_type="metric",
                status=status, latency_ms=latency,
                details={
                    "current_hour_txns": current_count,
                    "previous_hour_txns": prev_count,
                    "change_pct": round(
                        ((current_count - prev_count) / prev_count * 100) if prev_count > 0 else 0, 1
                    ),
                },
            )
        finally:
            db_manager.Session.remove()
    except Exception as e:
        latency = (time.time() - start) * 1000
        return HealthCheckResult(
            target="txn_rate", target_type="metric",
            status=HealthStatus.UNREACHABLE, latency_ms=latency,
            details={"error": str(e)},
        )


# Registry of all available health checks
HEALTH_CHECKS = {
    "database": check_database,
    "api": check_api_latency,
    "vector_store": check_vector_store,
    "llm": check_llm_service,
    "pos_devices": check_pos_devices,
    "txn_rate": check_transaction_rate,
}


async def run_all_checks() -> List[HealthCheckResult]:
    """Execute all health checks concurrently and return results."""
    results = []

    # Run scalar checks concurrently
    scalar_checks = [
        check_database(),
        check_api_latency(),
        check_vector_store(),
        check_llm_service(),
        check_transaction_rate(),
    ]
    scalar_results = await asyncio.gather(*scalar_checks, return_exceptions=True)

    for r in scalar_results:
        if isinstance(r, HealthCheckResult):
            results.append(r)
        elif isinstance(r, Exception):
            logger.error(f"[HealthCheck] Check failed with exception: {r}")

    # POS devices returns a list
    try:
        device_results = await check_pos_devices()
        results.extend(device_results)
    except Exception as e:
        logger.error(f"[HealthCheck] POS device check failed: {e}")

    return results
