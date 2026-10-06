from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.identity.service import IdentityService
from app.payment.service import PaymentService
from app.financial.service import FinancialService
from app.vending.service import VendingService

class PaymentRequest(BaseModel):
    credential_id: str
    account_id: str
    amount: int
    reference: str | None = None
    method: str = "NFC"
    provider: str = "local"
    idempotency_key: str | None = None
    device_id: str | None = None
    pin: str | None = None

class PinRequest(BaseModel):
    pin: str

class DeviceHeartbeatRequest(BaseModel):
    device_type: str
    status: str = "active"

class FinancialRequest(BaseModel):
    amount: int
    reference: str | None = None
    idempotency_key: str | None = None

class VendingRegisterRequest(BaseModel):
    machine_id: str
    name: str
    location: str = ""
    device_id: str | None = None
    status: str = "active"

class VendingUpdateRequest(BaseModel):
    name: str | None = None
    location: str | None = None
    device_id: str | None = None
    status: str | None = None

class VendingProductRequest(BaseModel):
    product_id: str
    name: str
    price: int
    stock: int
    enabled: bool = True
    slot: int | None = None
    capacity: int | None = None
    servo_channel: int | None = None

class VendingBeginRequest(BaseModel):
    product_id: str
    credential_id: str
    account_id: str
    idempotency_key: str

class VendingDispenseRequest(BaseModel):
    success: bool = True

def build_router(db):
    r = APIRouter(prefix="/api/v1")
    identity = IdentityService(db)
    payments = PaymentService(db)
    financial = FinancialService(db)
    vending = VendingService(db)

    @r.get("/health")
    def health(): return {"status": "ok", "service": "nvm"}

    @r.get("/system")
    def system(): return {"service": "nvm", "api_version": "v1"}

    @r.get("/audit")
    def audit(limit: int = 100):
        limit=max(1,min(limit,500))
        with db.connect() as c:
            rows=c.execute("SELECT id,event_type,entity_type,entity_id,detail,created_at FROM audit_events ORDER BY id DESC LIMIT ?",(limit,)).fetchall()
        return {"events":[dict(x) for x in rows]}

    @r.get("/devices/{device_id}/events")
    def device_events(device_id,limit:int=100):
        limit=max(1,min(limit,500))
        with db.connect() as c:
            rows=c.execute("SELECT id,device_id,event_type,payload,created_at FROM device_events WHERE device_id=? ORDER BY id DESC LIMIT ?",(device_id,limit)).fetchall()
        return {"device_id":device_id,"events":[dict(x) for x in rows]}

    @r.get("/dashboard")
    def dashboard():
        with db.connect() as c:
            members=c.execute("SELECT member_id,name,status,created_at FROM identity_members ORDER BY created_at DESC").fetchall()
            accounts=c.execute("""SELECT a.account_id,a.member_id,m.name AS member_name,a.account_type,a.status,a.created_at
                   FROM financial_accounts a JOIN identity_members m ON m.member_id=a.member_id ORDER BY a.created_at DESC""").fetchall()
            payments_rows=c.execute("""SELECT transaction_id,credential_id,account_id,amount,status,method,provider,device_id,created_at
                   FROM payment_transactions ORDER BY created_at DESC LIMIT 50""").fetchall()
            loans=c.execute("""SELECT loan_id,member_id,principal,installment_amount,remaining_balance,status,created_at
                   FROM loan_accounts ORDER BY created_at DESC LIMIT 50""").fetchall()
            machines=c.execute("SELECT machine_id,name,status,location,device_id,NULL AS last_seen FROM vending_machines ORDER BY name").fetchall()
            products=c.execute("""SELECT product_id,machine_id,name,price,stock,capacity,slot,servo_channel,enabled
                   FROM vending_products ORDER BY machine_id,slot,product_id""").fetchall()
            devices=c.execute("SELECT device_id,device_type,status,last_seen FROM device_registry ORDER BY device_id").fetchall()
        return {"members":[dict(x) for x in members],
                "accounts":[{**dict(x),"balance":financial.balance(x["account_id"])} for x in accounts],
                "payments":[dict(x) for x in payments_rows],"loans":[dict(x) for x in loans],
                "machines":[dict(x) for x in machines],"products":[dict(x) for x in products],
                "devices":[dict(x) for x in devices]}

    @r.post("/members/{member_id}/pin")
    def set_member_pin(member_id,q:PinRequest):
        try:return identity.set_pin(member_id,q.pin)
        except ValueError as e:raise HTTPException(400,str(e))

    @r.post("/devices/{device_id}/heartbeat")
    def device_heartbeat(device_id,q:DeviceHeartbeatRequest):
        if not device_id.strip(): raise HTTPException(400,"device_id_required")
        if not q.device_type.strip(): raise HTTPException(400,"device_type_required")
        with db.connect() as c:
            c.execute("""INSERT INTO device_registry(device_id,device_type,status,last_seen)
                   VALUES(?,?,?,CURRENT_TIMESTAMP) ON CONFLICT(device_id) DO UPDATE SET device_type=excluded.device_type,
                   status=excluded.status,last_seen=CURRENT_TIMESTAMP""",(device_id,q.device_type,q.status))
            c.execute("INSERT INTO device_events(device_id,event_type,payload) VALUES(?,?,?)",(device_id,"heartbeat",q.model_dump_json()))
            c.commit()
        return {"device_id":device_id,"device_type":q.device_type,"status":q.status}

    @r.post("/access/{credential_id}")
    def access(credential_id):
        result=identity.authorize_credential(credential_id)
        with db.connect() as c:
            c.execute("INSERT INTO identity_access_events(credential_id,member_id,result,reason) VALUES(?,?,?,?)",
                      (credential_id,result.get("member_id"),"allowed" if result["authorized"] else "denied",result["reason"]))
            c.commit()
        return result

    @r.get("/credentials/{credential_id}/account")
    def credential_account(credential_id):
        result=identity.account_for_credential(credential_id)
        if not result["authorized"]: raise HTTPException(404,result["reason"])
        return result

    @r.get("/accounts/{account_id}/balance")
    def account_balance(account_id):
        try:return {"account_id":account_id,"balance":financial.balance(account_id)}
        except ValueError as e:raise HTTPException(404,str(e))

    @r.get("/accounts/{account_id}/ledger")
    def account_ledger(account_id,limit:int=100):
        try:return {"account_id":account_id,"entries":financial.ledger(account_id,limit)}
        except ValueError as e:raise HTTPException(404,str(e))

    @r.post("/accounts/{account_id}/credit")
    def account_credit(account_id,q:FinancialRequest):
        try:return financial.credit(account_id,q.amount,q.reference,q.idempotency_key)
        except ValueError as e:
            code=str(e); raise HTTPException(409 if code=="insufficient_balance" else 400,code)

    @r.post("/accounts/{account_id}/debit")
    def account_debit(account_id,q:FinancialRequest):
        try:return financial.debit(account_id,q.amount,q.reference,q.idempotency_key)
        except ValueError as e:
            code=str(e); raise HTTPException(409 if code=="insufficient_balance" else 400,code)

    @r.get("/vending")
    def vending_list():
        return {"machines": vending.machines()}

    @r.post("/vending")
    def vending_register(q:VendingRegisterRequest):
        try:return vending.register(q.machine_id,q.name,q.location,q.device_id,q.status)
        except ValueError as e: raise HTTPException(409 if "already" in str(e) else 400,str(e))

    @r.get("/vending/{machine_id}")
    def vending_detail(machine_id):
        try:return {"machine":vending.machine(machine_id),"slots":vending.slots(machine_id)}
        except ValueError as e:raise HTTPException(404,str(e))

    @r.patch("/vending/{machine_id}")
    def vending_update(machine_id,q:VendingUpdateRequest):
        try:return vending.update_machine(machine_id,q.name,q.location,q.device_id,q.status)
        except ValueError as e:raise HTTPException(409 if "already" in str(e) else 400,str(e))

    @r.post("/vending/{machine_id}/enable")
    def vending_enable(machine_id):
        try:return vending.set_status(machine_id,"active")
        except ValueError as e:raise HTTPException(404 if str(e)=="machine_not_found" else 400,str(e))

    @r.post("/vending/{machine_id}/disable")
    def vending_disable(machine_id):
        try:return vending.set_status(machine_id,"disabled")
        except ValueError as e:raise HTTPException(404 if str(e)=="machine_not_found" else 400,str(e))

    @r.get("/vending/{machine_id}/products")
    def vending_products(machine_id):
        try:return {"machine":vending.machine(machine_id),"products":vending.products(machine_id)}
        except ValueError as e:raise HTTPException(404,str(e))

    @r.put("/vending/{machine_id}/products/{product_id}")
    def vending_product(machine_id,product_id,q:VendingProductRequest):
        if q.product_id!=product_id:raise HTTPException(400,"product_id_mismatch")
        try:return vending.upsert_product(machine_id,product_id,q.name,q.price,q.stock,q.enabled,q.slot,q.capacity,q.servo_channel)
        except ValueError as e:raise HTTPException(409 if "slot" in str(e) or str(e)=="no_free_slot" else 400,str(e))

    @r.post("/vending/{machine_id}/transactions")
    def vending_begin(machine_id,q:VendingBeginRequest):
        try:return vending.begin(machine_id,q.product_id,q.credential_id,q.account_id,q.idempotency_key)
        except ValueError as e:raise HTTPException(409 if str(e) in {"out_of_stock","machine_not_active"} else 400,str(e))

    @r.post("/vending/transactions/{transaction_id}/authorize")
    def vending_authorize(transaction_id):
        try:return vending.authorize(transaction_id)
        except PermissionError as e:raise HTTPException(403,str(e))
        except ValueError as e:raise HTTPException(400,str(e))

    @r.post("/vending/transactions/{transaction_id}/dispense")
    def vending_dispense(transaction_id,q:VendingDispenseRequest):
        try:return vending.dispense(transaction_id,q.success)
        except ValueError as e:raise HTTPException(409,str(e))

    @r.post("/payments")
    def payment(q:PaymentRequest):
        try:return payments.pay(**q.model_dump())
        except PermissionError as e:raise HTTPException(403,str(e))
        except ValueError as e:
            code=str(e);raise HTTPException(409 if code=="insufficient_balance" else 400,code)

    @r.post("/cashier/payments")
    def cashier_payment(q:PaymentRequest):
        if q.device_id is None:raise HTTPException(400,"device_id_required")
        try:
            with db.connect() as c:
                device=c.execute("SELECT device_id,status FROM device_registry WHERE device_id=?",(q.device_id,)).fetchone()
            if not device or device["status"]!="active":raise HTTPException(403,"device_not_active")
            if q.method!="NFC":raise HTTPException(400,"cashier_requires_nfc")
            return payments.pay(**q.model_dump())
        except PermissionError as e:raise HTTPException(403,str(e))
        except ValueError as e:
            code=str(e);raise HTTPException(409 if code=="insufficient_balance" else 400,code)

    return r
