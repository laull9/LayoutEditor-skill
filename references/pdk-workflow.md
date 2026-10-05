# PDK and technology workflow

A **technology file** (JSON) is this skill's PDK description. Write it once per process; every
tool then refers to layers by name and the same numbers reach the generator, audits, DRC,
remapping and extraction. `examples/cmos_lvs/cmos_tech.json` is a complete, illustrative file.

## Build the technology file

Start from the foundry's documents, never from guesses:

| Field | Source in a foundry PDK | Used by |
|---|---|---|
| `layers` name → `gds: [layer, datatype]` | layer map / stream map file | `LE(tech=...)`, audit, remap, preview colours |
| `units.dbu_m`, `units.grid_um` | design manual (database unit, manufacturing grid) | `layout_prep.py audit`, `normalize-dbu` |
| `connectivity.stack` | metal/via stack in the design manual or LVS deck | `extract_netlist.py` |
| `connectivity.ignore_datatypes` | fill, blockage or exclusion purposes | extraction |
| `devices` | device recognition layers in the LVS deck | extraction, `lvs_compare.py` |
| `drc` | design-rule manual (a subset you transcribe) | `pdk_tool.py drc-rules` → `drc_check.py` |

A text layer map with lines `<name> <purpose> <gds layer> <gds datatype>` (Virtuoso/OpenAccess
style) imports directly:

```bash
python3 scripts/pdk_tool.py import-layermap foundry.layermap layers.json --purposes drawing,pin,label
```

Purpose `drawing` keeps the bare name (`Metal1`); others become `Metal1.pin`. Paste the result
into the technology file, add units, stack, devices and rules, then validate:

```bash
python3 scripts/pdk_tool.py check tech.json        # exit 1 lists every problem
```

`check` rejects duplicate pairs, grids that are not whole DBU multiples, unknown layer names in the
stack, devices or rules, a stack that does not alternate conductor/via, and two stack entries on
one GDS layer number.

## Field reference

```json
{
  "name": "my_process",
  "units": {"dbu_m": 1e-9, "grid_um": 0.005},
  "layers": {"METAL1": {"gds": [8, 0], "color": [70, 130, 220]}, "METAL1.PIN": {"gds": [8, 2]}},
  "connectivity": {"stack": ["POLY", "CONT", "METAL1", "VIA1", "METAL2"], "ignore_datatypes": [22]},
  "devices": [{
    "name": "nmos", "method": "MOS-default",
    "layers": {"layerPoly": "POLY", "layerActive": "ACTIVE", "layerContact": "CONT",
               "layerRequiredWell": "PWELL", "layerOutsideWell": "NWELL"},
    "parameters": {},
    "ports": ["S", "D", "G"], "equivalent_ports": [["S", "D"]],
    "spice": {"prefix": "M", "models": ["nmos", "sg13_lv_nmos"], "pins": ["D", "G", "S", "B"]}
  }],
  "drc": [{"name": "M1 width", "rule": "minimumSize", "layer": "METAL1", "value": 0.16, "merge": true}]
}
```

- `stack` runs bottom to top: conductor, via, conductor, ... Index = LayoutEditor level.
- `devices[].method` is a LayoutEditor extraction method: `MOS-default`, `R-thinFilm`,
  `C-parallelPlate`, `C-nodeToGround`, `BJT-vertical`, `BJT-lateral`. `layers` keys are that
  method's layer parameters; `parameters` holds the rest (for `R-thinFilm`: `rsquare`,
  `resolution`). `ports` must match the method's port order (MOS: S, D, G).
- `spice.pins` is the pin order of a SPICE line; pins the layout device lacks (bulk) are dropped.
- `drc` uses the rule names of `scripts/drc_check.py`; `layer`/`layer2` may be names.

## Use it

```bash
"$LE_PY" scripts/layout_prep.py audit chip.gds tech.json --top TOP   # DBU, undeclared pairs, off-grid
python3 scripts/pdk_tool.py drc-rules tech.json rules.json
"$LE_PY" scripts/drc_check.py chip.gds TOP rules.json drc.txt
"$LE_PY" scripts/extract_netlist.py chip.gds tech.json chip_netlist.json --top TOP
python3 scripts/lvs_compare.py chip_netlist.json chip.sp tech.json lvs.txt
```

In generators, `LE(top="TOP", tech="tech.json")` accepts layer names everywhere a layer number
was accepted: `le.poly(cell, pts, "METAL1")`, `le.text(cell, "METAL1.PIN", x, y, "VDD")`.
Datatypes are written to the elements; names and colours are set per layer number.

To move a layout between two technologies that share layer names:

```bash
python3 scripts/pdk_tool.py port-map old_tech.json new_tech.json map.json
"$LE_PY" scripts/layout_prep.py remap old.gds new.gds map.json
```

Shapes on names the new technology lacks stay where they are; `port-map` lists them. Design rules
and device sizes do not port automatically: re-run audit, DRC and LVS in the new technology.

## Layer numbers versus layer/datatype pairs

LayoutEditor keys layer names, technology layers, DRC and extraction parameters on the **layer
number**. Datatypes stay on each element and survive GDS export (OASIS datatype round trips are
not separately verified). Consequences:

- `drcTool` checks every datatype of a layer number together. Keep fill or pin purposes on their
  own datatypes, but expect them in DRC of that number.
- Extraction also merges datatypes of a number. Pins and labels on `8/2`, `8/25` correctly join
  `8/0`. Fill or blockage purposes must be listed in `ignore_datatypes`.
- If two different materials share one layer number (rare), remap one of them to a free number
  before DRC or extraction.
- `setup.gdsAutoMapDatatypes = True` makes LayoutEditor assign one internal layer per pair on
  import (stored in `layers.num(n).mapToLayer/mapToDatatype`). The scripts here keep the default
  (`False`), where internal number = GDS layer.

## Vendor PDK packages in LayoutEditor

LayoutEditor ships encrypted technology packages (`library/*.ltgz`, for example the IHP SG13G2
open PDK) and component libraries (`*.lel`). They load through the GUI. In the tested headless
build, `components.addLib()` and `components.getLibs()` crash, and IHP components are not
reachable by `findComponent`. Bundled `.lel` libraries such as `LTspice` are reachable, and
`components.newComponent(name, library)` with `extractionMethod`/`extractionParameter` works.
`extract_netlist.py` therefore defines devices from the technology file instead of importing a
vendor library.

For PCells, schematic-driven layout and OpenAccess libraries, use the LayoutEditor GUI with the
foundry's package, then bring the exported GDS back to these scripts for audit, DRC, extraction
and LVS. Do not reverse-engineer encrypted packages.

## Limits

The technology file is a working subset. It does not replace a foundry DRC/LVS deck: density,
antenna, latch-up, ESD and recognition of every device variant remain foundry sign-off tasks.
Transcribe only the rules the task needs and say which ones were checked.
