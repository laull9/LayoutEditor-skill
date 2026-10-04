# LayoutEditor free license — measured limits and compliant workarounds

LayoutEditor is offered as free, reduced and full editions. The vendor's site says the free
edition contains the full feature set, but "export of some file formats is limited to small
designs". This file records what was measured headlessly (release 20260920, macOS). Re-measure
on other versions with the probes below.

## Capability matrix (free, headless)

| Capability | Status |
|---|---|
| `import LayoutScript` in the bundled Python; `project.newLayout()` without GUI | works |
| Cells, refs, 1-D arrays, polygons, paths, text, layers | works |
| `saveFile` → `.gds` / `.oas` / `.dxf` for designs under the gate below | works |
| `L.open()` GDS/OASIS | works |
| `drcTool` rules | works |
| `flatAll`, `toPolygon`, selection, element iteration | works (does not trigger the gate) |
| `booleanTool`, sizing | compute correctly, **but trip the export gate** (see below) |
| `saveScreenshot` headless | blank 3×3 PNG |

## The export gate

Console output on `drawing.saveFile("x.gds")`:

```
Feature disabled by license, full version required
Full Version of the LayoutEditor required to store design in selected format.
Design exceeds maximal size possible with the free version.
Design will be saved in LayoutEditor cloud format (.lec) instead.
```

`x.gds` is **not** written. `x.lec` (openable only with the vendor's cloud service) appears
instead, and no Python exception is raised.

Measured triggers:

| Probe | Result |
|---|---|
| 1,000 / 3,000 / 5,000 / 8,000 boxes | saved |
| 10,000 boxes | refused → limit on element count somewhere between 8k and 10k |
| two boxes 10 mm apart | saved → physical extent is not limited |
| one polygon with 400,000 vertices | saved → vertex count is not limited |
| ~600-element design after one `boolOnLayer` | refused, although the same final polygons drawn directly in a fresh layout save fine |

So two things count: the element count, and whether the boolean engine was used in the session.

### Bisecting the gate in your own generator

```python
import os
def probe(tag):
    tmp = "/tmp/_gate_%s.gds" % tag
    dr.saveFile(tmp); print(tag, os.path.exists(tmp))
```

Call `probe()` after each construction stage. The first `False` marks the stage that trips the gate.

## Compliant design patterns (no boolean engine)

| Instead of… | Do this | Helper |
|---|---|---|
| `etch = open_region − structures` | draw the **kept** material ("drawn = kept", light-field polarity) and tell the mask shop | — |
| a field polygon with a hole | two overlapping halves, each tracing around the hole | `field_halves` |
| more holes (etch windows) | zero-width bridges from each window to the field edge | `insert_windows` |
| `(island ⊕ w) − island − (open ⊖ stub)` (trench ring) | offset outline + clip against the shrunken open region → paths | `trench_ring` |
| `island ⊖ inset` (metal on an island) | hand-placed rectangles inset from the island edges | — |
| union of beam + fillet + body | one polygon per beam with integral fillets; let ends overlap the bodies | `dogbone` |
| ring frame | upper and lower U-shaped halves | `rrect_half` |
| analysis needing booleans (nets, enclosure) | raster analysis outside LayoutEditor, or a separate read-only session | `check_connectivity.py` |

To stay under the element limit, use hierarchy: a comb of 200 fingers is two array references
(two stored elements), not 200 polygons. A design with ~800 structural polygons after flattening,
built as cells and arrays, exported fine. Whether the gate counts stored or flattened elements
was not isolated, so keep both well below ~8,000 if you can.

## Ethics

The gate is a license boundary. Choosing drawing methods that do not need the licensed feature is
legitimate. Computing results with the boolean engine and then copying them into a fresh session
to export them is circumvention: don't. If the user genuinely needs booleans in the exported data,
say so and suggest the full edition, or exporting the primitive layers and doing the booleans in the
mask-prep flow.
