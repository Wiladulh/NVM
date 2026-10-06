-- Schema changes for NFC payment hardening are applied atomically by Database.migrate().
-- This migration marker is kept in SQL so the architecture version remains visible.
INSERT OR IGNORE INTO system_meta(key,value)
VALUES('nfc_payment_architecture_version','002');