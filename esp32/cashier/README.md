# NVM ESP32 Cashier — PN532 NFC

Cashier uses PN532 over I2C and sends NFC payments to the NVM API.

## Arduino library

Install **Adafruit PN532** from Arduino Library Manager.

## Wiring

Default sketch pins:

- PN532 SDA -> ESP32 GPIO 21
- PN532 SCL -> ESP32 GPIO 22
- PN532 IRQ -> ESP32 GPIO 4
- PN532 RESET -> ESP32 GPIO 5
- PN532 GND -> ESP32 GND
- PN532 VCC -> module-supported supply

If the module uses different pins, change the PN532_* constants in NvmCashier.ino.

## NFC credential format

The sketch converts the physical NFC UID to the form nfc-<lowercase hexadecimal UID>.

Example UID 04 A1 B2 C3 D4 55 66 becomes nfc-04a1b2c3d45566.

That value must be provisioned as the member credential_id in NVM before payment.

## Serial test

After Wi-Fi and NFC initialization:

SET <account_id> <amount>

Then tap the NFC credential. The sketch automatically calls POST /api/v1/cashier/payments.

Manual API harness remains available:

PAY <credential_id> <account_id> <amount> <sequence>

The server remains authoritative for credential authorization, account ownership, balance, idempotency and ledger debit.
