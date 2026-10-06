# NVM ESP32 Cashier — RC522 / PN532 Auto Detect

Cashier supports both RC522 and PN532. On startup it probes PN532 first, then falls back to RC522 automatically.

## Libraries

Install from Arduino Library Manager:
- Adafruit PN532
- MFRC522

## Default reader wiring

PN532 I2C:
- SDA GPIO 21
- SCL GPIO 22
- IRQ GPIO 4
- RESET GPIO 5

RC522 SPI:
- SCK GPIO 18
- MISO GPIO 19
- MOSI GPIO 23
- SS GPIO 27
- RST GPIO 26

Change constants in NvmCashier.ino for the actual wiring.

The UID is converted to nfc-<lowercase hexadecimal UID>, so the same physical card produces the same NVM credential_id regardless of reader type.

Serial:
SET <account_id> <amount>
Then tap the card.

Manual:
PAY <credential_id> <account_id> <amount> <sequence>
