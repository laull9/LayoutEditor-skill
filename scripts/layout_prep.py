# -*- coding: utf-8 -*-
"""
layout_prep — layout data preparation, inspection, format conversion, layer remapping and multi-GDS merging.

Run with LayoutEditor's bundled Python:
    <LE_PY> layout_prep.py inspect <input.gds> [--json]
    <LE_PY> layout_prep.py convert <input.gds> <output.oas/dxf/cif>
    <LE_PY> layout_prep.py remap <input.gds> <output.gds> <mapping.json> [--drop-unmapped]
    <LE_PY> layout_prep.py merge <spec.json> <output.gds> [TOP_NAME]

Functions can also be imported in Python:
    from layout_prep import inspect_layout, convert_format, remap_layers, merge_layouts
"""
import json
import os
import sys

try:
    from LayoutScript import project, point, strans
except ImportError:
    project = None

UM = 1000  # 1 µm = 1000 dbu (default)


def _ensure_le():
    if project is None:
        sys.exit("layout_prep requires LayoutEditor's bundled Python (LayoutScript module).")


def inspect_layout(path):
    """Inspect an existing mask layout and return structure and layer statistics."""
    _ensure_le()
    path = os.path.abspath(path)
    if not os.path.exists(path):
        raise FileNotFoundError("Layout file not found: %s" % path)

    L = project.newLayout()
    L.open(path)
    dr = L.drawing

    cells = []
    cl = dr.firstCell
    while cl:
        if cl.thisCell:
            cells.append(cl.thisCell.cellName)
        cl = cl.nextCell

    top_name = dr.currentCell.cellName if dr.currentCell else (cells[0] if cells else "")
    dbu = dr.databaseunits

    # Collect element and layer statistics across all cells
    layer_stats = {}
    total_elements = 0
    all_xs, all_ys = [], []

    cl = dr.firstCell
    while cl:
        c = cl.thisCell
        if c:
            el = c.firstElement
            while el:
                e = el.thisElement
                if e is not None:
                    total_elements += 1
                    lay = e.layerNum
                    st = layer_stats.setdefault(str(lay), {
                        "polygons": 0, "boxes": 0, "paths": 0, "texts": 0,
                        "cellrefs": 0, "arrays": 0, "total": 0
                    })
                    st["total"] += 1
                    if e.isPolygon():
                        st["polygons"] += 1
                    elif e.isBox():
                        st["boxes"] += 1
                    elif e.isPath():
                        st["paths"] += 1
                    elif e.isText():
                        st["texts"] += 1
                    elif e.isCellref():
                        st["cellrefs"] += 1
                    elif e.isCellrefArray():
                        st["arrays"] += 1

                    pa = e.getPoints()
                    if pa is not None and pa.size() > 0:
                        for i in range(pa.size()):
                            all_xs.append(pa.point(i).x() / UM)
                            all_ys.append(pa.point(i).y() / UM)
                el = el.nextElement
        cl = cl.nextCell

    bbox = [min(all_xs), min(all_ys), max(all_xs), max(all_ys)] if all_xs else None

    return {
        "file": os.path.basename(path),
        "path": path,
        "database_unit_m": dbu,
        "top_cell": top_name,
        "cells": cells,
        "cell_count": len(cells),
        "total_elements": total_elements,
        "bbox_um": bbox,
        "layers": layer_stats
    }


def convert_format(in_path, out_path):
    """Convert layout file format (e.g. GDSII to OASIS, DXF, CIF)."""
    _ensure_le()
    in_path = os.path.abspath(in_path)
    out_path = os.path.abspath(out_path)
    if not os.path.exists(in_path):
        raise FileNotFoundError("Input file not found: %s" % in_path)

    L = project.newLayout()
    L.open(in_path)
    dr = L.drawing
    if os.path.exists(out_path):
        os.remove(out_path)
    dr.saveFile(out_path)
    if not os.path.exists(out_path):
        raise RuntimeError("Failed to export to %s" % out_path)
    return out_path


def remap_layers(in_path, out_path, mapping, drop_unmapped=False):
    """Remap layer numbers in a layout.

    mapping: dict of {old_layer_int: new_layer_int}
    drop_unmapped: if True, delete elements whose layer is not in mapping.
    """
    _ensure_le()
    in_path = os.path.abspath(in_path)
    out_path = os.path.abspath(out_path)
    mapping = {int(k): int(v) for k, v in mapping.items()}

    L = project.newLayout()
    L.open(in_path)
    dr = L.drawing

    cl = dr.firstCell
    while cl:
        c = cl.thisCell
        if c:
            el = c.firstElement
            to_delete = []
            while el:
                e = el.thisElement
                if e is not None:
                    old_lay = e.layerNum
                    if old_lay in mapping:
                        e.layerNum = mapping[old_lay]
                    elif drop_unmapped:
                        to_delete.append(e)
                el = el.nextElement
            for e in to_delete:
                c.deleteElement(e)
        cl = cl.nextCell

    if os.path.exists(out_path):
        os.remove(out_path)
    dr.saveFile(out_path)
    if not os.path.exists(out_path):
        raise RuntimeError("Failed to save remapped layout to %s" % out_path)
    return out_path


def merge_layouts(spec, out_path, top_name="MERGED_TOP"):
    """Merge multiple layout files into a single master top cell.

    spec: list of dicts:
        [
            {"path": "die1.gds", "prefix": "D1_", "cell": "TOP", "offset": [0, 0], "angle": 0},
            {"path": "die2.gds", "prefix": "D2_", "cell": "TOP", "offset": [3000, 0], "angle": 0}
        ]
    """
    _ensure_le()
    out_path = os.path.abspath(out_path)
    master_L = project.newLayout()
    master_dr = master_L.drawing
    master_top = master_dr.currentCell
    master_top.cellName = top_name

    existing_cell_names = {top_name}

    for item in spec:
        p = os.path.abspath(item["path"])
        if not os.path.exists(p):
            raise FileNotFoundError("Merge input not found: %s" % p)
        prefix = item.get("prefix", "")
        req_cell = item.get("cell", None)
        offset = item.get("offset", [0, 0])
        ang = item.get("angle", 0)

        # Import the sub-file into the master drawing
        master_dr.importFile(p)

        # Find all newly imported cells
        cl = master_dr.firstCell
        new_cells = []
        while cl:
            c = cl.thisCell
            if c and c.cellName not in existing_cell_names:
                new_cells.append(c)
            cl = cl.nextCell

        # Rename newly imported cells if prefix is requested
        placed_cell = None
        for c in new_cells:
            old_name = c.cellName
            if req_cell and old_name == req_cell:
                placed_cell = c
            elif not req_cell and placed_cell is None:
                # Default to the first major cell or last imported cell
                placed_cell = c

            if prefix:
                c.cellName = prefix + old_name
            existing_cell_names.add(c.cellName)

        # If not uniquely identified, fallback to the last cell in the new batch
        if placed_cell is None and new_cells:
            placed_cell = new_cells[-1]

        if placed_cell:
            pt_off = point(int(round(offset[0] * UM)), int(round(offset[1] * UM)))
            ref_el = master_top.addCellref(placed_cell, pt_off)
            if ang % 360:
                t = strans()
                t.rotate(-ang)  # clockwise quirk
                ref_el.setTrans(t)

    top_obj = master_dr.findCell(top_name)
    if top_obj:
        master_dr.setCell(top_obj)
    if os.path.exists(out_path):
        os.remove(out_path)
    master_dr.saveFile(out_path)
    if not os.path.exists(out_path):
        raise RuntimeError("Failed to save merged layout to %s" % out_path)
    return out_path


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2

    cmd = argv[1]
    if cmd == "inspect":
        if len(argv) < 3:
            print("Usage: layout_prep.py inspect <input.gds> [--json]")
            return 2
        res = inspect_layout(argv[2])
        if "--json" in argv:
            print(json.dumps(res, indent=2))
        else:
            print("File: %s (DBU: %g m)" % (res["file"], res["database_unit_m"]))
            print("Top cell: %s | Total cells: %d" % (res["top_cell"], res["cell_count"]))
            print("Total elements: %d" % res["total_elements"])
            if res["bbox_um"]:
                print("Extent (µm): x=[%.2f, %.2f], y=[%.2f, %.2f], span=%.2f x %.2f µm" % (
                    res["bbox_um"][0], res["bbox_um"][2], res["bbox_um"][1], res["bbox_um"][3],
                    res["bbox_um"][2] - res["bbox_um"][0], res["bbox_um"][3] - res["bbox_um"][1]
                ))
            print("Layers:")
            for lnum, st in sorted(res["layers"].items(), key=lambda x: int(x[0])):
                print("  Layer %3s: %5d elements (poly: %d, box: %d, path: %d, ref: %d, text: %d)" % (
                    lnum, st["total"], st["polygons"], st["boxes"], st["paths"], st["cellrefs"], st["texts"]
                ))
        return 0

    elif cmd == "convert":
        if len(argv) < 4:
            print("Usage: layout_prep.py convert <input> <output>")
            return 2
        out = convert_format(argv[2], argv[3])
        print("Converted to:", out)
        return 0

    elif cmd == "remap":
        if len(argv) < 5:
            print("Usage: layout_prep.py remap <input> <output> <mapping.json> [--drop-unmapped]")
            return 2
        mapping = json.load(open(argv[4]))
        drop = "--drop-unmapped" in argv
        out = remap_layers(argv[2], argv[3], mapping, drop_unmapped=drop)
        print("Remapped saved to:", out)
        return 0

    elif cmd == "merge":
        if len(argv) < 4:
            print("Usage: layout_prep.py merge <spec.json> <output> [TOP_NAME]")
            return 2
        spec = json.load(open(argv[2]))
        top = argv[4] if len(argv) > 4 else "MERGED_TOP"
        out = merge_layouts(spec, argv[3], top_name=top)
        print("Merged layout saved to:", out)
        return 0

    else:
        print("Unknown command: %s" % cmd)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
