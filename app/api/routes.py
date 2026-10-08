from fastapi import APIRouter, HTTPException, Header, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel
import hashlib
import secrets
from app.identity.service import IdentityService
from app.identity.management import MemberManagementService
from app.device.management import DeviceManagementService
from app.vending.promo import PromotionService
from app.payment.service import PaymentService
from app.financial.service import FinancialService
from app.vending.service import VendingService
from app.core.backup import export_excel, export_rows_excel, create_native_backup, restore_native_backup, import_excel
from pathlib import Path
from uuid import uuid4

class PaymentRequest(BaseModel):
    credential_id: str
    account_id: str | None = None
    amount: int | None = None
    reference: str | None = None
    method: str = "NFC"
    provider: str = "local"
    idempotency_key: str | None = None
    device_id: str | None = None
    pin: str | None = None
    original_amount: int | None = None
    discount_amount: int = 0
    promo_id: str | None = None

class PinRequest(BaseModel):
    pin: str

class MemberCreateRequest(BaseModel):
    name: str
    nik: str | None = None
    address: str | None = None

class MemberUpdateRequest(BaseModel):
    name: str | None = None
    nik: str | None = None
    address: str | None = None
    status: str | None = None

class NfcCardRequest(BaseModel):
    card_uid: str
    credential_id: str | None = None

class PromoRequest(BaseModel):
    scope: str
    machine_id: str | None = None
    product_id: str | None = None
    payment_method: str
    payment_provider: str | None = None
    discount_percent: float
    starts_at: str | None = None
    ends_at: str | None = None
    priority: int = 0
    enabled: bool = True

class PromoUpdateRequest(BaseModel):
    scope: str | None = None
    machine_id: str | None = None
    product_id: str | None = None
    payment_method: str | None = None
    payment_provider: str | None = None
    discount_percent: float | None = None
    starts_at: str | None = None
    ends_at: str | None = None
    priority: int | None = None
    enabled: bool | None = None

class DeviceHeartbeatRequest(BaseModel):
    device_type: str
    status: str = "active"

class DeviceProvisionRequest(BaseModel):
    device_type: str

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
    account_id: str | None = None
    idempotency_key: str
    payment_method: str = "NFC"
    payment_provider: str = "local"

class VendingDispenseRequest(BaseModel):
    success: bool = True

class CashierDepositRequest(BaseModel):
    credential_id: str
    amount: int
    operator_pin: str
    member_pin: str
    idempotency_key: str

class OperatorPinRequest(BaseModel):
    pin: str

def build_router(db, app_settings=None):
    r = APIRouter(prefix="/api/v1")
    if app_settings is None:
        app_settings = __import__("app.core.config",fromlist=["get_settings"]).get_settings()
    identity = IdentityService(db)
    members = MemberManagementService(db)
    devices = DeviceManagementService(db)
    promos = PromotionService(db)
    payments = PaymentService(db)
    financial = FinancialService(db)
    vending = VendingService(db)

    def require_device(device_id: str, device_key: str | None):
        if not device_key:
            raise HTTPException(401,"device_auth_required")
        with db.connect() as c:
            row=c.execute("SELECT status,auth_key_hash FROM device_registry WHERE device_id=?",(device_id,)).fetchone()
        if not row or row["status"]!="active":
            raise HTTPException(403,"device_not_active")
        if not row["auth_key_hash"]:
            raise HTTPException(403,"device_not_provisioned")
        got=hashlib.sha256(device_key.encode("utf-8")).hexdigest()
        if not secrets.compare_digest(got,row["auth_key_hash"]):
            raise HTTPException(403,"invalid_device_key")
        return True


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
            cashier_count=c.execute(
                "SELECT COUNT(*) FROM payment_transactions WHERE transaction_source='CASHIER' AND status='completed'"
            ).fetchone()[0]
            cashier_out=c.execute(
                "SELECT COALESCE(SUM(COALESCE(final_amount,amount)),0) FROM payment_transactions "
                "WHERE transaction_source='CASHIER' AND status='completed' AND created_at>=date('now')"
            ).fetchone()[0]
            cashier_in=c.execute(
                "SELECT COALESCE(SUM(amount),0) FROM cashier_deposits "
                "WHERE status='completed' AND created_at>=date('now')"
            ).fetchone()[0]
            vending_count=c.execute(
                "SELECT COUNT(*) FROM vending_transactions WHERE transaction_source='VENDING' AND status='completed'"
            ).fetchone()[0]
            vending_in=c.execute(
                "SELECT COALESCE(SUM(amount),0) FROM vending_transactions "
                "WHERE transaction_source='VENDING' AND status='completed' AND created_at>=date('now')"
            ).fetchone()[0]
        return {"members":[dict(x) for x in members],
                "accounts":[{**dict(x),"balance":financial.balance(x["account_id"])} for x in accounts],
                "payments":[dict(x) for x in payments_rows],"loans":[dict(x) for x in loans],
                "machines":[dict(x) for x in machines],"products":[dict(x) for x in products],
                "devices":[dict(x) for x in devices],
                "stats":{
                    "cashier_transactions":cashier_count,
                    "cashier_money_in_today":cashier_in,
                    "cashier_money_out_today":cashier_out,
                    "vending_transactions":vending_count,
                    "vending_money_in_today":vending_in
                }}

    def require_admin(token):
        configured = getattr(app_settings,"admin_token","")
        if not configured or not token or not secrets.compare_digest(token,configured):
            raise HTTPException(401,"admin_auth_required")

    @r.get("/members")
    def members_list(include_deleted: bool = False, x_nvm_admin_token: str | None = Header(default=None)):
        require_admin(x_nvm_admin_token)
        return {"members": members.list(include_deleted)}

    @r.post("/members")
    def member_create(q: MemberCreateRequest, x_nvm_admin_token: str | None = Header(default=None)):
        require_admin(x_nvm_admin_token)
        member_id = "member-" + uuid4().hex
        try:
            return members.create(member_id,q.name,q.nik,q.address)
        except ValueError as e:
            raise HTTPException(409 if "already" in str(e) else 400,str(e))

    @r.get("/members/{member_id}")
    def member_get(member_id, x_nvm_admin_token: str | None = Header(default=None)):
        require_admin(x_nvm_admin_token)
        result = members.get(member_id)
        if result is None:
            raise HTTPException(404,"member_not_found")
        return result

    @r.patch("/members/{member_id}")
    def member_update(member_id,q: MemberUpdateRequest,x_nvm_admin_token: str | None = Header(default=None)):
        require_admin(x_nvm_admin_token)
        try:
            return members.update(member_id,q.name,q.nik,q.address,q.status)
        except ValueError as e:
            code=str(e)
            raise HTTPException(409 if "already" in code else 400,code)

    @r.delete("/members/{member_id}")
    def member_delete(member_id,x_nvm_admin_token: str | None = Header(default=None)):
        require_admin(x_nvm_admin_token)
        try:
            return members.soft_delete(member_id)
        except ValueError as e:
            raise HTTPException(404,str(e))

    @r.post("/members/{member_id}/nfc-cards")
    def member_add_nfc(member_id,q: NfcCardRequest,x_nvm_admin_token: str | None = Header(default=None)):
        require_admin(x_nvm_admin_token)
        try:
            return members.add_card(member_id,q.card_uid,q.credential_id)
        except ValueError as e:
            code=str(e)
            raise HTTPException(409 if "already" in code else 400,code)

    @r.post("/members/{member_id}/nfc-cards/{card_id}/revoke")
    def member_revoke_nfc(member_id,card_id,x_nvm_admin_token: str | None = Header(default=None)):
        require_admin(x_nvm_admin_token)
        try:
            result = members.revoke_card(card_id)
            if result["member_id"] != member_id:
                raise HTTPException(404,"nfc_card_not_found")
            return result
        except ValueError as e:
            raise HTTPException(404,str(e))

    @r.get("/nfc/cards/{card_uid}")
    def nfc_card_resolve(card_uid,x_nvm_admin_token: str | None = Header(default=None)):
        require_admin(x_nvm_admin_token)
        result = members.resolve_card(card_uid)
        if result is None:
            raise HTTPException(404,"nfc_card_not_found")
        return result

    @r.post("/members/{member_id}/pin")
    def set_member_pin(member_id,q:PinRequest):
        try:return identity.set_pin(member_id,q.pin)
        except ValueError as e:raise HTTPException(400,str(e))

    @r.get("/devices")
    def devices_list(include_deleted: bool = False, x_nvm_admin_token: str | None = Header(default=None)):
        require_admin(x_nvm_admin_token)
        return {"devices": devices.list(include_deleted)}

    @r.get("/devices/{device_id}")
    def device_get(device_id,x_nvm_admin_token: str | None = Header(default=None)):
        require_admin(x_nvm_admin_token)
        result = devices.get(device_id)
        if result is None:
            raise HTTPException(404,"device_not_found")
        return result

    @r.patch("/devices/{device_id}")
    def device_update(device_id,q: DeviceHeartbeatRequest,x_nvm_admin_token: str | None = Header(default=None)):
        require_admin(x_nvm_admin_token)
        try:
            return devices.update(device_id,q.device_type,q.status)
        except ValueError as e:
            raise HTTPException(400,str(e))

    @r.delete("/devices/{device_id}")
    def device_delete(device_id,x_nvm_admin_token: str | None = Header(default=None)):
        require_admin(x_nvm_admin_token)
        try:
            return devices.soft_delete(device_id)
        except ValueError as e:
            raise HTTPException(404,str(e))

    @r.post("/devices/{device_id}/provision")
    def device_provision(device_id,q:DeviceProvisionRequest,x_nvm_admin_token: str | None = Header(default=None)):
        if not getattr(app_settings,"admin_token","") or not x_nvm_admin_token or not secrets.compare_digest(x_nvm_admin_token,getattr(app_settings,"admin_token","")):
            raise HTTPException(401,"admin_auth_required")
        if not device_id.strip() or not q.device_type.strip():
            raise HTTPException(400,"device_id_and_type_required")
        key=secrets.token_urlsafe(32)
        digest=hashlib.sha256(key.encode("utf-8")).hexdigest()
        with db.connect() as c:
            c.execute("""INSERT INTO device_registry(device_id,device_type,status,last_seen,auth_key_hash,auth_key_hint)
                         VALUES(?,?, 'active',NULL,?,?)
                         ON CONFLICT(device_id) DO UPDATE SET device_type=excluded.device_type,
                         status='active',auth_key_hash=excluded.auth_key_hash,auth_key_hint=excluded.auth_key_hint""",
                      (device_id,q.device_type,digest,key[-6:]))
            c.commit()
        return {"device_id":device_id,"device_type":q.device_type,"device_key":key}

    @r.post("/devices/{device_id}/heartbeat")
    def device_heartbeat(device_id,q:DeviceHeartbeatRequest,x_nvm_device_key: str | None = Header(default=None)):
        if not device_id.strip(): raise HTTPException(400,"device_id_required")
        if not q.device_type.strip(): raise HTTPException(400,"device_type_required")
        require_device(device_id,x_nvm_device_key)
        with db.connect() as c:
            c.execute("""UPDATE device_registry SET device_type=?,status=?,last_seen=CURRENT_TIMESTAMP WHERE device_id=?""",
                      (q.device_type,q.status,device_id))
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

    @r.get("/promotions")
    def promotions_list(machine_id: str | None = None, payment_method: str | None = None,
                         include_disabled: bool = True, x_nvm_admin_token: str | None = Header(default=None)):
        require_admin(x_nvm_admin_token)
        try:
            return {"promotions": promos.list(machine_id,payment_method,include_disabled)}
        except ValueError as e:
            raise HTTPException(400,str(e))

    @r.post("/promotions")
    def promotion_create(q: PromoRequest,x_nvm_admin_token: str | None = Header(default=None)):
        require_admin(x_nvm_admin_token)
        try:
            return promos.create(q.scope,q.machine_id,q.product_id,q.payment_method,
                                 q.payment_provider,q.discount_percent,q.starts_at,q.ends_at,
                                 q.priority,q.enabled)
        except ValueError as e:
            raise HTTPException(400,str(e))

    @r.get("/promotions/resolve")
    def promotion_resolve(machine_id: str,product_id: str,payment_method: str,
                           payment_provider: str | None = None,
                           x_nvm_admin_token: str | None = Header(default=None)):
        require_admin(x_nvm_admin_token)
        try:
            result = promos.resolve(machine_id,product_id,payment_method,payment_provider)
            return {"promotion":result}
        except ValueError as e:
            raise HTTPException(400,str(e))

    @r.get("/promotions/{promo_id}")
    def promotion_get(promo_id,x_nvm_admin_token: str | None = Header(default=None)):
        require_admin(x_nvm_admin_token)
        result = promos.get(promo_id)
        if result is None:
            raise HTTPException(404,"promo_not_found")
        return result

    @r.patch("/promotions/{promo_id}")
    def promotion_update(promo_id,q: PromoUpdateRequest,x_nvm_admin_token: str | None = Header(default=None)):
        require_admin(x_nvm_admin_token)
        try:
            return promos.update(promo_id,**q.model_dump(exclude_none=True))
        except ValueError as e:
            raise HTTPException(400,str(e))

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
    def vending_begin(machine_id,q:VendingBeginRequest,x_nvm_device_key: str | None = Header(default=None)):
        try:
            machine=vending.machine(machine_id)
            if not machine.get("device_id"): raise HTTPException(403,"machine_device_not_configured")
            require_device(machine["device_id"],x_nvm_device_key)
            return vending.begin(machine_id,q.product_id,q.credential_id,q.account_id,q.idempotency_key,q.payment_method,q.payment_provider)
        except ValueError as e:raise HTTPException(409 if str(e) in {"out_of_stock","machine_not_active","qris_payment_provider_not_activated"} else 400,str(e))

    @r.post("/vending/transactions/{transaction_id}/authorize")
    def vending_authorize(transaction_id,x_nvm_device_key: str | None = Header(default=None)):
        try:
            tx=vending.get(transaction_id)
            machine=vending.machine(tx["machine_id"])
            if not machine.get("device_id"): raise HTTPException(403,"machine_device_not_configured")
            require_device(machine["device_id"],x_nvm_device_key)
            return vending.authorize(transaction_id)
        except PermissionError as e:raise HTTPException(403,str(e))
        except ValueError as e:raise HTTPException(400,str(e))

    @r.post("/vending/transactions/{transaction_id}/dispense")
    def vending_dispense(transaction_id,q:VendingDispenseRequest,x_nvm_device_key: str | None = Header(default=None)):
        try:
            tx=vending.get(transaction_id)
            machine=vending.machine(tx["machine_id"])
            if not machine.get("device_id"): raise HTTPException(403,"machine_device_not_configured")
            require_device(machine["device_id"],x_nvm_device_key)
            return vending.dispense(transaction_id,q.success)
        except ValueError as e:raise HTTPException(409,str(e))

    @r.post("/payments")
    def payment(q:PaymentRequest):
        try:return payments.pay(**q.model_dump())
        except PermissionError as e:raise HTTPException(403,str(e))
        except ValueError as e:
            code=str(e)
            raise HTTPException(409 if code in {"insufficient_balance", "idempotency_key_conflict"} else 400,code)

    @r.post("/cashier/operator-pin")
    def cashier_operator_pin(q:OperatorPinRequest,x_nvm_admin_token: str | None = Header(default=None)):
        token=getattr(app_settings,"admin_token","")
        if not token or not x_nvm_admin_token or not secrets.compare_digest(x_nvm_admin_token,token):
            raise HTTPException(401,"admin_auth_required")
        if not q.pin.isdigit() or not 4 <= len(q.pin) <= 6:
            raise HTTPException(400,"pin_must_be_4_to_6_digits")
        salt=secrets.token_hex(16)
        digest=hashlib.pbkdf2_hmac("sha256",q.pin.encode(),salt.encode(),120000).hex()
        with db.connect() as c:
            c.execute("INSERT OR REPLACE INTO system_meta(key,value) VALUES('cashier_operator_pin_hash',?)",(salt+":"+digest,))
            c.execute("INSERT INTO audit_events(event_type,entity_type,entity_id,detail) VALUES(?,?,?,?)",("cashier","operator_pin","system","updated"))
            c.commit()
        return {"status":"pin_updated"}

    def verify_operator_pin(pin):
        with db.connect() as c:
            row=c.execute("SELECT value FROM system_meta WHERE key='cashier_operator_pin_hash'").fetchone()
        if not row or not row["value"] or ":" not in row["value"]: return False
        salt,digest=row["value"].split(":",1)
        got=hashlib.pbkdf2_hmac("sha256",pin.encode(),salt.encode(),120000).hex()
        return secrets.compare_digest(got,digest)

    @r.post("/cashier/deposits")
    def cashier_deposit(q:CashierDepositRequest,x_nvm_device_key: str | None = Header(default=None),x_nvm_device_id: str | None = Header(default=None)):
        if not x_nvm_device_id: raise HTTPException(400,"device_id_required")
        require_device(x_nvm_device_id,x_nvm_device_key)
        if not verify_operator_pin(q.operator_pin): raise HTTPException(403,"invalid_operator_pin")
        if not q.idempotency_key: raise HTTPException(400,"idempotency_key_required")
        if not isinstance(q.amount,int) or q.amount<=0: raise HTTPException(400,"amount_must_be_positive_integer")
        auth=identity.authorize_credential(q.credential_id)
        if not auth["authorized"]: raise HTTPException(403,auth["reason"])
        account=identity.account_for_credential(q.credential_id)
        if not account["authorized"]: raise HTTPException(404,account["reason"])
        try:
            pin_ok=identity.verify_credential_pin(q.credential_id,q.member_pin)
        except PermissionError as e:
            raise HTTPException(403,str(e))
        if not pin_ok: raise HTTPException(403,"invalid_pin")
        with db.connect() as c:
            old=c.execute("SELECT * FROM cashier_deposits WHERE idempotency_key=?",(q.idempotency_key,)).fetchone()
        if old: return dict(old)
        before=financial.balance(account["account_id"])
        fin=financial.credit(account["account_id"],q.amount,reference="cashier-deposit:"+q.idempotency_key,idempotency_key="cashier-deposit:"+q.idempotency_key)
        after=before+q.amount
        tid="cash-"+uuid4().hex
        with db.connect() as c:
            c.execute("""INSERT INTO cashier_deposits
                (transaction_id,device_id,credential_id,member_id,account_id,amount,status,idempotency_key,balance_before,balance_after,completed_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)""",
                (tid,x_nvm_device_id,q.credential_id,account["member_id"],account["account_id"],q.amount,"completed",q.idempotency_key,before,after))
            c.execute("INSERT INTO audit_events(event_type,entity_type,entity_id,detail) VALUES(?,?,?,?)",
                      ("cashier","cashier_deposit",tid,f"deposit:{q.amount}:member={account['member_id']}:device={x_nvm_device_id}"))
            c.commit()
        return {"transaction_id":tid,"status":"completed","member_id":account["member_id"],"account_id":account["account_id"],"amount":q.amount,"balance_before":before,"balance_after":after,"financial_transaction_id":fin["transaction_id"]}

    @r.post("/cashier/payments")
    def cashier_payment(q:PaymentRequest,x_nvm_device_key: str | None = Header(default=None)):
        if q.device_id is None:raise HTTPException(400,"device_id_required")
        try:
            require_device(q.device_id,x_nvm_device_key)
            if q.method!="NFC":raise HTTPException(400,"cashier_requires_nfc")
            if q.provider!="local":raise HTTPException(400,"invalid_nfc_provider")
            result=payments.pay(**q.model_dump())
            with db.connect() as c:
                c.execute("UPDATE payment_transactions SET transaction_source='CASHIER' WHERE transaction_id=?",(result["transaction_id"],))
                c.commit()
            return result
        except PermissionError as e:raise HTTPException(403,str(e))
        except ValueError as e:
            code=str(e)
            raise HTTPException(409 if code in {"insufficient_balance", "idempotency_key_conflict"} else 400,code)

    @r.get("/audit/report")
    def audit_report(source:str="ALL",period:str="day",date:str|None=None,x_nvm_admin_token: str | None = Header(default=None)):
        token=getattr(app_settings,"admin_token","")
        if not token or not x_nvm_admin_token or not secrets.compare_digest(x_nvm_admin_token,token):
            raise HTTPException(401,"admin_auth_required")
        source=source.upper()
        if source not in {"ALL","CASHIER","VENDING"}: raise HTTPException(400,"invalid_source")
        if period not in {"day","week","month"}: raise HTTPException(400,"invalid_period")
        import datetime as dt
        date=date or dt.date.today().isoformat()
        if period=="day":
            start=date; end=date+" 23:59:59"
        elif period=="month":
            y,m=map(int,date[:7].split("-")); start=f"{y:04d}-{m:02d}-01"
            end=f"{y+1:04d}-01-01" if m==12 else f"{y:04d}-{m+1:02d}-01"
        else:
            d=dt.date.fromisoformat(date); monday=d-dt.timedelta(days=d.weekday())
            start=monday.isoformat(); end=(monday+dt.timedelta(days=7)).isoformat()
        queries=[]
        if source in {"ALL","CASHIER"}:
            queries.append("""SELECT transaction_id,created_at,'CASHIER' source,device_id,member_id,account_id,
                              'DEPOSIT' transaction_type,amount,status FROM cashier_deposits""")
        if source in {"ALL","VENDING"}:
            queries.append("""SELECT v.transaction_id,v.created_at,'VENDING' source,m.device_id,v.credential_id,
                              v.account_id,'PURCHASE' transaction_type,v.amount,v.status
                              FROM vending_transactions v LEFT JOIN vending_machines m ON m.machine_id=v.machine_id""")
        sql=" UNION ALL ".join("SELECT * FROM ("+q+") WHERE created_at>=? AND created_at<?" for q in queries)+" ORDER BY created_at DESC"
        args=[v for _ in queries for v in (start,end)]
        with db.connect() as c:
            rows=c.execute(sql,args).fetchall()
        return {"source":source,"period":period,"start":start,"end":end,"transactions":[dict(x) for x in rows]}

    @r.get("/audit/export.xlsx")
    def audit_export(source:str="ALL",period:str="day",date:str|None=None,x_nvm_admin_token: str | None = Header(default=None)):
        token=getattr(app_settings,"admin_token","")
        if not token or not x_nvm_admin_token or not secrets.compare_digest(x_nvm_admin_token,token):
            raise HTTPException(401,"admin_auth_required")
        root=Path(getattr(app_settings,"data_dir",Path.home()/".local/share/nvm"))/"exports"
        root.mkdir(parents=True,exist_ok=True)
        path=root/f"audit-{source.lower()}-{period}-{date or 'today'}.xlsx"
        data=audit_report(source,period,date)
        export_rows_excel(data["transactions"],path)
        return FileResponse(path,filename=path.name,media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    @r.post("/backup")
    def backup_create(x_nvm_admin_token: str | None = Header(default=None)):
        token=getattr(app_settings,"admin_token","")
        if not token or not x_nvm_admin_token or not secrets.compare_digest(x_nvm_admin_token,token):
            raise HTTPException(401,"admin_auth_required")
        root=Path(getattr(app_settings,"data_dir",Path.home()/".local/share/nvm"))/"backups"
        root.mkdir(parents=True,exist_ok=True)
        import datetime as dt
        path=root/f"NVM_BACKUP_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.nvm.zip"
        create_native_backup(db,path,include_excel=True)
        return FileResponse(path,filename=path.name,media_type="application/zip")

    @r.post("/backup/restore")
    async def backup_restore(file:UploadFile=File(...),x_nvm_admin_token: str | None = Header(default=None)):
        token=getattr(app_settings,"admin_token","")
        if not token or not x_nvm_admin_token or not secrets.compare_digest(x_nvm_admin_token,token):
            raise HTTPException(401,"admin_auth_required")
        if not file.filename or not file.filename.endswith(".nvm.zip"): raise HTTPException(400,"invalid_backup_file")
        root=Path(getattr(app_settings,"data_dir",Path.home()/".local/share/nvm"))/"backups"
        root.mkdir(parents=True,exist_ok=True); path=root/"restore-upload.nvm.zip"
        path.write_bytes(await file.read())
        try: result=restore_native_backup(db,path)
        except Exception as e: raise HTTPException(400,str(e))
        return {"status":"restored","manifest":result}

    @r.post("/backup/import-excel")
    async def backup_import_excel(file:UploadFile=File(...),x_nvm_admin_token: str | None = Header(default=None)):
        token=getattr(app_settings,"admin_token","")
        if not token or not x_nvm_admin_token or not secrets.compare_digest(x_nvm_admin_token,token):
            raise HTTPException(401,"admin_auth_required")
        if not file.filename or not file.filename.lower().endswith(".xlsx"): raise HTTPException(400,"invalid_excel_file")
        root=Path(getattr(app_settings,"data_dir",Path.home()/".local/share/nvm"))/"imports"
        root.mkdir(parents=True,exist_ok=True); path=root/"import.xlsx"; path.write_bytes(await file.read())
        try: result=import_excel(db,path)
        except Exception as e: raise HTTPException(400,str(e))
        return {"status":"imported","result":result}

    return r
