#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
exec bash "$HERE/mems_comb_drive/run_mems.sh" "${1:-$HERE/out}"
