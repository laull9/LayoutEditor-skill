# -*- coding: utf-8 -*-
"""
Compare an extracted netlist with a reference netlist (layout versus schematic).

Run with any Python 3.8+ (no LayoutEditor needed):
    python3 lvs_compare.py <extracted.json> <reference.sp|.json> <tech.json> [report.txt]
                           [--top CELL] [--json result.json]

<extracted.json>  output of extract_netlist.py.
<reference>       SPICE subset or JSON with the same structure as the extracted file.
<tech.json>       technology file; its devices map SPICE lines to components:
                  "spice": {"prefix": "M", "models": ["nmos"], "pins": ["D", "G", "S", "B"]}
                  Pins that the layout device does not have (e.g. bulk "B") are dropped.
                  "equivalent_ports": [["S", "D"]] makes those pins interchangeable.

SPICE subset: .subckt/.ends (nested subcircuits are flattened), `+` continuation lines,
`*` comments and `key=value` parameters (ignored). The subcircuit named --top, or the one
named like the extracted top, is compared; without subcircuits the top-level lines are used.

Matching: named nets (subcircuit pins and layout labels) anchor the comparison; all other nets
and all device names are matched by circuit structure (iterative refinement, then an exact
backtracking match). Device parameters (W/L, values) are not compared.
Exit code: 0 match, 1 mismatch, 2 usage/setup error.
"""
import argparse
from collections import Counter
from itertools import permutations
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tech import Tech  # noqa: E402

MAX_STEPS = 200000


class Circuit:
    def __init__(self, name, devices, ports=(), unnamed=None):
        self.name = name
        self.devices = devices            # [{"name", "component", "pins": {pin: net}}]
        self.ports = list(ports)
        self.nets = sorted({n for d in devices for n in d["pins"].values()} | set(self.ports))
        self.unnamed = unnamed            # regex for anonymous layout nets


# -- reference parsing -------------------------------------------------------

def _spice_lines(text):
    lines = []
    for raw in text.splitlines():
        line = re.split(r"[;$]", raw, maxsplit=1)[0].rstrip()
        if not line.strip() or line.lstrip().startswith("*"):
            continue
        if line.lstrip().startswith("+") and lines:
            lines[-1] += " " + line.lstrip()[1:]
        else:
            lines.append(line.strip())
    return lines


def parse_spice(text, tech, top=None):
    lines = _spice_lines(text)
    if lines and not lines[0].startswith((".", "x", "X", "m", "M", "r", "R", "c", "C", "q", "Q", "d", "D")):
        lines = lines[1:]  # SPICE title line
    subckts, body, current, warnings = {}, [], None, []
    for line in lines:
        tok = line.split()
        key = tok[0].lower()
        if key == ".subckt":
            current = tok[1]
            subckts[current] = {"ports": [t for t in tok[2:] if "=" not in t], "lines": []}
        elif key == ".ends":
            current = None
        elif key.startswith("."):
            if key not in (".end", ".global", ".param", ".model", ".include", ".lib", ".option", ".options"):
                warnings.append("ignored %s" % tok[0])
        else:
            (subckts[current]["lines"] if current else body).append(tok)

    lower = {k.lower(): k for k in subckts}
    dev_by_prefix = {}
    for dev in tech.devices:
        sp = dev.get("spice")
        if sp:
            dev_by_prefix.setdefault(sp.get("prefix", "X").upper(), []).append(dev)

    def device_for(tok):
        params = [t for t in tok[1:] if "=" not in t]
        for dev in dev_by_prefix.get(tok[0][0].upper(), []):
            sp = dev["spice"]
            n = len(sp["pins"])
            if len(params) < n:
                continue
            model = params[n] if len(params) > n else None
            models = [m.lower() for m in sp.get("models", [])]
            if not models or (model and model.lower() in models):
                return dev, params[:n]
        return None, None

    def expand(lines, prefix, netmap, depth=0):
        if depth > 32:
            raise ValueError("subcircuit nesting deeper than 32 levels")
        devices = []
        for tok in lines:
            name = prefix + tok[0]
            params = [t for t in tok[1:] if "=" not in t]
            if tok[0][0] in "xX" and params and params[-1].lower() in lower:
                sub = subckts[lower[params[-1].lower()]]
                nodes = params[:-1]
                if len(nodes) != len(sub["ports"]):
                    raise ValueError("%s connects %d nodes, subcircuit %s has %d ports"
                                     % (tok[0], len(nodes), params[-1], len(sub["ports"])))
                inner = {p: netmap.get(nd, prefix + nd) for p, nd in zip(sub["ports"], nodes)}
                devices += expand(sub["lines"], name + "/", inner, depth + 1)
                continue
            dev, nodes = device_for(tok)
            if dev is not None:
                pins = {p: netmap.get(nd, prefix + nd) for p, nd in zip(dev["spice"]["pins"], nodes) if p in dev["ports"]}
                devices.append({"name": name, "component": dev["name"], "pins": pins})
                continue
            raise ValueError("No technology device matches SPICE line: %s" % " ".join(tok))
        return devices

    if subckts:
        name = lower.get(top.lower()) if top else None
        if name is None and not body:
            used = {t[-1].lower() for sub in subckts.values() for t in sub["lines"] if t[0][0] in "xX"}
            roots = [k for k in subckts if k.lower() not in used]
            if len(roots) != 1:
                raise ValueError("Subcircuit %s not found; pass --top (available: %s)" % (top, ", ".join(subckts)))
            name = roots[0]
        if name is not None:
            sub = subckts[name]
            devices = expand(sub["lines"], "", {p: p for p in sub["ports"]})
            return Circuit(name, devices, sub["ports"]), warnings
    return Circuit(top or "TOP", expand(body, "", {}), ()), warnings


def load_reference(path, tech, top=None):
    if path.lower().endswith(".json"):
        data = json.load(open(path))
        return Circuit(data.get("top", "TOP"), data["devices"], data.get("pins", [])), []
    with open(path) as f:
        return parse_spice(f.read(), tech, top)


def load_extracted(path):
    data = json.load(open(path))
    prefix = data.get("unnamed_prefix", "Node_")
    return Circuit(data["top"], data["devices"], (), re.compile(r"^%s-?\d+$" % re.escape(prefix))), data


# -- comparison ----------------------------------------------------------------

def pin_classes(tech):
    classes = {}
    for dev in tech.devices:
        cls = {p: p for p in dev["ports"]}
        for group in dev.get("equivalent_ports", []):
            label = "=".join(sorted(group))
            for p in group:
                cls[p] = label
        classes[dev["name"]] = cls
    return classes


class Graph:
    """Bipartite device/net graph with comparable colors."""

    def __init__(self, circ, anchors, classes):
        self.c = circ
        self.devs = list(range(len(circ.devices)))
        self.nets = circ.nets
        self.anchor = {n: anchors.get(n.lower()) for n in self.nets}
        self.edges_d = []                 # per device: [(pin class, net)]
        self.edges_n = {n: [] for n in self.nets}
        for i, d in enumerate(circ.devices):
            cls = classes.get(d["component"], {})
            e = [(cls.get(p, p), n) for p, n in d["pins"].items()]
            self.edges_d.append(e)
            for pc, n in e:
                self.edges_n[n].append((pc, i))


def refine(graphs):
    table = {}

    def code(sig):
        return table.setdefault(sig, len(table))

    dcol = [[code(("D", g.c.devices[i]["component"])) for i in g.devs] for g in graphs]
    ncol = [{n: code(("N", g.anchor[n])) for n in g.nets} for g in graphs]
    prev = -1
    for _ in range(4 * max(len(g.devs) + len(g.nets) for g in graphs) + 2):
        new_d = [[code(("d", dcol[k][i], tuple(sorted((pc, ncol[k][n]) for pc, n in g.edges_d[i]))))
                  for i in g.devs] for k, g in enumerate(graphs)]
        new_n = [{n: code(("n", ncol[k][n], tuple(sorted((pc, dcol[k][i]) for pc, i in g.edges_n[n]))))
                  for n in g.nets} for k, g in enumerate(graphs)]
        dcol, ncol = new_d, new_n
        distinct = len(set(x for c in dcol for x in c)) + len(set(x for c in ncol for x in c.values()))
        if distinct == prev:
            break
        prev = distinct
    return dcol, ncol


def exact_match(ga, gb, dcol, ncol):
    """Backtracking device/net bijection consistent with colors. Returns mapping, None or 'limit'."""
    order = sorted(ga.devs, key=lambda i: Counter(dcol[0])[dcol[0][i]])
    cand = {}
    for j in gb.devs:
        cand.setdefault(dcol[1][j], []).append(j)
    used, dmap, nmap, rnmap = set(), {}, {}, {}
    steps = [0]

    def pin_groups(edges):
        # Equivalent pins share a class and may permute within it.
        groups = {}
        for pc, n in edges:
            groups.setdefault(pc, []).append(n)
        return groups

    def try_bind(na, nb, added):
        if na in nmap:
            return nmap[na] == nb
        if nb in rnmap or ncol[0][na] != ncol[1][nb]:
            return False
        nmap[na] = nb; rnmap[nb] = na; added.append(na)
        return True

    def bind_groups(ga_list, gb_list, added):
        if len(ga_list) != len(gb_list):
            return False
        for perm in permutations(gb_list):
            trial = []
            if all(try_bind(a, b, trial) for a, b in zip(ga_list, perm)):
                added += trial
                return True
            for a in trial:
                del rnmap[nmap.pop(a)]
        return False

    def rec(k):
        steps[0] += 1
        if steps[0] > MAX_STEPS:
            return "limit"
        if k == len(order):
            return True
        i = order[k]
        for j in cand.get(dcol[0][i], []):
            if j in used:
                continue
            groups_a, groups_b = pin_groups(ga.edges_d[i]), pin_groups(gb.edges_d[j])
            if set(groups_a) != set(groups_b):
                continue
            added, ok = [], True
            for pc in sorted(groups_a):
                if not bind_groups(groups_a[pc], groups_b[pc], added):
                    ok = False
                    break
            if ok:
                used.add(j); dmap[i] = j
                r = rec(k + 1)
                if r:
                    return r
                used.discard(j); del dmap[i]
            for a in added:
                del rnmap[nmap.pop(a)]
        return False

    r = rec(0)
    if r == "limit":
        return "limit"
    return (dmap, nmap) if r else None


def compare(layout, reference, tech):
    classes = pin_classes(tech)
    lay_named = {n.lower(): n for n in layout.nets if not (layout.unnamed and layout.unnamed.match(n))}
    ref_ports = {p.lower() for p in reference.ports}
    # A reference net is anchored when it is a subcircuit port or carries a layout label.
    anchors_ref = {n.lower(): n.lower() for n in reference.nets if n.lower() in ref_ports or n.lower() in lay_named}
    anchors_lay = {k: k for k in lay_named}
    ga, gb = Graph(layout, anchors_lay, classes), Graph(reference, anchors_ref, classes)
    lines, issues = [], []

    count_a = Counter(d["component"] for d in layout.devices)
    count_b = Counter(d["component"] for d in reference.devices)
    for comp in sorted(set(count_a) | set(count_b)):
        if count_a[comp] != count_b[comp]:
            issues.append("device count %s: layout %d, reference %d" % (comp, count_a[comp], count_b[comp]))
    for p in reference.ports:
        if p.lower() not in lay_named:
            issues.append("reference pin %s has no labelled net in the layout" % p)
    for k, n in sorted(lay_named.items()):
        if k not in {x.lower() for x in reference.nets}:
            issues.append("layout net %s does not exist in the reference" % n)

    def signature(g, net):
        return Counter("%s.%s" % (g.c.devices[i]["component"], pc) for pc, i in g.edges_n[net])

    ref_by_lower = {n.lower(): n for n in reference.nets}
    for k, n in sorted(lay_named.items()):
        if k in ref_by_lower:
            sa, sb = signature(ga, n), signature(gb, ref_by_lower[k])
            if sa != sb:
                issues.append("net %s: layout %s; reference %s" % (n, _fmt(sa), _fmt(sb)))

    dcol, ncol = refine([ga, gb])
    same = Counter(dcol[0]) == Counter(dcol[1]) and Counter(ncol[0].values()) == Counter(ncol[1].values())
    match = None
    if same and not issues:
        match = exact_match(ga, gb, dcol, ncol)
        if match is None:
            issues.append("structures refine equally but no exact device/net bijection exists")
    elif not issues:
        issues.append("circuit structure differs (net or device connectivity)")
    if not same:
        ca, cb = Counter(dcol[0]), Counter(dcol[1])
        extra = [layout.devices[i] for i in ga.devs if ca[dcol[0][i]] > cb.get(dcol[0][i], 0)]
        missing = [reference.devices[j] for j in gb.devs if cb[dcol[1][j]] > ca.get(dcol[1][j], 0)]
        for d in extra[:10]:
            issues.append("unmatched layout device %s %s %s" % (d["name"], d["component"], _pins(d)))
        for d in missing[:10]:
            issues.append("unmatched reference device %s %s %s" % (d["name"], d["component"], _pins(d)))

    passed = not issues and match not in (None, "limit")
    lines.append("LVS %s vs %s: %s" % (layout.name, reference.name, "PASS" if passed else "FAIL"))
    lines.append("layout:    %d devices, %d nets (%d labelled)" % (len(layout.devices), len(layout.nets), len(lay_named)))
    lines.append("reference: %d devices, %d nets (%d ports)" % (len(reference.devices), len(reference.nets), len(reference.ports)))
    if match == "limit":
        lines.append("exact matching stopped after %d steps; structure refines equally" % MAX_STEPS)
    elif passed:
        dmap, nmap = match
        lines.append("device map: " + ", ".join("%s=%s" % (layout.devices[i]["name"], reference.devices[j]["name"])
                                                  for i, j in sorted(dmap.items(), key=lambda kv: layout.devices[kv[0]]["name"])))
        internal = {a: b for a, b in nmap.items() if a.lower() not in lay_named}
        if internal:
            lines.append("internal nets: " + ", ".join("%s=%s" % kv for kv in sorted(internal.items())))
    for msg in issues:
        lines.append("  - " + msg)
    return passed, lines, issues


def _fmt(counter):
    return ", ".join("%s x%d" % kv for kv in sorted(counter.items())) or "nothing"


def _pins(d):
    return "(" + " ".join("%s=%s" % kv for kv in sorted(d["pins"].items())) + ")"


def main(argv):
    ap = argparse.ArgumentParser(description="Compare extracted and reference netlists")
    ap.add_argument("extracted"); ap.add_argument("reference"); ap.add_argument("tech")
    ap.add_argument("report", nargs="?"); ap.add_argument("--top"); ap.add_argument("--json")
    a = ap.parse_args(argv[1:])
    try:
        tech = Tech.load(a.tech)
        layout, data = load_extracted(a.extracted)
        reference, warnings = load_reference(a.reference, tech, a.top or layout.name)
    except (ValueError, KeyError, FileNotFoundError) as ex:
        print("lvs_compare: %s" % ex, file=sys.stderr)
        return 2
    passed, lines, issues = compare(layout, reference, tech)
    for w in data.get("warnings", []) + warnings:
        lines.append("  note: " + w)
    text = "\n".join(lines)
    print(text)
    if a.report:
        with open(a.report, "w") as f:
            f.write(text + "\n")
    if a.json:
        with open(a.json, "w") as f:
            json.dump({"result": "PASS" if passed else "FAIL", "issues": issues}, f, indent=2)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
