#!/usr/bin/env bash
# End-to-end Silicon Photonics (PIC) demo: generate → previews.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SKILL="$(cd "$HERE/../.." && pwd)"
OUT="${1:-$HERE/out}"
PY="${PYTHON:-python3}"
LE_PY="${LE_PY:-$("$SKILL/scripts/find_layouteditor.sh")}"

"$LE_PY" "$HERE/pic_chip.py" "$OUT"
"$LE_PY" "$SKILL/scripts/drc_check.py" "$OUT/pic_chip.gds" PIC_DEMO_CHIP "$HERE/pic_drc_rules.json" "$OUT/drc_report.txt"
"$PY" "$SKILL/scripts/render_preview.py" "$OUT/pic_chip_polys.json" "$OUT/preview" "$HERE/pic_views.json"
echo "PIC demo complete → $OUT"
