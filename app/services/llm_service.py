import asyncio
import os
from app.core.config import settings
from langchain_openai import ChatOpenAI
from app.core.logging import logger, LogLatency

class LLMService:
    def __init__(self):
        self.llm = self._init_llm()
        self.failure_count = 0
        self.circuit_open = False

    def _init_llm(self):
        """Initialize LLM with provider selection: vertex > gemini > groq > openai"""
        provider = getattr(settings, 'LLM_PROVIDER', os.getenv('LLM_PROVIDER', 'openai')).lower()
        
        if provider == "vertex":
            try:
                from langchain_google_vertexai import ChatVertexAI
                project_id = settings.GCP_PROJECT_ID or os.getenv("GCP_PROJECT_ID", "")
                location = settings.VERTEX_AI_LOCATION or os.getenv("VERTEX_AI_LOCATION", "asia-southeast1")
                model_name = settings.VERTEX_AI_MODEL or os.getenv("VERTEX_AI_MODEL", "gemini-2.5-flash")
                if project_id:
                    logger.info(f"LLMService using Vertex AI: {model_name} (project={project_id}, location={location})")
                    return ChatVertexAI(
                        model_name=model_name,
                        project=project_id,
                        location=location,
                        temperature=0.2,
                        convert_system_message_to_human=True,
                    )
                else:
                    logger.warning("GCP_PROJECT_ID not set for Vertex AI, falling back")
            except Exception as e:
                logger.warning(f"Vertex AI init failed: {e}, falling back to Gemini")
        
        if provider in ("gemini", "vertex"):  # vertex fallback chain
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
                api_key = settings.GOOGLE_GEMINI_API_KEY or os.getenv("GOOGLE_GEMINI_API_KEY", "")
                if api_key:
                    logger.info(f"LLMService using Gemini: {settings.GEMINI_MODEL_NAME}")
                    return ChatGoogleGenerativeAI(
                        model=settings.GEMINI_MODEL_NAME,
                        google_api_key=api_key,
                        temperature=0.2,
                        convert_system_message_to_human=True,
                    )
                else:
                    logger.warning("GOOGLE_GEMINI_API_KEY not set, falling back")
            except Exception as e:
                logger.warning(f"Gemini init failed: {e}, falling back")
        
        if provider in ("groq", "vertex", "gemini"):  # fallback chain
            try:
                from langchain_groq import ChatGroq
                groq_key = os.getenv("GROQ_API_KEY", "")
                if groq_key:
                    logger.info(f"LLMService using Groq: {settings.MODEL_NAME}")
                    return ChatGroq(
                        model=settings.MODEL_NAME,
                        api_key=groq_key,
                        temperature=0.2,
                    )
            except Exception as e:
                logger.warning(f"Groq init failed: {e}, falling back to OpenAI")
        
        if settings.OPENAI_API_KEY:
            logger.info(f"LLMService using OpenAI: {settings.MODEL_NAME}")
            return ChatOpenAI(
                model_name=settings.MODEL_NAME,
                temperature=0.2,
                openai_api_key=settings.OPENAI_API_KEY,
                openai_api_base=settings.AI_BASE_URL
            )
        
        logger.error("No valid LLM provider configured or missing API keys. LLM features will be disabled.")
        return None

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
