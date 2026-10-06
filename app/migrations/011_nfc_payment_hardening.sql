ALTER TABLE identity_credentials ADD COLUMN enabled INTEGER NOT NULL DEFAULT 1;
ALTER TABLE identity_credentials ADD COLUMN pin_failed_attempts INTEGER NOT NULL DEFAULT 0;
ALTER TABLE identity_credentials ADD COLUMN pin_blocked INTEGER NOT NULL DEFAULT 0;

ALTER TABLE credential_registry ADD COLUMN pin_failed_attempts INTEGER NOT NULL DEFAULT 0;
ALTER TABLE credential_registry ADD COLUMN pin_blocked INTEGER NOT NULL DEFAULT 0;

ALTER TABLE payment_transactions ADD COLUMN original_amount INTEGER;
ALTER TABLE payment_transactions ADD COLUMN discount_amount INTEGER NOT NULL DEFAULT 0;
ALTER TABLE payment_transactions ADD COLUMN final_amount INTEGER;
ALTER TABLE payment_transactions ADD COLUMN promo_id TEXT;
ALTER TABLE payment_transactions ADD COLUMN balance_before INTEGER;
ALTER TABLE payment_transactions ADD COLUMN balance_after INTEGER;

CREATE INDEX IF NOT EXISTS ix_identity_credentials_member_status
ON identity_credentials(member_id,status,enabled);

CREATE INDEX IF NOT EXISTS ix_credential_registry_member_status
ON credential_registry(member_id,status,enabled);

CREATE INDEX IF NOT EXISTS ix_payment_account_created
ON payment_transactions(account_id,created_at);

INSERT OR IGNORE INTO system_meta(key,value)
VALUES('nfc_payment_architecture_version','002');