# -*- coding: utf-8 -*-
"""
Electrical connectivity / isolation and mechanical-release check by rasterisation.

Run with any CPython that has numpy + Pillow (not LayoutEditor's Python):
    python3 check_connectivity.py <polys.json> <probes.json> [report.txt]

<polys.json>  flattened polygons written by le_helpers.LE.dump_flat_json (µm, per layer).
<probes.json> what to check, e.g.:
    {
      "resolution": 0.5,                  # µm per pixel; must be < half the smallest gap/trench
      "conductor_layers": ["3"],          # layers that conduct (drawn = kept material)
      "insulator_layers": ["1"],          # cut out of the conductor (e.g. oxide-refilled trenches)
      "release_layer": "4",               # optional: region where the structure is released
      "pads":   {"DRIVE": [0, 650], "GND": [500, 650]},
      "probes": [{"name": "shuttle", "xy": [0, 0], "expect": "GND"}]
    }

Checks:
  1. All pads sit on conductor and are pairwise isolated.
  2. Every probe lands in the connected region of its expected pad ("expect": pad name), or in a
     region with no pad ("expect": "FLOATING").
  3. Release (if release_layer given): every connected conductor region (insulators NOT removed)
     must touch conductor outside the release region, otherwise it would detach after release.
Exit code 0 = all pass, 1 = failure.

Method: polygons are filled with Pillow, connected regions are labelled with a run-length +
union-find pass (4-connectivity). With 0.5 µm pixels a 3 µm gap is ≥ 5 pixels, so polygon
edge rasterisation cannot bridge it. Memory: (extent/resolution)² bytes per raster.
"""
import json
import sys

import numpy as np
from PIL import Image, ImageDraw


class _DSU:
    def __init__(self, n):
        self.p = list(range(n))

    def find(self, a):
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a, b):
        a, b = self.find(a), self.find(b)
        if a != b:
            self.p[b] = a


class Raster:
    def __init__(self, data, res, margin=10.0):
        self.d = data
        x0, y0, x1, y1 = data["bbox"]
        self.x0, self.y1, self.res = x0 - margin, y1 + margin, res
        self.w = int((x1 - x0 + 2 * margin) / res) + 1
        self.h = int((y1 - y0 + 2 * margin) / res) + 1

    def px(self, p):
        return [((x - self.x0) / self.res, (self.y1 - y) / self.res) for x, y in p]

    def draw(self, on, off=()):
        im = Image.new("1", (self.w, self.h), 0)
        dr = ImageDraw.Draw(im)
        for lay in on:
            for p in self.d["polys"].get(lay, []):
                dr.polygon(self.px(p), fill=1)
        for lay in off:
            for p in self.d["polys"].get(lay, []):
                dr.polygon(self.px(p), fill=0)
        # NB: Pillow stores True as 255 — never use .view(np.int8) on this array
        return np.array(im).astype(bool)

    def label(self, img, anchor=None):
        rows, ids, anch, n = [], [], [], 0
        for r in range(self.h):
            row = img[r].astype(np.int8)
            dif = np.diff(np.concatenate(([0], row, [0])))
            s, e = np.flatnonzero(dif == 1), np.flatnonzero(dif == -1)
            rows.append((s, e))
            ids.append(np.arange(n, n + len(s)))
            n += len(s)
            if anchor is not None:
                cs = np.concatenate(([0], np.cumsum(anchor[r])))
                anch += list((cs[e] - cs[s]) > 0)
        dsu = _DSU(n)
        for r in range(self.h - 1):
            (s1, e1), (s2, e2) = rows[r], rows[r + 1]
            i = j = 0
            while i < len(s1) and j < len(s2):
                if s1[i] < e2[j] and s2[j] < e1[i]:
                    dsu.union(ids[r][i], ids[r + 1][j])
                if e1[i] < e2[j]:
                    i += 1
                else:
                    j += 1
        return rows, ids, dsu, anch

    def region_at(self, lab, x, y):
        rows, ids, dsu, _ = lab
        c, r = int((x - self.x0) / self.res), int((self.y1 - y) / self.res)
        if not (0 <= r < self.h):
            return None
        s, e = rows[r]
        k = np.flatnonzero((s <= c) & (c < e))
        return dsu.find(int(ids[r][k[0]])) if len(k) else None


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    data = json.load(open(argv[1]))
    cfg = json.load(open(argv[2]))
    ras = Raster(data, cfg.get("resolution", 0.5))
    cond, ins = cfg.get("conductor_layers", ["3"]), cfg.get("insulator_layers", [])
    lines = ["Connectivity check (conductor %s minus insulator %s, %.2f µm raster)" % (cond, ins, ras.res), ""]
    ok = True

    lab = ras.label(ras.draw(cond, ins))
    pad_region = {name: ras.region_at(lab, *xy) for name, xy in cfg.get("pads", {}).items()}
    for name, reg in pad_region.items():
        if reg is None:
            lines.append("FAIL pad %s is not on conductor" % name)
            ok = False
    regs = [r for r in pad_region.values() if r is not None]
    iso = len(set(regs)) == len(regs)
    ok &= iso
    lines.append("pads pairwise isolated (%d pads): %s" % (len(pad_region), "PASS" if iso else "FAIL"))
    if not iso:
        groups = {}
        for name, reg in pad_region.items():
            groups.setdefault(reg, []).append(name)
        for names in groups.values():
            if len(names) > 1:
                lines.append("  shorted: %s" % ", ".join(names))
    net_of = {}
    for name, reg in pad_region.items():
        net_of.setdefault(reg, name)
    for p in cfg.get("probes", []):
        reg = ras.region_at(lab, *p["xy"])
        got = "NOT_ON_CONDUCTOR" if reg is None else net_of.get(reg, "FLOATING")
        good = got == p["expect"]
        ok &= good
        lines.append("  %-4s %-40s -> %-12s (expect %s)" % ("OK" if good else "FAIL", p["name"], got, p["expect"]))

    if cfg.get("release_layer"):
        mech = ras.draw(cond)
        rel = ras.draw([cfg["release_layer"]])
        lab2 = ras.label(mech, anchor=mech & ~rel)
        anchored = {}
        for i, a in enumerate(lab2[3]):
            r = lab2[2].find(i)
            anchored[r] = anchored.get(r, False) or bool(a)
        floating = sum(1 for a in anchored.values() if not a)
        ok &= floating == 0
        lines += ["", "release check: %d conductor regions, %d fully inside the release area -> %s"
                  % (len(anchored), floating, "PASS" if floating == 0 else "FAIL (parts would detach)")]

    lines += ["", "RESULT: %s" % ("ALL PASS" if ok else "FAILURES FOUND")]
    rep = "\n".join(lines)
    print(rep)
    if len(argv) > 3:
        with open(argv[3], "w") as f:
            f.write(rep)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
