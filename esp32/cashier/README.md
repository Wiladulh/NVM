# NVM ESP32 Cashier

NFC cashier client for the NVM server.

## Protocol

1. Boot and heartbeat:
   POST /api/v1/devices/{device_id}/heartbeat
   Body: {"device_type":"esp32-cashier","status":"active"}

2. Read the NFC credential locally.

3. Send payment:
   POST /api/v1/cashier/payments
   Body:
   {"device_id":"cashier-01","credential_id":"test-credential-01","account_id":"...","amount":10000,"method":"NFC","provider":"local","idempotency_key":"cashier-01:123"}

4. The server verifies device status, NFC credential authorization, member/account ownership, balance, and idempotency, then commits the financial debit and payment transaction atomically.

5. The cashier keeps a local rolling transaction log (target: about 1 month) and retries the same idempotency key after network loss. Repeating the same request does not charge twice.

## Device identity

Use a stable device_id such as cashier-01. Do not put Wi-Fi passwords, API secrets, or production credentials in firmware source.

## Offline behavior

The MVP cashier does not invent an offline balance or authorize an offline payment. If the NVM server is unavailable, display an error and retain the attempted transaction locally for retry/status handling.

## Future QRIS

The common payment model already carries method, provider, provider transaction fields, and idempotency. QRIS can therefore be added later without changing the cashier NFC contract.
