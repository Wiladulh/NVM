from pathlib import Path
from tempfile import TemporaryDirectory
from fastapi.testclient import TestClient

import app.main as main
from app.core.db import Database


def test_cashier_device_registration_and_heartbeat_gate():
    with TemporaryDirectory() as d:
        old = main.get_settings
        db_path = Path(d) / "nvm.db"
        main.get_settings = lambda: type("S", (), {"db_path": db_path, "admin_token": "admin-secret"})()
        try:
            client = TestClient(main.create_app())

            unauthorized = client.post(
                "/api/v1/devices/cashier-01/heartbeat",
                json={"device_type": "esp32-cashier", "status": "active"},
                headers={"X-NVM-Device-Key": "invalid-key"},
            )
            assert unauthorized.status_code == 401

            provision = client.post(
                "/api/v1/devices/cashier-01/provision",
                json={"device_type": "esp32-cashier"},
                headers={"X-NVM-Admin-Token": "admin-secret"},
            )
            assert provision.status_code == 200
            data = provision.json()
            device_key = data["device_key"]
            assert data["device_id"] == "cashier-01"
            assert data["device_type"] == "esp32-cashier"

            heartbeat = client.post(
                "/api/v1/devices/cashier-01/heartbeat",
                json={"device_type": "esp32-cashier", "status": "active"},
                headers={"X-NVM-Device-Key": device_key},
            )
            assert heartbeat.status_code == 200
            hb = heartbeat.json()
            assert hb["device_id"] == "cashier-01"
            assert hb["device_type"] == "esp32-cashier"

            with Database(db_path).connect() as c:
                row = c.execute(
                    "SELECT device_id, device_type, status FROM device_registry WHERE device_id=?",
                    ("cashier-01",),
                ).fetchone()
                assert row is not None
                assert row["device_id"] == "cashier-01"
                assert row["device_type"] == "esp32-cashier"
                assert row["status"] == "active"
        finally:
            main.get_settings = old
