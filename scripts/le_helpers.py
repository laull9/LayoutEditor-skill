# -*- coding: utf-8 -*-
"""
le_helpers — geometry utilities + thin wrappers for juspertor LayoutEditor's LayoutScript Python API.

Two layers:
  1. Pure geometry (no dependencies, works in any Python 3): arcs, fillets, offsets, clipping,
     dog-bone beams with integral root fillets, keyhole windows, a DRC-safe dot-matrix font.
     All geometry is in micrometres (float).
  2. `LE` — a small wrapper around a headless LayoutEditor session (requires LayoutEditor's bundled
     Python, which ships the `LayoutScript` module). Converts µm → dbu (1 dbu = 1 nm), handles the
     clockwise-rotation quirk, verifies GDS export, and dumps flattened polygons to JSON for the
     analysis scripts (check_connectivity.py, render_preview.py).

Usage from a generator script run with LayoutEditor's Python:

    import sys, os; sys.path.insert(0, "/path/to/layouteditor-skill/scripts")
    from le_helpers import *
    le = LE(top="MY_CHIP", layers={1: ("M1_TRENCH", (230, 80, 60)), 3: ("M3_SI", (40, 140, 230))})
    le.poly(le.top, rect(0, 0, 100, 50), 3)
    le.save_gds("out.gds")
    le.dump_flat_json("out_polys.json")

License: MIT (see ../LICENSE).
"""
import json
import math
import os

UM = 1000  # dbu per µm (LayoutEditor default database unit = 1 nm)

# =============================================================================
# 1. Basic shapes and transforms (µm)
# =============================================================================

def arc(cx, cy, r, a0, a1, step=5.0):
    """Points on a circular arc from angle a0 to a1 (degrees, CCW positive), inclusive."""
    n = max(2, int(abs(a1 - a0) / step) + 1)
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / (n - 1))),
             cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / (n - 1)))) for i in range(n)]


def circle(cx, cy, r, n=360):
    return [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)) for i in range(n)]


def rect(x0, y0, x1, y1):
    """Axis-aligned rectangle from any two opposite corners, CCW."""
    x0, x1 = min(x0, x1), max(x0, x1)
    y0, y1 = min(y0, y1), max(y0, y1)
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def tr(pts, dx, dy):
    return [(x + dx, y + dy) for x, y in pts]


def rot(pts, deg):
    """Rotate about the origin, CCW positive."""
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return [(x * c - y * s, x * s + y * c) for x, y in pts]


def mirx(pts):
    """Mirror x → -x and reverse vertex order (keeps orientation)."""
    return [(-x, y) for x, y in pts][::-1]


def miry(pts):
    """Mirror y → -y and reverse vertex order (keeps orientation)."""
    return [(x, -y) for x, y in pts][::-1]


def area(pts):
    """Signed area (>0 for CCW)."""
    return 0.5 * sum(pts[i - 1][0] * pts[i][1] - pts[i][0] * pts[i - 1][1] for i in range(len(pts)))


def ccw(pts):
    return pts if area(pts) > 0 else pts[::-1]


def turn(a, b, c):
    """>0 when a→b→c turns left."""
    return (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])


# =============================================================================
# 2. Fillets, offsets, clipping
# =============================================================================

def round_poly(pts, r, closed=True, step=5.0):
    """Replace each vertex with a tangent arc of radius r.

    r may be a number or a per-vertex list (0 = keep sharp). For closed=False the end points are kept.
    The arc always sits inside the smaller angle at the vertex, so a convex corner is cut and a
    concave corner is filled. Radii larger than the adjacent edges allow are reduced automatically.
    """
    n = len(pts)
    rs = r if isinstance(r, (list, tuple)) else [r] * n
    out = []
    for i in range(n):
        p = pts[i]
        if (not closed and (i == 0 or i == n - 1)) or rs[i] <= 0:
            out.append(p)
            continue
        a, b = pts[i - 1], pts[(i + 1) % n]
        ax, ay = a[0] - p[0], a[1] - p[1]
        bx, by = b[0] - p[0], b[1] - p[1]
        la, lb = math.hypot(ax, ay), math.hypot(bx, by)
        ux, uy, vx, vy = ax / la, ay / la, bx / lb, by / lb
        th = math.acos(max(-1.0, min(1.0, ux * vx + uy * vy)))
        if th < 1e-6 or abs(th - math.pi) < 1e-6:
            out.append(p)
            continue
        rr = rs[i]
        d = rr / math.tan(th / 2)
        dmax = 0.49 * min(la, lb)
        if d > dmax:
            d = dmax
            rr = d * math.tan(th / 2)
        bxs, bys = ux + vx, uy + vy
        bl = math.hypot(bxs, bys)
        hc = rr / math.sin(th / 2)
        cx, cy = p[0] + bxs / bl * hc, p[1] + bys / bl * hc
        t1 = (p[0] + ux * d, p[1] + uy * d)
        t2 = (p[0] + vx * d, p[1] + vy * d)
        a1 = math.degrees(math.atan2(t1[1] - cy, t1[0] - cx))
        a2 = math.degrees(math.atan2(t2[1] - cy, t2[0] - cx))
        out += arc(cx, cy, rr, a1, a1 + (a2 - a1 + 540) % 360 - 180, step)
    return out


def round_by_turn(pts, r_convex, r_concave, step=5.0):
    """Round a CCW polygon with one radius for convex (left-turn) and another for concave vertices."""
    n = len(pts)
    return round_poly(pts, [r_convex if turn(pts[i - 1], pts[i], pts[(i + 1) % n]) > 0 else r_concave
                            for i in range(n)], step=step)


def offset_poly(pts, d):
    """Offset a closed polygon outward by d (d < 0 shrinks). Miter join, intended for smooth or
    rounded outlines; avoid very acute corners. Returns a CCW polygon."""
    pts = ccw(pts)
    n = len(pts)
    out = []
    for i in range(n):
        a, p, b = pts[i - 1], pts[i], pts[(i + 1) % n]
        e1 = (p[0] - a[0], p[1] - a[1])
        e2 = (b[0] - p[0], b[1] - p[1])
        l1, l2 = math.hypot(*e1), math.hypot(*e2)
        n1 = (e1[1] / l1, -e1[0] / l1)
        n2 = (e2[1] / l2, -e2[0] / l2)
        k = 1.0 + n1[0] * n2[0] + n1[1] * n2[1]
        out.append((p[0] + d * (n1[0] + n2[0]) / k, p[1] + d * (n1[1] + n2[1]) / k))
    return out


def point_in_poly(pt, poly):
    """Even-odd ray casting (works with keyhole polygons)."""
    x, y = pt
    c = False
    for i in range(len(poly)):
        x1, y1 = poly[i - 1]
        x2, y2 = poly[i]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            c = not c
    return c


def _seg_hits(a, b, poly):
    ts = []
    for i in range(len(poly)):
        c, d = poly[i - 1], poly[i]
        r = (b[0] - a[0], b[1] - a[1])
        s = (d[0] - c[0], d[1] - c[1])
        den = r[0] * s[1] - r[1] * s[0]
        if abs(den) < 1e-12:
            continue
        t = ((c[0] - a[0]) * s[1] - (c[1] - a[1]) * s[0]) / den
        u = ((c[0] - a[0]) * r[1] - (c[1] - a[1]) * r[0]) / den
        if 0 < t < 1 and 0 <= u <= 1:
            ts.append(t)
    return sorted(ts)


def clip_loop_outside(loop, q):
    """Return the parts of a closed polyline `loop` that lie outside polygon `q`.

    Result: list of open polylines. If the whole loop is outside, a single closed run is returned
    with one extra segment of overlap (so a flat-capped path has no seam gap).
    """
    n = len(loop)
    start = next((i for i in range(n) if not point_in_poly(loop[i], q)), None)
    if start is None:
        return []
    seq = loop[start:] + loop[:start] + [loop[start]]
    runs, cur, allout = [], [seq[0]], True
    for k in range(len(seq) - 1):
        a, b = seq[k], seq[k + 1]
        ts = [0.0] + _seg_hits(a, b, q) + [1.0]
        for j in range(len(ts) - 1):
            pa = (a[0] + (b[0] - a[0]) * ts[j], a[1] + (b[1] - a[1]) * ts[j])
            pb = (a[0] + (b[0] - a[0]) * ts[j + 1], a[1] + (b[1] - a[1]) * ts[j + 1])
            if point_in_poly(((pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2), q):
                allout = False
                if len(cur) > 1:
                    runs.append(cur)
                cur = []
            else:
                if not cur:
                    cur = [pa]
                cur.append(pb)
    if len(cur) > 1:
        runs.append(cur)
    if allout:
        return [seq + [seq[1]]]
    if len(runs) > 1 and runs[0][0] == seq[0] and runs[-1][-1] == seq[-1]:
        runs = [runs[-1] + runs[0][1:]] + runs[1:-1]   # join the two halves split at the start point
    return runs


def trench_ring(island, width, open_region=None, stub_open=None):
    """Centre-line polylines of an isolation-trench ring around `island`.

    island:      closed polygon (µm), ideally already rounded (round_poly) so the ring has round corners.
    width:       trench width; the centre line is offset by width/2 outside the island.
    open_region: polygon where the device layer is etched away anyway. Ring portions deep inside it
                 are dropped, so the ring becomes a U-shape whose ends terminate inside the etched area.
    stub_open:   that same region shrunk by the desired stub length (e.g. offset_poly(open, -5));
                 the trench ends then penetrate `stub` µm into the etched region. If None and
                 open_region is given, open_region is used directly (zero stub; not recommended).
    Make the island extend well into the open region (≥ 2×corner radius) so the cut lands on a
    straight segment; a cut through a rounded corner leaves a thin, DRC-failing sliver.
    """
    center = offset_poly(island, width / 2.0)
    if open_region is None:
        return [center + center[:2]]
    return clip_loop_outside(center, stub_open if stub_open is not None else open_region)


def dogbone(w, y1, y2, r1, r2, eps=5.0):
    """Beam along +Y (width w, from y1 to y2) with tangent root fillets r1 (at y1) and r2 (at y2),
    drawn as ONE polygon (no stitching seam at the stress-critical root). The ends extend eps
    beyond y1/y2 so they merge with the bodies they attach to. Rotate/translate as needed."""
    h = w / 2.0
    pts = ([(-h - r1, y1 - eps)] + arc(-h - r1, y1 + r1, r1, -90, 0)) if r1 > 0 else [(-h, y1 - eps)]
    if r2 > 0:
        pts += arc(-h - r2, y2 - r2, r2, 0, 90) + [(-h - r2, y2 + eps), (h + r2, y2 + eps)] \
            + arc(h + r2, y2 - r2, r2, 90, 180)
    else:
        pts += [(-h, y2 + eps), (h, y2 + eps)]
    pts += (arc(h + r1, y1 + r1, r1, 180, 270) + [(h + r1, y1 - eps)]) if r1 > 0 else [(h, y1 - eps)]
    return pts


def rrect(x0, y0, x1, y1, r):
    """Rounded rectangle (CCW)."""
    return round_poly(rect(x0, y0, x1, y1), r)


def rrect_half(hx, hy, r, upper=True, delta=6.0):
    """Upper (or lower) half of a centred rounded-rectangle boundary, from (hx,-delta) to (-hx,-delta).

    A ring (frame) without holes: outer_half + inner_half[::-1] gives a simple U-shaped polygon;
    draw upper and lower halves, which overlap by 2·delta at y=0.
    """
    q = arc(hx - r, hy - r, r, 0, 90) + arc(-hx + r, hy - r, r, 90, 180)
    pts = [(hx, -delta)] + q + [(-hx, -delta)]
    return pts if upper else [(x, -y) for x, y in pts]


def field_halves(hole_left_path, extent, overlap=5.0, hole_round=0.0):
    """Field polygon = square [-extent, extent]² minus an x-symmetric hole, as two simple polygons.

    hole_left_path: the hole boundary in the left half, starting at (overlap, y_bottom), running
                    through x < 0 and ending at (overlap, y_top). E.g. for a rectangular hole
                    |x|<a, |y|<b:  [(ov,-b), (-a,-b), (-a,b), (ov,b)].
    Returns (left, right), both CCW. They overlap by 2·overlap along x = 0 (mask data is a union).
    hole_round: radius applied to the hole's convex corners (= concave corners of the field).
    """
    left = [(overlap, extent), (-extent, extent), (-extent, -extent), (overlap, -extent)] + list(hole_left_path)
    left = round_by_turn(left, 0.0, hole_round)
    return left, mirx(left)


def insert_windows(poly, windows, edge_y):
    """Punch rectangular holes into a CCW polygon via zero-width vertical bridges to its edge at y=edge_y.

    windows: list of (x0, y0, x1, y1). Each bridge runs from the window top straight up to edge_y,
    so nothing else may lie between a window and that edge. Use for etch windows that hold marks
    or test structures inside a "drawn = kept" field polygon.
    """
    out = []
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        out.append(a)
        if abs(a[1] - edge_y) < 1e-9 and abs(b[1] - edge_y) < 1e-9 and a[0] > b[0]:
            for (x0, y0, x1, y1) in sorted(windows, key=lambda w: -(w[0] + w[2])):
                m = (x0 + x1) / 2.0
                if b[0] < m < a[0]:
                    out += [(m, edge_y), (m, y1), (x1, y1), (x1, y0), (x0, y0), (x0, y1), (m, y1), (m, edge_y)]
    return out


# =============================================================================
# 3. DRC-safe dot-matrix font for mask text
# =============================================================================
# Squares of side 1.3·pitch on a 5×7 grid: diagonal neighbours overlap → neck ≥ 0.42·pitch,
# non-adjacent pixels are ≥ 0.7·pitch apart. Pick pitch so both satisfy the layer's min width/space
# (pitch 8 µm → neck ≈ 3.4 µm, space 5.6 µm).
FONT = {
    "A": [".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "B": ["####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."],
    "C": [".####", "#....", "#....", "#....", "#....", "#....", ".####"],
    "D": ["####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."],
    "E": ["#####", "#....", "#....", "####.", "#....", "#....", "#####"],
    "F": ["#####", "#....", "#....", "####.", "#....", "#....", "#...."],
    "G": [".####", "#....", "#....", "#..##", "#...#", "#...#", ".###."],
    "H": ["#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "I": [".###.", "..#..", "..#..", "..#..", "..#..", "..#..", ".###."],
    "J": ["..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."],
    "K": ["#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"],
    "L": ["#....", "#....", "#....", "#....", "#....", "#....", "#####"],
    "M": ["#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"],
    "N": ["#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"],
    "O": [".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "P": ["####.", "#...#", "#...#", "####.", "#....", "#....", "#...."],
    "Q": [".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"],
    "R": ["####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"],
    "S": [".####", "#....", "#....", ".###.", "....#", "....#", "####."],
    "T": ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."],
    "U": ["#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "V": ["#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."],
    "W": ["#...#", "#...#", "#...#", "#.#.#", "#.#.#", "##.##", "#...#"],
    "X": ["#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"],
    "Y": ["#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."],
    "Z": ["#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"],
    "0": [".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."],
    "1": ["..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."],
    "2": [".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"],
    "3": ["####.", "....#", "....#", ".###.", "....#", "....#", "####."],
    "4": ["...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."],
    "5": ["#####", "#....", "####.", "....#", "....#", "#...#", ".###."],
    "6": [".###.", "#....", "#....", "####.", "#...#", "#...#", ".###."],
    "7": ["#####", "....#", "...#.", "..#..", ".#...", ".#...", ".#..."],
    "8": [".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."],
    "9": [".###.", "#...#", "#...#", ".####", "....#", "....#", ".###."],
    ".": [".....", ".....", ".....", ".....", ".....", ".....", "..#.."],
    "-": [".....", ".....", ".....", "#####", ".....", ".....", "....."],
    "=": [".....", ".....", "#####", ".....", "#####", ".....", "....."],
    "+": [".....", "..#..", "..#..", "#####", "..#..", "..#..", "....."],
    ":": [".....", "..#..", ".....", ".....", "..#..", ".....", "....."],
    "_": [".....", ".....", ".....", ".....", ".....", ".....", "#####"],
    "/": ["....#", "....#", "...#.", "..#..", ".#...", "#....", "#...."],
    " ": ["....."] * 7,
}


def dot_text(s, x0, y0, pitch, center=False):
    """Rectangles (µm) spelling `s` in the 5×7 dot font; (x0, y0) = bottom-left (or bottom-centre)."""
    sq = 1.3 * pitch
    width = (6 * len(s) - 1) * pitch
    if center:
        x0 -= width / 2.0
    out = []
    for k, ch in enumerate(s.upper()):
        glyph = FONT.get(ch)
        if glyph is None:
            raise KeyError("dot font has no glyph for %r; add it to FONT" % ch)
        for r, row in enumerate(glyph):
            for col, v in enumerate(row):
                if v == "#":
                    x = x0 + (6 * k + col) * pitch
                    y = y0 + (6 - r) * pitch
                    out.append(rect(x, y, x + sq, y + sq))
    return out


# =============================================================================
# 4. Headless LayoutEditor wrapper
# =============================================================================

class LE:
    """Headless LayoutEditor session working in µm.

    LE(top="NAME", layers={num: ("name", (r, g, b))}, tech=None)
      layer arguments accept a number, a (layer, datatype) pair or, with tech=Tech or a
      technology JSON path, a layer name such as "METAL1.PIN"
      .top                       top cell (the default cell, renamed, so no empty 'noname' is left)
      .cell(name)                new cell
      .poly(cell, pts, layer)    polygon from µm points
      .path(cell, pts, layer, w) path (flat caps) of width w µm
      .text(cell, layer, x, y, s, h=None)   text element (use on non-mask layers)
      .ref(parent, child, x, y, ang=0)      cell reference, ang = CCW degrees
      .array(parent, child, x0, y0, pitch_x, n)   1-D array along x (reliable form)
      .save_gds(path)            export + verify (raises on license refusal)
      .dump_flat_json(path, meta=None)  flatten in a temp cell, dump polygons/texts (call AFTER save)
    """

    def __init__(self, top="TOP", layers=None, tech=None):
        import LayoutScript as _ls  # only available in LayoutEditor's bundled Python
        self.ls = _ls
        self.L = _ls.project.newLayout()
        self.dr = self.L.drawing
        self.top = self.dr.currentCell
        self.top.cellName = top
        if isinstance(tech, str):
            from tech import Tech
            tech = Tech.load(tech)
        self.tech = tech
        self.layers = dict(layers or {})
        if tech is not None:
            for num, name in tech.native_names().items():
                self.layers.setdefault(num, (name, tech.colors.get(name, (128, 128, 128))))
        for k, (nm, col) in self.layers.items():
            _ls.layers.num(k).name = nm
            _ls.layers.num(k).setColor(*col)
        self._saved = False
        self.has_used_boolean = False

    # -- conversion --------------------------------------------------------
    def pa(self, pts):
        pa = self.ls.pointArray()
        for x, y in pts:
            pa.attach(int(round(x * UM)), int(round(y * UM)))
        return pa

    def pt(self, x, y):
        return self.ls.point(int(round(x * UM)), int(round(y * UM)))

    # -- drawing -----------------------------------------------------------
    def cell(self, name):
        c = self.dr.addCell().thisCell
        c.cellName = name
        return c

    def layer(self, ref):
        """Number, (layer, datatype) or technology layer name -> (layer, datatype)."""
        if self.tech is not None and isinstance(ref, str):
            return self.tech.pair(ref)
        if isinstance(ref, (tuple, list)):
            return int(ref[0]), int(ref[1])
        return int(ref), 0

    def _tag(self, e, ref):
        dt = self.layer(ref)[1]
        if dt:
            e.datatype = dt
        return e

    def poly(self, cell, pts, layer):
        return self._tag(cell.addPolygon(self.pa(pts), self.layer(layer)[0]), layer)

    def polys(self, cell, list_of_pts, layer):
        for p in list_of_pts:
            self.poly(cell, p, layer)

    def path(self, cell, pts, layer, w):
        return self._tag(cell.addPath(self.pa(pts), self.layer(layer)[0], int(round(w * UM))), layer)

    def text(self, cell, layer, x, y, s, h=None):
        e = self._tag(cell.addText(self.layer(layer)[0], self.pt(x, y), s), layer)
        if h:
            e.setWidth(int(round(h * UM)))
        return e

    def ref(self, parent, child, x, y, ang=0):
        e = parent.addCellref(child, self.pt(x, y))
        if ang % 360:
            t = self.ls.strans()
            t.rotate(-ang)  # LayoutEditor rotate() is clockwise
            e.setTrans(t)
            assert abs(e.getTrans().getAngle() - ang % 360) < 1e-6, "rotation convention changed?"
        return e

    def array(self, parent, child, x0, y0, pitch_x, n):
        return parent.addCellrefArray(child, self.pt(x0, y0), self.pt(x0 + pitch_x, y0), n, 1)

    # -- layer operations (boolean / sizing) -------------------------------
    def layer_boolean(self, cell, layer_a, layer_b, layer_out, op="A-B"):
        """Run boolean operation on cell: 'A-B' (difference), 'A+B' (union), 'A*B' (intersection), 'AxorB' (xor).

        Note: on LayoutEditor free license, using the boolean engine locks subsequent GDS export.
        """
        self.dr.setCell(cell)
        self.L.booleanTool.boolOnLayer(layer_a, layer_b, layer_out, "AxorB" if op == "A^B" else op)
        self.has_used_boolean = True

    def layer_size(self, cell, layer_src, layer_dst, delta_um, corner_type=0):
        """Offset/size layer geometry by delta_um (positive = expand, negative = shrink)."""
        self.dr.setCell(cell)
        self.dr.copyLayerSized(layer_src, layer_dst, int(round(delta_um * UM)), corner_type)
        self.has_used_boolean = True

    # -- export ------------------------------------------------------------
    def save_gds(self, path):
        path = os.path.abspath(path)
        lec = os.path.splitext(path)[0] + ".lec"
        lec_before = os.path.getmtime(lec) if os.path.exists(lec) else None
        if os.path.exists(path):
            os.remove(path)
        self.dr.setCell(self.top)
        self.dr.saveFile(path)
        if not os.path.exists(path):
            lec_new = os.path.exists(lec) and os.path.getmtime(lec) != lec_before
            raise RuntimeError(
                "LayoutEditor did not write %s%s. On the free license this happens after using the "
                "boolean engine or above ~8-10k elements; see references/free-version-limits.md."
                % (path, " (a cloud-only .lec was written instead)" if lec_new else ""))
        self._saved = True
        return path

    def dump_flat_json(self, path, meta=None):
        """Flatten the top cell into a temporary cell and write polygons (µm) per layer to JSON.

        Paths are converted to polygons; boxes are expanded to 4 points. Do not save the layout
        after calling this (the temporary cell would end up in the file).
        """
        flat = self.cell("_FLAT_TMP")
        flat.addCellref(self.top, self.ls.point(0, 0))
        self.dr.setCell(flat)
        flat.selectAll(); self.dr.flatAll(); flat.deselectAll()
        self.dr.pathSelect(); self.dr.toPolygon(); flat.deselectAll()
        polys, texts = {}, []
        xs, ys = [], []
        el = flat.firstElement
        while el:
            e = el.thisElement
            if e is not None and not e.isCellref() and not e.isCellrefArray():
                pa = e.getPoints()
                pts = [(pa.point(i).x() / UM, pa.point(i).y() / UM) for i in range(pa.size())]
                if e.isText():
                    texts.append([e.layerNum, pts[0][0], pts[0][1], e.getName()])
                else:
                    if e.isBox() and len(pts) == 2:
                        pts = rect(pts[0][0], pts[0][1], pts[1][0], pts[1][1])
                    polys.setdefault(str(e.layerNum), []).append(pts)
                    xs += [p[0] for p in pts]; ys += [p[1] for p in pts]
            el = el.nextElement
        data = {
            "format": "le-flat-polys/1",
            "unit": "um",
            "top": self.top.cellName,
            "bbox": [min(xs), min(ys), max(xs), max(ys)] if xs else None,
            "layers": {str(k): {"name": v[0], "color": list(v[1])} for k, v in self.layers.items()},
            "polys": polys,
            "texts": texts,
            "meta": meta or {},
        }
        with open(path, "w") as f:
            json.dump(data, f)
        return data


def comb_row(le, name, finger_w, gap, length, tip, n, layer):
    """Interdigitated comb row cell (needs an LE session).

    Moving fingers grow from y=0 (the moving edge) up to `length`; fixed fingers grow down from
    y=length+tip (the fixed edge) to y=tip. n moving fingers, n+1 fixed fingers, so every moving
    finger has equal gaps on both sides. Fingers overlap their root by 1 µm for clean merging.
    The cell is centred on x=0. Returns (cell, half_span_moving, half_span_fixed).
    """
    pitch = 2 * (finger_w + gap)
    xc = (pitch * (n - 1) + finger_w) / 2.0
    xf = xc + finger_w + gap
    fm = le.cell(name + "_FM"); le.poly(fm, rect(0, -1, finger_w, length), layer)
    ff = le.cell(name + "_FF"); le.poly(ff, rect(0, tip, finger_w, length + tip + 1), layer)
    row = le.cell(name)
    le.array(row, fm, -xc, 0, pitch, n)
    le.array(row, ff, -xf, 0, pitch, n + 1)
    return row, xc, xf
