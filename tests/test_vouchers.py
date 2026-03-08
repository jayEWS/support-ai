import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta, timezone
from app.repositories.voucher_repo import VoucherRepository
from app.models.models import Voucher

class TestVoucherRepository(unittest.TestCase):
    def setUp(self):
        self.mock_session = MagicMock()
        self.mock_db = MagicMock()
        self.mock_db.Session = MagicMock(return_value=self.mock_session)
        self.repo = VoucherRepository(self.mock_db.Session)

    def test_voucher_isolation_success(self):
        """Test that a voucher is found when tenant_id matches."""
        mock_voucher = Voucher()
        mock_voucher.code = "TEST100"
        mock_voucher.tenant_id = "tenant_a"
        mock_voucher.status = "active"
        mock_voucher.usage_count = 0
        mock_voucher.usage_limit = 1
        
        # Configure the mock to return our specific object
        # session.query(Voucher).filter_by(code=code).filter(Voucher.tenant_id == tenant_id).first()
        self.mock_session.query.return_value.filter_by.return_value.filter.return_value.first.return_value = mock_voucher
        
        result = self.repo.get_voucher("TEST100", tenant_id="tenant_a")
        self.assertIsNotNone(result)
        self.assertEqual(result["code"], "TEST100")

    def test_voucher_isolation_leak_prevention(self):
        """Test that a voucher from Tenant B is NOT accessible by Tenant A."""
        self.mock_session.query.return_value.filter_by.return_value.filter.return_value.first.return_value = None
        
        result = self.repo.get_voucher("TENANT_B_CODE", tenant_id="tenant_a")
        self.assertIsNone(result)

    def test_redeem_voucher_row_locking(self):
        """Verify that with_for_update() is called during redemption."""
        mock_voucher = Voucher()
        mock_voucher.code = "LOCKTEST"
        mock_voucher.tenant_id = "tenant_a"
        mock_voucher.status = "active"
        mock_voucher.usage_count = 0
        mock_voucher.usage_limit = 1
        mock_voucher.expiry_date = None
        
        # session.query(Voucher).filter_by(code=code).with_for_update().filter(Voucher.tenant_id == tenant_id).first()
        query_mock = self.mock_session.query.return_value
        filter_by_mock = query_mock.filter_by.return_value
        lock_mock = filter_by_mock.with_for_update.return_value
        filter_mock = lock_mock.filter.return_value
        filter_mock.first.return_value = mock_voucher
        
        self.repo.redeem_voucher("LOCKTEST", tenant_id="tenant_a")
        
        filter_by_mock.with_for_update.assert_called_once()

    def test_voucher_expiry(self):
        """Test that expired vouchers are rejected."""
        past_date = datetime.now(timezone.utc) - timedelta(days=1)
        mock_voucher = Voucher()
        mock_voucher.code = "EXPIRED"
        mock_voucher.tenant_id = "tenant_a"
        mock_voucher.status = "active"
        mock_voucher.usage_count = 0
        mock_voucher.usage_limit = 1
        mock_voucher.expiry_date = past_date
        
        query_mock = self.mock_session.query.return_value
        filter_by_mock = query_mock.filter_by.return_value
        lock_mock = filter_by_mock.with_for_update.return_value
        filter_mock = lock_mock.filter.return_value
        filter_mock.first.return_value = mock_voucher
        
        result = self.repo.redeem_voucher("EXPIRED", tenant_id="tenant_a")
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["message"], "Voucher expired")

if __name__ == "__main__":
    unittest.main()
