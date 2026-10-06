from uuid import uuid4
from app.payment.service import PaymentService

class VendingService:
    def __init__(self, db):
        self.db=db
        self.payment=PaymentService(db)

    def machine(self,machine_id):
        with self.db.connect() as c:
            r=c.execute("SELECT machine_id,name,status FROM vending_machines WHERE machine_id=?",(machine_id,)).fetchone()
        if not r: raise ValueError("machine_not_found")
        return dict(r)

    def products(self,machine_id):
        self.machine(machine_id)
        with self.db.connect() as c:
            return [dict(r) for r in c.execute("""SELECT product_id,name,price,stock,enabled
                FROM vending_products WHERE machine_id=? ORDER BY product_id""",(machine_id,)).fetchall()]

    def upsert_product(self,machine_id,product_id,name,price,stock,enabled=True):
        self.machine(machine_id)
        if not product_id.strip() or not name.strip(): raise ValueError("product_required")
        if not isinstance(price,int) or isinstance(price,bool) or price<=0: raise ValueError("price_must_be_positive_integer")
        if not isinstance(stock,int) or isinstance(stock,bool) or stock<0: raise ValueError("stock_must_be_nonnegative_integer")
        with self.db.connect() as c:
            c.execute("""INSERT INTO vending_products(product_id,machine_id,name,price,stock,enabled)
                VALUES(?,?,?,?,?,?) ON CONFLICT(product_id) DO UPDATE SET
                machine_id=excluded.machine_id,name=excluded.name,price=excluded.price,
                stock=excluded.stock,enabled=excluded.enabled""",
                (product_id,machine_id,name,price,stock,1 if enabled else 0))
            c.commit()
        return self.get_product(machine_id,product_id)

    def get_product(self,machine_id,product_id):
        with self.db.connect() as c:
            r=c.execute("SELECT product_id,machine_id,name,price,stock,enabled FROM vending_products WHERE product_id=? AND machine_id=?",(product_id,machine_id)).fetchone()
        if not r: raise ValueError("product_not_found")
        return dict(r)

    def begin(self,machine_id,product_id,credential_id,account_id,idempotency_key):
        self.machine(machine_id)
        if not idempotency_key: raise ValueError("idempotency_key_required")
        with self.db.connect() as c:
            old=c.execute("SELECT * FROM vending_transactions WHERE idempotency_key=?",(idempotency_key,)).fetchone()
            if old: return dict(old)
            p=c.execute("SELECT * FROM vending_products WHERE product_id=? AND machine_id=?",(product_id,machine_id)).fetchone()
            if not p: raise ValueError("product_not_found")
            if not p["enabled"]: raise ValueError("product_disabled")
            if p["stock"]<=0: raise ValueError("out_of_stock")
            tx="vend-"+uuid4().hex
            c.execute("""INSERT INTO vending_transactions
                (transaction_id,machine_id,product_id,credential_id,account_id,amount,status,dispense_status,idempotency_key)
                VALUES(?,?,?,?,?,?,?,?,?)""",
                (tx,machine_id,product_id,credential_id,account_id,p["price"],"pending","pending",idempotency_key))
            c.commit()
        return self.get(tx)

    def authorize(self,transaction_id):
        tx=self.get(transaction_id)
        if tx["status"]=="completed": return tx
        if tx["status"] in {"failed","refunded"}: return tx
        try:
            payment=self.payment.pay(tx["credential_id"],tx["account_id"],tx["amount"],
                reference=transaction_id,method="NFC",provider="local",
                idempotency_key="vending-payment:"+transaction_id,device_id=tx["machine_id"])
        except Exception:
            with self.db.connect() as c:
                c.execute("UPDATE vending_transactions SET status='failed',dispense_status='not_started' WHERE transaction_id=?",(transaction_id,))
                c.commit()
            raise
        with self.db.connect() as c:
            c.execute("UPDATE vending_transactions SET status='authorized',payment_transaction_id=? WHERE transaction_id=?",(payment["transaction_id"],transaction_id))
            c.commit()
        return self.get(transaction_id)

    def dispense(self,transaction_id,success=True):
        tx=self.get(transaction_id)
        if tx["status"]!="authorized": raise ValueError("transaction_not_authorized")
        if not success:
            return self._fail_and_refund(tx)
        with self.db.connect() as c:
            p=c.execute("SELECT stock FROM vending_products WHERE product_id=? AND machine_id=?",(tx["product_id"],tx["machine_id"])).fetchone()
            if not p or p["stock"]<=0:
                c.rollback()
                return self._fail_and_refund(tx)
            c.execute("UPDATE vending_products SET stock=stock-1 WHERE product_id=? AND machine_id=? AND stock>0",(tx["product_id"],tx["machine_id"]))
            c.execute("""UPDATE vending_transactions SET status='completed',dispense_status='success',
                completed_at=CURRENT_TIMESTAMP WHERE transaction_id=?""",(transaction_id,))
            c.execute("INSERT INTO audit_events(event_type,entity_type,entity_id,detail) VALUES(?,?,?,?)",
                ("vending","vending_transaction",transaction_id,"dispensed"))
            c.commit()
        return self.get(transaction_id)

    def _fail_and_refund(self,tx):
        self.payment.financial.credit(tx["account_id"],tx["amount"],
            reference="refund:"+tx["transaction_id"],
            idempotency_key="vending-refund:"+tx["transaction_id"])
        with self.db.connect() as c:
            c.execute("UPDATE vending_transactions SET status='refunded',dispense_status='failed' WHERE transaction_id=?",(tx["transaction_id"],))
            c.commit()
        return self.get(tx["transaction_id"])

    def get(self,transaction_id):
        with self.db.connect() as c:
            r=c.execute("SELECT * FROM vending_transactions WHERE transaction_id=?",(transaction_id,)).fetchone()
        if not r: raise ValueError("transaction_not_found")
        return dict(r)

    def machine_status(self,machine_id):
        return self.machine(machine_id)
