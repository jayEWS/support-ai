"""
AI Log Repository
==================
AI interaction observability: quality monitoring, cost tracking, hallucination detection.
"""

import time
from typing import Optional, List, Dict
from datetime import datetime, timedelta
from sqlalchemy import func, desc
from app.repositories.base import BaseRepository
from app.models.tenant_models import AIInteractionLog
from app.core.logging import logger


class AILogRepository(BaseRepository):
    """Tracks AI interactions for observability, billing, and quality monitoring."""

    def log_interaction(
        self,
        tenant_id: str,
        user_id: str = None,
        ticket_id: int = None,
        query: str = None,
        response: str = None,
        tokens_input: int = 0,
        tokens_output: int = 0,
        confidence_score: float = None,
        escalation_flag: bool = False,
        hallucination_flag: bool = False,
        retrieval_method: str = None,
        latency_ms: int = None,
        cost_usd: float = None,
        model_name: str = None,
        language: str = None,
    ) -> int:
        """Log a single AI interaction. Returns interaction_id."""
        with self.session_scope() as session:
            log = AIInteractionLog(
                tenant_id=tenant_id,
                user_id=user_id,
                ticket_id=ticket_id,
                query=query,
                response=response,
                tokens_input=tokens_input,
                tokens_output=tokens_output,
                tokens_total=tokens_input + tokens_output,
                confidence_score=confidence_score,
                escalation_flag=escalation_flag,
                hallucination_flag=hallucination_flag,
                retrieval_method=retrieval_method,
                latency_ms=latency_ms,
                cost_usd=cost_usd,
                model_name=model_name,
                language=language,
            )
            session.add(log)
            session.flush()
            return log.id

    def get_ai_metrics(self, tenant_id: str, days: int = 30) -> Dict:
        """
        Get aggregated AI quality metrics for a tenant.
        Returns: avg confidence, escalation rate, avg latency, total tokens, total cost, etc.
        """
        since = datetime.utcnow() - timedelta(days=days)
        with self.session_scope() as session:
            q = session.query(AIInteractionLog).filter(
                AIInteractionLog.tenant_id == tenant_id,
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
                func.sum(func.cast(AIInteractionLog.escalation_flag, type_=func.integer if hasattr(func, 'integer') else None)),
                func.sum(func.cast(AIInteractionLog.hallucination_flag, type_=func.integer if hasattr(func, 'integer') else None)),
            ).filter(
                AIInteractionLog.tenant_id == tenant_id,
                AIInteractionLog.created_at >= since,
            ).first()

            # Count escalations and hallucinations manually for compatibility
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

    def get_recent_interactions(self, tenant_id: str, limit: int = 20) -> List[dict]:
        """Get recent AI interactions for debugging/monitoring."""
        with self.session_scope() as session:
            logs = (
                session.query(AIInteractionLog)
                .filter_by(tenant_id=tenant_id)
                .order_by(desc(AIInteractionLog.created_at))
                .limit(limit)
                .all()
            )
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

    def get_low_confidence_interactions(self, tenant_id: str, threshold: float = 0.5, limit: int = 20) -> List[dict]:
        """Get interactions with low confidence scores (potential quality issues)."""
        with self.session_scope() as session:
            logs = (
                session.query(AIInteractionLog)
                .filter(
                    AIInteractionLog.tenant_id == tenant_id,
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
