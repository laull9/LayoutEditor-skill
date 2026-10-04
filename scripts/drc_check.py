# -*- coding: utf-8 -*-
"""
Run design-rule checks on a GDS with LayoutEditor's own drcTool (read-only; never saves).

Run with LayoutEditor's bundled Python:
    <LE_PYTHON> drc_check.py <layout.gds> <TOP_CELL> <rules.json> [report.txt]

rules.json — list of rules; values in µm:
    [
      {"name": "Si min width",        "rule": "minimumSize",            "layer": 3, "value": 2, "merge": true},
      {"name": "Si min space",        "rule": "minimumElementDistance", "layer": 3, "value": 2, "merge": true},
      {"name": "metal-trench space",  "rule": "minimumDistance",        "layer": 1, "layer2": 2, "value": 3},
      {"name": "Si encloses metal",   "rule": "minimumEnclosure",       "layer": 3, "layer2": 2, "value": 3},
      {"name": "no notches",          "rule": "minimumNotchOnLayer",    "layer": 2, "value": 3, "merge": true},
      {"name": "no self-intersection","rule": "noSelfintersectionOnLayer", "layer": 3}
    ]
  minimumEnclosure: `layer` (outer) must enclose `layer2` (inner) by ≥ value.

Exit code: 0 if all rules pass, 1 if any violation, 2 on usage/setup errors.
Notes:
  * The top cell is flattened into a temporary cell and paths are converted to polygons first.
  * Use "merge": true when features are built from overlapping polygons (cells, arrays, fillets).
  * Violation coordinates (first 20 per run) are listed to help locate problems.
"""
import json
import os
import sys

try:
    from LayoutScript import project, point
except ImportError:
    sys.exit("drc_check.py must run with LayoutEditor's bundled Python (module LayoutScript not found).")

UM = 1000


def main(argv):
    if len(argv) < 4:
        print(__doc__)
        return 2
    gds, topname, rules_path = argv[1], argv[2], argv[3]
    report_path = argv[4] if len(argv) > 4 else None
    rules = json.load(open(rules_path))

    L = project.newLayout()
    L.open(os.path.abspath(gds))
    dr = L.drawing
    top = dr.findCell(topname)
    if top is None:
        print("top cell %r not found in %s" % (topname, gds))
        return 2
    flat = dr.addCell().thisCell
    flat.cellName = "_DRC_FLAT"
    flat.addCellref(top, point(0, 0))
    dr.setCell(flat)
    flat.selectAll(); dr.flatAll(); flat.deselectAll()
    dr.pathSelect(); dr.toPolygon(); flat.deselectAll()

    dc = L.drcTool
    dc.setCheckCell()
    dispatch = {
        "minimumSize": lambda r: dc.minimumSize(int(r["value"] * UM), r["layer"], bool(r.get("merge", True)),
                                                bool(r.get("sharp_angles", False))),
        "minimumElementDistance": lambda r: dc.minimumElementDistance(int(r["value"] * UM), r["layer"],
                                                                      bool(r.get("merge", True))),
        "minimumDistance": lambda r: dc.minimumDistance(int(r["value"] * UM), r["layer"], r["layer2"]),
        "minimumEnclosure": lambda r: dc.minimumEnclosure(int(r["value"] * UM), r["layer"], r["layer2"]),
        "minimumNotchOnLayer": lambda r: dc.minimumNotchOnLayer(int(r["value"] * UM), r["layer"],
                                                                bool(r.get("merge", True)), False),
        "noSelfintersectionOnLayer": lambda r: dc.noSelfintersectionOnLayer(r["layer"]),
    }
    lines = ["LayoutEditor drcTool report — %s (cell %s, flattened)" % (os.path.basename(gds), topname), ""]
    prev, failed = 0, 0
    for r in rules:
        fn = dispatch.get(r["rule"])
        if fn is None:
            lines.append("%-40s SKIPPED (unknown rule %r)" % (r["name"], r["rule"]))
            continue
        dc.ruleName = r["name"]
        fn(r)
        n = dc.errorCount - prev
        prev = dc.errorCount
        failed += n > 0
        lines.append("%-40s %s" % (r["name"], "PASS" if n == 0 else "FAIL (%d)" % n))
    lines += ["", "total violations: %d" % dc.errorCount]
    if dc.errorCount:
        lines.append("first violations (value, p1, p2 in µm):")
        for i in range(min(dc.errorCount, 20)):
            try:
                p1, p2 = dc.getViolationPoint1(i), dc.getViolationPoint2(i)
                # getViolationValue() is reported in user units (µm) in the tested version
                lines.append("  %8.3f  (%.3f, %.3f)  (%.3f, %.3f)" % (
                    dc.getViolationValue(i), p1.x() / UM, p1.y() / UM, p2.x() / UM, p2.y() / UM))
            except Exception as ex:  # API differences between versions
                lines.append("  (could not read violation %d: %s)" % (i, ex))
                break
    lines += ["", "---- raw drcTool log ----", dc.result]
    rep = "\n".join(lines)
    print(rep)
    if report_path:
        with open(report_path, "w") as f:
            f.write(rep)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
