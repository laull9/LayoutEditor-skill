# -*- coding: utf-8 -*-
"""
Extract a device-level netlist with LayoutEditor's native extraction (read-only; never saves).

Run with LayoutEditor's bundled Python:
    <LE_PY> extract_netlist.py <layout> <tech.json> <netlist.json> [--top CELL] [--hierarchical]
                               [--native-dump extracted.net]

The technology file (references/pdk-workflow.md) supplies:
  connectivity.stack            conductor, via, conductor, ... bottom to top, as layer names
  connectivity.ignore_datatypes datatypes left out of connectivity (dummy fill, blockages)
  devices                       LayoutEditor extraction methods (MOS-default, R-thinFilm, ...)
Text labels on conductor layers name nets. Unlabelled nets are reported as Node_<n>.

Steps: name layers -> set technology layers -> flatten the top into a temporary cell ->
extractComponent for every device -> buildConnect -> extractNetList -> read the netList.
`--hierarchical` skips flattening; child cells then appear as subcircuit devices and labels
inside them do not name top-level nets.

Output (layouteditor-skill-netlist/1):
    {"top": "NAND2", "nets": ["A", "Y", "Node_9", ...],
     "devices": [{"name": "M1", "component": "nmos", "pins": {"G": "B", "D": "Node_9", "S": "Y"}}],
     "labels": {...}, "warnings": [...]}
Device sizes (W/L, resistance) are not read back; compare them separately if needed.
Exit code: 0 extracted, 2 setup error.
"""
import argparse
import json
import os
import sys

try:
    from LayoutScript import project, point, layers, components, setup
except ImportError:
    sys.exit("extract_netlist.py must run with LayoutEditor's bundled Python (module LayoutScript not found).")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tech import Tech  # noqa: E402

LIBRARY = "layouteditor_skill"
PROP_DEVICE, PROP_COMPONENT = 10, 20     # cellref properties set by extractComponent


def _strings(sl):
    return [sl.at(i) for i in range(sl.size())]


def _elements(cell):
    el = cell.firstElement
    while el:
        if el.thisElement is not None:
            yield el.thisElement
        el = el.nextElement


def setup_technology(tech):
    names = tech.native_names()
    for num, name in names.items():
        layers.num(num).name = name
    layers.technologyLayerRemoveAll()
    for num, kind, level in tech.stack_levels():
        layers.technologyLayerAdd(num, kind)
        layers.technologyLayerSetParameter(num, 0, level)
    setup.clearNetlistNotUseDatatype()
    for dt in tech.ignore_datatypes:
        setup.addNetlistNotUseDatatype(dt)
    for dev in tech.devices:
        comp = components.newComponent(dev["name"], LIBRARY)
        if comp is None:
            raise RuntimeError("Cannot create component %s" % dev["name"])
        comp.prefix = dev.get("prefix", dev.get("spice", {}).get("prefix", "X"))
        comp.extractionMethod = dev["method"]
        comp.extractionParameter = tech.extraction_parameter(dev)


def extract(layout, tech, top=None, hierarchical=False, native_dump=None):
    tech = tech if isinstance(tech, Tech) else Tech.load(tech)
    problems = tech.check()
    if problems:
        raise ValueError("Technology file problems:\n  " + "\n  ".join(problems))
    if not tech.stack:
        raise ValueError("connectivity.stack is empty; nothing connects")
    L = project.newLayout()
    L.open(os.path.abspath(layout))
    dr = L.drawing
    cell = dr.findCell(top) if top else dr.currentCell
    if cell is None:
        raise ValueError("Top cell not found: %s" % top)
    top_name = cell.cellName
    setup_technology(tech)

    if not hierarchical:
        flat = dr.addCell().thisCell
        flat.cellName = "_LVS_FLAT"
        flat.addCellref(cell, point(0, 0))
        dr.setCell(flat)
        flat.selectAll(); dr.flatAll(); flat.deselectAll()
        dr.pathSelect(); dr.toPolygon(); flat.deselectAll()
        cell = flat
    dr.setCell(cell)

    conductors = {num for num, kind, _ in tech.stack_levels() if kind == 2}
    labels, warnings = {}, []
    for e in _elements(cell):
        if e.isText() and e.datatype not in tech.ignore_datatypes:
            name = e.getName()
            if e.layerNum in conductors:
                labels.setdefault(name, []).append(e.layerNum)

    ex = L.extractionTool
    for dev in tech.devices:
        ex.extractComponent(dev["name"], LIBRARY)
    nt = L.netlistTool
    nt.buildConnect()
    nt.extractNetList()
    nl = nt.getExtractedNetList(cell.cellName)
    if nl is None:
        raise RuntimeError("LayoutEditor returned no netlist for %s" % cell.cellName)

    nets = _strings(nl.getNodes())
    by_index = {nl.getNode(n): n for n in nets}
    component_of = {}
    for e in _elements(cell):
        if e.isCellref():
            name = e.getPropertyString(PROP_DEVICE)
            if name:
                component_of[name] = e.getPropertyString(PROP_COMPONENT)
    devices = []
    for i in range(nl.devicesCount()):
        d = nl.getDevice(i)
        pins = {}
        for port in _strings(d.getConnectionNames()):
            idx = d.getNode(port)
            pins[port] = by_index.get(idx, "UNCONNECTED")
        devices.append({"name": d.devicename, "component": component_of.get(d.devicename, d.cellname),
                        "pins": pins})
    devices.sort(key=lambda d: d["name"])

    unnamed = setup.netlistUnnamedNodes or "Node_"
    for name in labels:
        if name not in nets:
            warnings.append("label %s is not on an extracted net (merged into another label?)" % name)
    for d in devices:
        if "UNCONNECTED" in d["pins"].values():
            warnings.append("device %s has an unconnected pin" % d["name"])
    if native_dump:
        nt.extractedNetlistSave(os.path.abspath(native_dump), 0)

    return {
        "format": "layouteditor-skill-netlist/1",
        "layout": os.path.abspath(layout),
        "technology": tech.name,
        "top": top_name,
        "flattened": not hierarchical,
        "nets": nets,
        "unnamed_prefix": unnamed,
        "devices": devices,
        "labels": labels,
        "warnings": warnings,
    }


def main(argv):
    ap = argparse.ArgumentParser(description="Native LayoutEditor netlist extraction")
    ap.add_argument("layout"); ap.add_argument("tech"); ap.add_argument("output")
    ap.add_argument("--top"); ap.add_argument("--hierarchical", action="store_true")
    ap.add_argument("--native-dump")
    a = ap.parse_args(argv[1:])
    try:
        res = extract(a.layout, a.tech, a.top, a.hierarchical, a.native_dump)
    except (ValueError, FileNotFoundError, RuntimeError) as ex:
        print("extract_netlist: %s" % ex, file=sys.stderr)
        return 2
    with open(a.output, "w") as f:
        json.dump(res, f, indent=2)
    print("Extracted %s: %d nets, %d devices -> %s" % (res["top"], len(res["nets"]), len(res["devices"]), a.output))
    for w in res["warnings"]:
        print("  warning: " + w)
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
