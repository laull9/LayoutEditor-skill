# -*- coding: utf-8 -*-
"""
tech — load and check a layouteditor-skill technology file (PDK description in JSON).

Pure Python, no LayoutEditor needed. One file names every layer once and drives generation,
layer remapping, DRC, layout audits and native extraction/LVS:

    {
      "name": "demo_cmos",
      "units": {"dbu_m": 1e-9, "grid_um": 0.005},
      "layers": {
        "METAL1":     {"gds": [6, 0], "color": [70, 130, 220]},
        "METAL1.PIN": {"gds": [6, 2]}
      },
      "connectivity": {"stack": ["POLY", "CONTACT", "METAL1", "VIA1", "METAL2"],
                       "ignore_datatypes": [22]},
      "devices": [{"name": "nmos", "method": "MOS-default",
                   "layers": {"layerPoly": "POLY", "layerActive": "ACTIVE", "layerContact": "CONTACT"},
                   "ports": ["S", "D", "G"], "equivalent_ports": [["S", "D"]],
                   "spice": {"prefix": "M", "models": ["nmos"], "pins": ["D", "G", "S", "B"]}}],
      "drc": [{"name": "M1 width", "rule": "minimumSize", "layer": "METAL1", "value": 0.5}]
    }

See references/pdk-workflow.md for the field reference.
"""
import json
import re

CONDUCTOR, VIA = 2, 1        # LayoutEditor technology layer types
DRC_LAYER_KEYS = ("layer", "layer2")


def parse_pair(value):
    """Accept [L, D], (L, D), "L/D", "L" or L and return an (int, int) pair (datatype 0 if absent)."""
    if isinstance(value, (list, tuple)):
        return int(value[0]), int(value[1]) if len(value) > 1 else 0
    if isinstance(value, int):
        return value, 0
    m = re.fullmatch(r"\s*(\d+)\s*(?:[/:]\s*(\d+))?\s*", str(value))
    if not m:
        raise ValueError("Bad layer/datatype %r; use [layer, datatype] or 'layer/datatype'" % (value,))
    return int(m.group(1)), int(m.group(2) or 0)


class Tech:
    def __init__(self, data, path=None):
        self.data = data
        self.path = path
        self.name = data.get("name", "unnamed")
        units = data.get("units", {})
        self.dbu_m = float(units.get("dbu_m", 1e-9))
        self.grid_um = units.get("grid_um")
        self.layers = {}            # name -> (layer, datatype)
        self.colors = {}
        for name, spec in data.get("layers", {}).items():
            spec = spec if isinstance(spec, dict) else {"gds": spec}
            self.layers[name] = parse_pair(spec["gds"])
            if "color" in spec:
                self.colors[name] = tuple(spec["color"])
        conn = data.get("connectivity", {})
        self.stack = list(conn.get("stack", []))
        self.ignore_datatypes = [int(d) for d in conn.get("ignore_datatypes", [])]
        self.devices = list(data.get("devices", []))
        self.drc = list(data.get("drc", []))

    @classmethod
    def load(cls, path):
        with open(path) as f:
            return cls(json.load(f), path)

    # -- lookups ---------------------------------------------------------
    def pair(self, ref):
        """Layer name, [L, D] or "L/D" -> (layer, datatype)."""
        if isinstance(ref, str) and ref in self.layers:
            return self.layers[ref]
        if isinstance(ref, str) and not re.fullmatch(r"[\d/: ]+", ref):
            raise KeyError("Layer %r is not defined in technology %s" % (ref, self.name))
        return parse_pair(ref)

    def number(self, ref):
        return self.pair(ref)[0]

    def by_pair(self):
        out = {}
        for name, p in self.layers.items():
            out.setdefault(p, []).append(name)
        return out

    def native_names(self):
        """Name for each GDS layer number inside LayoutEditor.

        LayoutEditor keys layer names, technology layers and extraction parameters on the layer
        number; datatypes ride on the elements. Datatype 0 names the number, else the first entry.
        """
        names = {}
        for name, (lay, dt) in self.layers.items():
            if lay not in names or dt == 0:
                names[lay] = name
        return names

    def native_name(self, ref):
        return self.native_names()[self.number(ref)]

    def drc_rules(self):
        """DRC rules with layer names resolved to numbers for scripts/drc_check.py."""
        rules = []
        for r in self.drc:
            r = dict(r)
            for k in DRC_LAYER_KEYS:
                if k in r:
                    r[k] = self.number(r[k])
            rules.append(r)
        return rules

    def device(self, name):
        for d in self.devices:
            if d["name"] == name:
                return d
        raise KeyError("Device %r not defined in technology %s" % (name, self.name))

    def extraction_parameter(self, dev):
        """LayoutEditor extractionParameter text: layer refs become native layer names."""
        lines = []
        for k, v in dev.get("layers", {}).items():
            lines.append("%s=%s" % (k, self.native_name(v)))
        for k, v in dev.get("parameters", {}).items():
            lines.append("%s=%s" % (k, v))
        lines.append("ports=" + ",".join(dev["ports"]))
        return "\n".join(lines)

    # -- validation ------------------------------------------------------
    def check(self):
        """Return a list of problems (empty list = usable)."""
        errors = []
        seen = {}
        for name, p in self.layers.items():
            if p in seen:
                errors.append("layers %s and %s both use %d/%d" % (seen[p], name, p[0], p[1]))
            seen[p] = name
            if not (0 <= p[0] <= 65535 and 0 <= p[1] <= 65535):
                errors.append("layer %s: %d/%d outside GDS range" % (name, p[0], p[1]))
        if not self.dbu_m > 0:
            errors.append("units.dbu_m must be positive")
        if self.grid_um is not None:
            ratio = self.grid_um * 1e-6 / self.dbu_m
            if ratio < 1 - 1e-9 or abs(ratio - round(ratio)) > 1e-6:
                errors.append("grid %.6g µm is not a whole multiple of the %.3g m DBU" % (self.grid_um, self.dbu_m))

        def known(ref, where):
            try:
                self.pair(ref)
                return True
            except (KeyError, ValueError) as ex:
                errors.append("%s: %s" % (where, ex))
                return False

        numbers = []
        for i, ref in enumerate(self.stack):
            if known(ref, "connectivity.stack[%d]" % i):
                numbers.append(self.number(ref))
        if len(set(numbers)) != len(numbers):
            errors.append("connectivity.stack uses a GDS layer number twice; extraction keys on "
                          "layer numbers, so remap distinct materials to distinct numbers first")
        if self.stack and len(self.stack) % 2 == 0:
            errors.append("connectivity.stack must alternate conductor, via, conductor ... "
                          "and start/end with a conductor")
        names = set()
        for dev in self.devices:
            where = "device %s" % dev.get("name", "?")
            if dev.get("name") in names:
                errors.append(where + ": duplicate name")
            names.add(dev.get("name"))
            for k in ("name", "method", "ports"):
                if k not in dev:
                    errors.append("%s: missing %r" % (where, k))
            for k, v in dev.get("layers", {}).items():
                known(v, "%s.layers.%s" % (where, k))
            ports = set(dev.get("ports", []))
            for group in dev.get("equivalent_ports", []):
                if not set(group) <= ports:
                    errors.append("%s: equivalent_ports %s not in ports" % (where, group))
            spice = dev.get("spice")
            if spice:
                if not spice.get("pins"):
                    errors.append(where + ": spice.pins missing")
                elif not ports <= set(spice["pins"]):
                    errors.append("%s: spice.pins must name every port %s" % (where, sorted(ports)))
        for i, r in enumerate(self.drc):
            for k in DRC_LAYER_KEYS:
                if k in r:
                    known(r[k], "drc[%d] %s.%s" % (i, r.get("name", "?"), k))
        return errors

    def stack_levels(self):
        """[(layer number, type, level)] for LayoutEditor's technology layers."""
        return [(self.number(ref), CONDUCTOR if i % 2 == 0 else VIA, i) for i, ref in enumerate(self.stack)]


def load(path):
    return Tech.load(path)
