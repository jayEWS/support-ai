"""add ops platform tables

Revision ID: ops_platform_001
Revises: drop_accountid_uq001
Create Date: 2026-03-18

Creates 6 new tables for the AI Operations Platform:
    - ops_health_checks
    - ops_incidents
    - ops_store_twins
    - ops_device_states
    - ops_automation_logs
    - ops_metric_samples

Does NOT modify any existing tables.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'ops_platform_001'
down_revision: Union[str, Sequence[str], None] = 'drop_accountid_uq001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create ops platform tables."""

    # 1. Health Checks
    op.create_table('ops_health_checks',
        sa.Column('CheckID', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('Target', sa.Unicode(length=100), nullable=False),
        sa.Column('TargetType', sa.Unicode(length=50), nullable=False),
        sa.Column('Status', sa.Unicode(length=20), nullable=False),
        sa.Column('LatencyMs', sa.Float(), nullable=True),
        sa.Column('Details', sa.UnicodeText(), nullable=True),
        sa.Column('CheckedAt', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('OutletID', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('CheckID')
    )
    op.create_index('ix_hc_target_time', 'ops_health_checks', ['Target', 'CheckedAt'], unique=False)
    op.create_index('ix_hc_status_time', 'ops_health_checks', ['Status', 'CheckedAt'], unique=False)

    # 2. Incidents
    op.create_table('ops_incidents',
        sa.Column('IncidentID', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('Title', sa.Unicode(length=255), nullable=False),
        sa.Column('Description', sa.UnicodeText(), nullable=True),
        sa.Column('Severity', sa.Unicode(length=20), nullable=False),
        sa.Column('Status', sa.Unicode(length=30), nullable=True),
        sa.Column('Category', sa.Unicode(length=50), nullable=True),
        sa.Column('Source', sa.Unicode(length=100), nullable=True),
        sa.Column('OutletID', sa.Integer(), nullable=True),
        sa.Column('DeviceID', sa.Unicode(length=50), nullable=True),
        sa.Column('RootCause', sa.UnicodeText(), nullable=True),
        sa.Column('Evidence', sa.UnicodeText(), nullable=True),
        sa.Column('RecommendedFix', sa.UnicodeText(), nullable=True),
        sa.Column('AutomationAction', sa.Unicode(length=100), nullable=True),
        sa.Column('AIConfidence', sa.Float(), nullable=True),
        sa.Column('InvestigationLog', sa.UnicodeText(), nullable=True),
        sa.Column('ResolvedBy', sa.Unicode(length=100), nullable=True),
        sa.Column('ResolvedAt', sa.DateTime(), nullable=True),
        sa.Column('ResolutionNotes', sa.UnicodeText(), nullable=True),
        sa.Column('CreatedAt', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('UpdatedAt', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('IncidentID')
    )
    op.create_index('ix_inc_severity_status', 'ops_incidents', ['Severity', 'Status'], unique=False)
    op.create_index('ix_inc_created', 'ops_incidents', ['CreatedAt'], unique=False)

    # 3. Store Digital Twins
    op.create_table('ops_store_twins',
        sa.Column('TwinID', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('OutletID', sa.Integer(), nullable=False),
        sa.Column('OutletName', sa.Unicode(length=100), nullable=True),
        sa.Column('OverallStatus', sa.Unicode(length=20), nullable=True),
        sa.Column('HealthScore', sa.Float(), nullable=True),
        sa.Column('TotalDevices', sa.Integer(), nullable=True),
        sa.Column('OnlineDevices', sa.Integer(), nullable=True),
        sa.Column('OfflineDevices', sa.Integer(), nullable=True),
        sa.Column('TxnCount1H', sa.Integer(), nullable=True),
        sa.Column('TxnTotal1H', sa.Float(), nullable=True),
        sa.Column('AvgTxnLatencyMs', sa.Float(), nullable=True),
        sa.Column('KDSQueueDepth', sa.Integer(), nullable=True),
        sa.Column('KDSAvgPrepTime', sa.Float(), nullable=True),
        sa.Column('IntegrationStatus', sa.UnicodeText(), nullable=True),
        sa.Column('StateSnapshot', sa.UnicodeText(), nullable=True),
        sa.Column('LastUpdated', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('TwinID'),
        sa.UniqueConstraint('OutletID')
    )
    op.create_index('ix_twin_outlet', 'ops_store_twins', ['OutletID'], unique=False)

    # 4. Device States
    op.create_table('ops_device_states',
        sa.Column('StateID', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('DeviceID', sa.Unicode(length=50), nullable=False),
        sa.Column('OutletID', sa.Integer(), nullable=False),
        sa.Column('DeviceType', sa.Unicode(length=50), nullable=False),
        sa.Column('DeviceName', sa.Unicode(length=100), nullable=True),
        sa.Column('Status', sa.Unicode(length=20), nullable=True),
        sa.Column('LastSeen', sa.DateTime(), nullable=True),
        sa.Column('LastError', sa.UnicodeText(), nullable=True),
        sa.Column('UptimePct24H', sa.Float(), nullable=True),
        sa.Column('Metrics', sa.UnicodeText(), nullable=True),
        sa.Column('LastUpdated', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('StateID')
    )
    op.create_index('ix_ds_outlet_type', 'ops_device_states', ['OutletID', 'DeviceType'], unique=False)
    op.create_index('ix_ds_status', 'ops_device_states', ['Status'], unique=False)
    op.create_index('ix_ds_device_id', 'ops_device_states', ['DeviceID'], unique=False)

    # 5. Automation Logs
    op.create_table('ops_automation_logs',
        sa.Column('AutoLogID', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('IncidentID', sa.Integer(), nullable=True),
        sa.Column('ActionType', sa.Unicode(length=100), nullable=False),
        sa.Column('Target', sa.Unicode(length=200), nullable=False),
        sa.Column('Parameters', sa.UnicodeText(), nullable=True),
        sa.Column('Result', sa.Unicode(length=20), nullable=False),
        sa.Column('ResultDetails', sa.UnicodeText(), nullable=True),
        sa.Column('ExecutedBy', sa.Unicode(length=50), nullable=True),
        sa.Column('ExecutedAt', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('RollbackAvailable', sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint('AutoLogID')
    )
    op.create_index('ix_auto_incident', 'ops_automation_logs', ['IncidentID'], unique=False)
    op.create_index('ix_auto_action_time', 'ops_automation_logs', ['ActionType', 'ExecutedAt'], unique=False)

    # 6. Metric Samples
    op.create_table('ops_metric_samples',
        sa.Column('SampleID', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('MetricName', sa.Unicode(length=100), nullable=False),
        sa.Column('Target', sa.Unicode(length=100), nullable=False),
        sa.Column('Value', sa.Float(), nullable=False),
        sa.Column('Unit', sa.Unicode(length=20), nullable=True),
        sa.Column('SampledAt', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('SampleID')
    )
    op.create_index('ix_metric_name_time', 'ops_metric_samples', ['MetricName', 'SampledAt'], unique=False)
    op.create_index('ix_metric_target_time', 'ops_metric_samples', ['Target', 'SampledAt'], unique=False)


def downgrade() -> None:
    """Drop all ops platform tables."""
    op.drop_table('ops_metric_samples')
    op.drop_table('ops_automation_logs')
    op.drop_table('ops_device_states')
    op.drop_table('ops_store_twins')
    op.drop_table('ops_incidents')
    op.drop_table('ops_health_checks')
