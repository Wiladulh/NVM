#!/usr/bin/env python3
import argparse
import sqlite3
from pathlib import Path

p=argparse.ArgumentParser()
p.add_argument("backup")
p.add_argument("database")
a=p.parse_args()

src=Path(a.backup)
dst=Path(a.database)
if not src.exists():
    raise SystemExit(f"backup_not_found: {src}")

srcdb=sqlite3.connect(src)
dst.parent.mkdir(parents=True,exist_ok=True)
tmp=dst.with_suffix(dst.suffix+".restore-tmp")
try:
    if tmp.exists(): tmp.unlink()
    tmpdb=sqlite3.connect(tmp)
    srcdb.backup(tmpdb)
    tmpdb.close()
finally:
    srcdb.close()

tmp.replace(dst)
print(f"restore_ok {dst}")
