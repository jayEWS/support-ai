import json
from app.schemas.schemas import IntentClassification, IntentType
from app.core.config import settings
from app.core.logging import logger, LogLatency

class IntentService:
    def __init__(self, llm_service=None):
        self.llm_service = llm_service

    async def classify(self, text: str) -> IntentClassification:
        with LogLatency("intent_service", "classify"):
            prompt = f"""Classify the user intent for a support system.
            Categories:
            - simple: General questions, greetings, or basic info.
            - deep_reasoning: Complex technical issues requiring step-by-step analysis.
            - escalation: User explicitly asks for a human, manager, or is very frustrated.
            - ticket_update: Questions about existing ticket status or requests to change it.
            - critical: Severe system failure, security issues, or urgent business loss.

            User Text: {text}

            Return ONLY a JSON object:
            {{"intent": "category", "confidence": 0.0-1.0, "reason": "brief reason"}}
            """
            
            try:
                if self.llm_service and self.llm_service.llm:
                    res = await self.llm_service.llm.ainvoke(prompt)
                    # Clean up JSON if LLM adds markdown
                    content = res.content.strip()
                    if content.startswith("```"):
                        content = content.split("```")[1]
                        if content.startswith("json"):
                            content = content[4:].strip()
                    
                    data = json.loads(content)
                    return IntentClassification(**data)
                else:
                    logger.warning("LLMService not available for IntentService, using fallback")
                    return IntentClassification(intent=IntentType.SIMPLE, confidence=0.5, reason="LLM unavailable")
            except Exception as e:
                logger.error(f"Intent classification failed: {e}")
                return IntentClassification(intent=IntentType.SIMPLE, confidence=0.5, reason="Fallback due to error")
