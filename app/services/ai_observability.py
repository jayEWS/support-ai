"""
AI Observability Service
=========================
Wraps AI interactions to capture quality metrics, detect hallucinations,
predict escalations, and track costs. This is the "AI-native" layer.

Used by:
- ChatService (portal AI responses)
- WhatsApp message processing
- Any future AI-powered feature
"""

import time
import re
from typing import Optional, Dict
from app.repositories.base import TenantContext
from app.repositories.ai_log_repo import AILogRepository
from app.repositories.usage_repo import UsageRepository
from app.core.logging import logger


# Cost estimation per 1K tokens (approximate)
COST_PER_1K_TOKENS = {
    "gemini-2.5-flash": 0.00035,
    "gemini-2.5-pro": 0.00125,
    "gpt-4o-mini": 0.00015,
    "gpt-4o": 0.005,
    "groq": 0.0001,  # Groq is very cheap
    "default": 0.0005,
}


class AIObservabilityService:
    """
    Tracks and monitors AI interactions for quality, cost, and performance.
    
    Usage:
        obs = AIObservabilityService(ai_log_repo, usage_repo)
        tracker = obs.start_tracking(user_id="user123", query="How do I close POS?")
        # ... do AI work ...
        tracker.complete(response="...", confidence=0.85, tokens_in=100, tokens_out=200)
    """

    def __init__(self, ai_log_repo: AILogRepository, usage_repo: UsageRepository):
        self.ai_log_repo = ai_log_repo
        self.usage_repo = usage_repo

    def start_tracking(self, user_id: str = None, query: str = None,
                       ticket_id: int = None) -> "InteractionTracker":
        """Start tracking an AI interaction. Returns a tracker to complete later."""
        return InteractionTracker(
            service=self,
            tenant_id=TenantContext.get(),
            user_id=user_id,
            query=query,
            ticket_id=ticket_id,
        )

    def get_dashboard_metrics(self, tenant_id: str = None, days: int = 30) -> Dict:
        """Get AI quality dashboard metrics."""
        tid = tenant_id or TenantContext.get()
        if not tid:
            return {"error": "No tenant context"}

        metrics = self.ai_log_repo.get_ai_metrics(tid, days=days)
        usage = self.usage_repo.get_current_usage(tid)

        return {
            "ai_quality": metrics,
            "current_usage": usage,
        }

    @staticmethod
    def detect_hallucination(response: str, context_docs: list = None) -> bool:
        """
        Basic hallucination detection heuristic.
        Checks if the response makes claims not supported by context.
        """
        if not response:
            return False

        # Obvious hallucination patterns
        hallucination_patterns = [
            r"as (a|an) AI",
            r"I don'?t have access to",
            r"I can'?t browse",
            r"my training data",
            r"as of my last update",
            r"I'?m not sure.*but.*I think",
        ]
        for pattern in hallucination_patterns:
            if re.search(pattern, response, re.IGNORECASE):
                return True

        # If we have context docs and response mentions specific data not in context
        if context_docs:
            # Check if response contains URLs or specific numbers not in any doc
            urls_in_response = re.findall(r'https?://\S+', response)
            context_text = " ".join(str(d) for d in context_docs)
            for url in urls_in_response:
                if url not in context_text:
                    return True

        return False

    @staticmethod
    def estimate_cost(tokens_input: int, tokens_output: int, model_name: str) -> float:
        """Estimate the cost of an AI interaction."""
        total_tokens = tokens_input + tokens_output
        cost_rate = COST_PER_1K_TOKENS.get(model_name, COST_PER_1K_TOKENS["default"])
        return round((total_tokens / 1000) * cost_rate, 6)


class InteractionTracker:
    """Tracks a single AI interaction from start to completion."""

    def __init__(
        self,
        service: AIObservabilityService,
        tenant_id: str,
        user_id: str = None,
        query: str = None,
        ticket_id: int = None,
    ):
        self.service = service
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.query = query
        self.ticket_id = ticket_id
        self.start_time = time.time()

    def complete(
        self,
        response: str = None,
        confidence: float = None,
        tokens_input: int = 0,
        tokens_output: int = 0,
        escalated: bool = False,
        retrieval_method: str = None,
        model_name: str = None,
        language: str = None,
        context_docs: list = None,
    ):
        """Complete the tracking and log the interaction."""
        latency_ms = int((time.time() - self.start_time) * 1000)

        # Hallucination detection
        hallucinated = AIObservabilityService.detect_hallucination(response, context_docs)

        # Cost estimation
        cost = AIObservabilityService.estimate_cost(tokens_input, tokens_output, model_name or "default")

        try:
            # Log to AI interaction table
            if self.tenant_id and self.service.ai_log_repo:
                self.service.ai_log_repo.log_interaction(
                    tenant_id=self.tenant_id,
                    user_id=self.user_id,
                    ticket_id=self.ticket_id,
                    query=self.query,
                    response=response,
                    tokens_input=tokens_input,
                    tokens_output=tokens_output,
                    confidence_score=confidence,
                    escalation_flag=escalated,
                    hallucination_flag=hallucinated,
                    retrieval_method=retrieval_method,
                    latency_ms=latency_ms,
                    cost_usd=cost,
                    model_name=model_name,
                    language=language,
                )

            # Update usage counters
            if self.tenant_id and self.service.usage_repo:
                total_tokens = tokens_input + tokens_output
                self.service.usage_repo.add_token_usage(
                    self.tenant_id, total_tokens, cost
                )

        except Exception as e:
            # Never let observability failures break the main flow
            logger.warning(f"AI observability logging error: {e}")

        return {
            "latency_ms": latency_ms,
            "cost_usd": cost,
            "hallucination_detected": hallucinated,
            "tokens_total": tokens_input + tokens_output,
        }
