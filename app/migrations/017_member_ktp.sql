-- STEP F: KTP-style member profile fields.
ALTER TABLE identity_members ADD COLUMN birth_place TEXT;
ALTER TABLE identity_members ADD COLUMN birth_date TEXT;
ALTER TABLE identity_members ADD COLUMN sex TEXT;
ALTER TABLE identity_members ADD COLUMN rt TEXT;
ALTER TABLE identity_members ADD COLUMN rw TEXT;
ALTER TABLE identity_members ADD COLUMN village TEXT;
ALTER TABLE identity_members ADD COLUMN district TEXT;
ALTER TABLE identity_members ADD COLUMN city_regency TEXT;
ALTER TABLE identity_members ADD COLUMN province TEXT;
ALTER TABLE identity_members ADD COLUMN religion TEXT;
ALTER TABLE identity_members ADD COLUMN marital_status TEXT;
ALTER TABLE identity_members ADD COLUMN occupation TEXT;
ALTER TABLE identity_members ADD COLUMN citizenship TEXT;
ALTER TABLE identity_members ADD COLUMN phone TEXT;
ALTER TABLE identity_members ADD COLUMN email TEXT;
ALTER TABLE identity_members ADD COLUMN registration_date TEXT;
CREATE INDEX IF NOT EXISTS ix_member_nik ON identity_members(nik);
INSERT OR IGNORE INTO system_meta(key,value) VALUES('member_ktp_schema_version','001');
