from pathlib import Path
from tempfile import TemporaryDirectory
from app.core.db import Database
from app.payment.service import PaymentService

def seed(db):
    with db.connect() as c:
        c.execute("INSERT INTO identity_members(member_id,name) VALUES('member-1','Test')")
        c.execute("INSERT INTO identity_credentials(credential_id,member_id,credential_type) VALUES('cred-1','member-1','nfc')")
        c.execute("INSERT INTO financial_accounts(account_id,member_id,account_type) VALUES('acct-1','member-1','savings')")
        c.execute("INSERT INTO financial_ledger(account_id,direction,amount,reference) VALUES('acct-1','credit',100000,'seed')")
        c.commit()

def test_nfc_payment_idempotency():
    with TemporaryDirectory() as d:
        db=Database(Path(d)/"nvm.db"); db.migrate(); seed(db)
        p=PaymentService(db)
        a=p.pay("cred-1","acct-1",25000,method="NFC",idempotency_key="idem-1")
        b=p.pay("cred-1","acct-1",25000,method="NFC",idempotency_key="idem-1")
        assert a["transaction_id"] == b["transaction_id"]
        with db.connect() as c:
            balance=c.execute("SELECT COALESCE(SUM(CASE WHEN direction='credit' THEN amount ELSE -amount END),0) FROM financial_ledger WHERE account_id='acct-1'").fetchone()[0]
        assert balance == 75000

def test_qris_is_a_supported_future_method():
    with TemporaryDirectory() as d:
        db=Database(Path(d)/"nvm.db"); db.migrate(); seed(db)
        result=PaymentService(db).pay("cred-1","acct-1",1000,method="QRIS",provider="future-qris",idempotency_key="q-1")
        assert result["method"] == "QRIS"
        assert result["provider"] == "future-qris"
