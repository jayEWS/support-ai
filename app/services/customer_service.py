from app.core.database import db_manager
from app.schemas.schemas import CustomerInfo
from app.core.logging import logger

class CustomerService:
    @staticmethod
    async def get_or_register_customer(identifier: str, name: str = None) -> CustomerInfo:
        user = db_manager.get_user(identifier)
        if user:
            logger.info(f"Customer recognized: {identifier}")
            return CustomerInfo(
                identifier=user["identifier"],
                name=user["name"],
                company=user["company"],
                is_new=False
            )
        
        # New customer logic
        logger.info(f"New customer detected: {identifier}")
        display_name = name or f"User {identifier[-4:]}"
        db_manager.create_or_update_user(identifier, name=display_name, state='asking_language')
        
        return CustomerInfo(
            identifier=identifier,
            name=display_name,
            is_new=True
        )

    @staticmethod
    def get_personalized_greeting(customer: CustomerInfo) -> str:
        """Multi-language greeting based on customer's language preference."""
        if customer.is_new:
            # New customer — language not yet known, use multi-language prompt
            return ("👋 Welcome to *Edgeworks Support*!\n\n"
                    "Please select your preferred language:\n"
                    "Silakan pilih bahasa Anda:\n"
                    "请选择您的语言：\n\n"
                    "1️⃣ Bahasa Indonesia\n"
                    "2️⃣ English\n"
                    "3️⃣ 中文\n\n"
                    "Reply with 1, 2, or 3 😊")
        
        # Existing customer — get their language
        user = db_manager.get_user(customer.identifier)
        lang = (user.get('language') if user else None) or 'id'
        name = customer.name or ''
        
        greetings = {
            'id': f"Hai {name}! 👋 Senang ketemu lagi.\nAda yang bisa saya bantu hari ini?",
            'en': f"Hi {name}! 👋 Great to see you again.\nHow can I help you today?",
            'zh': f"{name} 您好！👋 很高兴再次见到您。\n请问今天有什么可以帮助您的？",
        }
        return greetings.get(lang, greetings['id'])
