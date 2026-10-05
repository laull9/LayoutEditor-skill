#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SKILL="$(cd "$HERE/../.." && pwd)"
OUT="${1:-$HERE/out}"
PY="${PYTHON:-python3}"
LE_PY="${LE_PY:-$("$SKILL/scripts/find_layouteditor.sh")}"
mkdir -p "$OUT"
"$LE_PY" "$HERE/source_coupons.py" "$OUT" kelvin
"$LE_PY" "$HERE/source_coupons.py" "$OUT" line_space
"$LE_PY" "$SKILL/scripts/layout_prep.py" inspect "$OUT/kelvin.gds" --json > "$OUT/source_inspection.json"
"$LE_PY" "$SKILL/scripts/layout_prep.py" convert "$OUT/kelvin.gds" "$OUT/converted.dxf"
"$LE_PY" "$SKILL/scripts/layout_prep.py" convert "$OUT/kelvin.gds" "$OUT/converted.oas"
"$LE_PY" "$SKILL/scripts/layout_prep.py" remap "$OUT/kelvin.gds" "$OUT/remapped.gds" "$HERE/layer_map.json"
"$LE_PY" "$SKILL/scripts/layout_prep.py" merge "$OUT/merge_spec.json" "$OUT/dual_merged.gds" PREP_COUPONS
"$LE_PY" "$SKILL/scripts/dump_layout.py" "$OUT/dual_merged.gds" PREP_COUPONS "$OUT/merged_polys.json" "$HERE/layers.json"
"$PY" "$SKILL/scripts/render_preview.py" "$OUT/merged_polys.json" "$OUT/preview" "$HERE/views.json"
# Export after booleans depends on the installed edition. Keep the default demo usable on free.
if [[ "${RUN_LICENSED_BOOLEAN:-0}" == 1 ]]; then
  "$LE_PY" "$SKILL/scripts/layer_boolean.py" "$OUT/kelvin.gds" "$OUT/boolean_result.gds" "$HERE/bool_ops.json" TOP
else
  echo "Boolean export skipped; set RUN_LICENSED_BOOLEAN=1 with a suitable license."
fi
echo "Data prep complete: $OUT"
