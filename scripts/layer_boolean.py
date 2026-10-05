# -*- coding: utf-8 -*-
"""
layer_boolean — batch layer boolean operations and sizing using LayoutEditor's boolean engine.

Usage:
    <LE_PY> layer_boolean.py <in.gds> <out.gds> <operations.json> [TOP_CELL]

operations.json format:
    [
      {"op": "boolean", "type": "A-B", "layerA": 3, "layerB": 1, "target": 10},
      {"op": "boolean", "type": "A+B", "layerA": 10, "layerB": 2, "target": 12},
      {"op": "size", "layer": 10, "delta_um": 3.0, "target": 13, "corner": 0}
    ]

Boolean types:
    'A-B' (difference: A minus B)
    'A+B' (union: A or B)
    'A*B' (intersection: A and B)
    'AxorB' (xor: symmetric difference)

Size operations:
    delta_um: float (positive = expand, negative = shrink)
    corner: 0 = miter, 1 = round (approx), 2 = octagon

Note:
    Using the boolean engine trips the LayoutEditor free-edition GDS export gate.
    Ensure you run this on a licensed LayoutEditor or in an analysis/intermediate step.
"""
import json
import os
import sys

try:
    from LayoutScript import project
except ImportError:
    project = None

UM = 1000  # 1 µm = 1000 dbu


def _ensure_le():
    if project is None:
        sys.exit("layer_boolean requires LayoutEditor's bundled Python (LayoutScript module).")


def run_layer_operations(in_gds, out_gds, ops, top_name=None):
    """Run a sequence of boolean and sizing operations on a layout."""
    _ensure_le()
    in_gds = os.path.abspath(in_gds)
    out_gds = os.path.abspath(out_gds)
    if not os.path.exists(in_gds):
        raise FileNotFoundError("Input layout not found: %s" % in_gds)

    L = project.newLayout()
    L.open(in_gds)
    dr = L.drawing

    target_cell = dr.findCell(top_name) if top_name else dr.currentCell
    if target_cell is None:
        target_cell = dr.firstCell.thisCell if dr.firstCell else None

    if target_cell is None:
        raise ValueError("No valid cell found in %s" % in_gds)

    if top_name and dr.findCell(top_name) is None:
        raise ValueError("Requested top cell not found: " + top_name)
    if abs(dr.databaseunits - 1e-9) > 1e-15:
        raise ValueError("Layer operations require 1 nm DBU")
    dr.setCell(target_cell)
    bt = L.booleanTool

    for idx, item in enumerate(ops):
        op_kind = item.get("op", "boolean").lower()
        if op_kind == "boolean":
            lay_a = int(item["layerA"])
            lay_b = int(item["layerB"])
            lay_out = int(item["target"])
            b_type = item.get("type", "A-B")
            b_type = "AxorB" if b_type == "A^B" else b_type
            if b_type not in ("A-B", "B-A", "A+B", "A*B", "AxorB"):
                raise ValueError("Unknown boolean type: " + b_type)
            bt.boolOnLayer(lay_a, lay_b, lay_out, b_type)
        elif op_kind in ("size", "sizing", "offset"):
            lay_src = int(item["layer"])
            lay_dst = int(item["target"])
            delta_um = float(item["delta_um"])
            corner = int(item.get("corner", 0))
            delta_dbu = int(round(delta_um * UM))
            dr.copyLayerSized(lay_src, lay_dst, delta_dbu, corner)
        else:
            raise ValueError("Unknown operation kind: " + op_kind)

    dr.setCell(target_cell)
    if os.path.exists(out_gds):
        os.remove(out_gds)
    dr.saveFile(out_gds)
    if not os.path.exists(out_gds):
        raise RuntimeError("Failed to save output to %s (licensed full version required if gated)." % out_gds)

    return out_gds


def main(argv):
    if len(argv) < 4:
        print(__doc__)
        return 2

    in_gds = argv[1]
    out_gds = argv[2]
    ops_file = argv[3]
    top_name = argv[4] if len(argv) > 4 else None

    ops = json.load(open(ops_file))
    res = run_layer_operations(in_gds, out_gds, ops, top_name)
    print("Layer operations completed successfully:", res)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
