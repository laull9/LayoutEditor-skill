# Geometry techniques (boolean-free)

All helpers live in `scripts/le_helpers.py`, work in µm, and return point lists. They are pure
Python, so they can be unit-tested in any interpreter.

## Coordinates and orientation

- Put the origin at the device's symmetry centre. Symmetric parts can then be produced with
  `mirx`/`miry` (which also reverse vertex order to keep CCW orientation) or by rotated cell refs.
- Keep every polygon **CCW** (`ccw(pts)`); `round_by_turn` and `offset_poly` rely on it.
- `LE.ref(parent, child, x, y, ang)` takes CCW degrees. Design unit cells along +Y (beams) or
  centred on x=0 (combs) so that 0/90/180/270° placements cover all cases without mirroring.

## Fillets: `round_poly`, `round_by_turn`

`round_poly(pts, r)` replaces every vertex with a tangent arc. `r` may be per-vertex (0 = sharp).
The arc lies inside the smaller angle at the vertex: convex corners get cut and concave corners
get filled. Radii that do not fit are reduced automatically to 49% of the shorter adjacent edge.

`round_by_turn(pts, r_convex, r_concave)` picks the radius by turn direction. Typical uses:
- Etch/open regions: round convex corners only (`r_concave = 0`) when fixed structures attach right
  at the concave corners. Filling a concave corner would add material over their roots.
- Field polygons around a hole: the hole's convex corners are the field's concave corners, so
  `round_by_turn(field, 0, R)` reproduces exactly the same arcs as `round_by_turn(hole, R, 0)`.

Arc resolution: `step` (degrees) defaults to 5°. Chord error = r·(1 − cos(step/2)), which is
0.02 µm for r = 20 µm.

## Beams with integral root fillets: `dogbone`

```python
beam = dogbone(w=37, y1=0, y2=400, r1=20, r2=20)   # along +Y; place with LE.ref(..., ang)
```

The beam and both root fillets are a **single polygon**, so there is no stitching seam at the
stress-critical root. This matters for torsion and flexure beams, where FEM-verified fillet radii
must survive into the mask. The ends overrun by `eps` (5 µm) into the bodies they attach to. The
attached bodies need straight edges at least `w/2 + r` wide around the root. For round bodies, add
a small rectangular hub first.

## Frames without holes: `rrect_half`

```python
outer = rrect_half(hx_out, hy_out, R_out, upper=True)
inner = rrect_half(hx_in,  hy_in,  R_in,  upper=True)
le.poly(cell, outer + inner[::-1], layer)          # upper U; repeat with upper=False
```

The two halves overlap by `2·delta` at y = 0. Windows with notches (for example, slots for
recessed beams) are just a custom inner boundary list. Round it with per-vertex radii before
concatenating.

## Field material with holes: `field_halves` + `insert_windows`

For a "drawn = kept" layer the field (anchored material around the device) is the die minus the
open region. Without booleans:

```python
hole_left = [(ov, -b), (-a, -b), (-a, b), (ov, b)]          # left half of the hole, bottom → top
left, right = field_halves(hole_left, extent=HF, overlap=ov, hole_round=R)
left = insert_windows(left, [(x0, y0, x1, y1)], edge_y=HF)  # extra etch windows (bridged to y = HF)
```

- The hole must be mirror-symmetric about x = 0 (true for most devices). For asymmetric holes,
  build the left and right halves by hand with the same pattern.
- `insert_windows` bridges each window straight up to the field edge, so keep the path between a
  window and the top edge free of other windows. Group windows near that edge (marks, test
  structures), or bridge to another edge by adapting the function.
- Inside a window, draw kept features (mark pedestals, test combs) as separate polygons.

## Isolation-trench rings: `trench_ring`

```python
island = round_poly(ccw(island_pts), R_island)
for run in trench_ring(island, width=4, open_region=OPEN, stub_open=offset_poly(OPEN, -5)):
    le.path(cell, run, TRENCH, 4)
```

Steps: offset the rounded island outline by `+w/2` → clip away the parts inside the open region
shrunk by the stub length → emit flat-capped paths of width `w`. The trench ends penetrate the
etched region by `stub` µm, which guarantees a complete electrical cut after the structural etch.

Rules of thumb (each one came from a DRC failure):
- Let the island polygon **extend into the open region by at least 2× its corner radius**. If
  the clip cuts through a rounded corner, the slanted cut leaves a sliver thinner than the trench
  width.
- Keep the island's side edges **inside the open region's straight edges by more than the open
  region's corner radius**. Otherwise the trench crosses the etched boundary on its rounded corner.
- A ring that lies entirely in the field is returned closed, with one segment of overlap, so the
  flat caps leave no seam.
- Round trench corners (R ≥ 2× width). Sharp corners cause voids when the trench is refilled.
- For trenches drawn by hand (cuts across a moving frame), use `round_poly(pts, R, closed=False)`
  and start and end each path a few µm inside an etched edge.

## Comb drives: `comb_row`

```python
row, half_moving, half_fixed = comb_row(le, "COMB", finger_w=7, gap=3, length=100, tip=20, n=72, layer=SI)
le.ref(top, row, x_edge, 0, -90)        # moving root on the moving edge, fixed root on the fixed edge
```

- n moving and n+1 fixed fingers: every moving finger has equal gaps on both sides (lateral force
  balance, which matters for side instability).
- `tip` = clearance between finger tips and the opposite root; overlap = `length − tip`.
- Pitch = 2·(w + g). Check that `half_fixed` fits within the edge (corners and fillets).
- Drawn width and gap should already include bias (`w = w_target + 2b`, `g = g_target − 2b`).

## Mask text: `dot_text`

A 5×7 dot-matrix font made of overlapping squares (side 1.3 × pitch). Diagonal neighbours overlap,
giving a neck of 0.42 × pitch; non-adjacent dots are 0.7 × pitch apart. Choose
`pitch ≥ max(min_width / 0.42, min_space / 0.7)`; for example, pitch 8 µm passes 3 µm/3 µm rules.
Add missing glyphs to `FONT` (5 columns × 7 rows of `#`/`.`).

## Offsets: `offset_poly`

Miter offset of a closed polygon (`d > 0` grows). It is designed for rounded outlines. On very acute
corners the miter grows large, so round first. It is not a general polygon-offset library: self-
intersections are not removed. Use it for centre lines, cavities (open region + margin) and stub
regions (open region − stub).
