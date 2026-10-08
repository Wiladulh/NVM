-- STEP A: portable hardware identity and auto-registration.
-- Existing device credentials remain hashed; hardware identity is separate.

CREATE UNIQUE INDEX IF NOT EXISTS ux_device_hardware_id
ON device_registry(hardware_id);

CREATE INDEX IF NOT EXISTS ix_device_type_status
ON device_registry(device_type,status);

CREATE INDEX IF NOT EXISTS ix_device_mac
ON device_registry(mac_address);

INSERT OR IGNORE INTO system_meta(key,value)
VALUES('hardware_registry_schema_version','001');
