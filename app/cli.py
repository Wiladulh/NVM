import argparse
from pathlib import Path
from app.core.config import get_settings
from app.core.db import Database
def main():
    p=argparse.ArgumentParser(prog="nvm"); p.add_argument("command",nargs="?",choices=["init"]); a=p.parse_args()
    if a.command=="init":
        s=get_settings(); Database(s.db_path).migrate(Path(__file__).resolve().parents[1]/"database/migrations/001_initial.sql"); print(s.db_path)
    else: p.print_help()
if __name__=="__main__": main()
