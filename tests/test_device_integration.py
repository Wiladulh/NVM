from pathlib import Path
from tempfile import TemporaryDirectory
from fastapi.testclient import TestClient
import app.main as main

def test_device_heartbeat_and_vending_product_sync():
    with TemporaryDirectory() as d:
        old = main.get_settings
        main.get_settings = lambda: type("S", (), {"db_path": Path(d) / "nvm.db"})()
        try:
            client = TestClient(main.create_app())

            hb = client.post(
                "/api/v1/devices/cashier-01/heartbeat",
                json={"device_type": "esp32-cashier", "status": "active"},
            )
            assert hb.status_code == 200

            vm = client.post(
                "/api/v1/devices/vm-01/heartbeat",
                json={"device_type": "esp32-s3-vending", "status": "active"},
            )
            assert vm.status_code == 200

            with client.app.state.db.connect() as c:
                c.execute(
                    "INSERT INTO vending_machines(machine_id,name,status) VALUES('vm-01','Vending 01','active')"
                )
                c.commit()

            product = client.put(
                "/api/v1/vending/vm-01/products/water-01",
                json={
                    "product_id": "water-01",
                    "name": "Air Mineral",
                    "price": 3000,
                    "stock": 12,
                    "enabled": True,
                },
            )
            assert product.status_code == 200
            assert product.json()["stock"] == 12

            sync = client.get("/api/v1/vending/vm-01/products")
            assert sync.status_code == 200
            assert sync.json()["machine"]["machine_id"] == "vm-01"
            assert sync.json()["products"][0]["product_id"] == "water-01"

            dashboard = client.get("/api/v1/dashboard")
            assert dashboard.status_code == 200
            devices = {x["device_id"]: x for x in dashboard.json()["devices"]}
            assert devices["cashier-01"]["status"] == "active"
            assert devices["vm-01"]["device_type"] == "esp32-s3-vending"
        finally:
            main.get_settings = old
