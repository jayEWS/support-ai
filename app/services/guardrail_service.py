import re
from app.core.logging import logger


# ============ COMPREHENSIVE PROMPT INJECTION PATTERNS ============
# P0 Fix: Expanded from 4 patterns to 25+ covering known attack vectors.
# Categories: direct injection, role hijacking, data exfiltration, encoding bypass.

INJECTION_PATTERNS = [
    # --- Direct Instruction Override ---
    r"ignore\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?|rules?|context)",
    r"disregard\s+(all\s+)?(previous|prior|above)\s+(instructions?|prompts?)",
    r"forget\s+(all\s+)?(previous|prior|your)\s+(instructions?|rules?|training)",
    r"override\s+(all\s+)?(safety|security|content)\s+(filters?|policies?|rules?)",
    r"bypass\s+(all\s+)?(safety|security|content|guardrail)",

    # --- Role / Identity Hijacking ---
    r"you\s+are\s+now\s+(a|an|the)\s+",
    r"act\s+as\s+(a|an|if\s+you\s+are)\s+",
    r"pretend\s+(to\s+be|you\s*'?re)\s+",
    r"from\s+now\s+on[,.]?\s+you\s+(are|will|must|should)",
    r"new\s+(persona|identity|character|role)\s*[:=]",
    r"switch\s+(to|into)\s+(a\s+)?(different|new)\s+(mode|persona|role)",
    r"enter\s+(developer|debug|admin|god|sudo|root|jailbreak)\s+mode",
    r"(DAN|STAN|DUDE|AIM)\s+mode",

    # --- System Prompt / Prompt Extraction ---
    r"(show|print|output|display|reveal|repeat|echo)\s+(me\s+)?(the\s+)?(system|initial|original|hidden|secret)\s+(prompt|message|instructions?)",
    r"what\s+(is|are|was|were)\s+(your|the)\s+(system|original|initial|hidden)\s+(prompt|instructions?|message|rules?)",
    r"(beginning|start)\s+of\s+(the\s+)?(conversation|prompt|context)",

    # --- Data Exfiltration / Leaking ---
    r"(list|show|dump|print)\s+(all\s+)?(your|the|internal)\s+(tools?|functions?|API|endpoints?|keys?|secrets?|passwords?|credentials?)",
    r"(what|which)\s+(tools?|functions?|APIs?)\s+(do\s+you|are\s+you|can\s+you)",

    # --- Encoding / Obfuscation Attacks ---
    r"base64[:\s]+[A-Za-z0-9+/=]{20,}",  # Base64-encoded payloads
    r"\\x[0-9a-fA-F]{2}",               # Hex-encoded characters
    r"translate\s+(the\s+following|this)\s+from\s+base64",

    # --- Markdown / Injection Formatting ---
    r"\[system\]",
    r"<\|?(system|im_start|im_end|endoftext)\|?>",  # Token injection markers
    r"\{\{.*system.*\}\}",  # Template injection

    # --- Multi-turn / Context Manipulation ---
    r"(first|second|next)\s+(instruction|task|step)\s*:\s*(ignore|forget|disregard)",
    r"in\s+(this|the)\s+conversation,\s+the\s+rules\s+are",
]

# Compile for performance
_COMPILED_INJECTION_PATTERNS = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]

# Output hallucination phrases that indicate the model is breaking persona
HALLUCINATION_PHRASES = [
    "As an AI language model",
    "I don't have personal opinions",
    "As a large language model",
    "I'm just an AI",
    "my training data",
    "my knowledge cutoff",
    "I was trained by OpenAI",
    "I was trained by Google",
    "I was made by Anthropic",
]


class GuardrailService:
    @staticmethod
    def validate_input(text: str) -> bool:
        """
        Check for malicious input:
        - System prompt injection attempts (25+ patterns).
        - Excessive length.
        - Encoding-based bypass attempts.
        """
        if not text:
            return True

        # 1. Length check — hard cap
        if len(text) > 5000:
            logger.warning(f"[Guardrails] Input too long: {len(text)} chars")
            return False

        # 2. Comprehensive injection detection
        for pattern in _COMPILED_INJECTION_PATTERNS:
            if pattern.search(text):
                logger.warning(
                    f"[Guardrails] Blocked prompt injection (pattern={pattern.pattern[:40]}): "
                    f"{text[:80]}"
                )
                return False

        # 3. Excessive special character density (obfuscation indicator)
        if len(text) > 50:
            special_ratio = sum(1 for c in text if not c.isalnum() and c not in ' .,!?\n\r\t-') / len(text)
            if special_ratio > 0.5:
                logger.warning(f"[Guardrails] Suspicious character density ({special_ratio:.0%}): {text[:60]}")
                return False

        return True

    @staticmethod
    def validate_output(text: str) -> str:
        """
        Check and sanitize AI output:
        - Block persona-breaking hallucination phrases.
        - Mask sensitive data (PII).
        - Strip system-level token markers.
        """
        if not text:
            return text

        # 1. Block hallucination / persona breaks
        text_lower = text.lower()
        for phrase in HALLUCINATION_PHRASES:
            if phrase.lower() in text_lower:
                return (
                    "I apologize, but I am unable to answer that specific request right now. "
                    "How else can I help you with your POS system?"
                )

        # 2. Strip any leaked system/token markers from the output
        text = re.sub(r'<\|?(system|im_start|im_end|endoftext)\|?>', '', text)
        text = re.sub(r'\[/?system\]', '', text, flags=re.IGNORECASE)

        # 3. PII masking (defense-in-depth; pii_scrubber.py handles storage)
        # Credit card numbers (13-19 digits with optional separators)
        text = re.sub(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{1,7}\b', '[CARD MASKED]', text)
        # NRIC / National ID patterns (e.g., Singapore NRIC: S1234567D)
        text = re.sub(r'\b[STFGM]\d{7}[A-Z]\b', '[ID MASKED]', text, flags=re.IGNORECASE)
        # Phone numbers (international format)
        text = re.sub(r'\+?\d{1,4}[-\s]?\(?\d{1,4}\)?[-\s]?\d{3,4}[-\s]?\d{3,4}\b', '[PHONE MASKED]', text)

        return text


guardrail_service = GuardrailService()
