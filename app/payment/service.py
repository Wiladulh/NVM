from uuid import uuid4
from app.identity.service import IdentityService
class PaymentService:
    def __init__(self,db): self.db=db; self.identity=IdentityService(db)
    def pay(self,credential_id,account_id,amount,reference=None):
        if amount<=0: raise ValueError("amount must be positive")
        a=self.identity.authorize_credential(credential_id)
        if not a["authorized"]: raise PermissionError(a["reason"])
        tx=reference or "pay-"+uuid4().hex
        with self.db.connect() as c:
            bal=c.execute("SELECT COALESCE(SUM(CASE WHEN direction='credit' THEN amount ELSE -amount END),0) FROM financial_ledger WHERE account_id=?",(account_id,)).fetchone()[0]
            if bal<amount: raise ValueError("insufficient_balance")
            c.execute("INSERT INTO payment_transactions(transaction_id,credential_id,account_id,amount,status) VALUES(?,?,?,?,?)",(tx,credential_id,account_id,amount,"completed"))
            c.execute("INSERT INTO financial_ledger(account_id,direction,amount,reference) VALUES(?,?,?,?)",(account_id,"debit",amount,tx))
            c.execute("INSERT INTO audit_events(event_type,entity_type,entity_id,detail) VALUES(?,?,?,?)",("payment","payment_transaction",tx,"completed")); c.commit()
        return {"transaction_id":tx,"status":"completed","amount":amount}
