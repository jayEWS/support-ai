"""
Anomaly Detector
=================
Analyzes health check results and historical metric samples to detect anomalies.
Uses statistical thresholds and rule-based detection (no external ML dependency).
"""

import json
from typing import List, Optional, Dict, Tuple
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass

from app.core.logging import logger
from app.monitoring.health_checks import HealthCheckResult, HealthStatus


@dataclass
class Anomaly:
    """A detected anomaly ready for incident creation."""
    title: str
    description: str
    severity: str              # critical, high, medium, low
    category: str              # pos_health, kds_health, integration, database, api, printer
    source: str                # Which check detected it
    outlet_id: Optional[int] = None
    device_id: Optional[str] = None
    evidence: Optional[Dict] = None

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "description": self.description,
            "severity": self.severity,
            "category": self.category,
            "source": self.source,
            "outlet_id": self.outlet_id,
            "device_id": self.device_id,
            "evidence": self.evidence,
        }


class AnomalyDetector:
    """Rule-based anomaly detection engine."""

    # Severity thresholds
    DB_LATENCY_WARN_MS = 2000
    DB_LATENCY_CRIT_MS = 5000
    API_LATENCY_WARN_MS = 1000
    API_LATENCY_CRIT_MS = 3000
    DEVICE_OFFLINE_WARN_MIN = 15
    DEVICE_OFFLINE_CRIT_MIN = 60
    TXN_DROP_WARN_PCT = 50
    TXN_DROP_CRIT_PCT = 80

    def __init__(self):
        # Track previously seen anomalies to avoid duplicate incidents
        self._seen_anomalies: Dict[str, datetime] = {}
        self._dedup_window = timedelta(minutes=30)

    def _dedup_key(self, anomaly: Anomaly) -> str:
        """Generate a deduplication key for an anomaly."""
        return f"{anomaly.category}:{anomaly.source}:{anomaly.device_id or anomaly.outlet_id or 'global'}"

    def _is_duplicate(self, anomaly: Anomaly) -> bool:
        """Check if this anomaly was already detected recently."""
        key = self._dedup_key(anomaly)
        now = datetime.now(timezone.utc)

        if key in self._seen_anomalies:
            last_seen = self._seen_anomalies[key]
            if now - last_seen < self._dedup_window:
                return True

        self._seen_anomalies[key] = now
        return False

    def analyze(self, results: List[HealthCheckResult]) -> List[Anomaly]:
        """
        Analyze health check results and return detected anomalies.
        
        Args:
            results: List of HealthCheckResult from the latest check cycle.
            
        Returns:
            List of Anomaly objects representing detected issues.
        """
        anomalies = []

        for result in results:
            detected = self._analyze_single(result)
            for anomaly in detected:
                if not self._is_duplicate(anomaly):
                    anomalies.append(anomaly)

        if anomalies:
            logger.info(f"[AnomalyDetector] Detected {len(anomalies)} anomalies")

        return anomalies

    def _analyze_single(self, result: HealthCheckResult) -> List[Anomaly]:
        """Analyze a single health check result for anomalies."""
        anomalies = []

        if result.status == HealthStatus.HEALTHY:
            return anomalies

        # --- Database anomalies ---
        if result.target_type == "database":
            if result.status == HealthStatus.UNREACHABLE:
                anomalies.append(Anomaly(
                    title="Database Connection Lost",
                    description=f"Cannot reach database. Error: {result.details.get('error', 'Unknown')}",
                    severity="critical",
                    category="database",
                    source="health_check:database",
                    evidence=result.to_dict(),
                ))
            elif result.status == HealthStatus.CRITICAL:
                anomalies.append(Anomaly(
                    title="Database Critically Slow",
                    description=f"Database latency {result.latency_ms:.0f}ms exceeds {self.DB_LATENCY_CRIT_MS}ms threshold",
                    severity="high",
                    category="database",
                    source="health_check:database",
                    evidence=result.to_dict(),
                ))
            elif result.status == HealthStatus.DEGRADED:
                anomalies.append(Anomaly(
                    title="Database Performance Degraded",
                    description=f"Database latency {result.latency_ms:.0f}ms exceeds {self.DB_LATENCY_WARN_MS}ms warning threshold",
                    severity="medium",
                    category="database",
                    source="health_check:database",
                    evidence=result.to_dict(),
                ))

        # --- API anomalies ---
        elif result.target_type == "api":
            if result.status in (HealthStatus.UNREACHABLE, HealthStatus.CRITICAL):
                anomalies.append(Anomaly(
                    title="API Server Unreachable",
                    description=f"FastAPI server is not responding. Status: {result.status.value}",
                    severity="critical",
                    category="api",
                    source="health_check:api",
                    evidence=result.to_dict(),
                ))
            elif result.status == HealthStatus.DEGRADED:
                anomalies.append(Anomaly(
                    title="API Response Time High",
                    description=f"API latency {result.latency_ms:.0f}ms is above normal",
                    severity="medium",
                    category="api",
                    source="health_check:api",
                    evidence=result.to_dict(),
                ))

        # --- Vector store anomalies ---
        elif result.target_type == "vector_store":
            if result.status == HealthStatus.UNREACHABLE:
                anomalies.append(Anomaly(
                    title="Vector Store Unavailable",
                    description="Qdrant vector store is not accessible. RAG queries will fail.",
                    severity="high",
                    category="integration",
                    source="health_check:vector_store",
                    evidence=result.to_dict(),
                ))

        # --- LLM anomalies ---
        elif result.target_type == "llm":
            if result.status == HealthStatus.UNREACHABLE:
                anomalies.append(Anomaly(
                    title="LLM Provider Unavailable",
                    description=f"Cannot reach LLM provider. AI responses will be disabled.",
                    severity="high",
                    category="integration",
                    source="health_check:llm",
                    evidence=result.to_dict(),
                ))
            elif result.status == HealthStatus.DEGRADED:
                anomalies.append(Anomaly(
                    title="LLM Rate Limited",
                    description="LLM provider is rate limiting requests. Response times may increase.",
                    severity="medium",
                    category="integration",
                    source="health_check:llm",
                    evidence=result.to_dict(),
                ))

        # --- POS device anomalies ---
        elif result.target_type in ("pos_device", "pos_terminal", "printer", "kds", "scanner", "payment_terminal"):
            details = result.details or {}
            minutes_since = details.get("minutes_since_seen")

            if result.status == HealthStatus.CRITICAL:
                anomalies.append(Anomaly(
                    title=f"Device Offline: {details.get('device_name', result.target)}",
                    description=(
                        f"Device {result.target} ({result.target_type}) has been offline "
                        f"for {minutes_since:.0f} minutes" if minutes_since else
                        f"Device {result.target} ({result.target_type}) is offline"
                    ),
                    severity="high" if result.target_type in ("pos_terminal", "payment_terminal") else "medium",
                    category="pos_health",
                    source=f"health_check:pos_device:{result.target}",
                    outlet_id=result.outlet_id,
                    device_id=result.target,
                    evidence=result.to_dict(),
                ))
            elif result.status == HealthStatus.UNREACHABLE:
                anomalies.append(Anomaly(
                    title=f"Device Never Seen: {details.get('device_name', result.target)}",
                    description=f"Device {result.target} has no last_seen timestamp. May be misconfigured.",
                    severity="low",
                    category="pos_health",
                    source=f"health_check:pos_device:{result.target}",
                    outlet_id=result.outlet_id,
                    device_id=result.target,
                    evidence=result.to_dict(),
                ))

        # --- Transaction rate anomalies ---
        elif result.target_type == "metric" and result.target == "txn_rate":
            details = result.details or {}
            change_pct = details.get("change_pct", 0)

            if result.status == HealthStatus.CRITICAL:
                anomalies.append(Anomaly(
                    title="Transaction Volume Collapsed",
                    description=(
                        f"Transaction count dropped {abs(change_pct):.0f}% "
                        f"(from {details.get('previous_hour_txns', '?')} to {details.get('current_hour_txns', '?')}). "
                        "Possible POS system failure."
                    ),
                    severity="critical",
                    category="pos_health",
                    source="health_check:txn_rate",
                    evidence=result.to_dict(),
                ))
            elif result.status == HealthStatus.DEGRADED:
                anomalies.append(Anomaly(
                    title="Transaction Volume Drop Detected",
                    description=(
                        f"Transaction count dropped {abs(change_pct):.0f}% compared to previous hour. "
                        "Monitoring for further decline."
                    ),
                    severity="medium",
                    category="pos_health",
                    source="health_check:txn_rate",
                    evidence=result.to_dict(),
                ))

        return anomalies

    def cleanup_stale(self):
        """Remove expired entries from the dedup cache."""
        now = datetime.now(timezone.utc)
        stale_keys = [
            k for k, v in self._seen_anomalies.items()
            if now - v > self._dedup_window * 2
        ]
        for k in stale_keys:
            del self._seen_anomalies[k]
