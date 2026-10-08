class DeviceManagementService:
    ALLOWED_TYPES = {"esp32-cashier", "esp32-vending", "cashier", "vending"}
    ALLOWED_STATUS = {"active", "disabled", "maintenance", "offline"}

    def __init__(self, db):
        self.db = db

    def list(self, include_deleted=False):
        where = "" if include_deleted else "WHERE deleted_at IS NULL"
        with self.db.connect() as c:
            rows = c.execute(
                f"""
                SELECT * FROM device_registry
                {where}
                ORDER BY device_id
                """
            ).fetchall()
            return [dict(r) for r in rows]

    def get(self, device_id):
        with self.db.connect() as c:
            row = c.execute(
                "SELECT * FROM device_registry WHERE device_id=?",
                (device_id,),
            ).fetchone()
            return dict(row) if row else None

    def update(self, device_id, device_type=None, status=None):
        current = self.get(device_id)
        if current is None:
            raise ValueError("device_not_found")
        if device_type is not None and device_type not in self.ALLOWED_TYPES:
            raise ValueError("invalid_device_type")
        if status is not None and status not in self.ALLOWED_STATUS:
            raise ValueError("invalid_device_status")
        new_type = device_type or current["device_type"]
        new_status = status or current["status"]
        with self.db.connect() as c:
            c.execute(
                """
                UPDATE device_registry
                SET device_type=?,status=?
                WHERE device_id=?
                """,
                (new_type, new_status, device_id),
            )
            c.commit()
        return self.get(device_id)

    def soft_delete(self, device_id):
        current = self.get(device_id)
        if current is None:
            raise ValueError("device_not_found")
        with self.db.connect() as c:
            c.execute(
                """
                UPDATE device_registry
                SET status='disabled',deleted_at=CURRENT_TIMESTAMP
                WHERE device_id=?
                """,
                (device_id,),
            )
            c.commit()
        return self.get(device_id)
