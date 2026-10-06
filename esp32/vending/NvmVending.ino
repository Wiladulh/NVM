#include <Arduino.h>
#include <Wire.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <Adafruit_PN532.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <ESP32Servo.h>

const char* WIFI_SSID="CHANGE_ME";
const char* WIFI_PASSWORD="CHANGE_ME";
const char* NVM_BASE_URL="http://192.168.1.24:8080";
const char* DEVICE_ID="vm-01";

#define I2C_SDA 8
#define I2C_SCL 9
#define PN532_IRQ 7
#define PN532_RESET 10
#define BUTTON_UP 4
#define BUTTON_DOWN 5
#define BUTTON_SELECT 6
#define SERVO_PIN 3
#define OLED_ADDR 0x3C

Adafruit_PN532 nfc(PN532_IRQ, PN532_RESET);
Adafruit_SSD1306 display(128,64,&Wire,-1);
Servo dispenser;

unsigned long lastHeartbeat=0;
bool nfcReady=false, displayReady=false;
int selectedIndex=0, productCount=0;

struct Product { String id,name; long price; int stock; bool enabled; };
Product productsList[16];

String request(const String& method,const String& path,const String& body,int& code){
  HTTPClient http; http.begin(String(NVM_BASE_URL)+path);
  http.addHeader("Content-Type","application/json");
  if(method=="GET") code=http.GET(); else if(method=="POST") code=http.POST(body); else code=-1;
  String out=code>0?http.getString():""; http.end(); return out;
}

String jsonString(const String& json,const String& key){
  String marker=String("\"")+key+"\":\"";
  int p=json.indexOf(marker); if(p<0) return "";
  p+=marker.length(); int e=json.indexOf('"',p);
  return e<0?"":json.substring(p,e);
}

long jsonLong(const String& json,const String& key){
  String marker=String("\"")+key+"\":";
  int p=json.indexOf(marker); if(p<0) return -1;
  p+=marker.length(); while(p<(int)json.length() && json[p]==' ') p++;
  int e=p; while(e<(int)json.length() && isDigit(json[e])) e++;
  return json.substring(p,e).toInt();
}

void showMessage(const String& a,const String& b="",const String& c=""){
  if(!displayReady){Serial.printf("DISPLAY: %s | %s | %s\n",a.c_str(),b.c_str(),c.c_str());return;}
  display.clearDisplay(); display.setTextSize(1); display.setTextColor(SSD1306_WHITE); display.setCursor(0,0);
  display.println(a); if(b.length()) display.println(b); if(c.length()) display.println(c); display.display();
}

void heartbeat(){
  int code=0;
  String body="{\"device_type\":\"esp32-s3-vending\",\"status\":\"active\"}";
  String reply=request("POST",String("/api/v1/devices/")+DEVICE_ID+"/heartbeat",body,code);
  Serial.printf("HEARTBEAT %d %s\n",code,reply.c_str());
}

void connectWifi(){
  WiFi.mode(WIFI_STA); WiFi.begin(WIFI_SSID,WIFI_PASSWORD); Serial.print("WiFi");
  while(WiFi.status()!=WL_CONNECTED){delay(500);Serial.print(".");}
  Serial.printf("\nIP %s\n",WiFi.localIP().toString().c_str());
}

String uidToCredential(const uint8_t* uid,uint8_t len){
  String out="nfc-"; for(uint8_t i=0;i<len;i++){if(uid[i]<16)out+="0";out+=String(uid[i],HEX);}
  out.toLowerCase(); return out;
}

void parseProducts(const String& json){
  productCount=0; int pos=0;
  while(productCount<16){
    int p=json.indexOf("\"product_id\":\"",pos); if(p<0)break;
    int s=p+15,e=json.indexOf('"',s); if(e<0)break;
    Product &x=productsList[productCount]; x.id=json.substring(s,e);
    int n=json.indexOf("\"name\":\"",e), ns=n<0?-1:n+9, ne=ns<0?-1:json.indexOf('"',ns);
    x.name=(ns>=0&&ne>=0)?json.substring(ns,ne):x.id;
    int q=json.indexOf("\"price\":",e); x.price=q>=0?jsonLong(json.substring(q),"price"):0;
    q=json.indexOf("\"stock\":",e); x.stock=q>=0?jsonLong(json.substring(q),"stock"):0;
    q=json.indexOf("\"enabled\":",e); x.enabled=q>=0&&json.substring(q,q+20).indexOf("true")>=0;
    pos=e+1; productCount++;
  }
}

bool products(){
  int code=0; String reply=request("GET",String("/api/v1/vending/")+DEVICE_ID+"/products","",code);
  Serial.printf("PRODUCTS %d %s\n",code,reply.c_str());
  if(code<200||code>=300){showMessage("SERVER ERROR","Products unavailable");return false;}
  parseProducts(reply); if(!productCount){showMessage("NVM VENDING","No products");return false;}
  if(selectedIndex>=productCount)selectedIndex=0;
  Product &x=productsList[selectedIndex]; showMessage("SELECT PRODUCT",x.name,"Rp "+String(x.price)); return true;
}

String resolveAccount(const String& credential){
  int code=0; String reply=request("GET","/api/v1/credentials/"+credential+"/account","",code);
  if(code<200||code>=300)return ""; return jsonString(reply,"account_id");
}

String beginTransaction(const String& product,const String& credential,const String& account,const String& sequence){
  String body="{\"product_id\":\""+product+"\",\"credential_id\":\""+credential+"\",\"account_id\":\""+account+"\",\"idempotency_key\":\""+String(DEVICE_ID)+":"+sequence+"\"}";
  int code=0; String reply=request("POST",String("/api/v1/vending/")+DEVICE_ID+"/transactions",body,code);
  Serial.printf("BEGIN %d %s\n",code,reply.c_str()); return jsonString(reply,"transaction_id");
}

bool authorize(const String& tx){
  int code=0; String reply=request("POST","/api/v1/vending/transactions/"+tx+"/authorize","",code);
  Serial.printf("AUTHORIZE %d %s\n",code,reply.c_str()); return code>=200&&code<300;
}

bool dispense(const String& tx){
  dispenser.write(70); delay(700); dispenser.write(10);
  int code=0; String reply=request("POST","/api/v1/vending/transactions/"+tx+"/dispense","{\"success\":true}",code);
  Serial.printf("DISPENSE %d %s\n",code,reply.c_str()); return code>=200&&code<300;
}

void scanNfc(){
  if(!nfcReady||!productCount)return;
  Product &x=productsList[selectedIndex]; if(!x.enabled||x.stock<=0)return;
  uint8_t uid[7]={0},len=0; if(!nfc.readPassiveTargetID(PN532_MIFARE_ISO14443A,uid,&len,50))return;
  String credential=uidToCredential(uid,len); showMessage("CARD DETECTED",credential,"Checking...");
  String account=resolveAccount(credential);
  if(!account.length()){showMessage("CARD REJECTED","No active account");delay(1200);return;}
  String tx=beginTransaction(x.id,credential,account,String(millis()));
  if(!tx.length()||!authorize(tx)){showMessage("PAYMENT FAILED");delay(1200);return;}
  showMessage("PAYMENT OK",x.name,"Dispensing...");
  if(dispense(tx)){showMessage("TAKE PRODUCT",x.name);delay(800);products();}
  else showMessage("DISPENSE ERROR","Payment refunded");
  delay(1000);
}

void setup(){
  Serial.begin(115200); delay(300);
  pinMode(BUTTON_UP,INPUT_PULLUP); pinMode(BUTTON_DOWN,INPUT_PULLUP); pinMode(BUTTON_SELECT,INPUT_PULLUP);
  Wire.begin(I2C_SDA,I2C_SCL); displayReady=display.begin(SSD1306_SWITCHCAPVCC,OLED_ADDR);
  dispenser.setPeriodHertz(50); dispenser.attach(SERVO_PIN,500,2400); dispenser.write(10);
  showMessage("NVM VENDING","Starting..."); connectWifi(); heartbeat();
  nfc.begin(); nfcReady=nfc.getFirmwareVersion()!=0; if(nfcReady)nfc.SAMConfig(); else Serial.println("NFC ERROR pn532_not_found");
  products();
}

void loop(){
  if(WiFi.status()!=WL_CONNECTED){showMessage("SERVER ERROR","WiFi disconnected");connectWifi();return;}
  if(millis()-lastHeartbeat>=30000UL){lastHeartbeat=millis();heartbeat();}
  if(digitalRead(BUTTON_UP)==LOW){if(productCount)selectedIndex=(selectedIndex+productCount-1)%productCount;products();delay(250);}
  if(digitalRead(BUTTON_DOWN)==LOW){if(productCount)selectedIndex=(selectedIndex+1)%productCount;products();delay(250);}
  if(digitalRead(BUTTON_SELECT)==LOW){showMessage("READY",productCount?productsList[selectedIndex].name:"No product","Tap NFC card");delay(250);}
  scanNfc();
  if(Serial.available()){
    String line=Serial.readStringUntil('\n'); line.trim();
    if(line=="PRODUCTS")products();
  }
}
