from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.identity.service import IdentityService
from app.payment.service import PaymentService
from app.financial.service import FinancialService

class PaymentRequest(BaseModel):
    credential_id: str
    account_id: str
    amount: int
    reference: str | None = None
    method: str = "NFC"
    provider: str = "local"
    idempotency_key: str | None = None

class FinancialRequest(BaseModel):
    amount: int
    reference: str | None = None
    idempotency_key: str | None = None

def build_router(db):
    r = APIRouter(prefix="/api/v1")
    identity = IdentityService(db)
    payments = PaymentService(db)
    financial = FinancialService(db)

    @r.get("/health")
    def health():
        return {"status": "ok", "service": "nvm"}

    @r.get("/system")
    def system():
        return {"service": "nvm", "api_version": "v1"}

    @r.post("/access/{credential_id}")
    def access(credential_id):
        result = identity.authorize_credential(credential_id)
        with db.connect() as c:
            c.execute(
                "INSERT INTO identity_access_events(credential_id,member_id,result,reason) VALUES(?,?,?,?)",
                (credential_id, result.get("member_id"),
                 "allowed" if result["authorized"] else "denied", result["reason"]),
            )
            c.commit()
        return result

    @r.get("/accounts/{account_id}/balance")
    def account_balance(account_id):
        try:
            return {"account_id": account_id, "balance": financial.balance(account_id)}
        except ValueError as e:
            raise HTTPException(404, str(e))

    @r.get("/accounts/{account_id}/ledger")
    def account_ledger(account_id, limit: int = 100):
        try:
            return {"account_id": account_id, "entries": financial.ledger(account_id, limit)}
        except ValueError as e:
            raise HTTPException(404, str(e))

    @r.post("/accounts/{account_id}/credit")
    def account_credit(account_id, q: FinancialRequest):
        try:
            return financial.credit(account_id, q.amount, q.reference, q.idempotency_key)
        except ValueError as e:
            code = str(e)
            raise HTTPException(409 if code == "insufficient_balance" else 400, code)

    @r.post("/accounts/{account_id}/debit")
    def account_debit(account_id, q: FinancialRequest):
        try:
            return financial.debit(account_id, q.amount, q.reference, q.idempotency_key)
        except ValueError as e:
            code = str(e)
            raise HTTPException(409 if code == "insufficient_balance" else 400, code)

    @r.post("/payments")
    def payment(q: PaymentRequest):
        try:
            return payments.pay(**q.model_dump())
        except PermissionError as e:
            raise HTTPException(403, str(e))
        except ValueError as e:
            raise HTTPException(400, str(e))

    return r
