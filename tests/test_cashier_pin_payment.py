from pathlib import Path
from tempfile import TemporaryDirectory
from fastapi.testclient import TestClient
import app.main as main

def test_cashier_pin_payment_debits_and_returns_balance():
    with TemporaryDirectory() as d:
        old = main.get_settings
        main.get_settings = lambda: type("S", (), {"db_path": Path(d) / "nvm.db"})()
        try:
            client = TestClient(main.create_app())
            with client.app.state.db.connect() as c:
                c.execute("INSERT INTO identity_members(member_id,name) VALUES('m1','Member')")
                c.execute("INSERT INTO identity_credentials(credential_id,member_id,credential_type) VALUES('cred1','m1','nfc')")
                c.execute("INSERT INTO financial_accounts(account_id,member_id,account_type) VALUES('a1','m1','savings')")
                c.execute("INSERT INTO financial_ledger(account_id,direction,amount,reference) VALUES('a1','credit',50000,'seed')")
                c.commit()
            assert client.post("/api/v1/members/m1/pin", json={"pin":"1234"}).status_code == 200
            assert client.post("/api/v1/devices/cashier-01/heartbeat",
                               json={"device_type":"esp32-cashier","status":"active"}).status_code == 200
            bad = client.post("/api/v1/cashier/payments", json={
                "device_id":"cashier-01","credential_id":"cred1","account_id":"a1",
                "amount":10000,"method":"NFC","pin":"9999","idempotency_key":"bad"})
            assert bad.status_code == 403 and bad.json()["detail"] == "invalid_pin"
            ok = client.post("/api/v1/cashier/payments", json={
                "device_id":"cashier-01","credential_id":"cred1","account_id":"a1",
                "amount":10000,"method":"NFC","pin":"1234","idempotency_key":"ok"})
            assert ok.status_code == 200
            assert ok.json()["balance"] == 40000
        finally:
            main.get_settings = old
