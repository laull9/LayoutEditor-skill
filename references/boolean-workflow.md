# Layer boolean and sizing workflow

Reference guide for programmatic layer logic operations in LayoutEditor.

## 1. Batch boolean operations

Command:
```bash
python scripts/layer_boolean.py <in.gds> <out.gds> <operations.json> [TOP_CELL]
```

`operations.json`:
```json
[
  {"op": "boolean", "type": "A-B", "layerA": 3, "layerB": 1, "target": 10},
  {"op": "boolean", "type": "A+B", "layerA": 10, "layerB": 2, "target": 11},
  {"op": "boolean", "type": "A*B", "layerA": 11, "layerB": 4, "target": 12},
  {"op": "boolean", "type": "AxorB", "layerA": 1, "layerB": 2, "target": 13},
  {"op": "size", "layer": 10, "delta_um": 2.5, "target": 14, "corner": 0}
]
```

### Operation types
- `A-B`: Difference (features on Layer A that are not covered by Layer B).
- `A+B`: Union (merges overlapping or adjacent geometry across Layer A and Layer B).
- `A*B`: Intersection (keeps only overlapping areas between Layer A and Layer B).
- `AxorB`: Symmetric difference (XOR).
- `size`: Expands (positive `delta_um`) or shrinks (negative `delta_um`) polygons.
  - `corner`: `0` for miter, `1` for rounded, `2` for octagon sizing.

---

## 2. In-code Python API (`le_helpers.LE`)

```python
from le_helpers import LE

le = LE(top="MY_CHIP")
# ... draw geometry on layers 1 and 2 ...

# Layer boolean on the current cell
le.layer_boolean(le.top, layer_a=1, layer_b=2, layer_out=3, op="A-B")

# Layer sizing / offset on the current cell
le.layer_size(le.top, layer_src=3, layer_dst=4, delta_um=2.0)
```

---

## 3. License consideration and best practices

1. **Free license boundary**:
   Using `booleanTool` or `dr.copyLayerSized` registers the boolean engine in the session. On the free edition, this causes `dr.saveFile("*.gds")` to write a cloud-only `.lec` file instead of GDS.
2. **When to use boolean operations**:
   - In environments with a licensed (reduced or full) LayoutEditor.
   - For offline DRC and verification scripts that inspect polygons without needing to export a new GDS.
   Export eligibility still depends on the installed edition; small geometry does not guarantee export.
3. **When to use analytical geometry (`geometry-techniques.md`)**:
   - In automated pipelines running under the free license that must guarantee GDS export.
   - For MEMS dog-bone root fillets, comb fingers, and keyhole etch windows.
