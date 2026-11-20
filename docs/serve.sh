#!/bin/sh
set -eu

exec python3 -m http.server --bind 127.0.0.1 "$@"
