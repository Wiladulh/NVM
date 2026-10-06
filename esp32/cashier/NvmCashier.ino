#include <Arduino.h>
#include <Wire.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <Adafruit_PN532.h>

// Configure locally before flashing. Never commit real Wi-Fi credentials.
const char* WIFI_SSID = "CHANGE_ME";
const char* WIFI_PASSWORD = "CHANGE_ME";
const char* NVM_BASE_URL = "http://192.168.1.24:8080";
const char* DEVICE_ID = "cashier-01";

// PN532 I2C wiring: SDA/SCL use the ESP32 defaults below.
// IRQ/RESET may be changed to match the actual module wiring.
#define PN532_SDA 21
#define PN532_SCL 22
#define PN532_IRQ 4
#define PN532_RESET 5

Adafruit_PN532 nfc(PN532_IRQ, PN532_RESET);

unsigned long lastHeartbeat = 0;
bool nfcReady = false;
String paymentAccount = "";
long paymentAmount = 0;
unsigned long paymentSequence = 0;

String postJson(const String& path, const String& body, int& code) {
  HTTPClient http;
  http.begin(String(NVM_BASE_URL) + path);
  http.addHeader("Content-Type", "application/json");
  code = http.POST(body);
  String payload = code > 0 ? http.getString() : "";
  http.end();
  return payload;
}

void heartbeat() {
  int code = 0;
  String body = "{\"device_type\":\"esp32-cashier\",\"status\":\"active\"}";
  String reply = postJson(String("/api/v1/devices/") + DEVICE_ID + "/heartbeat", body, code);
  Serial.printf("HEARTBEAT %d %s\n", code, reply.c_str());
}

void connectWifi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.printf("\nIP %s\n", WiFi.localIP().toString().c_str());
}

String uidToCredential(const uint8_t* uid, uint8_t uidLength) {
  String out = "nfc-";
  for (uint8_t i = 0; i < uidLength; ++i) {
    if (uid[i] < 0x10) out += "0";
    out += String(uid[i], HEX);
  }
  out.toLowerCase();
  return out;
}

void cashierPayment(const String& credential, const String& account, long amount, const String& sequence) {
  if (amount <= 0 || account.length() == 0) {
    Serial.println("ERR set account and positive amount first");
    return;
  }

  String body = "{\"device_id\":\"" + String(DEVICE_ID) +
                "\",\"credential_id\":\"" + credential +
                "\",\"account_id\":\"" + account +
                "\",\"amount\":" + String(amount) +
                ",\"method\":\"NFC\",\"provider\":\"local\",\"idempotency_key\":\"" +
                String(DEVICE_ID) + ":" + sequence + "\"}";
  int code = 0;
  String reply = postJson("/api/v1/cashier/payments", body, code);
  Serial.printf("PAYMENT %d %s\n", code, reply.c_str());
}

bool initNfc() {
  Wire.begin(PN532_SDA, PN532_SCL);
  nfc.begin();
  uint32_t version = nfc.getFirmwareVersion();
  if (!version) {
    Serial.println("NFC ERROR pn532_not_found");
    return false;
  }
  nfc.SAMConfig();
  Serial.printf("NFC READY PN5%lu\n", (unsigned long)((version >> 24) & 0xFF));
  return true;
}

void scanNfc() {
  if (!nfcReady || paymentAccount.length() == 0 || paymentAmount <= 0) return;

  uint8_t uid[7] = {0};
  uint8_t uidLength = 0;
  bool found = nfc.readPassiveTargetID(PN532_MIFARE_ISO14443A, uid, &uidLength, 50);
  if (!found) return;

  String credential = uidToCredential(uid, uidLength);
  ++paymentSequence;
  Serial.printf("NFC UID -> %s amount=%ld account=%s\n",
                credential.c_str(), paymentAmount, paymentAccount.c_str());
  cashierPayment(credential, paymentAccount, paymentAmount, String(paymentSequence));
  delay(700);
}

void setup() {
  Serial.begin(115200);
  delay(300);
  connectWifi();
  heartbeat();
  nfcReady = initNfc();

  Serial.println("Commands:");
  Serial.println("SET account amount");
  Serial.println("PAY credential account amount sequence");
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    connectWifi();
  }

  if (millis() - lastHeartbeat >= 30000UL) {
    lastHeartbeat = millis();
    heartbeat();
  }

  if (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    line.trim();

    if (line.startsWith("SET ")) {
      int p = line.indexOf(' ', 4);
      if (p > 4) {
        paymentAccount = line.substring(4, p);
        paymentAmount = line.substring(p + 1).toInt();
        Serial.printf("READY account=%s amount=%ld\n",
                      paymentAccount.c_str(), paymentAmount);
      } else {
        Serial.println("ERR usage: SET account amount");
      }
    } else if (line.startsWith("PAY ")) {
      int p1 = line.indexOf(' ', 4);
      int p2 = line.indexOf(' ', p1 + 1);
      int p3 = line.indexOf(' ', p2 + 1);
      if (p1 > 0 && p2 > p1 && p3 > p2) {
        cashierPayment(line.substring(4, p1), line.substring(p1 + 1, p2),
                       line.substring(p2 + 1, p3).toInt(), line.substring(p3 + 1));
      } else {
        Serial.println("ERR usage: PAY credential account amount sequence");
      }
    }
  }

  scanNfc();
}
