---
name: layouteditor-skill
description: Script mask and IC layouts with juspertor LayoutEditor's LayoutScript Python API. Use to generate GDSII/OASIS, inspect or audit existing layouts, remap layer/datatype pairs, normalize database units, convert formats, merge files, assemble reticles or wafers, run DRC, extract netlists natively and compare them with a SPICE reference (LVS), and set up a JSON technology file from a foundry PDK. Includes MEMS, photonics, data-prep, assembly and CMOS LVS examples. Requires LayoutEditor, not KLayout.
license: MIT
metadata:
  runtime: Requires juspertor LayoutEditor with its LayoutScript Python interpreter, plus a separate Python 3.8+ with numpy, Pillow and matplotlib for analysis and previews. The bash runners and native API are verified on macOS; Linux and Windows need local validation.
  author: laull9
  version: "0.4.0"
  tested-layouteditor: "20260920"
---

# LayoutEditor layout automation

Use LayoutEditor's native API for reproducible geometry, checked exports, DRC and extraction.
Keep the user's source layout, technology, units, chosen format and license constraints explicit.
The examples teach distinct tasks with illustrative rules; none is a foundry-qualified process.

## Runtime

Paths below are relative to this skill's directory; run scripts by absolute path from the
user's working directory and write outputs there, never inside the skill.

`scripts/find_layouteditor.sh` prints the interpreter that can import `LayoutScript` (`LE_PY`).
Generators, data preparation, assembly, DRC and extraction run with it. Previews, raster checks,
`pdk_tool.py` and `lvs_compare.py` use a separate Python (`PYTHON`) with numpy, Pillow and
matplotlib. If LayoutEditor is missing, point to the [official download](https://layouteditor.com/download.html).

The tested macOS build crashes on a second `project.newLayout()` in one process. Keep one native
layout session per process; every script here does.

## Choose a workflow

| Task | Read or run |
|---|---|
| Inspect, audit, convert, remap, normalize units or merge existing layouts | [Data preparation](references/data-prep-and-assembly.md); `examples/mask_prep/run_prep_demo.sh` |
| Describe a process: layer map, units, stack, devices, rules | [PDK workflow](references/pdk-workflow.md); `scripts/pdk_tool.py` |
| Extract a netlist and compare it with a schematic netlist (LVS) | [Extraction and LVS](references/extraction-lvs.md); `examples/cmos_lvs/run_lvs_demo.sh` |
| Mixed-die rectangular reticle or circular wafer | [Data preparation](references/data-prep-and-assembly.md); `examples/wafer_assembly/run_assembly.sh` |
| Waveguide primitives, connected MZI, ring and shallow-etch grating | [Photonics](references/photonic-layout.md); `examples/photonic_circuit/run_pic_demo.sh` |
| Comb actuator, isolation trenches, fillets and release masks | [SOI MEMS](references/mems-soi-process.md), [geometry](references/geometry-techniques.md); `examples/mems_comb_drive/run_mems.sh` |
| Layer booleans or sizing | [Boolean workflow](references/boolean-workflow.md), [license limits](references/free-version-limits.md); `scripts/layer_boolean.py` |
| DRC, raster connectivity and visual review | [Verification](references/verification.md) |
| API failures | [API notes](references/layoutscript-api.md), [troubleshooting](references/troubleshooting.md) |

Pass an output directory to each runner. Every runner generates its own inputs there.

## Before touching an existing file

1. `"$LE_PY" scripts/layout_prep.py inspect FILE --json`: DBU, candidate tops, `layer/datatype` statistics.
2. Several tops → choose one with the user and pass `--top` to every later step.
3. DBU not 1 nm → `layout_prep.py normalize-dbu` into a copy. Never set `databaseunits` alone;
   that rescales the physical design.
4. With a technology file → `layout_prep.py audit FILE tech.json` for undeclared pairs and
   off-grid points before DRC or extraction.

## Geometry, layer and export constraints

- `LE` and the generators use µm at 1 nm DBU. `LE(tech="tech.json")` accepts layer names and
  `(layer, datatype)` pairs wherever a layer number was accepted.
- Remap with `"L/D"` keys when datatypes carry meaning (pins, labels, fill); a bare layer key
  moves every datatype of that layer. Cell references are never dropped.
- LayoutEditor's DRC, technology layers and extraction act per layer **number** across all
  datatypes. Put fill/blockage datatypes in `connectivity.ignore_datatypes`.
- `strans.rotate()` is clockwise. `LE.ref(..., ang)` takes CCW degrees. Use 1-D arrays only.
- Free-edition boolean/sizing and element limits can block GDS export. Never stage, reload or
  change format to bypass a license gate. Default examples avoid boolean exports.
- Confirm every export exists and is nonempty. The prep tools write via a temporary file and
  replace the output only after success. Save before flattening, dumping or extracting; those
  steps add temporary cells. Never save an analysis session back to the source.
- Native headless screenshots are blank. Render polygon dumps with `render_preview.py`; dumps are
  previews, not interchange files (no datatypes, properties or nets).
- Free-edition exports add a "Generated with the LayoutEditor" text to each cell; it is not part
  of the design. Ignore it when comparing outputs.
- Keep explanatory text, die and field boundaries on reference layers, not on mask layers.

## Working procedure

Collect dimensions, mask polarities, technology and the requested top cell before generating
geometry. Put parameters in one place and distinguish supplied values from assumptions. For a
fabrication task, start from the foundry's layer map and rules: build or extend a technology file,
run `pdk_tool.py check`, and draw by layer name. Do not invent rules, layer numbers or device
recognition layers; ask for them.

Build reusable cells, save the hierarchy, then verify what the task needs:

- Conversion/remapping/unit changes: reopen output and compare geometry, units, hierarchy and
  layer/datatype pairs. DXF and other non-GDS formats can change path, text or hierarchy semantics.
- Assembly: die bounds, pairwise separation, street geometry and placement counts.
- Circuits: audit, `pdk_tool.py drc-rules` → `drc_check.py`, then `extract_netlist.py` →
  `lvs_compare.py` against the user's netlist. Read the device and net maps; investigate every
  warning about labels or unconnected pins.
- Device masks (MEMS): DRC, raster connectivity/release probes, review small gaps and joints,
  compare drawn dimensions with a validated physical model.
- Photonics: port continuity, coupling gaps and drawn path lengths. Optical behavior requires a
  PDK model or simulation.

Report exported files, executed checks with their results, and what remains unverified. LVS here
compares topology only: no device sizes, parasitics or foundry deck rules. The JSON DRC runner
covers six rule types; density, antenna and other foundry checks need the foundry deck. For PCells,
schematic-driven layout or OpenAccess libraries use the LayoutEditor GUI and return to these
scripts with the exported GDS. See [coverage and gaps](docs/coverage-assessment.zh-CN.md).

## Rebuild examples and assets

```bash
python3 scripts/update_assets.py /tmp/layouteditor-skill-examples
```

Use an analysis Python with numpy, Pillow, matplotlib and **gdstk** (verifier only). It runs all
five examples, seven independent output checks and nine native contract tests, then rebuilds the
README images and `assets/manifest.json`. See [example validation](docs/example-validation.md).
