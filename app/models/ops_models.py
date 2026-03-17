"""
Operations Platform — SQLAlchemy Models
========================================
Models for health checks, incidents, digital twin state, and automation logs.
These extend the existing models.py without modifying it — new tables only.

Tables created:
    - ops_health_checks     — Periodic health check results
    - ops_incidents         — Detected anomalies / incidents
    - ops_store_twins       — Digital twin state snapshots per store
    - ops_device_states     — Per-device state within a store twin
    - ops_automation_logs   — Every automated action (audit trail)
    - ops_metric_samples    — Time-series metric samples for trending

All tables use the "ops_" prefix to avoid collision with existing tables.
"""

from sqlalchemy import (
    Column, Integer, Unicode, UnicodeText, DateTime, Float,
    Boolean, ForeignKey, Index, Text, func, JSON
)
from app.models.models import Base, USE_APP_SCHEMA, tenant_id_column
from datetime import datetime


class HealthCheck(Base):
    """Periodic health check result for a target service/device."""
    __tablename__ = "ops_health_checks"
    __table_args__ = (
        Index("ix_hc_target_time", "Target", "CheckedAt"),
        Index("ix_hc_status_time", "Status", "CheckedAt"),
        {"schema": "app"} if USE_APP_SCHEMA else {},
    )

    id = Column("CheckID", Integer, primary_key=True, autoincrement=True)
    target = Column("Target", Unicode(100), nullable=False, index=True)
    target_type = Column("TargetType", Unicode(50), nullable=False)  # database, api, pos, kds, integration, printer
    status = Column("Status", Unicode(20), nullable=False)           # healthy, degraded, critical, unreachable
    latency_ms = Column("LatencyMs", Float, nullable=True)
    details = Column("Details", UnicodeText, nullable=True)          # JSON payload with check-specific data
    checked_at = Column("CheckedAt", DateTime, server_default=func.now())
    outlet_id = Column("OutletID", Integer, nullable=True)
    tenant_id = tenant_id_column()


class Incident(Base):
    """Detected anomaly or incident requiring investigation / automation."""
    __tablename__ = "ops_incidents"
    __table_args__ = (
        Index("ix_inc_severity_status", "Severity", "Status"),
        Index("ix_inc_created", "CreatedAt"),
        {"schema": "app"} if USE_APP_SCHEMA else {},
    )

    id = Column("IncidentID", Integer, primary_key=True, autoincrement=True)
    title = Column("Title", Unicode(255), nullable=False)
    description = Column("Description", UnicodeText)
    severity = Column("Severity", Unicode(20), nullable=False)       # critical, high, medium, low
    status = Column("Status", Unicode(30), default="detected")       # detected, investigating, auto_fixing, resolved, escalated
    category = Column("Category", Unicode(50))                       # pos_health, kds_health, integration, database, api, printer
    source = Column("Source", Unicode(100))                          # Which health check / monitor triggered it
    outlet_id = Column("OutletID", Integer, nullable=True)
    device_id = Column("DeviceID", Unicode(50), nullable=True)

    # AI Analysis results
    root_cause = Column("RootCause", UnicodeText, nullable=True)
    evidence = Column("Evidence", UnicodeText, nullable=True)        # JSON: logs, metrics, twin state
    recommended_fix = Column("RecommendedFix", UnicodeText, nullable=True)
    automation_action = Column("AutomationAction", Unicode(100), nullable=True)  # Action name or null
    ai_confidence = Column("AIConfidence", Float, nullable=True)
    investigation_log = Column("InvestigationLog", UnicodeText, nullable=True)  # Full AI reasoning chain

    # Resolution
    resolved_by = Column("ResolvedBy", Unicode(100), nullable=True)  # "auto" or agent username
    resolved_at = Column("ResolvedAt", DateTime, nullable=True)
    resolution_notes = Column("ResolutionNotes", UnicodeText, nullable=True)

    created_at = Column("CreatedAt", DateTime, server_default=func.now())
    updated_at = Column("UpdatedAt", DateTime, server_default=func.now(), onupdate=func.now())
    tenant_id = tenant_id_column()


class StoreTwin(Base):
    """Digital twin snapshot of a store's operational state."""
    __tablename__ = "ops_store_twins"
    __table_args__ = (
        Index("ix_twin_outlet", "OutletID"),
        {"schema": "app"} if USE_APP_SCHEMA else {},
    )

    id = Column("TwinID", Integer, primary_key=True, autoincrement=True)
    outlet_id = Column("OutletID", Integer, nullable=False, unique=True)
    outlet_name = Column("OutletName", Unicode(100))

    # Aggregate health
    overall_status = Column("OverallStatus", Unicode(20), default="unknown")  # healthy, degraded, critical
    health_score = Column("HealthScore", Float, default=100.0)               # 0-100

    # Component counts
    total_devices = Column("TotalDevices", Integer, default=0)
    online_devices = Column("OnlineDevices", Integer, default=0)
    offline_devices = Column("OfflineDevices", Integer, default=0)

    # Transaction metrics (latest window)
    txn_count_1h = Column("TxnCount1H", Integer, default=0)
    txn_total_1h = Column("TxnTotal1H", Float, default=0.0)
    avg_txn_latency_ms = Column("AvgTxnLatencyMs", Float, nullable=True)

    # KDS metrics
    kds_queue_depth = Column("KDSQueueDepth", Integer, default=0)
    kds_avg_prep_time = Column("KDSAvgPrepTime", Float, nullable=True)

    # Integration status
    integration_status = Column("IntegrationStatus", UnicodeText, nullable=True)  # JSON map: {name: status}

    # Full state snapshot (JSON blob for AI consumption)
    state_snapshot = Column("StateSnapshot", UnicodeText, nullable=True)

    last_updated = Column("LastUpdated", DateTime, server_default=func.now(), onupdate=func.now())
    tenant_id = tenant_id_column()


class DeviceState(Base):
    """Individual device state within a store's digital twin."""
    __tablename__ = "ops_device_states"
    __table_args__ = (
        Index("ix_ds_outlet_type", "OutletID", "DeviceType"),
        Index("ix_ds_status", "Status"),
        {"schema": "app"} if USE_APP_SCHEMA else {},
    )

    id = Column("StateID", Integer, primary_key=True, autoincrement=True)
    device_id = Column("DeviceID", Unicode(50), nullable=False, index=True)
    outlet_id = Column("OutletID", Integer, nullable=False)
    device_type = Column("DeviceType", Unicode(50), nullable=False)   # pos_terminal, printer, kds, scanner, payment_terminal
    device_name = Column("DeviceName", Unicode(100), nullable=True)

    status = Column("Status", Unicode(20), default="unknown")        # online, offline, degraded, error
    last_seen = Column("LastSeen", DateTime, nullable=True)
    last_error = Column("LastError", UnicodeText, nullable=True)
    uptime_pct_24h = Column("UptimePct24H", Float, nullable=True)    # 0-100

    # Device-specific metrics (JSON)
    metrics = Column("Metrics", UnicodeText, nullable=True)           # {"cpu": 45, "memory": 60, "disk": 78, ...}

    last_updated = Column("LastUpdated", DateTime, server_default=func.now(), onupdate=func.now())
    tenant_id = tenant_id_column()


class AutomationLog(Base):
    """Audit log for every automated action taken by the system."""
    __tablename__ = "ops_automation_logs"
    __table_args__ = (
        Index("ix_auto_incident", "IncidentID"),
        Index("ix_auto_action_time", "ActionType", "ExecutedAt"),
        {"schema": "app"} if USE_APP_SCHEMA else {},
    )

    id = Column("AutoLogID", Integer, primary_key=True, autoincrement=True)
    incident_id = Column("IncidentID", Integer, nullable=True)
    action_type = Column("ActionType", Unicode(100), nullable=False)  # retry_integration, restart_pos_service, clear_queue, etc.
    target = Column("Target", Unicode(200), nullable=False)           # What was acted on
    parameters = Column("Parameters", UnicodeText, nullable=True)     # JSON input parameters
    result = Column("Result", Unicode(20), nullable=False)            # success, failed, skipped, blocked
    result_details = Column("ResultDetails", UnicodeText, nullable=True)
    executed_by = Column("ExecutedBy", Unicode(50), default="system") # "system" | "agent:username"
    executed_at = Column("ExecutedAt", DateTime, server_default=func.now())
    rollback_available = Column("RollbackAvailable", Boolean, default=False)
    tenant_id = tenant_id_column()


class MetricSample(Base):
    """Time-series metric sample for trending and anomaly detection."""
    __tablename__ = "ops_metric_samples"
    __table_args__ = (
        Index("ix_metric_name_time", "MetricName", "SampledAt"),
        Index("ix_metric_target_time", "Target", "SampledAt"),
        {"schema": "app"} if USE_APP_SCHEMA else {},
    )

    id = Column("SampleID", Integer, primary_key=True, autoincrement=True)
    metric_name = Column("MetricName", Unicode(100), nullable=False)  # db_latency, api_p95, pos_txn_rate, kds_queue
    target = Column("Target", Unicode(100), nullable=False)           # database, outlet_1, device_XYZ
    value = Column("Value", Float, nullable=False)
    unit = Column("Unit", Unicode(20), nullable=True)                 # ms, count, percent, bytes
    sampled_at = Column("SampledAt", DateTime, server_default=func.now())
    tenant_id = tenant_id_column()
