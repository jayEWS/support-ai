"""
Digital Twin Manager
=====================
Maintains a real-time digital twin of each store (outlet).
The twin aggregates device states, transaction activity, integration status,
and computes a health score that the AI uses for contextual diagnosis.

Design principles:
    - Twins are updated incrementally (not rebuilt from scratch each cycle)
    - State snapshots are JSON blobs for flexible AI consumption
    - Health scores use weighted component scoring
"""

import json
import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta

from app.core.logging import logger
from app.monitoring.health_checks import HealthCheckResult, HealthStatus


# Health score weights (must sum to 1.0)
WEIGHTS = {
    "devices": 0.35,
    "transactions": 0.25,
    "database": 0.15,
    "api": 0.10,
    "llm": 0.05,
    "vector_store": 0.10,
}


def _status_to_score(status: HealthStatus) -> float:
    """Convert a HealthStatus to a 0-100 score."""
    return {
        HealthStatus.HEALTHY: 100.0,
        HealthStatus.DEGRADED: 60.0,
        HealthStatus.CRITICAL: 20.0,
        HealthStatus.UNREACHABLE: 0.0,
    }.get(status, 50.0)


class TwinManager:
    """Manages digital twin state for all stores."""

    async def update_from_health_checks(self, results: List[HealthCheckResult]):
        """
        Update digital twins based on the latest health check results.
        Groups results by outlet and updates each store twin.
        """
        from app.core.database import db_manager
        if not db_manager:
            return

        # Group device results by outlet
        outlet_devices: Dict[int, List[HealthCheckResult]] = {}
        infra_results: Dict[str, HealthCheckResult] = {}

        for r in results:
            if r.outlet_id is not None:
                outlet_devices.setdefault(r.outlet_id, []).append(r)
            else:
                # Infrastructure-level results (database, api, llm, etc.)
                infra_results[r.target_type] = r

        # Also fetch all known outlets from DB and create twins if needed
        try:
            await self._ensure_outlet_twins(db_manager, outlet_devices)
        except Exception as e:
            logger.error(f"[TwinManager] Failed to ensure outlet twins: {e}")

        # Update each outlet twin
        for outlet_id, device_results in outlet_devices.items():
            try:
                await self._update_outlet_twin(
                    db_manager, outlet_id, device_results, infra_results
                )
            except Exception as e:
                logger.error(f"[TwinManager] Failed to update twin for outlet {outlet_id}: {e}")

        # Update device states
        for r in results:
            if r.target_type in ("pos_device", "pos_terminal", "printer", "kds", "scanner", "payment_terminal"):
                try:
                    await self._update_device_state(db_manager, r)
                except Exception as e:
                    logger.error(f"[TwinManager] Failed to update device state {r.target}: {e}")

    async def _ensure_outlet_twins(self, db_manager, outlet_devices: Dict):
        """Create twin records for outlets that don't have one yet."""
        from app.models.ops_models import StoreTwin
        from app.models.models import Outlet

        session = db_manager.get_session()
        try:
            # Get all outlets
            outlets = session.query(Outlet).all()
            existing_twins = {
                t.outlet_id for t in session.query(StoreTwin.outlet_id).all()
            }

            for outlet in outlets:
                if outlet.id not in existing_twins:
                    twin = StoreTwin(
                        outlet_id=outlet.id,
                        outlet_name=outlet.name,
                        overall_status="unknown",
                        health_score=100.0,
                    )
                    session.add(twin)

            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"[TwinManager] Ensure twins failed: {e}")
        finally:
            db_manager.Session.remove()

    async def _update_outlet_twin(
        self,
        db_manager,
        outlet_id: int,
        device_results: List[HealthCheckResult],
        infra_results: Dict[str, HealthCheckResult],
    ):
        """Update a single outlet's digital twin."""
        from app.models.ops_models import StoreTwin
        from app.models.models import POSTransaction
        from sqlalchemy import func as sqlfunc

        session = db_manager.get_session()
        try:
            twin = session.query(StoreTwin).filter_by(outlet_id=outlet_id).first()
            if not twin:
                twin = StoreTwin(outlet_id=outlet_id, outlet_name=f"Outlet {outlet_id}")
                session.add(twin)

            # Device counts
            total = len(device_results)
            online = sum(1 for r in device_results if r.status == HealthStatus.HEALTHY)
            offline = sum(1 for r in device_results if r.status in (HealthStatus.CRITICAL, HealthStatus.UNREACHABLE))

            twin.total_devices = total
            twin.online_devices = online
            twin.offline_devices = offline

            # Transaction metrics (last 1 hour)
            now = datetime.now(timezone.utc)
            one_hour_ago = now - timedelta(hours=1)
            try:
                txn_stats = session.query(
                    sqlfunc.count(POSTransaction.id),
                    sqlfunc.coalesce(sqlfunc.sum(POSTransaction.total_amount), 0),
                ).filter(
                    POSTransaction.outlet_id == outlet_id,
                    POSTransaction.timestamp >= one_hour_ago,
                ).first()

                if txn_stats:
                    twin.txn_count_1h = txn_stats[0] or 0
                    twin.txn_total_1h = float(txn_stats[1] or 0)
            except Exception:
                pass

            # Compute health score
            device_score = (online / total * 100) if total > 0 else 100.0
            db_score = _status_to_score(infra_results["database"].status) if "database" in infra_results else 100.0
            api_score = _status_to_score(infra_results["api"].status) if "api" in infra_results else 100.0
            llm_score = _status_to_score(infra_results["llm"].status) if "llm" in infra_results else 100.0
            vs_score = _status_to_score(infra_results["vector_store"].status) if "vector_store" in infra_results else 100.0
            txn_score = 100.0  # Default healthy; anomaly detector handles drops separately
            if "metric" in infra_results:
                txn_score = _status_to_score(infra_results["metric"].status)

            health_score = (
                device_score * WEIGHTS["devices"]
                + txn_score * WEIGHTS["transactions"]
                + db_score * WEIGHTS["database"]
                + api_score * WEIGHTS["api"]
                + llm_score * WEIGHTS["llm"]
                + vs_score * WEIGHTS["vector_store"]
            )

            twin.health_score = round(health_score, 1)

            # Overall status from health score
            if health_score >= 80:
                twin.overall_status = "healthy"
            elif health_score >= 50:
                twin.overall_status = "degraded"
            else:
                twin.overall_status = "critical"

            # Build state snapshot for AI consumption
            twin.state_snapshot = json.dumps({
                "outlet_id": outlet_id,
                "health_score": twin.health_score,
                "overall_status": twin.overall_status,
                "devices": {
                    "total": total,
                    "online": online,
                    "offline": offline,
                    "details": [
                        {
                            "device_id": r.target,
                            "type": r.target_type,
                            "status": r.status.value,
                            "details": r.details,
                        }
                        for r in device_results
                    ],
                },
                "transactions": {
                    "count_1h": twin.txn_count_1h,
                    "total_1h": twin.txn_total_1h,
                },
                "infrastructure": {
                    k: {"status": v.status.value, "latency_ms": v.latency_ms}
                    for k, v in infra_results.items()
                },
                "timestamp": now.isoformat(),
            })

            session.commit()

        except Exception as e:
            session.rollback()
            logger.error(f"[TwinManager] Update outlet {outlet_id} twin failed: {e}")
        finally:
            db_manager.Session.remove()

    async def _update_device_state(self, db_manager, result: HealthCheckResult):
        """Update individual device state record."""
        from app.models.ops_models import DeviceState

        session = db_manager.get_session()
        try:
            state = session.query(DeviceState).filter_by(device_id=result.target).first()
            if not state:
                state = DeviceState(
                    device_id=result.target,
                    outlet_id=result.outlet_id or 0,
                    device_type=result.target_type,
                    device_name=result.details.get("device_name", result.target) if result.details else result.target,
                )
                session.add(state)

            state.status = result.status.value
            state.last_updated = datetime.now(timezone.utc)

            if result.details:
                if result.details.get("last_seen"):
                    try:
                        state.last_seen = datetime.fromisoformat(result.details["last_seen"])
                    except (ValueError, TypeError):
                        pass

                state.metrics = json.dumps(result.details)

                if result.status in (HealthStatus.CRITICAL, HealthStatus.UNREACHABLE):
                    state.last_error = result.details.get("error", f"Status: {result.status.value}")

            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"[TwinManager] Device state update failed: {e}")
        finally:
            db_manager.Session.remove()

    async def get_store_twin(self, outlet_id: int) -> Optional[Dict]:
        """Get the digital twin state for a specific store."""
        from app.core.database import db_manager
        from app.models.ops_models import StoreTwin, DeviceState

        if not db_manager:
            return None

        session = db_manager.get_session()
        try:
            twin = session.query(StoreTwin).filter_by(outlet_id=outlet_id).first()
            if not twin:
                return None

            devices = session.query(DeviceState).filter_by(outlet_id=outlet_id).all()

            return {
                "outlet_id": twin.outlet_id,
                "outlet_name": twin.outlet_name,
                "overall_status": twin.overall_status,
                "health_score": twin.health_score,
                "total_devices": twin.total_devices,
                "online_devices": twin.online_devices,
                "offline_devices": twin.offline_devices,
                "txn_count_1h": twin.txn_count_1h,
                "txn_total_1h": twin.txn_total_1h,
                "kds_queue_depth": twin.kds_queue_depth,
                "last_updated": twin.last_updated.isoformat() if twin.last_updated else None,
                "state_snapshot": json.loads(twin.state_snapshot) if twin.state_snapshot else None,
                "devices": [
                    {
                        "device_id": d.device_id,
                        "device_type": d.device_type,
                        "device_name": d.device_name,
                        "status": d.status,
                        "last_seen": d.last_seen.isoformat() if d.last_seen else None,
                        "last_error": d.last_error,
                        "uptime_pct_24h": d.uptime_pct_24h,
                        "metrics": json.loads(d.metrics) if d.metrics else None,
                    }
                    for d in devices
                ],
            }
        finally:
            db_manager.Session.remove()

    async def get_all_twins(self) -> List[Dict]:
        """Get summary of all store twins."""
        from app.core.database import db_manager
        from app.models.ops_models import StoreTwin

        if not db_manager:
            return []

        session = db_manager.get_session()
        try:
            twins = session.query(StoreTwin).order_by(StoreTwin.health_score.asc()).all()
            return [
                {
                    "outlet_id": t.outlet_id,
                    "outlet_name": t.outlet_name,
                    "overall_status": t.overall_status,
                    "health_score": t.health_score,
                    "total_devices": t.total_devices,
                    "online_devices": t.online_devices,
                    "offline_devices": t.offline_devices,
                    "txn_count_1h": t.txn_count_1h,
                    "last_updated": t.last_updated.isoformat() if t.last_updated else None,
                }
                for t in twins
            ]
        finally:
            db_manager.Session.remove()
