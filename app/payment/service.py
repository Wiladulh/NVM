from uuid import uuid4
from app.identity.service import IdentityService
from app.financial.service import FinancialService

class PaymentService:
    def __init__(self, db):
        self.db = db
        self.identity = IdentityService(db)
        self.financial = FinancialService(db)

    def pay(self, credential_id, account_id, amount, reference=None,
            method="NFC", provider="local", idempotency_key=None, device_id=None):
        if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
            raise ValueError("amount_must_be_positive_integer")
        if method not in {"NFC", "QRIS", "CASH"}:
            raise ValueError("unsupported_payment_method")
        auth = self.identity.authorize_credential(credential_id)
        if not auth["authorized"]:
            raise PermissionError(auth["reason"])
        if auth.get("member_id"):
            with self.db.connect() as c:
                account = c.execute("SELECT member_id FROM financial_accounts WHERE account_id=?",
                                    (account_id,)).fetchone()
            if not account:
                raise ValueError("account_not_found")
            if account["member_id"] != auth["member_id"]:
                raise PermissionError("credential_account_mismatch")
        with self.db.connect() as c:
            if idempotency_key:
                row = c.execute("SELECT transaction_id,status,amount,method,provider FROM payment_transactions WHERE idempotency_key=?",
                                (idempotency_key,)).fetchone()
                if row:
                    return dict(row)
            tx = reference or "pay-" + uuid4().hex
            financial_tx = self.financial.debit_on_connection(
                c, account_id, amount, reference=tx, idempotency_key="payment:" + tx
            )
            c.execute("""INSERT INTO payment_transactions
                   (transaction_id,credential_id,account_id,amount,status,method,provider,idempotency_key,device_id)
                   VALUES(?,?,?,?,?,?,?,?,?)""",
                (tx, credential_id, account_id, amount, "completed", method, provider, idempotency_key, device_id))
            c.execute("INSERT INTO audit_events(event_type,entity_type,entity_id,detail) VALUES(?,?,?,?)",
                      ("payment", "payment_transaction", tx,
                       f"completed:{method}:{provider}:device={device_id or '-'}:financial={financial_tx['transaction_id']}"))
            c.commit()
        return {"transaction_id": tx, "status": "completed", "amount": amount,
                "method": method, "provider": provider, "device_id": device_id}
