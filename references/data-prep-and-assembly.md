# Layout data preparation, merging and wafer assembly

Tools and workflows for handling existing layout files, merging multi-project dies, and generating dicing streets.

## 1. Inspection and conversion

### Inspect layout
Command:
```bash
python scripts/layout_prep.py inspect <input.gds> [--json]
```
Extracts:
- Top cell name and total cell hierarchy count.
- Database units (e.g. `1e-9 m` = 1 nm).
- Total element count across all cells.
- Exact bounding box extent `[x0, y0, x1, y1]` in µm.
- Per-layer breakdown of polygons, boxes, paths, text labels, and cell references.

### Format conversion
Command:
```bash
python scripts/layout_prep.py convert <input.gds> <output.dxf / output.oas / output.cif>
```
LayoutEditor automatically determines file format from extension.

### Layer remapping and filtering
Command:
```bash
python scripts/layout_prep.py remap <input.gds> <output.gds> <mapping.json> [--drop-unmapped]
```
`mapping.json`:
```json
{
  "1": 101,
  "2": 102
}
```
If `--drop-unmapped` is specified, any geometry not present in the mapping dictionary is dropped from the output.

---

## 2. Multi-die merging (GDS Merge)

Command:
```bash
python scripts/layout_prep.py merge <spec.json> <output.gds> [TOP_NAME]
```
`spec.json`:
```json
[
  {"path": "mems_chip.gds", "prefix": "MEMS_", "offset": [-1500, 0], "angle": 0},
  {"path": "pic_chip.gds", "prefix": "PIC_", "offset": [1500, 0], "angle": 0}
]
```
Key behaviours:
1. Imports external layout files into a master session without file corruptions.
2. Applies namespace prefixes (`MEMS_`, `PIC_`) to avoid cell name collisions between sub-chips.
3. Places references in a unified master top cell at specified `(x, y)` coordinate offsets and angles.

---

## 3. Wafer and Reticle assembly

Command:
```bash
python scripts/wafer_assembly.py <config.json> <output.gds> [report.txt]
```

### Config schema (`config.json`)
```json
{
  "title": "WAFER_4INCH_ASSEMBLY",
  "wafer_diameter_mm": 100.0,
  "edge_exclusion_mm": 3.0,
  "dicing_street_width_um": 80.0,
  "street_layer": 11,
  "wafer_boundary_layer": 11,
  "mark_layer": 11,
  "dies": [
    {
      "name": "CHIP_A",
      "width_um": 2000.0,
      "height_um": 2000.0,
      "gds_path": "path/to/chip.gds",
      "cell_name": "TOP"
    }
  ]
}
```

### Calculation and geometry
1. Effective usable wafer radius:
   $$R_{\text{eff}} = \frac{\text{wafer\_diameter}}{2} - \text{edge\_exclusion}$$
2. Die fit condition: a die centered at $(x_c, y_c)$ is placed if and only if all four of its corners satisfy:
   $$x_i^2 + y_i^2 \le R_{\text{eff}}^2$$
3. Cross marks: automatically drawn in street intersections across the wafer to facilitate dicing blade optical alignment.
4. Export gate note: on the free edition, designs with more than ~8k–10k elements will trigger the export gate. For full wafer assembly with thousands of small dies, use a commercial license or restrict the field to a test coupon / reticle size (e.g. 26 mm).
