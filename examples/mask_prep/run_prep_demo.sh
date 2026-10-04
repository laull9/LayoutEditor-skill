#!/usr/bin/env bash
# End-to-end mask preparation, inspection, format conversion, layer remapping,
# multi-GDS merging, and boolean layer operations demo.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SKILL="$(cd "$HERE/../.." && pwd)"
OUT="${1:-$HERE/out}"
LE_PY="${LE_PY:-$("$SKILL/scripts/find_layouteditor.sh")}"

mkdir -p "$OUT"

# 1. Ensure input GDS exists
INPUT_GDS="$SKILL/examples/mems_comb_drive/out/demo_chip.gds"
if [ ! -f "$INPUT_GDS" ]; then
    echo "Building prerequisite MEMS layout..."
    "$LE_PY" "$SKILL/examples/mems_comb_drive/demo_chip.py" "$SKILL/examples/mems_comb_drive/out"
fi

echo "--- 1. Inspecting Layout ---"
"$LE_PY" "$SKILL/scripts/layout_prep.py" inspect "$INPUT_GDS"

echo "--- 2. Converting GDS to DXF ---"
"$LE_PY" "$SKILL/scripts/layout_prep.py" convert "$INPUT_GDS" "$OUT/converted.dxf"

echo "--- 3. Remapping Layers ---"
cat << 'EOF' > "$OUT/layer_map.json"
{
  "1": 101,
  "2": 102,
  "3": 103,
  "4": 104
}
EOF
"$LE_PY" "$SKILL/scripts/layout_prep.py" remap "$INPUT_GDS" "$OUT/remapped.gds" "$OUT/layer_map.json"
"$LE_PY" "$SKILL/scripts/layout_prep.py" inspect "$OUT/remapped.gds"

echo "--- 4. Merging Multiple GDS Files (Dual-Die) ---"
cat << EOF > "$OUT/merge_spec.json"
[
  {"path": "$INPUT_GDS", "prefix": "LEFT_", "offset": [-1100, 0]},
  {"path": "$INPUT_GDS", "prefix": "RIGHT_", "offset": [1100, 0]}
]
EOF
"$LE_PY" "$SKILL/scripts/layout_prep.py" merge "$OUT/merge_spec.json" "$OUT/dual_merged.gds" DUAL_CHIP
"$LE_PY" "$SKILL/scripts/layout_prep.py" inspect "$OUT/dual_merged.gds"

echo "--- 5. Layer Boolean & Sizing Operations ---"
cat << 'EOF' > "$OUT/bool_ops.json"
[
  {"op": "boolean", "type": "A-B", "layerA": 3, "layerB": 1, "target": 20},
  {"op": "size", "layer": 20, "delta_um": 2.0, "target": 21}
]
EOF
"$LE_PY" "$SKILL/scripts/layer_boolean.py" "$INPUT_GDS" "$OUT/boolean_result.gds" "$OUT/bool_ops.json" DEMO_CHIP
"$LE_PY" "$SKILL/scripts/layout_prep.py" inspect "$OUT/boolean_result.gds"

echo "Data prep demo complete → $OUT"
