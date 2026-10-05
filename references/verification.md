# Verification

A layout is not done until it passes four checks: design rules, connectivity, physics sanity
against the verified model, and a visual review of zoomed previews.

## 1. Design rules — `scripts/drc_check.py`

```bash
"$LE_PY" scripts/drc_check.py layout.gds TOP rules.json report.txt   # exit 1 on violations
```

- Uses LayoutEditor's own `drcTool` on a flattened temporary cell (never saved).
- Rule types: `minimumSize`, `minimumElementDistance`, `minimumDistance`, `minimumEnclosure`,
  `minimumNotchOnLayer`, `noSelfintersectionOnLayer`. Values in µm. See the docstring for JSON keys.
- `"merge": true` (the default) merges overlapping polygons first. Without it every intentional
  overlap (cells, fillet overruns, keyhole halves) is reported.
- Violations are printed with coordinates. Render a zoom view around them before changing anything.
- For a "drawn = kept" structural layer, `minimumSize` checks line widths and
  `minimumElementDistance` checks etched gaps.

Starter rule set (SOI MEMS, see `examples/demo_drc_rules.json`): structure width/gap ≥ 2, metal
width/space ≥ 3, trench width/space ≥ 3, backside feature ≥ 200, structure encloses metal ≥ 3,
metal-to-trench ≥ 3.

Typical first-run failures and fixes:

| Failure | Cause | Fix |
|---|---|---|
| metal width < 3 µm at text | vector-font glyph tips | `dot_text` with a large enough pitch |
| trench width ~1–2.5 µm at a ring end | ring clipped through a rounded corner | extend the island deeper into the open region |
| backside feature < 200 µm | a narrow channel (beam slot) in the open region | widen the channel |
| metal–trench distance | label or pad placed next to a ring | move it ≥ 20 µm away |

## 2. Connectivity, isolation, release — `scripts/check_connectivity.py`

For electrical circuits with a conductor/via stack, devices and a reference netlist, use native
extraction and LVS instead ([extraction and LVS](extraction-lvs.md)). The raster check below
suits MEMS and other layouts where "connected" means touching material on given layers and
where release or mechanical anchoring matters.

```bash
python3 scripts/check_connectivity.py polys.json probes.json report.txt   # exit 1 on failure
```

Method: rasterise the conductor layers (minus insulating trenches) at `resolution` µm, label 4-
connected regions with run-length encoding and union-find, then:
- **pads pairwise isolated**: no two pads share a region;
- **probes**: each probe point (finger, beam root, frame band, anchor…) lies in the region of its
  expected pad (`"expect": "<pad>"` or `"FLOATING"`);
- **release**: with trenches *not* removed (they are mechanically solid), every region must touch
  material outside the release (backside) layer. Otherwise it detaches.

Choose `resolution` ≤ smallest gap / 5 (0.5 µm for 3 µm gaps). Memory ≈ (extent / resolution)²
bytes per raster (a 6 mm die at 0.5 µm needs about 144 MB per raster).

Probe placement tips: put probes **inside** the first and last finger of each comb row (finger
centre, half-way along its length), on both sides of every trench, on each band segment of a
partitioned frame, on beam roots, anchors and the field. Express expectations as a netlist
table in the report.

## 3. Physics sanity — compare the drawn geometry to the verified model

The layout must reproduce the model that the user validated (FEM, measurements). Re-derive key
figures from the *drawn* parameters and compare. For torsional resonators:

```
f = 1/(2π) · sqrt( 2·G·Jt / (L·J) )            # two beams of length L
G  = E / (2(1+ν))                               # isotropic; Si (110)-ish: E ≈ 130 GPa, ν ≈ 0.22–0.28
Jt = a·b³/3 · (1 − 0.63β + 0.052β⁵),  a ≥ b,  β = b/a     # Saint-Venant rectangular section
J  = ρ·t·∫ r² dA  over everything that rotates (plate, frame, moving fingers)  # ρ_Si = 2330 kg/m³
```

- Use the **fabricated** beam width (target), not the drawn width with bias.
- Compute J piecewise from the layout parameters: rectangles ∫y² dA = w·(y₁³ − y₀³)/3, minus
  windows and slots, plus finger rows.
- Back-fit unknown thicknesses: the analytic formula fitting **both** modes of a dual-axis
  device at one thickness is strong evidence that the thickness is right.
- Expect the analytic value to be a few percent low compared with FEM, because root fillets
  stiffen the beam and the formula ignores them. Treat ±5–10% as consistent, and recommend
  re-running FEM on the GDS for sign-off.
- Report the bias sensitivity (width ±2 µm) as well.
- For scanners that use frequency ratios (Lissajous, raster), report the ratio too. Small
  deviations from integer ratios matter more than absolute values.

Similar checks: comb capacitance gradient (N·ε·t/g per side), electrostatic pull-in margins, beam
stress at the target angle (scale the FEM stress by angle).

## 4. Visual review — `scripts/render_preview.py`

```bash
python3 scripts/render_preview.py polys.json preview/ views.json
```

Always open and inspect, at least:
- the overview: everything present, nothing overlapping by accident, pads reachable;
- a comb zoom: equal gaps, tip clearances, roots merged into edges;
- each beam root: fillets intact and tangent, beam axis centred;
- every trench end: it enters the etched region on a straight segment;
- frame partitions: bands continuous, island U-trenches closed;
- marks: clearances, verniers readable, no metal over regions that will be etched;
- labels: readable, clear of rings.

Fix what you see, regenerate, and re-run checks 1–3. Iterate until everything is clean.
