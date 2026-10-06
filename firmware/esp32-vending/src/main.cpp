#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ESP32Servo.h>

const char* WIFI_SSID = "CHANGE_ME";
const char* WIFI_PASS = "CHANGE_ME";
const char* SERVER = "http://192.168.1.1:8000/api/v1";
const char* MACHINE_ID = "nvm-vending-01";

static const int SERVO_PIN = 18;
static const int BUTTON_PIN = 4;
Servo dispenser;

String postJson(const String& url,const String& body){
  HTTPClient h; h.begin(url); h.addHeader("Content-Type","application/json");
  int code=h.POST(body); String out=h.getString(); h.end();
  Serial.printf("HTTP %d %s\\n",code,out.c_str()); return out;
}

bool serverOnline(){
  HTTPClient h; h.begin(String(SERVER)+"/health"); int code=h.GET(); h.end(); return code==200;
}

void dispense(){
  dispenser.write(110); delay(700);
  dispenser.write(10); delay(700);
}

void setup(){
  Serial.begin(115200);
  pinMode(BUTTON_PIN,INPUT_PULLUP);
  dispenser.attach(SERVO_PIN);
  dispenser.write(10);
  WiFi.begin(WIFI_SSID,WIFI_PASS);
  while(WiFi.status()!=WL_CONNECTED){delay(300);Serial.print(".");}
  Serial.printf("\nVending %s online: %s\\n",MACHINE_ID,WiFi.localIP().toString().c_str());
}

void loop(){
  if(digitalRead(BUTTON_PIN)==LOW){
    if(!serverOnline()){ Serial.println("ERROR: SERVER OFFLINE"); delay(1000); return; }
    // Hardware adapters (NFC/display/buttons) feed these values in the final wiring layer.
    String product="water";
    String credential="test-credential-01";
    String account="acct-fin-1";
    String key="esp32-"+String(ESP.getEfuseMac(),HEX)+"-"+String(millis());
    String begin=postJson(String(SERVER)+"/vending/"+MACHINE_ID+"/transactions",
      "{\"product_id\":\""+product+"\",\"credential_id\":\""+credential+"\",\"account_id\":\""+account+"\",\"idempotency_key\":\""+key+"\"}");
    // Transaction id is intentionally supplied by the server; production UI parses JSON before continuing.
    int p=begin.indexOf("\"transaction_id\":\"");
    if(p>=0){
      p+=18; int e=begin.indexOf('"',p); String tx=begin.substring(p,e);
      postJson(String(SERVER)+"/vending/transactions/"+tx+"/authorize","{}");
      dispense();
      postJson(String(SERVER)+"/vending/transactions/"+tx+"/dispense","{\"success\":true}");
    }
    while(digitalRead(BUTTON_PIN)==LOW) delay(20);
  }
  delay(20);
}
