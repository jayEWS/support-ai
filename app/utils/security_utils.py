import re

class SecurityEngine:
    @staticmethod
    def mask_pii(text: str) -> str:
        """
        Masks common PII patterns to protect user privacy.
        """
        if not text: return text
        
        # Email masking
        text = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '[EMAIL_MASKED]', text)
        
        # Credit Card masking (basic 16-digit)
        text = re.sub(r'\b(?:\d[ -]*?){13,16}\b', '[CARD_MASKED]', text)
        
        # Phone number masking (Indonesian/Generic)
        text = re.sub(r'(\+62|08|628)\d{8,11}', '[PHONE_MASKED]', text)
        
        return text

    @staticmethod
    def check_jailbreak(text: str) -> bool:
        """
        Simple heuristic check for common prompt injection attempts.
        """
        patterns = ["ignore all previous instructions", "system prompt", "developer mode"]
        for p in patterns:
            if p in text.lower():
                return True
        return False
