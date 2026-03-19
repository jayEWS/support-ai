"""
LLM Service — Multi-Provider with Ollama-First (100% Free)
============================================================
Provider priority:  ollama (local free) → groq → vertex → gemini → openai
Auto-fallback:      big model timeout → smaller model automatically
Circuit breaker:    5 failures → 60s cooldown
"""

import asyncio
import os
import httpx
from typing import Optional
from app.core.config import settings
from app.core.logging import logger, LogLatency


# ════════════════════════════════════════════════════════════════════
#  Ollama LangChain-Compatible Wrapper
# ════════════════════════════════════════════════════════════════════

class OllamaResponse:
    """Minimal response object matching LangChain AIMessage.content interface."""
    def __init__(self, content: str):
        self.content = content


class OllamaLLM:
    """
    Lightweight async wrapper around the Ollama REST API.
    Compatible with LangChain's .ainvoke() / .invoke() interface.
    No extra pip dependency needed — uses httpx (already installed).
    """

    def __init__(self, model: str, host: str = "http://localhost:11434",
                 temperature: float = 0.1, num_ctx: int = 4096, timeout: int = 60):
        self.model = model
        self.host = host.rstrip("/")
        self.temperature = temperature
        self.num_ctx = num_ctx
        self.timeout = timeout

    def _to_text(self, prompt) -> str:
        """Convert various prompt formats to plain text."""
        if isinstance(prompt, str):
            return prompt
        if isinstance(prompt, list):
            return "\n\n".join(
                m.content if hasattr(m, 'content') else str(m) for m in prompt
            )
        return str(prompt)

    async def ainvoke(self, prompt, **kwargs) -> OllamaResponse:
        """Async invoke — compatible with LangChain LLM interface."""
        text = self._to_text(prompt)
        payload = {
            "model": self.model,
            "prompt": text,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_ctx": self.num_ctx,
                "num_predict": kwargs.get("max_tokens", 1024),
            }
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f"{self.host}/api/generate", json=payload)
            resp.raise_for_status()
            return OllamaResponse(content=resp.json().get("response", ""))

    def invoke(self, prompt, **kwargs) -> OllamaResponse:
        """Sync invoke fallback."""
        text = self._to_text(prompt)
        payload = {
            "model": self.model,
            "prompt": text,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_ctx": self.num_ctx,
            }
        }
        resp = httpx.post(f"{self.host}/api/generate", json=payload, timeout=self.timeout)
        resp.raise_for_status()
        return OllamaResponse(content=resp.json().get("response", ""))


# ════════════════════════════════════════════════════════════════════
#  Ollama Health & Model Management
# ════════════════════════════════════════════════════════════════════

def _check_ollama_available(host: str) -> bool:
    """Check if Ollama server is reachable."""
    try:
        return httpx.get(f"{host}/api/tags", timeout=5).status_code == 200
    except Exception:
        return False


def _check_model_exists(host: str, model: str) -> bool:
    """Check if a specific model is already pulled in Ollama."""
    try:
        resp = httpx.get(f"{host}/api/tags", timeout=5)
        if resp.status_code == 200:
            for m in resp.json().get("models", []):
                name = m.get("name", "")
                if name == model or name.startswith(model.split(":")[0]):
                    return True
    except Exception:
        pass
    return False


def _auto_pull_model(host: str, model: str) -> bool:
    """Attempt to pull a model if not available (blocking, best-effort)."""
    try:
        logger.info(f"[Ollama] Model '{model}' not found. Starting pull (may take a while)...")
        with httpx.stream("POST", f"{host}/api/pull", json={"name": model}, timeout=600) as resp:
            for line in resp.iter_lines():
                if "success" in line.lower():
                    logger.info(f"[Ollama] Model '{model}' pulled successfully!")
                    return True
        return _check_model_exists(host, model)
    except Exception as e:
        logger.warning(f"[Ollama] Auto-pull failed for '{model}': {e}")
        return False


# ════════════════════════════════════════════════════════════════════
#  Main LLM Service
# ════════════════════════════════════════════════════════════════════

class LLMService:
    def __init__(self):
        self.llm = None
        self.llm_fallback = None          # Smaller/faster model for timeouts
        self.provider_name = "none"
        self.failure_count = 0
        self.circuit_open = False
        self._init_providers()

    def _init_providers(self):
        """Initialize LLM: ollama (free) → groq → vertex → gemini → openai"""
        provider = getattr(settings, 'LLM_PROVIDER', 'groq').lower()

        # Try providers in priority order
        attempts = [
            ("ollama", self._try_ollama),
            ("groq",   self._try_groq),
            ("vertex", self._try_vertex),
            ("gemini", self._try_gemini),
            ("openai", self._try_openai),
        ]

        # Try configured provider first
        for name, init_fn in attempts:
            if name == provider:
                self.llm = init_fn()
                if self.llm:
                    return

        # Then try all others as fallback
        for name, init_fn in attempts:
            if name != provider:
                self.llm = init_fn()
                if self.llm:
                    return

        logger.error("[LLMService] ❌ No LLM provider available. AI features disabled.")

    # ── Provider Initializers ────────────────────────────────────────

    def _try_ollama(self) -> Optional[OllamaLLM]:
        host = settings.OLLAMA_HOST
        model = settings.OLLAMA_MODEL
        fallback = settings.OLLAMA_FALLBACK_MODEL

        if not _check_ollama_available(host):
            logger.info(f"[LLMService] Ollama not reachable at {host}. Skipping.")
            return None

        # Check primary model, fall back to smaller one if needed
        if not _check_model_exists(host, model):
            if _check_model_exists(host, fallback):
                logger.info(f"[LLMService] Primary '{model}' not found. Using fallback '{fallback}'.")
                model = fallback
            else:
                logger.info(f"[LLMService] Pulling fallback model '{fallback}'...")
                if not _auto_pull_model(host, fallback):
                    return None
                model = fallback

        self.provider_name = f"ollama:{model}"
        logger.info(f"[LLMService] ✅ Using Ollama: {model} (host={host})")

        primary = OllamaLLM(
            model=model, host=host,
            temperature=settings.TEMPERATURE,
            num_ctx=settings.OLLAMA_NUM_CTX,
            timeout=settings.OLLAMA_TIMEOUT,
        )

        # Setup auto-fallback to smaller model on timeout
        if fallback != model and _check_model_exists(host, fallback):
            self.llm_fallback = OllamaLLM(
                model=fallback, host=host,
                temperature=settings.TEMPERATURE,
                num_ctx=min(settings.OLLAMA_NUM_CTX, 2048),
                timeout=30,
            )
            logger.info(f"[LLMService] Auto-fallback model: {fallback}")

        return primary

    def _try_groq(self):
        try:
            from langchain_groq import ChatGroq
            api_key = settings.GROQ_API_KEY or os.getenv("GROQ_API_KEY", "")
            if not api_key:
                return None
            self.provider_name = f"groq:{settings.MODEL_NAME}"
            logger.info(f"[LLMService] ✅ Using Groq: {settings.MODEL_NAME}")
            return ChatGroq(model=settings.MODEL_NAME, api_key=api_key, temperature=settings.TEMPERATURE)
        except Exception as e:
            logger.warning(f"[LLMService] Groq init failed: {e}")
            return None

    def _try_vertex(self):
        try:
            from langchain_google_vertexai import ChatVertexAI
            project_id = settings.GCP_PROJECT_ID or os.getenv("GCP_PROJECT_ID", "")
            if not project_id:
                return None
            self.provider_name = f"vertex:{settings.VERTEX_AI_MODEL}"
            logger.info(f"[LLMService] ✅ Using Vertex AI: {settings.VERTEX_AI_MODEL}")
            return ChatVertexAI(
                model_name=settings.VERTEX_AI_MODEL, project=project_id,
                location=settings.VERTEX_AI_LOCATION, temperature=0.2,
                convert_system_message_to_human=True,
            )
        except Exception as e:
            logger.warning(f"[LLMService] Vertex AI init failed: {e}")
            return None

    def _try_gemini(self):
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            api_key = settings.GOOGLE_GEMINI_API_KEY or os.getenv("GOOGLE_GEMINI_API_KEY", "")
            if not api_key:
                return None
            self.provider_name = f"gemini:{settings.GEMINI_MODEL_NAME}"
            logger.info(f"[LLMService] ✅ Using Gemini: {settings.GEMINI_MODEL_NAME}")
            return ChatGoogleGenerativeAI(
                model=settings.GEMINI_MODEL_NAME, google_api_key=api_key,
                temperature=0.1, max_retries=3,
            )
        except Exception as e:
            logger.warning(f"[LLMService] Gemini init failed: {e}")
            return None

    def _try_openai(self):
        try:
            if settings.OPENAI_API_KEY and not settings.OPENAI_API_KEY.startswith("sk-your"):
                from langchain_community.chat_models import ChatOpenAI
                self.provider_name = f"openai:{settings.MODEL_NAME}"
                logger.info(f"[LLMService] ✅ Using OpenAI: {settings.MODEL_NAME}")
                return ChatOpenAI(
                    model_name=settings.MODEL_NAME, temperature=0.2,
                    openai_api_key=settings.OPENAI_API_KEY,
                    openai_api_base=settings.AI_BASE_URL,
                )
        except Exception as e:
            logger.warning(f"[LLMService] OpenAI init failed: {e}")
        return None

    # ── Core Methods ─────────────────────────────────────────────────

    async def reason(self, text: str) -> str:
        """Deep reasoning with auto-fallback to smaller model on timeout."""
        if self.circuit_open:
            return "System is currently overloaded. Please try again later."

        with LogLatency("llm_service", "reason"):
            prompt = f"Perform deep reasoning for this support request: {text}. Provide a detailed step-by-step solution."
            timeout = settings.OLLAMA_TIMEOUT if "ollama" in self.provider_name else 30

            try:
                res = await asyncio.wait_for(self.llm.ainvoke(prompt), timeout=timeout)
                self.failure_count = 0
                return res.content
            except asyncio.TimeoutError:
                # Auto-fallback to smaller model
                if self.llm_fallback:
                    logger.warning("[LLMService] Primary timed out → trying fallback model...")
                    try:
                        res = await asyncio.wait_for(self.llm_fallback.ainvoke(prompt), timeout=30)
                        return res.content
                    except Exception:
                        pass
                logger.error("LLM reasoning timed out (all models)")
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
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._reset_circuit())
            except RuntimeError:
                pass

    async def _reset_circuit(self):
        await asyncio.sleep(60)
        self.circuit_open = False
        self.failure_count = 0
        logger.info("[LLMService] Circuit breaker reset")
