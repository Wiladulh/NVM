#pragma once
#include <Arduino.h>
#include <Wire.h>
#include <SPI.h>
#include <Adafruit_PN532.h>
#include <MFRC522.h>

// Maximum UID size supported by ISO14443-A readers (including 10-byte UIDs).
static constexpr uint8_t NVM_MAX_UID_LENGTH = 10;

// NVM NFC abstraction: application code never depends on a concrete reader.
enum NvmReaderType { NVM_READER_NONE, NVM_READER_PN532, NVM_READER_RC522 };

class NvmCardReader {
public:
  NvmReaderType type = NVM_READER_NONE;

  NvmCardReader(int pnIrq, int pnReset, int sck, int miso, int mosi, int ss, int rst)
    : pn532(pnIrq, pnReset), rc522(ss, rst),
      rcSck(sck), rcMiso(miso), rcMosi(mosi), rcSs(ss) {}

  // Initializes I2C and tries PN532 first, then RC522 over SPI.
  bool begin(int sda, int scl) {
    Wire.begin(sda, scl);
    Wire.setClock(400000);

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

  // Returns true once per reader-detected card presentation. A false result
  // means no readable card is currently detected; the caller may keep polling.
  // The caller must provide a buffer of at least NVM_MAX_UID_LENGTH bytes.
  bool readUID(uint8_t* uid, uint8_t& len) {
    len = 0;
    if (type == NVM_READER_NONE)
      return false;

    if (type == NVM_READER_PN532) {
      uint8_t detectedLen = 0;
      if (!pn532.readPassiveTargetID(PN532_MIFARE_ISO14443A, uid, &detectedLen, 50))
        return false;
      len = detectedLen > NVM_MAX_UID_LENGTH ? NVM_MAX_UID_LENGTH : detectedLen;
      return len > 0;
    }

    if (type == NVM_READER_RC522) {
      if (!rc522.PICC_IsNewCardPresent() || !rc522.PICC_ReadCardSerial())
        return false;
      len = rc522.uid.size > NVM_MAX_UID_LENGTH ? NVM_MAX_UID_LENGTH : rc522.uid.size;
      for (uint8_t i = 0; i < len; ++i)
        uid[i] = rc522.uid.uidByte[i];
      rc522.PICC_HaltA();
      rc522.PCD_StopCrypto1();
      return len > 0;
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
