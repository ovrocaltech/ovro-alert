#!/usr/bin/env bash
# Deprecated shim — use: lwa-voltage-beam submit "$@"
set -euo pipefail
exec lwa-voltage-beam submit "$@"
