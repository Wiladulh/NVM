-- Transaction separation, cashier deposits, operator PIN, and retention metadata
CREATE TABLE IF NOT EXISTS cashier_deposits(
    transaction_id TEXT PRIMARY KEY,
    device_id TEXT NOT NULL,
    credential_id TEXT NOT NULL,
    member_id TEXT NOT NULL,
    account_id TEXT NOT NULL,
    amount INTEGER NOT NULL CHECK(amount>0),
    status TEXT NOT NULL DEFAULT 'pending',
    idempotency_key TEXT UNIQUE,
    balance_before INTEGER,
    balance_after INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_cashier_deposit_created ON cashier_deposits(created_at);
CREATE INDEX IF NOT EXISTS ix_cashier_deposit_device ON cashier_deposits(device_id,created_at);
CREATE INDEX IF NOT EXISTS ix_cashier_deposit_member ON cashier_deposits(member_id,created_at);

ALTER TABLE payment_transactions ADD COLUMN transaction_source TEXT NOT NULL DEFAULT 'WEBUI';
ALTER TABLE vending_transactions ADD COLUMN transaction_source TEXT NOT NULL DEFAULT 'VENDING';

CREATE INDEX IF NOT EXISTS ix_payment_source_created ON payment_transactions(transaction_source,created_at);
CREATE INDEX IF NOT EXISTS ix_vending_source_created ON vending_transactions(transaction_source,created_at);

INSERT OR IGNORE INTO system_meta(key,value) VALUES('cashier_operator_pin_hash','');
INSERT OR IGNORE INTO system_meta(key,value) VALUES('transaction_retention_months','12');
