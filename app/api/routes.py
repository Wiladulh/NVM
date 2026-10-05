from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.identity.service import IdentityService
from app.payment.service import PaymentService

class PaymentRequest(BaseModel):
    credential_id: str
    account_id: str
    amount: int
    reference: str | None = None
    method: str = "NFC"
    provider: str = "local"
    idempotency_key: str | None = None

def build_router(db):
    r = APIRouter(prefix="/api/v1")
    identity = IdentityService(db)
    payments = PaymentService(db)

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

    @r.post("/payments")
    def payment(q: PaymentRequest):
        try:
            return payments.pay(**q.model_dump())
        except PermissionError as e:
            raise HTTPException(403, str(e))
        except ValueError as e:
            raise HTTPException(400, str(e))

    return r
