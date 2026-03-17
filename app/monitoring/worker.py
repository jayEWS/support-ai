"""
Monitoring Worker
==================
Background async worker that runs the monitor → detect → analyze → fix loop.

Loop cadence: Every 2 minutes (configurable via MONITORING_INTERVAL_SECONDS).

Lifecycle:
    1. Run all health checks
    2. Persist results to ops_health_checks
    3. Feed results to AnomalyDetector
    4. For each anomaly → create Incident
    5. For each incident → trigger AI analysis (if enabled)
    6. For auto-fixable incidents → run automation
    7. Update Digital Twin state
    8. Sleep until next cycle
"""

import asyncio
import json
from datetime import datetime, timezone
from typing import Optional

from app.core.logging import logger
from app.core.config import settings
from app.monitoring.health_checks import run_all_checks, HealthCheckResult
from app.monitoring.anomaly_detector import AnomalyDetector, Anomaly


# Configurable interval (default 2 minutes)
MONITORING_INTERVAL = int(getattr(settings, "MONITORING_INTERVAL_SECONDS", 120))


class MonitoringWorker:
    """
    Autonomous background worker that continuously monitors system health,
    detects anomalies, creates incidents, and triggers automated responses.
    """

    def __init__(self):
        self.detector = AnomalyDetector()
        self.running = False
        self.cycle_count = 0
        self.last_cycle_at: Optional[datetime] = None
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the monitoring loop as a background task."""
        if self.running:
            logger.warning("[MonitoringWorker] Already running, skipping start.")
            return
        self.running = True
        logger.info(f"[MonitoringWorker] Starting — interval={MONITORING_INTERVAL}s")
        self._task = asyncio.create_task(self._loop())
        return self._task

    async def stop(self):
        """Gracefully stop the monitoring loop."""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("[MonitoringWorker] Stopped.")

    async def _loop(self):
        """Main monitoring loop."""
        # Initial delay to let the server finish booting
        await asyncio.sleep(15)

        while self.running:
            try:
                await self._run_cycle()
            except Exception as e:
                logger.error(f"[MonitoringWorker] Cycle error: {e}", exc_info=True)

            await asyncio.sleep(MONITORING_INTERVAL)

    async def _run_cycle(self):
        """Execute one complete monitoring cycle."""
        self.cycle_count += 1
        self.last_cycle_at = datetime.now(timezone.utc)
        cycle_id = f"cycle_{self.cycle_count}"

        logger.info(f"[MonitoringWorker] ── Cycle {self.cycle_count} starting ──")

        # 1. Run all health checks
        results = await run_all_checks()
        logger.info(f"[MonitoringWorker] {len(results)} health check results collected")

        # 2. Persist health check results
        await self._persist_health_checks(results)

        # 3. Detect anomalies
        anomalies = self.detector.analyze(results)

        if anomalies:
            logger.warning(f"[MonitoringWorker] {len(anomalies)} anomalies detected!")

            # 4. Create incidents for each anomaly
            for anomaly in anomalies:
                incident_id = await self._create_incident(anomaly)

                # 5. Trigger AI analysis if we have an incident
                if incident_id:
                    await self._trigger_ai_analysis(incident_id, anomaly)

        # 6. Update digital twin state
        await self._update_digital_twin(results)

        # 7. Periodic cleanup
        if self.cycle_count % 30 == 0:  # Every ~1 hour
            self.detector.cleanup_stale()
            await self._cleanup_old_records()

        logger.info(f"[MonitoringWorker] ── Cycle {self.cycle_count} complete ──")

    async def _persist_health_checks(self, results: list):
        """Save health check results to the database."""
        from app.core.database import db_manager

        if not db_manager:
            return

        try:
            session = db_manager.get_session()
            try:
                from app.models.ops_models import HealthCheck

                for result in results:
                    hc = HealthCheck(
                        target=result.target,
                        target_type=result.target_type,
                        status=result.status.value,
                        latency_ms=result.latency_ms,
                        details=json.dumps(result.details) if result.details else None,
                        checked_at=result.checked_at,
                        outlet_id=result.outlet_id,
                    )
                    session.add(hc)

                session.commit()
            except Exception as e:
                session.rollback()
                logger.error(f"[MonitoringWorker] Failed to persist health checks: {e}")
            finally:
                db_manager.Session.remove()
        except Exception as e:
            logger.error(f"[MonitoringWorker] DB session error: {e}")

    async def _create_incident(self, anomaly: Anomaly) -> Optional[int]:
        """Create an incident record from a detected anomaly."""
        from app.core.database import db_manager

        if not db_manager:
            return None

        try:
            session = db_manager.get_session()
            try:
                from app.models.ops_models import Incident

                incident = Incident(
                    title=anomaly.title,
                    description=anomaly.description,
                    severity=anomaly.severity,
                    status="detected",
                    category=anomaly.category,
                    source=anomaly.source,
                    outlet_id=anomaly.outlet_id,
                    device_id=anomaly.device_id,
                    evidence=json.dumps(anomaly.evidence) if anomaly.evidence else None,
                )
                session.add(incident)
                session.commit()

                incident_id = incident.id
                logger.info(f"[MonitoringWorker] Incident #{incident_id} created: {anomaly.title}")
                return incident_id

            except Exception as e:
                session.rollback()
                logger.error(f"[MonitoringWorker] Failed to create incident: {e}")
                return None
            finally:
                db_manager.Session.remove()
        except Exception as e:
            logger.error(f"[MonitoringWorker] DB session error: {e}")
            return None

    async def _trigger_ai_analysis(self, incident_id: int, anomaly: Anomaly):
        """
        Trigger AI analysis for an incident.
        Runs the AI Support Engineer agent to investigate and recommend fixes.
        """
        try:
            from app.agents.support_agent import SupportEngineerAgent
            agent = SupportEngineerAgent()
            result = await agent.investigate_incident(incident_id, anomaly)

            if result:
                # Update incident with AI findings
                from app.core.database import db_manager
                if db_manager:
                    session = db_manager.get_session()
                    try:
                        from app.models.ops_models import Incident
                        incident = session.query(Incident).filter_by(id=incident_id).first()
                        if incident:
                            incident.root_cause = result.get("root_cause", "")
                            incident.recommended_fix = result.get("recommended_fix", "")
                            incident.automation_action = result.get("automation_action")
                            incident.ai_confidence = result.get("confidence", 0.0)
                            incident.investigation_log = json.dumps(result.get("investigation_log", []))
                            incident.status = "investigating"

                            # If auto-fix is recommended with high confidence, trigger it
                            if (result.get("automation_action")
                                    and result.get("confidence", 0) >= 0.8
                                    and anomaly.severity in ("critical", "high")):
                                await self._trigger_automation(
                                    incident_id,
                                    result["automation_action"],
                                    anomaly
                                )
                                incident.status = "auto_fixing"

                            session.commit()
                    except Exception as e:
                        session.rollback()
                        logger.error(f"[MonitoringWorker] Failed to update incident with AI analysis: {e}")
                    finally:
                        db_manager.Session.remove()

        except ImportError:
            logger.debug("[MonitoringWorker] AI agent not available, skipping analysis")
        except Exception as e:
            logger.error(f"[MonitoringWorker] AI analysis failed for incident #{incident_id}: {e}")

    async def _trigger_automation(self, incident_id: int, action_type: str, anomaly: Anomaly):
        """Execute automated recovery action for an incident."""
        try:
            from app.automation.engine import AutomationEngine
            engine = AutomationEngine()
            await engine.execute(
                incident_id=incident_id,
                action_type=action_type,
                target=anomaly.device_id or anomaly.source,
                context=anomaly.to_dict(),
            )
        except ImportError:
            logger.debug("[MonitoringWorker] Automation engine not available")
        except Exception as e:
            logger.error(f"[MonitoringWorker] Automation failed for incident #{incident_id}: {e}")

    async def _update_digital_twin(self, results: list):
        """Update digital twin state based on health check results."""
        try:
            from app.digital_twin.twin_manager import TwinManager
            manager = TwinManager()
            await manager.update_from_health_checks(results)
        except ImportError:
            logger.debug("[MonitoringWorker] Twin manager not available")
        except Exception as e:
            logger.error(f"[MonitoringWorker] Digital twin update failed: {e}")

    async def _cleanup_old_records(self):
        """Purge old health check records (keep last 7 days)."""
        from app.core.database import db_manager
        from datetime import timedelta

        if not db_manager:
            return

        try:
            session = db_manager.get_session()
            try:
                from app.models.ops_models import HealthCheck, MetricSample
                cutoff = datetime.now(timezone.utc) - timedelta(days=7)

                deleted = session.query(HealthCheck).filter(
                    HealthCheck.checked_at < cutoff
                ).delete()

                deleted_m = session.query(MetricSample).filter(
                    MetricSample.sampled_at < cutoff
                ).delete()

                session.commit()
                if deleted or deleted_m:
                    logger.info(
                        f"[MonitoringWorker] Cleaned up {deleted} health checks, "
                        f"{deleted_m} metric samples older than 7 days"
                    )
            except Exception as e:
                session.rollback()
                logger.error(f"[MonitoringWorker] Cleanup failed: {e}")
            finally:
                db_manager.Session.remove()
        except Exception as e:
            logger.error(f"[MonitoringWorker] Cleanup session error: {e}")

    def get_status(self) -> dict:
        """Return current worker status for the API."""
        return {
            "running": self.running,
            "cycle_count": self.cycle_count,
            "last_cycle_at": self.last_cycle_at.isoformat() if self.last_cycle_at else None,
            "interval_seconds": MONITORING_INTERVAL,
            "detector_cache_size": len(self.detector._seen_anomalies),
        }


# Singleton instance
monitoring_worker = MonitoringWorker()
