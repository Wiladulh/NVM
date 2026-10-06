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
    device_id: str | None = None

class DeviceHeartbeatRequest(BaseModel):
    device_type: str
    status: str = "active"

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

    @r.get("/dashboard")
    def dashboard():
        with db.connect() as c:
            members = c.execute("SELECT member_id,name,status,created_at FROM identity_members ORDER BY created_at DESC").fetchall()
            accounts = c.execute("""SELECT a.account_id,a.member_id,m.name AS member_name,
                          a.account_type,a.status,a.created_at
                   FROM financial_accounts a JOIN identity_members m ON m.member_id=a.member_id
                   ORDER BY a.created_at DESC""").fetchall()
            payments_rows = c.execute("""SELECT transaction_id,credential_id,account_id,amount,status,method,provider,device_id,created_at
                   FROM payment_transactions ORDER BY created_at DESC LIMIT 50""").fetchall()
            loans = c.execute("""SELECT loan_id,member_id,principal,installment_amount,
                          remaining_balance,status,created_at
                   FROM loan_accounts ORDER BY created_at DESC LIMIT 50""").fetchall()
            machines = c.execute("SELECT machine_id,name,status,NULL AS last_seen FROM vending_machines ORDER BY name").fetchall()
            devices = c.execute("SELECT device_id,device_type,status,last_seen FROM device_registry ORDER BY device_id").fetchall()
        return {
            "members": [dict(x) for x in members],
            "accounts": [{**dict(x), "balance": financial.balance(x["account_id"])} for x in accounts],
            "payments": [dict(x) for x in payments_rows],
            "loans": [dict(x) for x in loans],
            "machines": [dict(x) for x in machines],
            "devices": [dict(x) for x in devices],
        }

    @r.post("/devices/{device_id}/heartbeat")
    def device_heartbeat(device_id, q: DeviceHeartbeatRequest):
        if not device_id.strip():
            raise HTTPException(400, "device_id_required")
        if not q.device_type.strip():
            raise HTTPException(400, "device_type_required")
        with db.connect() as c:
            c.execute("""INSERT INTO device_registry(device_id,device_type,status,last_seen)
                   VALUES(?,?,?,CURRENT_TIMESTAMP)
                   ON CONFLICT(device_id) DO UPDATE SET device_type=excluded.device_type,
                     status=excluded.status,last_seen=CURRENT_TIMESTAMP""",
                (device_id, q.device_type, q.status))
            c.execute("INSERT INTO device_events(device_id,event_type,payload) VALUES(?,?,?)",
                      (device_id, "heartbeat", q.model_dump_json()))
            c.commit()
        return {"device_id": device_id, "device_type": q.device_type, "status": q.status}

    @r.post("/access/{credential_id}")
    def access(credential_id):
        result = identity.authorize_credential(credential_id)
        with db.connect() as c:
            c.execute("INSERT INTO identity_access_events(credential_id,member_id,result,reason) VALUES(?,?,?,?)",
                      (credential_id, result.get("member_id"),
                       "allowed" if result["authorized"] else "denied", result["reason"]))
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

    @r.post("/cashier/payments")
    def cashier_payment(q: PaymentRequest):
        if q.device_id is None:
            raise HTTPException(400, "device_id_required")
        try:
            with db.connect() as c:
                device = c.execute("SELECT device_id,status FROM device_registry WHERE device_id=?",
                                   (q.device_id,)).fetchone()
            if not device or device["status"] != "active":
                raise HTTPException(403, "device_not_active")
            if q.method != "NFC":
                raise HTTPException(400, "cashier_requires_nfc")
            return payments.pay(**q.model_dump())
        except PermissionError as e:
            raise HTTPException(403, str(e))
        except ValueError as e:
            raise HTTPException(400, str(e))

    return r
