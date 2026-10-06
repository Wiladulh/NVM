# NVM ESP32-S3 Vending

Vending hardware integrates:
- PN532 NFC over I2C
- SSD1306 128x64 I2C display
- three buttons: UP, DOWN, SELECT
- servo dispenser
- Wi-Fi heartbeat and NVM API

## Libraries

Install from Arduino Library Manager:
- Adafruit PN532
- Adafruit GFX Library
- Adafruit SSD1306
- ESP32Servo

## Default wiring

ESP32-S3 defaults in NvmVending.ino:
- I2C SDA GPIO 8
- I2C SCL GPIO 9
- PN532 IRQ GPIO 7
- PN532 RESET GPIO 10
- UP GPIO 4
- DOWN GPIO 5
- SELECT GPIO 6
- Servo GPIO 3
- OLED I2C address 0x3C

Change constants for the actual ESP32-S3 board and wiring.

## Flow

1. Vending downloads product/stock from NVM.
2. UP/DOWN selects a product.
3. SELECT displays the ready state.
4. Customer taps NFC.
5. UID becomes nfc-<lowercase hex UID>.
6. NVM resolves the credential to the member's active account.
7. Vending creates and authorizes the transaction.
8. Servo dispenses.
9. Vending reports successful dispensing.
10. NVM decrements stock. If dispensing fails, NVM refunds the payment.

The server remains authoritative for authorization, balance, payment, stock and transaction state.
