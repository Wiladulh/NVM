from pathlib import Path
from tempfile import TemporaryDirectory
from fastapi.testclient import TestClient
import app.main as main

def test_cashier_payment_requires_active_registered_device():
    with TemporaryDirectory() as d:
        old = main.get_settings
        main.get_settings = lambda: type("S", (), {"db_path": Path(d) / "nvm.db"})()
        try:
            client = TestClient(main.create_app())
            q = {
                "device_id": "cashier-01",
                "credential_id": "test-credential-01",
                "account_id": "member-account-01",
                "amount": 1000,
                "method": "NFC",
                "provider": "local",
                "idempotency_key": "cashier-01:1",
            }
            assert client.post("/api/v1/cashier/payments", json=q).status_code == 403

            hb = client.post(
                "/api/v1/devices/cashier-01/heartbeat",
                json={"device_type": "esp32-cashier", "status": "active"},
            )
            assert hb.status_code == 200
            assert client.post("/api/v1/cashier/payments", json=q).status_code != 403
        finally:
            main.get_settings = old
