#!/bin/sh
set -eu
PREFIX=${NVM_PREFIX:-/opt/nvm}
"$PREFIX/venv/bin/pip" install --upgrade "$PWD"
