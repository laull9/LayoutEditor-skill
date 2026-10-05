#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SKILL="$(cd "$HERE/../.." && pwd)"
OUT="${1:-$HERE/out}"
PY="${PYTHON:-python3}"
LE_PY="${LE_PY:-$("$SKILL/scripts/find_layouteditor.sh")}"
mkdir -p "$OUT/inputs"
"$LE_PY" "$HERE/process_dies.py" "$OUT/inputs" resistor
"$LE_PY" "$HERE/process_dies.py" "$OUT/inputs" mixer
cp "$HERE/wafer_config.json" "$OUT/config.json"
"$LE_PY" "$SKILL/scripts/wafer_assembly.py" "$OUT/config.json" "$OUT/reticle_assembly.gds" "$OUT/assembly_report.txt"
"$PY" "$SKILL/scripts/render_preview.py" "$OUT/reticle_assembly.polys.json" "$OUT/preview" "$HERE/views.json"
echo "Assembly complete: $OUT"
