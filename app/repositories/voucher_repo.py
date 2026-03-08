"""
Voucher Repository
==================
Row-level locked operations for POS vouchers to prevent financial fraud (Double Spend).
"""

from typing import Optional, List
from sqlalchemy import select
from app.repositories.base import BaseRepository
from app.models.models import Voucher
from datetime import datetime, timezone
from app.core.logging import logger


class VoucherRepository(BaseRepository):
    """
    Manages POS voucher validation and redemption.
    Includes row-level locking for multi-tenant financial integrity.
    """

    def get_voucher(self, code: str, tenant_id: str = None) -> Optional[dict]:
        """Read-only check of voucher status."""
        code = code.upper()
        with self.session_scope() as session:
            query = session.query(Voucher).filter_by(code=code)
            if tenant_id:
                query = query.filter(Voucher.tenant_id == tenant_id)
            
            v = query.first()
            if not v:
                return None
            
            return self._voucher_to_dict(v)

    def check_voucher_validity(self, code: str, tenant_id: str = None) -> dict:
        """Verbose check for UI/Tool feedback."""
        code = code.upper()
        with self.session_scope() as session:
            query = session.query(Voucher).filter_by(code=code)
            if tenant_id:
                query = query.filter(Voucher.tenant_id == tenant_id)
            
            v = query.first()
            if not v:
                return {"valid": False, "reason": "Invalid voucher code"}
            
            # Check expiry
            if v.expiry_date:
                now = datetime.now(timezone.utc)
                # Ensure expiry_date is timezone aware
                exp = v.expiry_date
                if exp.tzinfo is None:
                    exp = exp.replace(tzinfo=timezone.utc)
                
                if exp < now:
                    return {"valid": False, "reason": "Voucher expired at " + exp.isoformat()}
            
            # Check usage
            if v.usage_count >= v.usage_limit:
                 return {"valid": False, "reason": f"Usage limit reached ({v.usage_count}/{v.usage_limit})"}

            if v.status == "redeemed":
                 return {"valid": False, "reason": "Voucher status is already 'redeemed'"}
            
            return {
                "valid": True,
                "code": v.code,
                "campaign_id": v.campaign_id,
                "remaining_uses": v.usage_limit - v.usage_count,
                "expiry": v.expiry_date.isoformat() if v.expiry_date else None
            }

    def redeem_voucher(self, code: str, agent_id: str = "system", tenant_id: str = None) -> dict:
        """
        Redeem a voucher with row-level locking (SELECT ... FOR UPDATE).
        Prevents race condition where concurrent requests spend the same voucher.
        """
        code = code.upper()
        # Note: session_scope will automatically commit/rollback at the end
        with self.session_scope() as session:
            # P0 Fix: with_for_update() ensures this row is locked until commit
            query = session.query(Voucher).filter_by(code=code).with_for_update()
            if tenant_id:
                query = query.filter(Voucher.tenant_id == tenant_id)
            
            v = query.first()
            
            if not v:
                return {"status": "error", "message": "Invalid voucher code"}

            if v.status == "redeemed" or v.usage_count >= v.usage_limit:
                 return {"status": "error", "message": "Voucher already redeemed or limit reached"}

            # Standard checks
            if v.expiry_date:
                now = datetime.now(timezone.utc)
                exp = v.expiry_date
                if exp.tzinfo is None:
                    exp = exp.replace(tzinfo=timezone.utc)
                if exp < now:
                    return {"status": "error", "message": "Voucher expired"}

            # Perform redemption
            v.usage_count += 1
            if v.usage_count >= v.usage_limit:
                v.status = "redeemed"
            
            logger.info(f"Voucher redeemed: {code} by {agent_id} (Usage: {v.usage_count}/{v.usage_limit})")
            
            return {
                "status": "success",
                "message": f"Voucher {code} redeemed successfully",
                "usage_count": v.usage_count,
                "limit": v.usage_limit
            }

    @staticmethod
    def _voucher_to_dict(v: Voucher) -> dict:
        return {
            "code": v.code,
            "campaign_id": v.campaign_id,
            "status": v.status,
            "usage_count": v.usage_count,
            "usage_limit": v.usage_limit,
            "expiry_date": v.expiry_date.isoformat() if v.expiry_date else None
        }
