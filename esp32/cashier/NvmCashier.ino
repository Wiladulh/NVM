#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include "NvmKeypad.h"
#include "NvmCardReader.h"

const char* WIFI_SSID="CHANGE_ME";
const char* WIFI_PASSWORD="CHANGE_ME";
const char* NVM_BASE_URL="http://192.168.1.24:8080";
const char* DEVICE_ID="cashier-01";
LiquidCrystal_I2C lcd(0x27,16,2);

#define PN532_SDA 21
#define PN532_SCL 22
#define PN532_IRQ 4
#define PN532_RESET 5
#define RC522_SCK 18
#define RC522_MISO 19
#define RC522_MOSI 23
#define RC522_SS 27
#define RC522_RST 26

NvmCardReader card(PN532_IRQ,PN532_RESET,RC522_SCK,RC522_MISO,RC522_MOSI,RC522_SS,RC522_RST);
unsigned long lastHeartbeat=0,paymentSequence=0;
bool readerReady=false;
String paymentAccount="";
long paymentAmount=0;

String postJson(const String& path,const String& body,int& code){
  HTTPClient http; http.begin(String(NVM_BASE_URL)+path);
  http.addHeader("Content-Type","application/json"); code=http.POST(body);
  String out=code>0?http.getString():""; http.end(); return out;
}

void heartbeat(){
  int code=0;
  String body="{\"device_type\":\"esp32-cashier\",\"status\":\"active\"}";
  Serial.printf("HEARTBEAT %d %s\n",code,postJson(String("/api/v1/devices/")+DEVICE_ID+"/heartbeat",body,code).c_str());
}

void connectWifi(){
  WiFi.mode(WIFI_STA); WiFi.begin(WIFI_SSID,WIFI_PASSWORD); Serial.print("WiFi");
  while(WiFi.status()!=WL_CONNECTED){delay(500);Serial.print(".");}
  Serial.printf("\nIP %s\n",WiFi.localIP().toString().c_str());
}

String uidToCredential(const uint8_t* uid,uint8_t len){
  String out="nfc-";
  for(uint8_t i=0;i<len;i++){if(uid[i]<16)out+="0";out+=String(uid[i],HEX);}
  out.toLowerCase(); return out;
}

void cashierPayment(const String& credential,const String& account,long amount,const String& seq,const String& pin){
  if(amount<=0||account.length()==0){Serial.println("ERR set account and positive amount first");return;}
  String body="{\"device_id\":\""+String(DEVICE_ID)+"\",\"credential_id\":\""+credential+
              "\",\"account_id\":\""+account+"\",\"amount\":"+String(amount)+
              ",\"method\":\"NFC\",\"provider\":\"local\",\"idempotency_key\":\""+
              String(DEVICE_ID)+":"+seq+"\",\"pin\":\""+pin+"\"}";
  int code=0; String reply=postJson("/api/v1/cashier/payments",body,code);
  Serial.printf("PAYMENT %d %s\n",code,reply.c_str());
  if(code==200){
    int p=reply.indexOf("\"balance\":");
    long bal=p>=0?reply.substring(p+10).toInt():0;
    lcdShow("SUKSES","Saldo terpotong");
    delay(1200);
    lcdShow("Saldo sisa","Rp."+String(bal));
    delay(2200);
  }else if(code==403){lcdShow("GAGAL","PIN salah");delay(1800);}
  else if(code==409){lcdShow("GAGAL","Saldo tidak cukup");delay(1800);}
  else {lcdShow("GAGAL","Server "+String(code));delay(1800);}
}

String findAccount(const String& credential){
  HTTPClient http;
  http.begin(String(NVM_BASE_URL)+"/api/v1/credentials/"+credential+"/account");
  http.setTimeout(8000);
  int code=http.GET();
  String out=code>0?http.getString():"";
  http.end();
  if(code!=200)return "";
  String key="\"account_id\":\"";
  int p=out.indexOf(key);
  if(p<0)return "";
  p+=key.length();
  int e=out.indexOf("\"",p);
  return e>p?out.substring(p,e):"";
}

void scanCard(){
  if(!readerReady||paymentAmount<=0)return;
  uint8_t uid[7]={0},len=0;
  if(!card.readUID(uid,len))return;
  String credential=uidToCredential(uid,len); ++paymentSequence;
  paymentAccount=findAccount(credential);
  if(paymentAccount==""){lcdShow("KARTU DITOLAK","Akun tidak ada");delay(1800);return;}
  lcdShow("Kartu diterima","PIN:");
  String pin=readKeyDigits("PIN:",true);
  Serial.printf("CARD %s -> %s amount=%ld account=%s\n",card.name(),credential.c_str(),paymentAmount,paymentAccount.c_str());
  cashierPayment(credential,paymentAccount,paymentAmount,String(paymentSequence),pin);
  delay(700);
}


void lcdShow(String a,String b=""){
  lcd.setCursor(0,0); lcd.print("                ");
  lcd.setCursor(0,0); lcd.print(a.substring(0,16));
  lcd.setCursor(0,1); lcd.print("                ");
  lcd.setCursor(0,1); lcd.print(b.substring(0,16));
}
String readKeyDigits(const char* title,bool masked){
  String s=""; lcdShow(title,"");
  while(true){
    char k=nvmKeypad.getKey();
    if(k>='0'&&k<='9'&&s.length()<9){
      s+=k; String v="";
      for(size_t i=0;i<s.length();++i) v+=masked?"*":String(s[i]);
      lcdShow(title,v);
    }else if(k=='*'&&!s.isEmpty()){
      s.remove(s.length()-1);
    }else if(k=='#'&&!s.isEmpty()){
      return s;
    }
    delay(5);
  }
}
long readCashierAmount(){
  return readKeyDigits("Nominal:","").toInt();
}
void setup(){
  Serial.begin(115200); delay(300); connectWifi(); heartbeat();
  readerReady=card.begin(PN532_SDA,PN532_SCL);
  lcdShow("KASIR NVM","Masukkan nominal");
}

void loop(){
  if(WiFi.status()!=WL_CONNECTED)connectWifi();
  if(millis()-lastHeartbeat>=30000UL){lastHeartbeat=millis();heartbeat();}
  if(paymentAmount<=0) paymentAmount=readCashierAmount();\n  if(paymentAmount>0) scanCard();\n  paymentAmount=0;
}
