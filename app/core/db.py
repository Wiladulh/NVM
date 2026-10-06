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
                c.executescript(path.read_text(encoding="utf-8"))

            # Upgrade databases created before the finalized vending schema.
            vending_columns = {row[1] for row in c.execute("PRAGMA table_info(vending_machines)")}
            if vending_columns and "machine_id" not in vending_columns:
                c.execute("ALTER TABLE vending_machines ADD COLUMN machine_id TEXT")
                c.execute("UPDATE vending_machines SET machine_id='legacy-' || rowid WHERE machine_id IS NULL")
                c.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_vending_machines_machine_id ON vending_machines(machine_id)")

            columns = {row[1] for row in c.execute("PRAGMA table_info(payment_transactions)")}
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
            c.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_payment_idempotency ON payment_transactions(idempotency_key) WHERE idempotency_key IS NOT NULL")
            c.execute("CREATE INDEX IF NOT EXISTS ix_payment_provider_tx ON payment_transactions(provider,provider_transaction_id)")
            c.execute("CREATE INDEX IF NOT EXISTS ix_payment_device ON payment_transactions(device_id,created_at)")
            c.commit()
