#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>

// Configure locally before flashing. Never commit real Wi-Fi credentials.
const char* WIFI_SSID = "CHANGE_ME";
const char* WIFI_PASSWORD = "CHANGE_ME";
const char* NVM_BASE_URL = "http://192.168.1.24:8080";
const char* DEVICE_ID = "cashier-01";

unsigned long lastHeartbeat = 0;

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
  String body = "{"device_type":"esp32-cashier","status":"active"}";
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

void cashierPayment(const String& credential, const String& account, long amount, const String& sequence) {
  String body = "{"device_id":"" + String(DEVICE_ID) +
                "","credential_id":"" + credential +
                "","account_id":"" + account +
                "","amount":" + String(amount) +
                ","method":"NFC","provider":"local","idempotency_key":"" +
                String(DEVICE_ID) + ":" + sequence + ""}";
  int code = 0;
  String reply = postJson("/api/v1/cashier/payments", body, code);
  Serial.printf("PAYMENT %d %s\n", code, reply.c_str());
}

void setup() {
  Serial.begin(115200);
  delay(300);
  connectWifi();
  heartbeat();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    connectWifi();
  }
  if (millis() - lastHeartbeat >= 30000UL) {
    lastHeartbeat = millis();
    heartbeat();
  }

  // Integration harness:
  // PAY <credential_id> <account_id> <amount> <sequence>
  if (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    line.trim();
    if (line.startsWith("PAY ")) {
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
}
