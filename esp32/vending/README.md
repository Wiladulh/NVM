# NVM ESP32-S3 Vending — RC522 / PN532 Auto Detect

Vending supports both RC522 and PN532. Startup probes PN532 first, then falls back to RC522 automatically.

## Libraries

Install from Arduino Library Manager:
- Adafruit PN532
- MFRC522
- Adafruit GFX Library
- Adafruit SSD1306
- ESP32Servo

## Default reader wiring

PN532 I2C:
- SDA GPIO 8
- SCL GPIO 9
- IRQ GPIO 7
- RESET GPIO 10

RC522 SPI:
- SCK GPIO 12
- MISO GPIO 13
- MOSI GPIO 11
- SS GPIO 14
- RST GPIO 15

Change constants in NvmVending.ino for the actual ESP32-S3 board and wiring.

The UID is converted to nfc-<lowercase hexadecimal UID>. The NVM server remains authoritative for credential, account, balance, stock, transaction, and refund state.
