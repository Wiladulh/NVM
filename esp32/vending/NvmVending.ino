#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>

// Configure locally before flashing. Never commit real Wi-Fi credentials.
const char* WIFI_SSID = "CHANGE_ME";
const char* WIFI_PASSWORD = "CHANGE_ME";
const char* NVM_BASE_URL = "http://192.168.1.24:8080";
const char* DEVICE_ID = "vm-01";

unsigned long lastHeartbeat = 0;

String request(const String& method, const String& path, const String& body, int& code) {
  HTTPClient http;
  http.begin(String(NVM_BASE_URL) + path);
  http.addHeader("Content-Type", "application/json");
  if (method == "GET") code = http.GET();
  else if (method == "POST") code = http.POST(body);
  else code = -1;
  String payload = code > 0 ? http.getString() : "";
  http.end();
  return payload;
}

String jsonString(const String& json, const String& key) {
  String marker = """ + key + "":"";
  int start = json.indexOf(marker);
  if (start < 0) return "";
  start += marker.length();
  int end = json.indexOf('"', start);
  return end < 0 ? "" : json.substring(start, end);
}

void heartbeat() {
  int code = 0;
  String body = "{"device_type":"esp32-s3-vending","status":"active"}";
  String reply = request("POST", String("/api/v1/devices/") + DEVICE_ID + "/heartbeat", body, code);
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

void products() {
  int code = 0;
  String reply = request("GET", String("/api/v1/vending/") + DEVICE_ID + "/products", "", code);
  Serial.printf("PRODUCTS %d %s\n", code, reply.c_str());
}

String beginTransaction(const String& product, const String& credential, const String& account, const String& sequence) {
  String body = "{"product_id":"" + product +
                "","credential_id":"" + credential +
                "","account_id":"" + account +
                "","idempotency_key":"" + String(DEVICE_ID) + ":" + sequence + ""}";
  int code = 0;
  String reply = request("POST", String("/api/v1/vending/") + DEVICE_ID + "/transactions", body, code);
  Serial.printf("BEGIN %d %s\n", code, reply.c_str());
  return jsonString(reply, "transaction_id");
}

bool authorize(const String& transaction) {
  int code = 0;
  String reply = request("POST", "/api/v1/vending/transactions/" + transaction + "/authorize", "", code);
  Serial.printf("AUTHORIZE %d %s\n", code, reply.c_str());
  return code >= 200 && code < 300;
}

void dispense(const String& transaction, bool success) {
  int code = 0;
  String body = String("{"success":") + (success ? "true" : "false") + "}";
  String reply = request("POST", "/api/v1/vending/transactions/" + transaction + "/dispense", body, code);
  Serial.printf("DISPENSE %d %s\n", code, reply.c_str());
}

void setup() {
  Serial.begin(115200);
  delay(300);
  connectWifi();
  heartbeat();
  products();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) connectWifi();
  if (millis() - lastHeartbeat >= 30000UL) {
    lastHeartbeat = millis();
    heartbeat();
  }

  // Integration harness:
  // PRODUCTS
  // BUY <product_id> <credential_id> <account_id> <sequence>
  // DISPENSE <transaction_id> <1|0>
  if (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    line.trim();
    if (line == "PRODUCTS") {
      products();
    } else if (line.startsWith("BUY ")) {
      int p1 = line.indexOf(' ', 4);
      int p2 = line.indexOf(' ', p1 + 1);
      int p3 = line.indexOf(' ', p2 + 1);
      if (p1 > 0 && p2 > p1 && p3 > p2) {
        String tx = beginTransaction(line.substring(4, p1), line.substring(p1 + 1, p2),
                                     line.substring(p2 + 1, p3), line.substring(p3 + 1));
        if (tx.length() && authorize(tx)) {
          Serial.println("AUTHORIZED_TX " + tx);
          Serial.println("Now dispense physically, then use: DISPENSE " + tx + " 1");
        }
      } else {
        Serial.println("ERR usage: BUY product credential account sequence");
      }
    } else if (line.startsWith("DISPENSE ")) {
      int p = line.indexOf(' ', 9);
      if (p > 9) dispense(line.substring(9, p), line.substring(p + 1).toInt() != 0);
      else Serial.println("ERR usage: DISPENSE transaction_id 1|0");
    }
  }
}
