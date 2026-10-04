---
name: LayoutEditor-skill
description: Script, export, verify, prepare and preview mask layouts (GDSII, OASIS, DXF) headlessly with juspertor LayoutEditor's LayoutScript Python API (layouteditor.com — not KLayout). Covers 4 core domains: (1) layout data prep (inspection, format conversion, layer remapping, multi-GDS merging, and boolean layer operations); (2) Silicon Photonics (PIC) waveguide circuits (Euler bends, S-bends, MZI, ring resonators, grating couplers); (3) wafer/reticle multi-die assembly with dicing streets and alignment marks; (4) parametric MEMS/SOI mask generation without booleans. Includes verified API quirks and free-license limits.
license: MIT
compatibility: Requires juspertor LayoutEditor (https://layouteditor.com/download.html) — its bundled Python provides the LayoutScript module — plus Python 3.8+ with numpy, Pillow and matplotlib for analysis/previews, and a shell to run scripts. Agent-agnostic (Agent Skills format). Verified on macOS; Linux/Windows follow the same API.
metadata:
  author: laull9
  version: "0.2.0"
  tested-layouteditor: "20260920"
---

# LayoutEditor headless layout (v0.2)

Automate mask-layout generation, preparation, wafer assembly and verification with LayoutEditor's bundled Python interpreter (no GUI required).

Four primary workflows (ordered by daily usage frequency):
1. **Layout data preparation and boolean operations**: inspect cell hierarchies and layer distributions, convert between GDS/DXF/OASIS, remap layers, safely merge external GDS files without naming collisions, and execute batch layer booleans / sizing.
2. **Integrated Silicon Photonics (PIC)**: draw low-loss Euler bends, cosine S-bends, directional couplers, ring resonators, MZI filters, and fiber grating couplers.
3. **Wafer and Reticle assembly**: arrange multiple dies across wafers (4/6/8-inch) or reticles with automated dicing streets, cross marks, and area utilization analysis.
4. **Parametric MEMS/SOI masks**: generate comb actuators, cantilevers, isolation trenches, and run headless DRC / raster connectivity / release verification.

## 0. Locate the interpreter

```bash
scripts/find_layouteditor.sh
```

Generators, `layout_prep.py`, `wafer_assembly.py`, `layer_boolean.py`, `drc_check.py` and `le_helpers.LE` run with LayoutEditor's bundled Python.
Analysis and rendering scripts (`check_connectivity.py`, `render_preview.py`) use a standard Python 3 with numpy, Pillow and matplotlib.

Smoke tests for all workflows:
```bash
examples/mask_prep/run_prep_demo.sh /tmp/le_prep       # Data prep, conversion & boolean instance
examples/photonic_circuit/run_pic_demo.sh /tmp/le_pic   # Silicon Photonics instance
examples/wafer_assembly/run_assembly.sh /tmp/le_wafer  # Multi-die wafer assembly instance
examples/mems_comb_drive/run_mems.sh /tmp/le_mems      # MEMS comb-drive instance (or examples/run_demo.sh)
```

## 1. Operating rules and license boundary

1. **Free license GDS export gate**: on the free edition, using `booleanTool` or `copyLayerSized` locks subsequent GDS export (saving writes a cloud-only `.lec` instead). Designs exceeding ~8k–10k elements trigger the same gate.
   - For free-edition generator workflows: draw final shapes analytically using `le_helpers.py` (light-field "drawn = kept", keyhole polygons, offset+clip trench rings).
   - For licensed or intermediate analysis steps: use `scripts/layer_boolean.py` or `le.layer_boolean()`.
2. **Export check**: always verify the file exists on disk after export (`LE.save_gds()` does this automatically).
3. **Rotation is clockwise**: `strans.rotate()` is clockwise. `LE.ref(..., ang)` accepts CCW degrees and handles inversion.
4. **1-D arrays only**: `addCellrefArray` is reliable only for 1-D arrays (`ny = 1`).
5. **Headless screenshots**: native `saveScreenshot` produces blank images headlessly. Always render previews using `scripts/render_preview.py` from the JSON dump.
6. **Mask text**: use `le_helpers.dot_text` (DRC-safe 5×7 dot font).
7. **Units**: LayoutEditor database unit is 1 nm (`1e-09 m`). Write all Python coordinates in µm (float).

## 2. Tool directory

| Script | Purpose |
|---|---|
| `scripts/le_helpers.py` | Geometry (fillets, offsets, keyhole field, trench rings, dot font) + `LE` session wrapper + layer boolean/sizing hooks |
| `scripts/photonic_helpers.py` | PIC geometry (straight, cosine S-bends, Euler bends, linear tapers, directional couplers, ring resonators, MZI, grating couplers) |
| `scripts/layout_prep.py` | Inspect layout structure, convert formats (GDS/OASIS/DXF/CIF), remap layers, merge multi-GDS layouts with cell prefixing |
| `scripts/wafer_assembly.py` | Wafer-level (4/6/8-in) and reticle tiling, dicing street generation, cross marks, silicon utilization reporting |
| `scripts/layer_boolean.py` | Batch layer difference, union, intersection, xor and sizing |
| `scripts/drc_check.py` | Run LayoutEditor's built-in `drcTool` from JSON rule configurations |
| `scripts/check_connectivity.py` | High-resolution raster netlist, electrical isolation and mechanical release verification |
| `scripts/render_preview.py` | Headless multi-layer and zoomed window PNG preview rendering |
| `scripts/find_layouteditor.sh` | Locate LayoutEditor's bundled Python interpreter across platforms |

## 3. Workflows and references

- **MEMS / Sensor design**: see `references/mems-soi-process.md` and `references/geometry-techniques.md`. Reference implementation: `examples/mems_comb_drive/` and `examples/demo_chip.py`.
- **Silicon Photonics (PIC)**: see `references/photonic-layout.md`. Reference implementation: `examples/photonic_circuit/`.
- **Wafer Assembly and Data Prep**: see `references/data-prep-and-assembly.md`. Reference implementation: `examples/wafer_assembly/` and `examples/mask_prep/`.
- **Layer Booleans**: see `references/boolean-workflow.md` and `references/free-version-limits.md`.
- **Verification**: see `references/verification.md`.
