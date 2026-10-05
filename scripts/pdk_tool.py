# -*- coding: utf-8 -*-
"""
pdk_tool — work with layout-skill technology files (any Python 3.8+, no LayoutEditor).

    python3 pdk_tool.py check <tech.json>
    python3 pdk_tool.py drc-rules <tech.json> <rules.json>
    python3 pdk_tool.py import-layermap <foundry.map> <layers.json> [--purposes drawing,pin,label]
    python3 pdk_tool.py port-map <from_tech.json> <to_tech.json> <mapping.json>

check            validate layer pairs, units, connectivity stack, devices and DRC layer names.
drc-rules        resolve layer names into the numeric rule list read by drc_check.py.
import-layermap  read a text layer map with lines `<layer> <purpose> <gds layer> <gds datatype>`
                 (Virtuoso/OpenAccess style; `#` comments) into a "layers" block. Purpose
                 "drawing" keeps the bare name; other purposes become NAME.PURPOSE.
port-map         pair mapping {"L/D": "L2/D2"} for every layer name both files define, for
                 `layout_prep.py remap` when moving a layout between technologies.
Exit code: 0 OK, 1 problems found, 2 usage error.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tech import Tech  # noqa: E402


def cmd_check(path):
    tech = Tech.load(path)
    problems = tech.check()
    print("%s: %d layers, stack %s, %d devices, %d DRC rules" % (
        tech.name, len(tech.layers), " / ".join(tech.stack) or "-", len(tech.devices), len(tech.drc)))
    for p in problems:
        print("  - " + p)
    print("OK" if not problems else "PROBLEMS")
    return 0 if not problems else 1


def cmd_drc_rules(path, out):
    tech = Tech.load(path)
    problems = tech.check()
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    rules = tech.drc_rules()
    with open(out, "w") as f:
        json.dump(rules, f, indent=1)
    shared = [n for n in {r[k] for r in rules for k in ("layer", "layer2") if k in r}
              if len([p for p in tech.layers.values() if p[0] == n]) > 1]
    print("wrote %d rules -> %s" % (len(rules), out))
    if shared:
        print("note: drcTool checks layer numbers %s across all their datatypes" % sorted(shared))
    return 0


def parse_layermap(text, purposes=None):
    layers = {}
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        tok = line.split()
        if len(tok) < 4 or not (tok[2].isdigit() and tok[3].isdigit()):
            continue
        name, purpose = tok[0], tok[1]
        if purposes and purpose not in purposes:
            continue
        key = name if purpose == "drawing" else "%s.%s" % (name, purpose)
        layers[key] = {"gds": [int(tok[2]), int(tok[3])]}
    return layers


def cmd_import_layermap(path, out, purposes=None):
    with open(path) as f:
        layers = parse_layermap(f.read(), purposes)
    if not layers:
        print("no `<name> <purpose> <layer> <datatype>` lines found in %s" % path, file=sys.stderr)
        return 1
    with open(out, "w") as f:
        json.dump({"layers": layers}, f, indent=1)
    print("imported %d layer purposes -> %s" % (len(layers), out))
    return 0


def cmd_port_map(src, dst, out):
    a, b = Tech.load(src), Tech.load(dst)
    mapping, missing = {}, []
    for name, pair in sorted(a.layers.items()):
        if name in b.layers:
            if pair != b.layers[name]:
                mapping["%d/%d" % pair] = "%d/%d" % b.layers[name]
        else:
            missing.append(name)
    with open(out, "w") as f:
        json.dump(mapping, f, indent=1)
    print("%d pairs change -> %s" % (len(mapping), out))
    if missing:
        print("not in %s (left unmapped): %s" % (b.name, ", ".join(missing)))
    return 0


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    cmd, args = argv[1], argv[2:]
    if cmd == "check" and len(args) == 1:
        return cmd_check(args[0])
    if cmd == "drc-rules" and len(args) == 2:
        return cmd_drc_rules(*args)
    if cmd == "import-layermap" and len(args) >= 2:
        purposes = None
        if "--purposes" in args:
            purposes = set(args[args.index("--purposes") + 1].split(","))
        return cmd_import_layermap(args[0], args[1], purposes)
    if cmd == "port-map" and len(args) == 3:
        return cmd_port_map(*args)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
