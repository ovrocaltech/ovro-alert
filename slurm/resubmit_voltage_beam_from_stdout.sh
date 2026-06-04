#!/usr/bin/env bash
# Deprecated shim — use: lwa-voltage-beam resubmit "$@"
set -euo pipefail
exec lwa-voltage-beam resubmit "$@"
