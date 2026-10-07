import sqlite3
import hashlib
import secrets
from pathlib import Path
from importlib.resources import files as resource_files

class Database:
    def __init__(self, path: Path):
        self.path = Path(path)

    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        c = sqlite3.connect(self.path)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        return c

    def migrate(self, migrations_dir: Path | None = None):
        if migrations_dir is not None:
            paths = sorted(migrations_dir.glob("*.sql"))
        else:
            root = resource_files("app").joinpath("migrations")
            paths = sorted(Path(root).glob("*.sql"))

        with self.connect() as c:
            for path in paths:
                if path.name == "013_feature_foundation.sql":
                    marker = c.execute(
                        "SELECT value FROM system_meta WHERE key='f01_schema_extension_version'"
                    ).fetchone()
                    if marker and marker[0] == "001":
                        continue

                    member_columns = {row[1] for row in c.execute("PRAGMA table_info(identity_members)")}
                    for name, definition in {
                        "nik": "TEXT",
                        "address": "TEXT",
                        "deleted_at": "TEXT",
                    }.items():
                        if name not in member_columns:
                            c.execute(f"ALTER TABLE identity_members ADD COLUMN {name} {definition}")

                    c.execute(
                        "CREATE UNIQUE INDEX IF NOT EXISTS ux_member_nik_active "
                        "ON identity_members(nik) "
                        "WHERE nik IS NOT NULL AND deleted_at IS NULL"
                    )
                    c.execute(
                        "CREATE INDEX IF NOT EXISTS ix_member_status "
                        "ON identity_members(status)"
                    )

                    device_columns = {row[1] for row in c.execute("PRAGMA table_info(device_registry)")}
                    if "deleted_at" not in device_columns:
                        c.execute("ALTER TABLE device_registry ADD COLUMN deleted_at TEXT")
                    c.execute(
                        "CREATE INDEX IF NOT EXISTS ix_device_status "
                        "ON device_registry(status)"
                    )
                    c.execute(
                        "CREATE INDEX IF NOT EXISTS ix_device_deleted "
                        "ON device_registry(deleted_at)"
                    )

                if path.name == "011_nfc_payment_hardening.sql":
                    marker = c.execute(
                        "SELECT value FROM system_meta WHERE key='nfc_payment_architecture_version'"
                    ).fetchone()
                    if marker and marker[0] == "002":
                        continue
                    for table in ("identity_credentials", "credential_registry"):
                        columns = {row[1] for row in c.execute(f"PRAGMA table_info({table})")}
                        additions = {
                            "pin_failed_attempts": "INTEGER NOT NULL DEFAULT 0",
                            "pin_blocked": "INTEGER NOT NULL DEFAULT 0",
                        }
                        if table == "identity_credentials":
                            additions["enabled"] = "INTEGER NOT NULL DEFAULT 1"
                        for name, definition in additions.items():
                            if name not in columns:
                                c.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")

                    columns = {row[1] for row in c.execute("PRAGMA table_info(payment_transactions)")}
                    target = {
                        "transaction_id": "TEXT PRIMARY KEY",
                        "credential_id": "TEXT NOT NULL",
                        "account_id": "TEXT NOT NULL",
                        "amount": "INTEGER NOT NULL CHECK(amount>=0)",
                        "status": "TEXT NOT NULL",
                        "created_at": "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP",
                        "method": "TEXT NOT NULL DEFAULT 'NFC'",
                        "provider": "TEXT NOT NULL DEFAULT 'local'",
                        "idempotency_key": "TEXT",
                        "provider_transaction_id": "TEXT",
                        "provider_reference": "TEXT",
                        "failure_reason": "TEXT",
                        "device_id": "TEXT",
                        "original_amount": "INTEGER",
                        "discount_amount": "INTEGER NOT NULL DEFAULT 0",
                        "final_amount": "INTEGER",
                        "promo_id": "TEXT",
                        "balance_before": "INTEGER",
                        "balance_after": "INTEGER",
                    }
                    select_defaults = {
                        "method": "'NFC'",
                        "provider": "'local'",
                        "idempotency_key": "NULL",
                        "provider_transaction_id": "NULL",
                        "provider_reference": "NULL",
                        "failure_reason": "NULL",
                        "device_id": "NULL",
                        "original_amount": "amount",
                        "discount_amount": "0",
                        "final_amount": "amount",
                        "promo_id": "NULL",
                        "balance_before": "NULL",
                        "balance_after": "NULL",
                    }
                    select_parts = [
                        name if name in columns else select_defaults.get(name, "NULL")
                        for name in target
                    ]
                    c.execute("CREATE TABLE payment_transactions_new(" +
                              ",".join(f"{name} {definition}" for name, definition in target.items()) +
                              ")")
                    c.execute(
                        "INSERT INTO payment_transactions_new(" +
                        ",".join(target.keys()) + ") SELECT " +
                        ",".join(select_parts) + " FROM payment_transactions"
                    )
                    c.execute("DROP TABLE payment_transactions")
                    c.execute("ALTER TABLE payment_transactions_new RENAME TO payment_transactions")
                    c.execute(
                        "CREATE UNIQUE INDEX IF NOT EXISTS ux_payment_idempotency "
                        "ON payment_transactions(idempotency_key) WHERE idempotency_key IS NOT NULL"
                    )
                    c.execute(
                        "CREATE INDEX IF NOT EXISTS ix_payment_provider_tx "
                        "ON payment_transactions(provider,provider_transaction_id)"
                    )
                    c.execute(
                        "CREATE INDEX IF NOT EXISTS ix_payment_device "
                        "ON payment_transactions(device_id,created_at)"
                    )
                    c.execute(
                        "CREATE INDEX IF NOT EXISTS ix_payment_account_created "
                        "ON payment_transactions(account_id,created_at)"
                    )
                    c.execute(
                        "INSERT OR IGNORE INTO system_meta(key,value) "
                        "VALUES('nfc_payment_architecture_version','002')"
                    )
                    continue

                if path.name == "008_member_pin.sql":
                    columns = {row[1] for row in c.execute("PRAGMA table_info(identity_members)")}
                    if "pin_salt" not in columns: c.execute("ALTER TABLE identity_members ADD COLUMN pin_salt TEXT")
                    if "pin_hash" not in columns: c.execute("ALTER TABLE identity_members ADD COLUMN pin_hash TEXT")
                    continue

                if path.name == "006_vending.sql":
                    product_columns = {
                        row[1] for row in c.execute("PRAGMA table_info(vending_products)")
                    }
                    product_additions = {
                        "machine_id": "TEXT",
                        "stock": "INTEGER NOT NULL DEFAULT 0",
                        "enabled": "INTEGER NOT NULL DEFAULT 1",
                    }
                    for name, definition in product_additions.items():
                        if name not in product_columns:
                            c.execute(f"ALTER TABLE vending_products ADD COLUMN {name} {definition}")

                    transaction_columns = {
                        row[1] for row in c.execute("PRAGMA table_info(vending_transactions)")
                    }
                    transaction_additions = {
                        "credential_id": "TEXT",
                        "account_id": "TEXT",
                        "dispense_status": "TEXT NOT NULL DEFAULT 'pending'",
                        "idempotency_key": "TEXT",
                        "payment_transaction_id": "TEXT",
                        "completed_at": "TEXT",
                    }
                    for name, definition in transaction_additions.items():
                        if name not in transaction_columns:
                            c.execute(f"ALTER TABLE vending_transactions ADD COLUMN {name} {definition}")

                if path.name == "009_vending_registry.sql":
                    machine_columns = {row[1] for row in c.execute("PRAGMA table_info(vending_machines)")}
                    machine_additions = {
                        "location": "TEXT NOT NULL DEFAULT ''",
                        "device_id": "TEXT",
                        "updated_at": "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP",
                    }
                    for name, definition in machine_additions.items():
                        if name not in machine_columns:
                            c.execute(f"ALTER TABLE vending_machines ADD COLUMN {name} {definition}")

                    product_columns = {row[1] for row in c.execute("PRAGMA table_info(vending_products)")}
                    product_additions = {
                        "slot": "INTEGER",
                        "capacity": "INTEGER NOT NULL DEFAULT 0",
                        "servo_channel": "INTEGER",
                    }
                    for name, definition in product_additions.items():
                        if name not in product_columns:
                            c.execute(f"ALTER TABLE vending_products ADD COLUMN {name} {definition}")

                    machines = [row[0] for row in c.execute("SELECT machine_id FROM vending_machines ORDER BY machine_id")]
                    for machine_id in machines:
                        rows = c.execute(
                            "SELECT product_id,stock,slot FROM vending_products "
                            "WHERE machine_id=? ORDER BY created_at,product_id",
                            (machine_id,),
                        ).fetchall()
                        used = {row["slot"] for row in rows if row["slot"] is not None}
                        next_slot = 1
                        for row in rows:
                            slot = row["slot"]
                            if slot is None:
                                while next_slot in used:
                                    next_slot += 1
                                if next_slot <= 5:
                                    slot = next_slot
                                    used.add(slot)
                                else:
                                    continue
                            c.execute(
                                "UPDATE vending_products SET slot=?, capacity=CASE WHEN capacity=0 THEN stock ELSE capacity END, "
                                "servo_channel=CASE WHEN servo_channel IS NULL THEN ? ELSE servo_channel END "
                                "WHERE product_id=?",
                                (slot, slot, row["product_id"]),
                            )
                            next_slot += 1

                c.executescript(path.read_text(encoding="utf-8"))

            vending_tx_columns = {row[1] for row in c.execute("PRAGMA table_info(vending_transactions)")}
            vending_tx_additions = {
                "base_amount": "INTEGER",
                "discount_amount": "INTEGER NOT NULL DEFAULT 0",
                "payment_method": "TEXT NOT NULL DEFAULT 'NFC'",
                "payment_provider": "TEXT NOT NULL DEFAULT 'local'",
                "payment_status": "TEXT NOT NULL DEFAULT 'pending'",
            }
            for name, definition in vending_tx_additions.items():
                if name not in vending_tx_columns:
                    c.execute(f"ALTER TABLE vending_transactions ADD COLUMN {name} {definition}")
            c.execute("UPDATE vending_transactions SET base_amount=amount WHERE base_amount IS NULL")

            vending_columns = {row[1] for row in c.execute("PRAGMA table_info(vending_machines)")}
            if vending_columns and "machine_id" not in vending_columns:
                c.execute("ALTER TABLE vending_machines ADD COLUMN machine_id TEXT")
                c.execute("UPDATE vending_machines SET machine_id='legacy-' || rowid WHERE machine_id IS NULL")
                c.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_vending_machines_machine_id ON vending_machines(machine_id)")

            columns = {row[1] for row in c.execute("PRAGMA table_info(payment_transactions)")}
            if "transaction_source" not in columns:
                c.execute("ALTER TABLE payment_transactions ADD COLUMN transaction_source TEXT NOT NULL DEFAULT 'WEBUI'")
            vending_cols = {row[1] for row in c.execute("PRAGMA table_info(vending_transactions)")}
            if "transaction_source" not in vending_cols:
                c.execute("ALTER TABLE vending_transactions ADD COLUMN transaction_source TEXT NOT NULL DEFAULT 'VENDING'")
            c.execute("CREATE INDEX IF NOT EXISTS ix_payment_source_created ON payment_transactions(transaction_source,created_at)")
            c.execute("CREATE INDEX IF NOT EXISTS ix_vending_source_created ON vending_transactions(transaction_source,created_at)")
            c.execute("INSERT OR IGNORE INTO system_meta(key,value) VALUES('transaction_retention_months','12')")
            pin_row = c.execute("SELECT value FROM system_meta WHERE key='cashier_operator_pin_hash'").fetchone()
            if not pin_row or not pin_row["value"]:
                salt=secrets.token_hex(16)
                digest=hashlib.pbkdf2_hmac("sha256",b"9992",salt.encode(),120000).hex()
                c.execute("INSERT OR REPLACE INTO system_meta(key,value) VALUES('cashier_operator_pin_hash',?)",(salt+":"+digest,))
            additions = {
                "method": "TEXT NOT NULL DEFAULT 'NFC'",
                "provider": "TEXT NOT NULL DEFAULT 'local'",
                "idempotency_key": "TEXT",
                "provider_transaction_id": "TEXT",
                "provider_reference": "TEXT",
                "failure_reason": "TEXT",
                "device_id": "TEXT",
            }
            for name, definition in additions.items():
                if name not in columns:
                    c.execute(f"ALTER TABLE payment_transactions ADD COLUMN {name} {definition}")
            c.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_payment_idempotency "
                "ON payment_transactions(idempotency_key) WHERE idempotency_key IS NOT NULL"
            )
            c.execute(
                "CREATE INDEX IF NOT EXISTS ix_payment_provider_tx "
                "ON payment_transactions(provider,provider_transaction_id)"
            )
            c.execute(
                "CREATE INDEX IF NOT EXISTS ix_payment_device "
                "ON payment_transactions(device_id,created_at)"
            )
            device_columns = {row[1] for row in c.execute("PRAGMA table_info(device_registry)")}
            for name, definition in {
                "auth_key_hash": "TEXT",
                "auth_key_hint": "TEXT",
            }.items():
                if name not in device_columns:
                    c.execute(f"ALTER TABLE device_registry ADD COLUMN {name} {definition}")
            c.execute("CREATE INDEX IF NOT EXISTS ix_device_auth ON device_registry(device_id,auth_key_hash)")
            c.commit()
