-- F01: schema extension for member, NFC, device lifecycle and
-- extensible vending promotion policies.
--
-- Existing financial/payment/vending transaction tables remain intact.
-- QRIS remains foundation-only; no provider is activated here.

CREATE TABLE IF NOT EXISTS member_nfc_cards(
    card_id TEXT PRIMARY KEY,
    member_id TEXT NOT NULL REFERENCES identity_members(member_id),
    credential_id TEXT REFERENCES identity_credentials(credential_id),
    card_uid TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    revoked_at TEXT,
    CHECK(status IN ('active','revoked'))
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_member_nfc_card_uid
ON member_nfc_cards(card_uid);

CREATE INDEX IF NOT EXISTS ix_member_nfc_member
ON member_nfc_cards(member_id,status);

CREATE INDEX IF NOT EXISTS ix_member_nfc_credential
ON member_nfc_cards(credential_id);

CREATE TABLE IF NOT EXISTS vending_promotion_policies(
    promo_id TEXT PRIMARY KEY,
    scope TEXT NOT NULL,
    machine_id TEXT REFERENCES vending_machines(machine_id),
    product_id TEXT REFERENCES vending_products(product_id),
    payment_method TEXT NOT NULL,
    payment_provider TEXT,
    discount_percent REAL NOT NULL,
    starts_at TEXT,
    ends_at TEXT,
    priority INTEGER NOT NULL DEFAULT 0,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK(scope IN ('global','local')),
    CHECK(payment_method IN ('NFC','QRIS')),
    CHECK(discount_percent >= 0.1 AND discount_percent <= 100.0),
    CHECK((scope='global' AND machine_id IS NULL) OR
          (scope='local' AND machine_id IS NOT NULL)),
    CHECK(ends_at IS NULL OR starts_at IS NULL OR ends_at > starts_at)
);

CREATE INDEX IF NOT EXISTS ix_vending_promotion_lookup
ON vending_promotion_policies(machine_id,product_id,payment_method,enabled,priority);

CREATE INDEX IF NOT EXISTS ix_vending_promotion_scope
ON vending_promotion_policies(scope,payment_method,enabled,priority);

CREATE INDEX IF NOT EXISTS ix_vending_promotion_provider
ON vending_promotion_policies(payment_method,payment_provider);

INSERT OR IGNORE INTO system_meta(key,value)
VALUES('f01_schema_extension_version','001');