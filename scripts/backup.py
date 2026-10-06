#!/usr/bin/env python3
import argparse
import sqlite3
from pathlib import Path

p=argparse.ArgumentParser()
p.add_argument("database")
p.add_argument("output")
a=p.parse_args()

src=Path(a.database)
dst=Path(a.output)
dst.parent.mkdir(parents=True,exist_ok=True)

if not src.exists():
    raise SystemExit(f"database_not_found: {src}")

srcdb=sqlite3.connect(src)
dstdb=sqlite3.connect(dst)
try:
    srcdb.backup(dstdb)
finally:
    dstdb.close()
    srcdb.close()

print(f"backup_ok {dst}")
