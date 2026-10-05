#!/bin/sh
set -eu
PREFIX=${NVM_PREFIX:-/opt/nvm}
python3 -m venv "$PREFIX/venv"
"$PREFIX/venv/bin/pip" install --upgrade pip
"$PREFIX/venv/bin/pip" install "$PWD"
mkdir -p "${NVM_DATA_DIR:-/var/lib/nvm}"
echo "NVM installed at $PREFIX"
