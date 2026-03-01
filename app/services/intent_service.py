import json
from app.schemas.schemas import IntentClassification, IntentType
from app.core.config import settings
from langchain_openai import ChatOpenAI
from app.core.logging import logger, LogLatency

class IntentService:
    def __init__(self):
        self.llm = ChatOpenAI(
            model_name=settings.MODEL_NAME,
            temperature=0,
            openai_api_key=settings.OPENAI_API_KEY,
            openai_api_base=settings.AI_BASE_URL
        )

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
                res = await self.llm.ainvoke(prompt)
                data = json.loads(res.content.replace('```json','').replace('```','').strip())
                return IntentClassification(**data)
            except Exception as e:
                logger.error(f"Intent classification failed: {e}")
                return IntentClassification(intent=IntentType.SIMPLE, confidence=0.5, reason="Fallback due to error")
