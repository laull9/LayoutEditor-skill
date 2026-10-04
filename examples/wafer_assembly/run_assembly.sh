#!/usr/bin/env bash
# End-to-end multi-die assembly and dicing street demo.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SKILL="$(cd "$HERE/../.." && pwd)"
OUT="${1:-$HERE/out}"
LE_PY="${LE_PY:-$("$SKILL/scripts/find_layouteditor.sh")}"

mkdir -p "$OUT"

# Ensure the MEMS die GDS exists
MEMS_GDS="$SKILL/examples/mems_comb_drive/out/demo_chip.gds"
if [ ! -f "$MEMS_GDS" ]; then
    echo "Building prerequisite MEMS die..."
    "$LE_PY" "$SKILL/examples/mems_comb_drive/demo_chip.py" "$SKILL/examples/mems_comb_drive/out"
fi

# Run wafer assembly
"$LE_PY" "$SKILL/scripts/wafer_assembly.py" "$HERE/wafer_config.json" "$OUT/reticle_assembly.gds" "$OUT/assembly_report.txt"

# Inspect the result
"$LE_PY" "$SKILL/scripts/layout_prep.py" inspect "$OUT/reticle_assembly.gds"

echo "Assembly complete → $OUT"
