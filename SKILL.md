---
name: layout-skill
description: Script, export, verify and preview mask layouts (GDSII) headlessly with juspertor LayoutEditor's LayoutScript Python API (layouteditor.com — not KLayout). Use when asked to draw or generate a layout with LayoutEditor, write LayoutScript Python, produce GDS from code, run LayoutEditor DRC, check electrical connectivity/isolation or mechanical release of a layout, render layout previews, or design MEMS/SOI masks (isolation trenches, metal, front DRIE, backside cavity). Includes verified API quirks and the free-license export limits.
license: MIT
compatibility: Requires juspertor LayoutEditor (https://layouteditor.com/download.html) — its bundled Python provides the LayoutScript module — plus Python 3.8+ with numpy, Pillow and matplotlib for analysis/previews, and a shell to run scripts. Agent-agnostic (Agent Skills format). Verified on macOS; Linux/Windows follow the same API.
metadata:
  author: laull9
  version: "1.0.0"
  tested-layouteditor: "20260920"
---

# LayoutEditor headless layout

Generate layouts from Python with LayoutEditor's bundled interpreter, export GDS, then verify
(design rules, connectivity, release, physics sanity) and render previews, with no GUI. The tools are
generic. The bundled demo (a MEMS comb-actuator test chip) shows every technique end to end.

## 0. Locate the interpreter

```bash
scripts/find_layouteditor.sh
```

This prints the bundled Python that can `import LayoutScript` (on macOS:
`/Applications/layout.app/Contents/MacOS/Frameworks/Python.framework/Versions/3.x/bin/python3.x`).
Generators, `drc_check.py` and `le_helpers.LE` must run with it. Analysis scripts
(`check_connectivity.py`, `render_preview.py`) need a normal CPython with numpy, Pillow and
matplotlib, which LayoutEditor's Python lacks.

If LayoutEditor is not installed, ask the user to install it from the official site
(<https://layouteditor.com/download.html>; the free edition is enough). See `README.md` → *Install LayoutEditor*.
If the interpreter is elsewhere, set `LE_PY=/path/to/python` or `LAYOUTEDITOR_HOME=/install/dir`.

Smoke test the whole tool chain (about 10 s):

```bash
examples/run_demo.sh /tmp/le_demo
```

Expected result: DRC 0 violations, pads isolated, all probes OK, previews written.

## 1. Non-negotiable rules

1. **Free license: no `booleanTool` in a script that exports GDS.** After a boolean on a
   non-trivial design, `saveFile("*.gds")` silently writes a cloud-only `.lec` instead. Draw final
   mask shapes directly (light-field "drawn = kept" layers, keyhole field polygons, offset+clip
   trench rings). Never re-import boolean results into a fresh layout to dodge the check; that
   circumvents the license. Details: `references/free-version-limits.md`.
2. **Always check the export**: `LE.save_gds()` raises if the `.gds` was not written.
3. **Rotation is clockwise** in `strans.rotate()`. `LE.ref(..., ang)` takes CCW degrees and handles it.
4. **Arrays**: only 1-D (`ny = 1`) `addCellrefArray` is reliable. Flatten with `drawing.flatAll()`
   (`cell.flatSelect()` skips arrays).
5. **No headless screenshots**: they come out blank. Render from the JSON dump instead.
6. **Mask text**: use `le_helpers.dot_text` (DRC-safe). The built-in text→polygon glyphs have
   sub-µm spikes.
7. **Units**: 1 dbu = 1 nm. Write geometry in µm (floats). `LE` converts.
8. **Do not save after flattening or analysis** in the same session.

## 2. Workflow

1. **Pin down the source geometry before drawing.** Collect every dimension from the user's
   verified model (FEM/COMSOL screenshots, papers, spreadsheets, scripts). Back-fit missing values
   from verified results (for example, layer thickness from a simulated resonance) rather than
   guessing. List what is still assumed. Ask the user when a choice changes the physics.
2. **Parameterise**: one dict `P` in µm at the top of the generator. Derive drawn sizes from
   targets and process bias (lines `+2·bias`, gaps `−2·bias`). Keep magic numbers out of the code.
3. **Choose layers and polarity** (`references/mems-soi-process.md` for SOI MEMS): number,
   name, colour, and "drawn = etched/kept" for each mask. Put reference outlines and notes on
   non-mask layers.
4. **Generate** with `scripts/le_helpers.py`. Start from `examples/demo_chip.py`.
   - Unit cells (finger, beam, mark) → 1-D arrays → sub-assemblies → top. Design unit cells to be
     symmetric so that rotation alone covers all placements.
   - Use `round_poly`/`dogbone`/`rrect_half`/`field_halves`/`insert_windows`/`trench_ring` for
     filleted, hole-free, boolean-free geometry (`references/geometry-techniques.md`).
5. **Export and dump**: `le.save_gds(path)`, then `le.dump_flat_json(path_json, meta=...)`.
6. **Verify**. Do all four and fix until clean (`references/verification.md`):
   - `drc_check.py <gds> <TOP> rules.json` (LayoutEditor drcTool; exit 1 on violations; prints coordinates).
   - `check_connectivity.py polys.json probes.json` (nets, isolation, released parts).
   - A physics sanity check of key figures computed from the *drawn* dimensions (frequency,
     stiffness, capacitance…) against the user's simulation.
   - `render_preview.py polys.json outdir views.json`, then **look at the zoom views yourself**:
     gaps, fillets, trench ends, mark clearances, labels.
7. **Report**: what was built, the verification results (with numbers), and the remaining
   assumptions or decisions the user must confirm. Keep the generator re-runnable and document how.

## 3. Files

| Path | Purpose |
|---|---|
| `scripts/le_helpers.py` | Geometry (fillets, offsets, clipping, dog-bone beams, keyhole windows, trench rings, dot font) + `LE` session wrapper + `comb_row` + JSON dump |
| `scripts/drc_check.py` | DRC with LayoutEditor's drcTool from a JSON rule list |
| `scripts/check_connectivity.py` | Raster connectivity/isolation/release check from a JSON probe list |
| `scripts/render_preview.py` | Overview, per-layer and zoom PNGs from the JSON dump |
| `scripts/find_layouteditor.sh` | Print the bundled interpreter path |
| `examples/demo_chip.py` + `demo_*.json` + `run_demo.sh` | End-to-end reference implementation |
| `references/layoutscript-api.md` | Verified API signatures, idioms, quirks |
| `references/free-version-limits.md` | What the free license allows, the export gate, compliant workarounds |
| `references/geometry-techniques.md` | How to draw fillets, rings, holes, combs and text without booleans |
| `references/mems-soi-process.md` | SOI-MEMS mask conventions, design rules, isolation and routing, marks, test structures |
| `references/verification.md` | DRC rule sets, connectivity method, analytic checks, review checklist |
| `references/troubleshooting.md` | Symptom → cause → fix |
