#!/bin/sh
set -eu
exec python3 -m uvicorn app.main:app --host "${NVM_HOST:-127.0.0.1}" --port "${NVM_PORT:-8011}"
