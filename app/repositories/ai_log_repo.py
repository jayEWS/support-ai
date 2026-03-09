"""
AI Log Repository
==================
AI interaction observability: quality monitoring, cost tracking, hallucination detection.
"""

import time
from typing import Optional, List, Dict
from datetime import datetime, timedelta, timezone
from sqlalchemy import func, desc
from app.repositories.base import BaseRepository
from app.models.tenant_models import AIInteractionLog
from app.core.logging import logger


class AILogRepository(BaseRepository):
    """Tracks AI interactions for observability, billing, and quality monitoring."""

    def log_interaction(
        self,
        tenant_id: str = None,
        **kwargs
    ) -> int:
        """Log a single AI interaction, scoped by tenant."""
        with self.session_scope() as session:
            effective_tenant_id = tenant_id or self.tenant_id
            log = AIInteractionLog(
                tenant_id=effective_tenant_id,
                **kwargs
            )
            session.add(log)
            session.flush()
            return log.id

    def get_ai_metrics(self, tenant_id: str = None, days: int = 30) -> Dict:
        """
        Get aggregated AI quality metrics for current tenant.
        """
        since = datetime.now(timezone.utc) - timedelta(days=days)
        with self.session_scope() as session:
            q = session.query(AIInteractionLog).filter(
                AIInteractionLog.tenant_id == (tenant_id or self.tenant_id),
                AIInteractionLog.created_at >= since,
            )

            total = q.count()
            if total == 0:
                return {
                    "total_interactions": 0,
                    "avg_confidence": None,
                    "escalation_rate": 0,
                    "hallucination_rate": 0,
                    "avg_latency_ms": None,
                    "total_tokens": 0,
                    "total_cost_usd": 0,
                }

            # Aggregates
            stats = session.query(
                func.avg(AIInteractionLog.confidence_score),
                func.avg(AIInteractionLog.latency_ms),
                func.sum(AIInteractionLog.tokens_total),
                func.sum(AIInteractionLog.cost_usd),
            ).filter(
                AIInteractionLog.tenant_id == (tenant_id or self.tenant_id),
                AIInteractionLog.created_at >= since,
            ).first()

            # Count escalations and hallucinations manually
            escalations = q.filter(AIInteractionLog.escalation_flag == True).count()
            hallucinations = q.filter(AIInteractionLog.hallucination_flag == True).count()

            return {
                "total_interactions": total,
                "avg_confidence": round(float(stats[0]), 3) if stats[0] else None,
                "escalation_rate": round(escalations / total, 3) if total > 0 else 0,
                "hallucination_rate": round(hallucinations / total, 3) if total > 0 else 0,
                "avg_latency_ms": round(float(stats[1])) if stats[1] else None,
                "total_tokens": int(stats[2]) if stats[2] else 0,
                "total_cost_usd": round(float(stats[3]), 4) if stats[3] else 0,
                "period_days": days,
            }

    def get_recent_interactions(self, tenant_id: str = None, limit: int = 20) -> List[dict]:
        """Get recent AI interactions for current tenant."""
        with self.session_scope() as session:
            q = session.query(AIInteractionLog)
            q = q.filter_by(tenant_id=tenant_id or self.tenant_id)
            logs = q.order_by(desc(AIInteractionLog.created_at)).limit(limit).all()
            return [
                {
                    "id": l.id,
                    "user_id": l.user_id,
                    "query": (l.query[:100] + "...") if l.query and len(l.query) > 100 else l.query,
                    "confidence": l.confidence_score,
                    "escalated": l.escalation_flag,
                    "tokens": l.tokens_total,
                    "latency_ms": l.latency_ms,
                    "model": l.model_name,
                    "created_at": str(l.created_at),
                }
                for l in logs
            ]

    def get_low_confidence_interactions(self, tenant_id: str = None, threshold: float = 0.5, limit: int = 20) -> List[dict]:
        """Get interactions with low confidence scores for current tenant."""
        with self.session_scope() as session:
            logs = (
                session.query(AIInteractionLog).filter(
                    AIInteractionLog.tenant_id == (tenant_id or self.tenant_id),
                    AIInteractionLog.confidence_score != None,
                    AIInteractionLog.confidence_score < threshold,
                )
                .order_by(desc(AIInteractionLog.created_at))
                .limit(limit)
                .all()
            )
            return [
                {
                    "id": l.id,
                    "query": l.query,
                    "response": (l.response[:200] + "...") if l.response and len(l.response) > 200 else l.response,
                    "confidence": l.confidence_score,
                    "model": l.model_name,
                    "created_at": str(l.created_at),
                }
                for l in logs
            ]
