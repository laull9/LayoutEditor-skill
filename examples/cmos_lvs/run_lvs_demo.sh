#!/usr/bin/env bash
# Technology file -> generate NAND2 -> audit -> DRC -> native extraction -> LVS -> previews.
# The good layout must pass; the short and open variants must fail LVS.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SKILL="$(cd "$HERE/../.." && pwd)"
OUT="${1:-$HERE/out}"
PY="${PYTHON:-python3}"
LE_PY="${LE_PY:-$("$SKILL/scripts/find_layouteditor.sh")}"
TECH="$HERE/cmos_tech.json"
mkdir -p "$OUT"

"$PY" "$SKILL/scripts/pdk_tool.py" check "$TECH"
"$PY" "$SKILL/scripts/pdk_tool.py" drc-rules "$TECH" "$OUT/drc_rules.json"
for v in good short open; do
  "$LE_PY" "$HERE/nand2.py" "$OUT" "$v"
done
"$LE_PY" "$SKILL/scripts/layout_prep.py" audit "$OUT/nand2_good.gds" "$TECH" --json > "$OUT/audit_good.json"
"$LE_PY" "$SKILL/scripts/drc_check.py" "$OUT/nand2_good.gds" NAND2 "$OUT/drc_rules.json" "$OUT/drc_report.txt"

for v in good short open; do
  "$LE_PY" "$SKILL/scripts/extract_netlist.py" "$OUT/nand2_$v.gds" "$TECH" "$OUT/nand2_${v}_netlist.json" \
    --native-dump "$OUT/nand2_${v}.net"
  set +e
  "$PY" "$SKILL/scripts/lvs_compare.py" "$OUT/nand2_${v}_netlist.json" "$HERE/nand2.sp" "$TECH" \
    "$OUT/lvs_${v}.txt" --json "$OUT/lvs_${v}.json"
  status=$?
  set -e
  expect=0; [[ "$v" != good ]] && expect=1
  if [[ "$status" != "$expect" ]]; then
    echo "LVS for $v returned $status, expected $expect" >&2
    exit 1
  fi
done
"$PY" "$SKILL/scripts/render_preview.py" "$OUT/nand2_good_polys.json" "$OUT/preview" "$HERE/views.json"
echo "LVS demo complete: good passes, short and open fail as intended -> $OUT"
