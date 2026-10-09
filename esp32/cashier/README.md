# NVM ESP32 Cashier — NFC + PIN + LCD + Keypad

Minimum cashier flow:
1. Petugas memasukkan nominal dengan keypad 4x4 (# konfirmasi, * hapus).
2. Pembeli menempelkan kartu NFC.
3. ESP32 mencari rekening aktif milik credential tersebut.
4. Pembeli memasukkan PIN 4–6 digit; LCD menampilkan *.
5. ESP32 mengirim nominal + credential + PIN ke server NVM.
6. Server memverifikasi credential dan PIN lalu melakukan debit pada Financial Core.
7. LCD menampilkan SUKSES, saldo terpotong, dan saldo sisa. Saldo kurang/PIN salah ditolak.

## Hardware
- ESP32
- LCD 16x2 I2C, address default 0x27
- Keypad matrix 4x4
- PN532 I2C atau RC522 SPI

## Wiring
LCD: SDA 21, SCL 22.
Keypad rows: 32,33,25,26. Columns: 13,14,16,17.
PN532: SDA 21, SCL 22, IRQ 39, RESET 5.
RC522: SCK 18, MISO 19, MOSI 23, SS 27, RST 4.

Libraries: LiquidCrystal_I2C, Keypad, Adafruit PN532, MFRC522.

## Server
Set WIFI_SSID, WIFI_PASSWORD, and NVM_BASE_URL.
Set PIN member melalui POST /api/v1/members/<member_id>/pin dengan body {"pin":"1234"}.
Credential NFC harus aktif, terhubung ke member aktif, dan member harus mempunyai rekening savings aktif.
