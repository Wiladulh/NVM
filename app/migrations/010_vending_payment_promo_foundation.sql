CREATE TABLE IF NOT EXISTS vending_promo_rules(
    promo_id TEXT PRIMARY KEY,
    machine_id TEXT NOT NULL REFERENCES vending_machines(machine_id),
    product_id TEXT REFERENCES vending_products(product_id),
    payment_method TEXT NOT NULL CHECK(payment_method IN ('NFC','QRIS')),
    payment_provider TEXT,
    discount_percent INTEGER NOT NULL DEFAULT 0 CHECK(discount_percent>=0 AND discount_percent<=100),
    starts_at TEXT,
    ends_at TEXT,
    priority INTEGER NOT NULL DEFAULT 0,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK(ends_at IS NULL OR starts_at IS NULL OR ends_at>starts_at)
);
CREATE INDEX IF NOT EXISTS ix_vending_promo_lookup
ON vending_promo_rules(machine_id,product_id,payment_method,enabled,starts_at,ends_at,priority);
CREATE INDEX IF NOT EXISTS ix_vending_promo_provider
ON vending_promo_rules(payment_method,payment_provider);