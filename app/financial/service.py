from decimal import Decimal
from app.core.db import Database
class FinancialService:
    def __init__(self,db): self.db=db
    def balance(self,account_id):
        with self.db.connect() as c:
            r=c.execute("SELECT COALESCE(SUM(CASE WHEN direction='credit' THEN amount ELSE -amount END),0) balance FROM financial_ledger WHERE account_id=?",(account_id,)).fetchone()
        return Decimal(str(r["balance"]))
