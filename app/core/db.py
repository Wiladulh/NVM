import sqlite3
from pathlib import Path
class Database:
    def __init__(self,path:Path): self.path=path
    def connect(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        c=sqlite3.connect(self.path); c.row_factory=sqlite3.Row; c.execute("PRAGMA foreign_keys=ON"); return c
    def migrate(self,path:Path):
        with self.connect() as c: c.executescript(path.read_text(encoding="utf-8")); c.commit()
