#!/usr/bin/env bash
# End-to-end demo: generate → DRC → connectivity/release → previews.
# Needs LayoutEditor (for generation + DRC) and a CPython with numpy, Pillow, matplotlib.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SKILL="$(cd "$HERE/../.." && pwd)"
OUT="${1:-$HERE/out}"
PY="${PYTHON:-python3}"
LE_PY="${LE_PY:-$("$SKILL/scripts/find_layouteditor.sh")}"

"$LE_PY" "$HERE/demo_chip.py" "$OUT"
"$LE_PY" "$SKILL/scripts/drc_check.py" "$OUT/demo_chip.gds" DEMO_CHIP "$HERE/demo_drc_rules.json" "$OUT/drc_report.txt"
"$PY" "$SKILL/scripts/check_connectivity.py" "$OUT/demo_chip_polys.json" "$HERE/demo_probes.json" "$OUT/connectivity_report.txt"
"$PY" "$SKILL/scripts/render_preview.py" "$OUT/demo_chip_polys.json" "$OUT/preview" "$HERE/demo_views.json"
echo "done → $OUT"
