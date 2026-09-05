#!/usr/bin/env bash
# Compatibility entry point; keep the legacy staging/mount layout unchanged.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
exec bash "$ROOT/scripts/status-dspark-tp4.sh" "$@"
