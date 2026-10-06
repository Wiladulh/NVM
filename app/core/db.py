import sqlite3
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
                # 006_vending.sql creates indexes on columns introduced by the
                # finalized vending schema. Older databases already have the
                # legacy tables from 001_initial.sql, so add those columns
                # before executing 006. This preserves all legacy rows.
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
                            c.execute(
                                f"ALTER TABLE vending_products ADD COLUMN {name} {definition}"
                            )

                    transaction_columns = {
                        row[1]
                        for row in c.execute("PRAGMA table_info(vending_transactions)")
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
                            c.execute(
                                f"ALTER TABLE vending_transactions ADD COLUMN {name} {definition}"
                            )

                c.executescript(path.read_text(encoding="utf-8"))

            # Upgrade databases created before the finalized vending schema.
            vending_columns = {
                row[1] for row in c.execute("PRAGMA table_info(vending_machines)")
            }
            if vending_columns and "machine_id" not in vending_columns:
                c.execute("ALTER TABLE vending_machines ADD COLUMN machine_id TEXT")
                c.execute(
                    "UPDATE vending_machines SET machine_id='legacy-' || rowid "
                    "WHERE machine_id IS NULL"
                )
                c.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS "
                    "ux_vending_machines_machine_id ON vending_machines(machine_id)"
                )

            columns = {
                row[1] for row in c.execute("PRAGMA table_info(payment_transactions)")
            }
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
                    c.execute(
                        f"ALTER TABLE payment_transactions ADD COLUMN {name} {definition}"
                    )
            c.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_payment_idempotency "
                "ON payment_transactions(idempotency_key) "
                "WHERE idempotency_key IS NOT NULL"
            )
            c.execute(
                "CREATE INDEX IF NOT EXISTS ix_payment_provider_tx "
                "ON payment_transactions(provider,provider_transaction_id)"
            )
            c.execute(
                "CREATE INDEX IF NOT EXISTS ix_payment_device "
                "ON payment_transactions(device_id,created_at)"
            )
            c.commit()
