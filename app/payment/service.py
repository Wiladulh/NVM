from uuid import uuid4
from app.identity.service import IdentityService

class PaymentService:
    def __init__(self, db):
        self.db = db
        self.identity = IdentityService(db)

    def pay(self, credential_id, account_id, amount, reference=None,
            method="NFC", provider="local", idempotency_key=None):
        if amount <= 0:
            raise ValueError("amount must be positive")
        allowed_methods = {"NFC", "QRIS", "CASH"}
        if method not in allowed_methods:
            raise ValueError("unsupported_payment_method")
        if idempotency_key:
            with self.db.connect() as c:
                row = c.execute(
                    "SELECT transaction_id,status,amount FROM payment_transactions WHERE idempotency_key=?",
                    (idempotency_key,),
                ).fetchone()
                if row:
                    return dict(row)

        auth = self.identity.authorize_credential(credential_id)
        if not auth["authorized"]:
            raise PermissionError(auth["reason"])

        tx = reference or "pay-" + uuid4().hex
        with self.db.connect() as c:
            if idempotency_key:
                row = c.execute(
                    "SELECT transaction_id,status,amount FROM payment_transactions WHERE idempotency_key=?",
                    (idempotency_key,),
                ).fetchone()
                if row:
                    return dict(row)

            balance = c.execute(
                "SELECT COALESCE(SUM(CASE WHEN direction='credit' THEN amount ELSE -amount END),0) "
                "FROM financial_ledger WHERE account_id=?",
                (account_id,),
            ).fetchone()[0]
            if balance < amount:
                raise ValueError("insufficient_balance")

            c.execute(
                """INSERT INTO payment_transactions
                   (transaction_id,credential_id,account_id,amount,status,method,provider,
                    idempotency_key)
                   VALUES(?,?,?,?,?,?,?,?)""",
                (tx, credential_id, account_id, amount, "completed", method, provider, idempotency_key),
            )
            c.execute(
                "INSERT INTO financial_ledger(account_id,direction,amount,reference) VALUES(?,?,?,?)",
                (account_id, "debit", amount, tx),
            )
            c.execute(
                "INSERT INTO audit_events(event_type,entity_type,entity_id,detail) VALUES(?,?,?,?)",
                ("payment", "payment_transaction", tx, f"completed:{method}:{provider}"),
            )
            c.commit()
        return {"transaction_id": tx, "status": "completed", "amount": amount,
                "method": method, "provider": provider}
