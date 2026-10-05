# Native extraction and LVS

Two steps, two interpreters:

```bash
"$LE_PY"  scripts/extract_netlist.py layout.gds tech.json netlist.json --top TOP [--native-dump x.net]
python3   scripts/lvs_compare.py netlist.json reference.sp tech.json lvs.txt [--json lvs.json]
```

`extract_netlist.py` uses LayoutEditor's own engine: technology layers, `extractComponent`,
`buildConnect` and `extractNetList`. `lvs_compare.py` compares that netlist with a reference.
Run `examples/cmos_lvs/run_lvs_demo.sh OUT` to see a passing NAND2 and two failing variants.

## Prepare the layout

- **Labels name nets.** Put a text on a conductor of the stack (any datatype not ignored), with
  its origin inside the shape. Every reference subcircuit port needs one. Unlabelled nets appear
  as `Node_<n>` and are matched by structure.
- **Stack.** Conductor, via, conductor ... from the technology file. A via connects only the
  conductors directly below and above it. Diffusion (`ACTIVE`) is not a conductor in this model:
  MOS-default places the device's S/D ports on the contact layer and G on poly.
- **Devices.** Each technology device becomes a script-defined component in the library
  `layouteditor_skill`; extraction replaces each recognised device by a cell `<top>#<name>` carrying
  properties 10 (device name), 20 (component) and 30 (library).
- **Hierarchy.** By default the top is flattened into a temporary cell before extraction, so
  labels inside child cells name nets. `--hierarchical` keeps cells: LayoutEditor then reports
  each child as a subcircuit device and labels inside children do not reach the top.
- **Fill.** List fill/blockage datatypes in `connectivity.ignore_datatypes`; otherwise a fill
  tile touching two nets shorts them.

## Read the result

`netlist.json` lists nets, devices with `pins`, label locations by layer and warnings:

- `label X is not on an extracted net` — two labels landed on one net (a short) and LayoutEditor
  kept the other name.
- `device M3 has an unconnected pin` — a port did not reach any conductor.

`--native-dump` also writes LayoutEditor's dump format (`#Dump of the LayoutEditor netlist`).
Its format may change between releases; keep the JSON as the artifact.

## Reference netlists

SPICE subset: `.subckt NAME pins ... .ends`, nested subcircuits (flattened with `/` paths),
continuation lines, `*` comments, parameters (`W=` ...) ignored. A line maps to a technology
device by `spice.prefix` and model name; nodes follow `spice.pins`. The compared subcircuit is
`--top`, else the one named like the extracted top, else the only root subcircuit. A JSON file in
the extracted format also works, so two layouts can be compared with each other.

## How the comparison decides

1. Device counts per component, reference ports without a layout label, layout labels missing
   from the reference, and per named net the multiset of `component.pin` connections.
2. Iterative colour refinement of the device/net graph. Equivalent pins (MOS S/D) share a class.
3. An exact backtracking bijection of devices and nets (bounded at 200 000 steps).

PASS requires every step. The report gives the device map and internal net map on PASS, and on
FAIL the differing nets and devices with their pins. Exit codes: 0 match, 1 mismatch, 2 setup.

Not compared: device sizes (W/L, R, C), parameters, parasitic resistance/capacitance, bulk
connections dropped by `spice.pins`, and soft connections through wells or substrate.

## Native LVS findings (tested build 20260920, headless)

- `netlistTool.layoutVersusNetlist()` and `getLVSResults()` run. A SPICE netlist loaded with
  `netlistLoad()` imports `M` lines as four anonymous ports, and `X` lines bind by subcircuit
  name, not to the library component. The native compare then reports missing/additional
  devices even for a correct layout. `lvs_compare.py` replaces that step.
- `extractedNetlistSave(file, 2)` (SPICE) writes only a header for script-defined components;
  type `0` (dump) works. `saveNetlist(netlist, file, "spice")` writes nothing.
- Script-defined components do not store `extractionDeviceParameter` values on the device, so
  sizes are not read back. Measure gate W/L from the geometry when the task needs it.
- `R-thinFilm` resistors (`layerResistance`, `layerContact`, `rsquare`, `resolution`, `ports`)
  extract and connect.
- In the GUI, schematic-driven layout plus `layoutVersusSchematic()` is the vendor's LVS path.

## Typical failures

| Report | Likely cause |
|---|---|
| all nets merged into one | `ACTIVE` listed as a conductor, or poly and diffusion on one level |
| `reference pin A has no labelled net` | label missing, on a non-stack layer, outside the shape, or on an ignored datatype |
| one label missing + a net with doubled gate connections | short between two labelled nets |
| a labelled net loses connections, an extra `Node_n` appears | open: missing via/contact or a gap |
| zero devices | device layer names wrong, well layers absent, or `extractComponent` not run |
| unmatched devices with S/D swapped only | `equivalent_ports` missing for that device |
