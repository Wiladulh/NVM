from pathlib import Path
from tempfile import TemporaryDirectory
import pytest
from app.core.db import Database
from app.vending.service import VendingService

def seed(db):
    with db.connect() as c:
        c.execute("INSERT INTO identity_members(member_id,name) VALUES('pm-member','Payment Method Test')")
        c.execute("INSERT INTO financial_accounts(account_id,member_id,account_type) VALUES('pm-acct','pm-member','savings')")
        c.execute("INSERT INTO vending_machines(machine_id,name,status) VALUES('pm-01','Payment Method Vending','active')")
        c.execute("INSERT INTO vending_products(product_id,machine_id,name,price,stock) VALUES('water','pm-01','Water',5000,2)")
        c.execute("INSERT INTO credential_registry(credential_id,credential_type,member_id,status,enabled) VALUES('pm-nfc','nfc','pm-member','active',1)")
        c.commit()

def test_vending_transaction_binds_payment_method_and_provider():
    with TemporaryDirectory() as d:
        db=Database(Path(d)/"nvm.db"); db.migrate(); seed(db)
        f=VendingService(db)
        f.payment.financial.credit("pm-acct",10000,idempotency_key="pm-credit")
        tx=f.begin("pm-01","water","pm-nfc","pm-acct","pm-nfc-1","NFC","local")
        assert tx["payment_method"]=="NFC"
        assert tx["payment_provider"]=="local"
        assert tx["base_amount"]==5000
        assert tx["discount_amount"]==0
        assert tx["amount"]==5000
        assert tx["payment_status"]=="pending"
        done=f.dispense(f.authorize(tx["transaction_id"])["transaction_id"],True)
        assert done["payment_status"]=="completed"

def test_vending_qris_is_stored_separately_but_not_activated():
    with TemporaryDirectory() as d:
        db=Database(Path(d)/"nvm.db"); db.migrate(); seed(db)
        f=VendingService(db)
        tx=f.begin("pm-01","water","pm-nfc","pm-acct","pm-qris-1","QRIS","provider-x")
        assert tx["payment_method"]=="QRIS"
        assert tx["payment_provider"]=="provider-x"
        with pytest.raises(ValueError, match="qris_payment_provider_not_activated"):
            f.authorize(tx["transaction_id"])
        failed=f.get(tx["transaction_id"])
        assert failed["payment_status"]=="failed"
        assert failed["status"]=="failed"

def test_vending_rejects_invalid_method_provider_pair():
    with TemporaryDirectory() as d:
        db=Database(Path(d)/"nvm.db"); db.migrate(); seed(db)
        f=VendingService(db)
        with pytest.raises(ValueError, match="invalid_nfc_provider"):
            f.begin("pm-01","water","pm-nfc","pm-acct","pm-invalid-1","NFC","provider-x")
