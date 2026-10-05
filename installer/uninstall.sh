#!/bin/sh
set -eu
PREFIX=${NVM_PREFIX:-/opt/nvm}
rm -rf "$PREFIX"
echo "NVM application removed; instance data preserved."
