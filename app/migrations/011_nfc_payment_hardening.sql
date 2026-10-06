ALTER TABLE identity_credentials ADD COLUMN enabled INTEGER NOT NULL DEFAULT 1;
ALTER TABLE identity_credentials ADD COLUMN pin_failed_attempts INTEGER NOT NULL DEFAULT 0;
ALTER TABLE identity_credentials ADD COLUMN pin_blocked INTEGER NOT NULL DEFAULT 0;

ALTER TABLE credential_registry ADD COLUMN pin_failed_attempts INTEGER NOT NULL DEFAULT 0;
ALTER TABLE credential_registry ADD COLUMN pin_blocked INTEGER NOT NULL DEFAULT 0;

CREATE TABLE payment_transactions_new(
    transaction_id TEXT PRIMARY KEY,
    credential_id TEXT NOT NULL,
    account_id TEXT NOT NULL,
    amount INTEGER NOT NULL CHECK(amount>=0),
    status TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    method TEXT NOT NULL DEFAULT 'NFC',
    provider TEXT NOT NULL DEFAULT 'local',
    idempotency_key TEXT,
    provider_transaction_id TEXT,
    provider_reference TEXT,
    failure_reason TEXT,
    device_id TEXT,
    original_amount INTEGER,
    discount_amount INTEGER NOT NULL DEFAULT 0,
    final_amount INTEGER,
    promo_id TEXT,
    balance_before INTEGER,
    balance_after INTEGER
);

INSERT INTO payment_transactions_new(
    transaction_id,credential_id,account_id,amount,status,created_at,
    method,provider,idempotency_key,provider_transaction_id,provider_reference,
    failure_reason,device_id,original_amount,discount_amount,final_amount,
    promo_id,balance_before,balance_after
)
SELECT
    transaction_id,credential_id,account_id,amount,status,created_at,
    'NFC','local',NULL,NULL,NULL,NULL,NULL,amount,0,amount,NULL,NULL,NULL
FROM payment_transactions;

DROP TABLE payment_transactions;
ALTER TABLE payment_transactions_new RENAME TO payment_transactions;

CREATE UNIQUE INDEX IF NOT EXISTS ux_payment_idempotency
ON payment_transactions(idempotency_key)
WHERE idempotency_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_payment_provider_tx
ON payment_transactions(provider,provider_transaction_id);

CREATE INDEX IF NOT EXISTS ix_payment_device
ON payment_transactions(device_id,created_at);

CREATE INDEX IF NOT EXISTS ix_payment_account_created
ON payment_transactions(account_id,created_at);

INSERT OR IGNORE INTO system_meta(key,value)
VALUES('nfc_payment_architecture_version','002');