# Data preparation and assembly

Run native tools with the interpreter returned by `scripts/find_layouteditor.sh`.

## Existing layouts

```bash
"$LE_PY" scripts/layout_prep.py inspect input.gds [--top CELL] --json
"$LE_PY" scripts/layout_prep.py audit input.gds tech.json [--top CELL]
"$LE_PY" scripts/layout_prep.py convert input.gds output.oas
"$LE_PY" scripts/layout_prep.py remap input.gds output.gds mapping.json [--drop-unmapped]
"$LE_PY" scripts/layout_prep.py normalize-dbu input.gds output.gds [--dbu 1e-9]
"$LE_PY" scripts/layout_prep.py merge sources.json merged.gds TOP
```

**Inspect** reports DBU (`dbu_is_1nm`), candidate top cells (cells nothing references), element
counts and statistics keyed by `"layer/datatype"`; texts are counted under their texttype.
References are counted separately and never under a layer. `bbox_um` measures the chosen top
(`--top`, else LayoutEditor's current cell), including transformed references and path widths,
excluding text. When `top_cells` lists several names, pass `--top` everywhere.

**Audit** compares a file with a technology file ([PDK workflow](pdk-workflow.md)): DBU,
layer/datatype pairs the technology does not declare, declared layers that are unused, and every
vertex, reference origin or array pitch off `units.grid_um`. Exit 1 lists the problems.

**Remap** keys are pairs or bare layer numbers:

```json
{"6/2": "16/0", "6/22": [16, 22], "1": 101}
```

A pair key maps exactly that pair. A bare layer key changes the layer and keeps each element's
datatype unless the value is a pair. Pair keys win. `--drop-unmapped` deletes shapes and texts
matched by neither form; cell references are always kept. Identity entries plus
`--drop-unmapped` extract a layer subset.

**Normalize DBU.** Setting `databaseunits` alone keeps the integers and rescales the physical
design (10 nm → 1 nm would shrink it tenfold). `normalize-dbu` first resizes every cell by
old/new: shapes, path widths, reference origins and array pitches. It checks the top extent is
unchanged. A non-integer or coarsening factor would round coordinates and is refused unless
`--allow-rounding` is passed. Text magnification is scaled too; check label size if it matters.

All commands write to a temporary file beside the output and replace the output only after a
nonempty write, so an input can be rewritten in place and a license refusal leaves nothing.

A merge specification selects source tops and unique namespaces:

```json
[
  {"path":"kelvin.gds","cell":"TOP","prefix":"K_","offset":[-850,0]},
  {"path":"line_space.gds","cell":"TOP","prefix":"LS_","offset":[850,0],"angle":0}
]
```

Paths in this merge specification are relative to the shell's working directory. The demo writes
absolute paths. Every source is renamed in its own process **before** import, so colliding `TOP`
and `PAD` cells stay separate. Prefix conflicts and missing cells fail. Angles use CCW degrees.
Merge sources and destination must use 1 nm DBU; normalize other files first. Source staging saves ordinary geometry; it does
not bypass an export license refusal.

Convert by output extension. Reopen the result and verify what matters for the task. The examples
exercise GDS→OASIS and GDS→DXF; OASIS geometry is checked independently. The DXF example verifies
an export was written, without claiming a lossless hierarchy/text round-trip. CIF, Gerber and
other vendor formats need their own fixtures and checks.

## Mixed-die assembly

```bash
"$LE_PY" scripts/wafer_assembly.py config.json assembly.gds report.txt
```

```json
{
  "title":"MIXED_RETICLE",
  "mode":"reticle",
  "field_size_mm":[16,12],
  "edge_exclusion_mm":0.2,
  "dicing_street_width_um":100,
  "pattern":["RES","FLUID"],
  "dies":[
    {"name":"RES","width_um":3000,"height_um":2000,"gds_path":"inputs/resistor.gds","cell_name":"DIE"},
    {"name":"FLUID","width_um":3000,"height_um":2000,"gds_path":"inputs/mixer.gds","cell_name":"DIE"}
  ]
}
```

Config source paths resolve relative to the **config file**. Sources must exist, contain the
requested cell and fit the declared die rectangle centered at `(0,0)`. No missing-source placeholder
is substituted. Input namespaces use each die's unique name.

`mode:"wafer"` (default for older configs) uses `wafer_diameter_mm`, with a circular boundary.
`mode:"reticle"` uses a rectangular `field_size_mm`. Both reserve edge exclusion and half a street
around each slot. Default layers: 11 boundary reference, 21 dicing street, 22 alignment crosses.

The slot width/height are the maximum die width/height; pitch adds street width. The cyclic
`pattern` chooses one source per slot, so types share a single placement grid. Smaller dies leave
unused slot area. This is deterministic placement, not a packing optimizer. Wafer flats, notches,
steppers and manufacturing-specific street masks are not modeled.

Outputs include GDS, `.report.json` (placements, counts, gross and usable area), `.polys.json` and
an optional text report. Utilization measures summed declared die area divided by gross field or
wafer area. Keep hierarchy for repeated dies. Flattening all previews/DRC can still consume large
memory; the examples are small fields, not wafer-scale performance benchmarks.
