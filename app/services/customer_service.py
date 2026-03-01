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
        db_manager.create_or_update_user(identifier, name=display_name)
        
        return CustomerInfo(
            identifier=identifier,
            name=display_name,
            is_new=True
        )

    @staticmethod
    def get_personalized_greeting(customer: CustomerInfo) -> str:
        if customer.is_new:
            return f"Halo {customer.name}! Selamat datang di layanan bantuan kami. Mohon lengkapi profil Anda jika diperlukan."
        return f"Halo {customer.name}! Ada yang bisa kami bantu kembali hari ini?"
