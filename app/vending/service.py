class VendingService:
    def __init__(self,db): self.db=db
    def machine_status(self,machine_id):
        with self.db.connect() as c:
            r=c.execute("SELECT machine_id,name,status FROM vending_machines WHERE machine_id=?",(machine_id,)).fetchone()
        return dict(r) if r else None
