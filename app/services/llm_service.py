import asyncio
from app.core.config import settings
from langchain_openai import ChatOpenAI
from app.core.logging import logger, LogLatency

class LLMService:
    def __init__(self):
        self.llm = ChatOpenAI(
            model_name=settings.MODEL_NAME,
            temperature=0.2,
            openai_api_key=settings.OPENAI_API_KEY,
            openai_api_base=settings.AI_BASE_URL
        )
        self.failure_count = 0
        self.circuit_open = False

    async def reason(self, text: str) -> str:
        if self.circuit_open:
            return "System is currently overloaded. Please try again later."

        with LogLatency("llm_service", "reason"):
            prompt = f"Perform deep reasoning for this support request: {text}. Provide a detailed step-by-step solution."
            
            try:
                # Timeout control
                res = await asyncio.wait_for(self.llm.ainvoke(prompt), timeout=30.0)
                self.failure_count = 0
                return res.content
            except asyncio.TimeoutError:
                logger.error("LLM reasoning timed out")
                self._handle_failure()
                return "Reasoning took too long. Escalating to human."
            except Exception as e:
                logger.error(f"LLM reasoning failed: {e}")
                self._handle_failure()
                return "Technical error during reasoning. Escalating to human."

    def _handle_failure(self):
        self.failure_count += 1
        if self.failure_count > 5:
            self.circuit_open = True
            asyncio.create_task(self._reset_circuit())

    async def _reset_circuit(self):
        await asyncio.sleep(60)
        self.circuit_open = False
        self.failure_count = 0
        logger.info("Circuit breaker reset")
