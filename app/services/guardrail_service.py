import re
from app.core.logging import logger

class GuardrailService:
    @staticmethod
    def validate_input(text: str) -> bool:
        """
        Check for malicious input:
        - System prompt injection attempts.
        - Excessive length.
        - Harmful patterns.
        """
        if not text:
            return True
            
        # 1. Simple injection check (case-insensitive)
        injection_patterns = [
            r"ignore\s+all\s+previous\s+instructions",
            r"system\s+role",
            r"output\s+the\s+prompt",
            r"you\s+are\s+now\s+a\s+hacker",
        ]
        
        for pattern in injection_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                logger.warning(f"[Guardrails] Blocked potential prompt injection: {text[:50]}")
                return False
                
        # 2. Length check
        if len(text) > 5000:
            logger.warning(f"[Guardrails] Input too long: {len(text)} chars")
            return False
            
        return True

    @staticmethod
    def validate_output(text: str) -> str:
        """
        Check and sanitize AI output:
        - Remove system-like technical markers.
        - Check for hallucination markers (like 'As an AI...').
        - Mask sensitive data if it looks like PII.
        """
        if not text:
            return text
            
        # 1. Block "As an AI model" canned responses if we want a strict persona
        hallucination_phrases = [
            "As an AI language model",
            "I don't have personal opinions",
        ]
        for phrase in hallucination_phrases:
            if phrase in text:
                return "I apologize, but I am unable to answer that specific request right now. How else can I help you with your POS system?"

        # 2. Basic PII masking (very simple regex for demonstration)
        # In a real app, use Presidio or similar.
        # Mask 16-digit credit card numbers
        text = re.sub(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b', "[CARD MASKED]", text)
        
        return text

guardrail_service = GuardrailService()
