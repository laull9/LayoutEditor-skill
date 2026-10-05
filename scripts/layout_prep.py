# -*- coding: utf-8 -*-
"""
layout_prep — inspect, audit, convert, remap, normalize units and merge existing layouts.

Run with LayoutEditor's bundled Python:
    <LE_PY> layout_prep.py inspect <input> [--top CELL] [--json]
    <LE_PY> layout_prep.py audit <input> <tech.json> [--top CELL] [--json]
    <LE_PY> layout_prep.py convert <input> <output.gds/oas/dxf/cif>
    <LE_PY> layout_prep.py remap <input> <output> <mapping.json> [--drop-unmapped]
    <LE_PY> layout_prep.py normalize-dbu <input> <output> [--dbu 1e-9] [--allow-rounding]
    <LE_PY> layout_prep.py merge <spec.json> <output.gds> [TOP_NAME]

Layer keys are "layer/datatype" pairs. A remap mapping may mix pair keys ("6/2": "16/0") with
layer-only keys ("1": 101, datatype kept); pair keys win. Outputs are written to a temporary
file and moved into place only after LayoutEditor has written them, so a failed run never
leaves a partial output and an input can be rewritten in place.

Functions can also be imported:
    from layout_prep import inspect_layout, audit_layout, convert_format, remap_layers,
                            normalize_dbu, merge_layouts
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

try:
    from LayoutScript import project, point, strans
except ImportError:
    project = None

UM = 1000  # 1 µm = 1000 dbu at the 1 nm DBU used by the helpers


def _ensure_le():
    if project is None:
        sys.exit("layout_prep requires LayoutEditor's bundled Python (LayoutScript module).")


def _open(path):
    _ensure_le()
    path = os.path.abspath(path)
    if not os.path.isfile(path):
        raise FileNotFoundError("Layout file not found: %s" % path)
    L = project.newLayout()
    L.open(path)
    return L, L.drawing


def _save(dr, out_path, cell=None):
    """Write via a temporary file in the target folder, then atomically replace out_path."""
    out_path = os.path.abspath(out_path)
    folder, base = os.path.split(out_path)
    stem, ext = os.path.splitext(base)
    fd, tmp = tempfile.mkstemp(prefix="." + stem + ".tmp-", suffix=ext, dir=folder)
    os.close(fd)
    os.remove(tmp)  # LayoutEditor must create the file itself; an existing one hides failures
    if cell is not None:
        dr.setCell(cell)
    try:
        dr.saveFile(tmp)
        if not os.path.isfile(tmp) or os.path.getsize(tmp) == 0:
            raise RuntimeError("LayoutEditor did not write %s (license refusal or unsupported format; "
                               "see references/free-version-limits.md)" % out_path)
        os.replace(tmp, out_path)
    finally:
        for leftover in (tmp, os.path.splitext(tmp)[0] + ".lec"):
            if os.path.exists(leftover):
                os.remove(leftover)
    return out_path


def _cells(dr):
    out = []
    cl = dr.firstCell
    while cl:
        if cl.thisCell:
            out.append(cl.thisCell)
        cl = cl.nextCell
    return out


def _elements(cell):
    el = cell.firstElement
    while el:
        if el.thisElement is not None:
            yield el.thisElement
        el = el.nextElement


def _is_ref(e):
    return e.isCellref() or e.isCellrefArray()


def _kind(e):
    if e.isPolygon():
        return "polygons"
    if e.isBox():
        return "boxes"
    if e.isPath():
        return "paths"
    if e.isText():
        return "texts"
    return "other"


def pair_key(layer, datatype):
    return "%d/%d" % (layer, datatype)


def top_cells(dr):
    """Cells that no other cell references, i.e. candidate tops."""
    cells = _cells(dr)
    used = set()
    for c in cells:
        for e in _elements(c):
            if _is_ref(e) and e.depend() is not None:
                used.add(e.depend().cellName)
    return [c.cellName for c in cells if c.cellName not in used]


def _pick_top(dr, top):
    if top:
        cell = dr.findCell(top)
        if cell is None:
            raise ValueError("Top cell not found: %s" % top)
        return cell
    return dr.currentCell


def _bbox_um(dr, cell):
    scale = dr.databaseunits * 1e6
    xs, ys = [], []
    for e in _elements(cell):
        if not e.isText():
            b = e.getBoundingBox()
            xs += [b.left() * scale, b.right() * scale]
            ys += [b.bottom() * scale, b.top() * scale]
    return [min(xs), min(ys), max(xs), max(ys)] if xs else None


def inspect_layout(path, top=None):
    """Structure, units, references and per layer/datatype statistics of a layout file."""
    L, dr = _open(path)
    cells = _cells(dr)
    pairs, layers = {}, {}
    refs = {"cellrefs": 0, "arrays": 0}
    total = 0
    for c in cells:
        for e in _elements(c):
            total += 1
            if _is_ref(e):
                refs["arrays" if e.isCellrefArray() else "cellrefs"] += 1
                continue
            kind = _kind(e)
            for table, key in ((pairs, pair_key(e.layerNum, e.datatype)), (layers, str(e.layerNum))):
                st = table.setdefault(key, {"polygons": 0, "boxes": 0, "paths": 0, "texts": 0, "other": 0, "total": 0})
                st[kind] += 1
                st["total"] += 1
    chosen = _pick_top(dr, top)
    tops = top_cells(dr)
    return {
        "file": os.path.basename(path),
        "path": os.path.abspath(path),
        "database_unit_m": dr.databaseunits,
        "user_unit": dr.userunits,
        "dbu_is_1nm": abs(dr.databaseunits - 1e-9) < 1e-15,
        "top_cell": chosen.cellName if chosen else "",
        "top_cells": tops,
        "cells": [c.cellName for c in cells],
        "cell_count": len(cells),
        "total_elements": total,
        "references": refs,
        "bbox_um": _bbox_um(dr, chosen) if chosen else None,
        "layer_datatypes": dict(sorted(pairs.items(), key=lambda kv: tuple(map(int, kv[0].split("/"))))),
        "layers": dict(sorted(layers.items(), key=lambda kv: int(kv[0]))),
    }


def audit_layout(path, tech, top=None, max_examples=20):
    """Compare a layout with a technology file: DBU, undeclared layer pairs and off-grid points."""
    from tech import Tech
    tech = tech if isinstance(tech, Tech) else Tech.load(tech)
    L, dr = _open(path)
    declared = tech.by_pair()
    used, unknown = {}, {}
    off_grid, examples = 0, []
    grid = None
    if tech.grid_um:
        grid = int(round(tech.grid_um * 1e-6 / dr.databaseunits))
    for c in _cells(dr):
        for e in _elements(c):
            if not _is_ref(e):
                key = (e.layerNum, e.datatype)
                table = used if key in declared else unknown
                table[key] = table.get(key, 0) + 1
            if grid and grid > 1:
                pa = e.getPoints()
                for i in range(pa.size()):
                    p = pa.point(i)
                    if p.x() % grid or p.y() % grid:
                        off_grid += 1
                        if len(examples) < max_examples:
                            s = dr.databaseunits * 1e6
                            examples.append({"cell": c.cellName, "x_um": p.x() * s, "y_um": p.y() * s})
    chosen = _pick_top(dr, top)
    tops = top_cells(dr)
    problems = []
    if abs(dr.databaseunits - tech.dbu_m) > 1e-15:
        problems.append("DBU %g m differs from technology %g m; run normalize-dbu" % (dr.databaseunits, tech.dbu_m))
    if unknown:
        problems.append("%d elements on layer/datatype pairs not in the technology" % sum(unknown.values()))
    if off_grid:
        problems.append("%d vertices or placements off the %.4g µm grid" % (off_grid, tech.grid_um))
    if len(tops) > 1 and top is None:
        problems.append("several top cells %s; pass --top" % tops)
    return {
        "file": os.path.basename(path),
        "technology": tech.name,
        "top_cell": chosen.cellName if chosen else "",
        "top_cells": tops,
        "database_unit_m": dr.databaseunits,
        "declared_pairs_used": {pair_key(*k): {"names": declared[k], "elements": n} for k, n in sorted(used.items())},
        "undeclared_pairs": {pair_key(*k): n for k, n in sorted(unknown.items())},
        "declared_but_unused": sorted(n for k, names in declared.items() if k not in used for n in names),
        "grid_um": tech.grid_um,
        "off_grid_points": off_grid,
        "off_grid_examples": examples,
        "problems": problems,
        "ok": not problems,
    }


def convert_format(in_path, out_path):
    """Convert by output extension (GDS, OASIS, DXF, CIF, ...). Reopen and check what matters."""
    L, dr = _open(in_path)
    return _save(dr, out_path, dr.currentCell)


def parse_mapping(mapping):
    """{"1": 101, "6/2": "16/0", "7/0": [17, 3]} -> (layer_map, pair_map)."""
    from tech import parse_pair
    layer_map, pair_map = {}, {}
    for k, v in mapping.items():
        key = str(k)
        if "/" in key or ":" in key:
            pair_map[parse_pair(key)] = parse_pair(v)
        else:
            if isinstance(v, (list, tuple)) or "/" in str(v) or ":" in str(v):
                layer_map[int(key)] = parse_pair(v)
            else:
                layer_map[int(key)] = (int(v), None)  # keep each element's datatype
    return layer_map, pair_map


def remap_layers(in_path, out_path, mapping, drop_unmapped=False):
    """Remap layer/datatype pairs in every cell. Cell references are never dropped.

    mapping: {"old_layer": new_layer} keeps the datatype; {"L/D": "L2/D2"} maps one pair.
    drop_unmapped: delete shapes and texts whose pair matches neither form.
    Returns {"changed": n, "dropped": n}.
    """
    layer_map, pair_map = parse_mapping(mapping)
    L, dr = _open(in_path)
    top = dr.currentCell
    changed = dropped = 0
    for c in _cells(dr):
        doomed = []
        for e in _elements(c):
            if _is_ref(e):
                continue
            key = (e.layerNum, e.datatype)
            if key in pair_map:
                new = pair_map[key]
            elif e.layerNum in layer_map:
                lay, dt = layer_map[e.layerNum]
                new = (lay, e.datatype if dt is None else dt)
            else:
                if drop_unmapped:
                    doomed.append(e)
                continue
            if new != key:
                e.layerNum = new[0]
                e.datatype = new[1]
                changed += 1
        for e in doomed:
            c.deleteElement(e)
        dropped += len(doomed)
    _save(dr, out_path, top)
    return {"output": os.path.abspath(out_path), "changed": changed, "dropped": dropped}


def normalize_dbu(in_path, out_path, target=1e-9, allow_rounding=False):
    """Rescale every cell so physical geometry is unchanged at a new database unit.

    Setting `databaseunits` alone reinterprets the integers and shrinks or grows the design.
    This scales each cell (shapes, path widths, reference origins and array pitches) by
    old/new first. A non-integer factor rounds coordinates and is refused unless allowed.
    """
    L, dr = _open(in_path)
    old = dr.databaseunits
    top = dr.currentCell
    factor = old / target
    exact = abs(factor - round(factor)) < 1e-9 and round(factor) >= 1
    if not exact and not allow_rounding:
        raise ValueError("DBU %g m -> %g m is a factor of %.6g; coordinates would be rounded. "
                         "Pass --allow-rounding only after checking the finest feature." % (old, target, factor))
    before = _bbox_um(dr, top) if top else None
    if abs(factor - 1) > 1e-12:
        for c in _cells(dr):
            c.resize(float(factor))
    dr.databaseunits = target
    dr.userunits = target * 1e6  # keep µm as the display unit
    after = _bbox_um(dr, top) if top else None
    tol = max(old, target) * 1e6
    if before and after and max(abs(a - b) for a, b in zip(before, after)) > tol + 1e-9:
        raise RuntimeError("Extent changed during rescale: %s -> %s µm" % (before, after))
    _save(dr, out_path, top)
    return {"output": os.path.abspath(out_path), "from_dbu_m": old, "to_dbu_m": target,
            "factor": factor, "rounded": not exact, "bbox_um": after}


def import_namespaced(master_dr, path, prefix, cell_name=None):
    """Prefix in a source session BEFORE import, so colliding names cannot be merged."""
    _ensure_le()
    path = os.path.abspath(path)
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    if abs(master_dr.databaseunits - 1e-9) > 1e-15:
        raise ValueError("Merge requires 1 nm DBU")
    # This macOS build crashes on a second project.newLayout() in one process.
    # Rename in a separate LayoutEditor Python process, then import once names are safe.
    with tempfile.TemporaryDirectory(prefix="le-import-") as tmp:
        staged = os.path.join(tmp, "namespaced.gds")
        manifest = os.path.join(tmp, "cells.json")
        subprocess.run([sys.executable, os.path.abspath(__file__), "_stage", path,
                        staged, prefix, cell_name or "", manifest], check=True)
        info = json.load(open(manifest))
        chosen_name = info["top"]
        if any(master_dr.findCell(n) is not None for n in info["cells"]):
            raise ValueError("Cell namespace collision; supply a unique prefix for each source")
        master_dr.importFile(staged)
    imported = master_dr.findCell(chosen_name)
    if imported is None:
        raise RuntimeError("Imported top cell missing: " + chosen_name)
    return imported


def stage_namespaced(path, out, prefix, cell_name, manifest):
    L, dr = _open(path)
    if abs(dr.databaseunits - 1e-9) > 1e-15:
        raise ValueError("Merge requires 1 nm DBU; run `layout_prep.py normalize-dbu` first")
    chosen = dr.findCell(cell_name) if cell_name else dr.currentCell
    if chosen is None:
        raise ValueError("Source top cell not found: " + cell_name)
    cells = _cells(dr)
    for c in cells:
        c.cellName = prefix + c.cellName
    dr.setCell(chosen)
    dr.saveFile(out)
    if not os.path.isfile(out) or os.path.getsize(out) == 0:
        raise RuntimeError("Cannot stage namespaced source; check LayoutEditor license")
    with open(manifest, "w") as f:
        json.dump({"top": chosen.cellName, "cells": [c.cellName for c in cells]}, f)


def merge_layouts(spec, out_path, top_name="MERGED_TOP"):
    """Merge sources with unique prefixes, explicit top cells and CCW placement angles."""
    _ensure_le()
    if not spec:
        raise ValueError("Merge specification is empty")
    master_L = project.newLayout()
    dr = master_L.drawing
    top = dr.currentCell
    top.cellName = top_name
    for item in spec:
        child = import_namespaced(dr, item["path"], item.get("prefix", ""), item.get("cell"))
        x, y = item.get("offset", [0, 0])
        e = top.addCellref(child, point(int(round(x * UM)), int(round(y * UM))))
        ang = item.get("angle", 0)
        if ang % 360:
            t = strans()
            t.rotate(-ang)
            e.setTrans(t)
    return _save(dr, out_path, top)


def _print_inspection(res):
    print("File: %s (DBU %g m%s)" % (res["file"], res["database_unit_m"], "" if res["dbu_is_1nm"] else ", NOT 1 nm"))
    print("Top cell: %s | candidate tops: %s | cells: %d" % (res["top_cell"], ", ".join(res["top_cells"]), res["cell_count"]))
    print("Elements: %d (cell refs %d, arrays %d)" % (res["total_elements"], res["references"]["cellrefs"],
                                                       res["references"]["arrays"]))
    b = res["bbox_um"]
    if b:
        print("Extent (µm): x=[%.3f, %.3f], y=[%.3f, %.3f], span %.3f x %.3f" % (
            b[0], b[2], b[1], b[3], b[2] - b[0], b[3] - b[1]))
    print("Layer/datatype:")
    for key, st in res["layer_datatypes"].items():
        print("  %-9s %6d  (poly %d, box %d, path %d, text %d)" % (
            key, st["total"], st["polygons"], st["boxes"], st["paths"], st["texts"]))


def main(argv):
    if len(argv) > 1 and argv[1] == "_stage":
        stage_namespaced(*argv[2:7])
        return 0
    ap = argparse.ArgumentParser(prog="layout_prep.py", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("inspect"); p.add_argument("input"); p.add_argument("--top"); p.add_argument("--json", action="store_true")
    p = sub.add_parser("audit"); p.add_argument("input"); p.add_argument("tech"); p.add_argument("--top")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("convert"); p.add_argument("input"); p.add_argument("output")
    p = sub.add_parser("remap"); p.add_argument("input"); p.add_argument("output"); p.add_argument("mapping")
    p.add_argument("--drop-unmapped", action="store_true")
    p = sub.add_parser("normalize-dbu"); p.add_argument("input"); p.add_argument("output")
    p.add_argument("--dbu", type=float, default=1e-9); p.add_argument("--allow-rounding", action="store_true")
    p = sub.add_parser("merge"); p.add_argument("spec"); p.add_argument("output"); p.add_argument("top", nargs="?", default="MERGED_TOP")
    a = ap.parse_args(argv[1:])

    if a.cmd == "inspect":
        res = inspect_layout(a.input, a.top)
        print(json.dumps(res, indent=2)) if a.json else _print_inspection(res)
        return 0
    if a.cmd == "audit":
        res = audit_layout(a.input, a.tech, a.top)
        if a.json:
            print(json.dumps(res, indent=2))
        else:
            print("Audit %s against %s: %s" % (res["file"], res["technology"], "OK" if res["ok"] else "PROBLEMS"))
            for line in res["problems"]:
                print("  - " + line)
            for key, n in res["undeclared_pairs"].items():
                print("  undeclared %-9s %d elements" % (key, n))
            for ex in res["off_grid_examples"][:5]:
                print("  off grid: %s (%.4f, %.4f) µm" % (ex["cell"], ex["x_um"], ex["y_um"]))
        return 0 if res["ok"] else 1
    if a.cmd == "convert":
        print("Converted to:", convert_format(a.input, a.output))
        return 0
    if a.cmd == "remap":
        res = remap_layers(a.input, a.output, json.load(open(a.mapping)), drop_unmapped=a.drop_unmapped)
        print("Remapped %(changed)d elements, dropped %(dropped)d -> %(output)s" % res)
        return 0
    if a.cmd == "normalize-dbu":
        res = normalize_dbu(a.input, a.output, a.dbu, a.allow_rounding)
        print("DBU %g -> %g m (factor %.6g%s) -> %s" % (res["from_dbu_m"], res["to_dbu_m"], res["factor"],
                                                       ", rounded" if res["rounded"] else "", res["output"]))
        return 0
    if a.cmd == "merge":
        print("Merged layout saved to:", merge_layouts(json.load(open(a.spec)), a.output, top_name=a.top))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
