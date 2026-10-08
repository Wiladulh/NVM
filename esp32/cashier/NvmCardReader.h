#pragma once
#include <Arduino.h>
#include <Wire.h>
#include <SPI.h>
#include <Adafruit_PN532.h>
#include <MFRC522.h>

// NVM NFC abstraction: application code never depends on a concrete reader.
enum NvmReaderType { NVM_READER_NONE, NVM_READER_PN532, NVM_READER_RC522 };

class NvmCardReader {
public:
  NvmReaderType type = NVM_READER_NONE;

  NvmCardReader(int pnIrq, int pnReset, int sck, int miso, int mosi, int ss, int rst)
    : pn532(pnIrq, pnReset), rc522(ss, rst),
      rcSck(sck), rcMiso(miso), rcMosi(mosi), rcSs(ss) {}

  bool begin(int sda, int scl) {
    Wire.begin(sda, scl);
    Wire.setClock(400000);

    // Prefer PN532 when physically present; otherwise fall back to RC522.
    pn532.begin();
    uint32_t version = pn532.getFirmwareVersion();
    if (version) {
      pn532.SAMConfig();
      type = NVM_READER_PN532;
      Serial.printf("NFC READY PN532 fw=%lu\n",
                    (unsigned long)((version >> 24) & 0xFF));
      return true;
    }

    SPI.begin(rcSck, rcMiso, rcMosi, rcSs);
    rc522.PCD_Init();
    delay(50);
    byte vr = rc522.PCD_ReadRegister(MFRC522::VersionReg);
    if (vr == 0x91 || vr == 0x92 || vr == 0x88) {
      type = NVM_READER_RC522;
      Serial.printf("NFC READY RC522 version=0x%02X\n", vr);
      return true;
    }

    type = NVM_READER_NONE;
    Serial.println("NFC ERROR: PN532/RC522 not detected");
    return false;
  }

  bool readUID(uint8_t* uid, uint8_t& len) {
    if (type == NVM_READER_PN532) {
      uint8_t detectedLen = 0;
      if (!pn532.readPassiveTargetID(PN532_MIFARE_ISO14443A, uid, &detectedLen, 50))
        return false;
      len = detectedLen > 7 ? 7 : detectedLen;
      return len > 0;
    }

    if (type == NVM_READER_RC522) {
      if (!rc522.PICC_IsNewCardPresent() || !rc522.PICC_ReadCardSerial())
        return false;
      len = rc522.uid.size > 7 ? 7 : rc522.uid.size;
      for (uint8_t i = 0; i < len; ++i)
        uid[i] = rc522.uid.uidByte[i];
      rc522.PICC_HaltA();
      rc522.PCD_StopCrypto1();
      return true;
    }

    return false;
  }

  const char* name() const {
    return type == NVM_READER_PN532 ? "PN532" :
           type == NVM_READER_RC522 ? "RC522" : "NONE";
  }

private:
  Adafruit_PN532 pn532;
  MFRC522 rc522;
  int rcSck, rcMiso, rcMosi, rcSs;
};
