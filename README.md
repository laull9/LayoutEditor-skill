# LayoutEditor-skill

English | [简体中文](README.zh-CN.md)

An agent skill that lets Codex, Claude Code and other coding agents do layout work through
[juspertor LayoutEditor](https://layouteditor.com). Describe the mask, chip or file problem in
plain language. The agent drives LayoutEditor's Python API, checks what it produced and tells you
what passed and what is still unverified.

![What the bundled examples produce](assets/showcase_grid.png)

## What your agent can do with it

**Work with layouts you already have.** Find the top cells, units and every layer/datatype pair
in a GDS. Audit it against your process: undeclared layers, wrong database unit, off-grid
vertices. Remap pin and fill datatypes without touching drawing data. Rescale a 10 nm file to
1 nm without changing its size. Convert to OASIS or DXF. Merge files whose cell names collide.

**Set up a process once, then draw by name.** The agent writes a small JSON technology file from
your foundry's layer map and design manual: layers, units, metal/via stack, device recognition
layers and the design rules you care about. Generators then say `"METAL1.PIN"` instead of `8/2`,
and DRC, audits and extraction read the same file.

**Check circuits natively.** LayoutEditor's own engine extracts transistors, resistors and nets
from the layout. The skill compares the result with your SPICE netlist and names the short, open
or miswired device when they differ.

**Generate masks from parameters.** SOI MEMS actuators with fillets, isolation trenches and
release checks; photonic MZIs, rings, gratings and Euler bends; test coupons; mixed-die reticles
and circular wafer maps.

**Show its work.** Every runner writes the GDS, a DRC report, verification output and PNG
previews that you can open and review.

## Ask for things like

- "Inspect `chip.gds` and tell me which layers and datatypes it uses and whether it is on a 5 nm grid."
- "This file is in 10 nm units; give me a 1 nm copy and prove nothing moved."
- "Move every `*.pin` datatype to 2 and drop the fill datatype before I send this out."
- "Here is our layer map and rule table. Make a technology file and check my layout against it."
- "Draw a two-input NAND in that process, run DRC, extract it and LVS it against `nand2.sp`."
- "Merge these three test chips onto a 16×12 mm reticle with 100 µm streets."
- "Parametric comb drive with 3 µm gaps, then check the pads are isolated and nothing floats after release."

## How it works

When a request involves layout, the agent loads [SKILL.md](SKILL.md). It routes the task to the
right reference and script and lists the checks that must pass before the agent reports
success. The agent then:

1. finds LayoutEditor's bundled Python, which ships the `LayoutScript` module;
2. inspects existing inputs first (units, tops, layer pairs) and asks you for anything a
   fabrication result depends on: rules, layer numbers, device layers;
3. runs generators, data-prep tools, DRC and native extraction in LayoutEditor's interpreter,
   one layout session per process;
4. runs previews, raster checks and LVS comparison in an ordinary Python;
5. reports the files written, the checks executed with their results, and what was not verified.

The scripts work equally well by hand; each one documents its command line at the top of the file.

## Requirements and installation

- **LayoutEditor** from the [official download page](https://layouteditor.com/download.html).
  On macOS, place `layout.app` in `/Applications`. The free edition runs every bundled example.
  Boolean export and larger layouts depend on your license. This project is independent of
  juspertor GmbH and does not distribute LayoutEditor.
- **Python 3.8+** with `numpy pillow matplotlib` for previews and analysis.

```bash
npx skills add laull9/LayoutEditor-skill        # add -g for a global install
```

Or clone it into your agent's skill folder under the name `layout-skill`:

```bash
git clone https://github.com/laull9/LayoutEditor-skill ~/.claude/skills/layout-skill
```

Check the interpreter discovery and install the analysis packages:

```bash
~/.claude/skills/layout-skill/scripts/find_layouteditor.sh
python3 -m pip install numpy pillow matplotlib
```

`LE_PY` and `PYTHON` override either interpreter. macOS is tested; Linux and Windows still need
local validation.

## Bundled examples

Each runner takes an output folder, generates its own inputs and stops on a failed check.

| Example | Run | What it shows |
|---|---|---|
| CMOS LVS | `examples/cmos_lvs/run_lvs_demo.sh /tmp/le_lvs` | Technology file → NAND2 drawn by layer name → audit → 7 DRC rules → native extraction → LVS. The correct layout passes; an A–B short and a missing via fail with named causes. |
| Data preparation | `examples/mask_prep/run_prep_demo.sh /tmp/le_prep` | Two coupons with colliding TOP/PAD names; OASIS/DXF conversion, layer remapping, namespaced merge. |
| Photonics | `examples/photonic_circuit/run_pic_demo.sh /tmp/le_pic` | Connected MZI (ΔL = 40 µm), ring with a 200 nm gap, shallow-etch gratings, Euler bend; 3 DRC rules. |
| Mixed reticle | `examples/wafer_assembly/run_assembly.sh /tmp/le_assembly` | 25 resistor and microfluidic dies in a 16×12 mm field with streets and alignment marks. |
| SOI MEMS | `examples/mems_comb_drive/run_mems.sh /tmp/le_mems` | Comb actuator with fillets, trenches and backside cavity; 9 DRC rules, pad isolation and release checks. |

![NAND2 drawn from the technology file](assets/lvs_nand2.png)

LVS output for the three NAND2 variants:

![LVS reports: good passes, short and open fail](assets/lvs_verification.png)

All examples use illustrative dimensions and rules. They demonstrate the method, not a
qualified process.

## Limits

- LVS compares circuit topology: devices, pins and nets. Device sizes (W/L, R), parasitics and
  foundry deck rules are not compared.
- The JSON DRC runner has six rule types. Density, antenna, fill and other foundry checks need
  the foundry's deck.
- LayoutEditor's encrypted PDK packages, PCells, schematic-driven layout and OpenAccess libraries
  work in its GUI, not in these headless scripts. Export GDS from the GUI and continue here.
- LayoutEditor checks and extracts per layer number. Datatypes of one number are checked
  together unless the technology file excludes them from connectivity.
- Free-edition boolean/sizing can block export; the skill never works around a license gate.

Measured native behavior and open gaps: [coverage assessment](docs/coverage-assessment.zh-CN.md)
(Chinese), [TODO](TODO.md).

## Repository map

| Path | Contents |
|---|---|
| [SKILL.md](SKILL.md) | What the agent reads: routing, constraints, procedure |
| [references/](references/) | [Data prep](references/data-prep-and-assembly.md), [PDK workflow](references/pdk-workflow.md), [extraction and LVS](references/extraction-lvs.md), [verification](references/verification.md), [photonics](references/photonic-layout.md), [SOI MEMS](references/mems-soi-process.md), [geometry](references/geometry-techniques.md), [booleans](references/boolean-workflow.md), [license limits](references/free-version-limits.md), [API notes](references/layoutscript-api.md), [troubleshooting](references/troubleshooting.md) |
| `scripts/` | `layout_prep.py`, `tech.py`, `pdk_tool.py`, `extract_netlist.py`, `lvs_compare.py`, `drc_check.py`, `check_connectivity.py`, `render_preview.py`, `wafer_assembly.py`, `le_helpers.py`, `photonic_helpers.py`, `layer_boolean.py`, `dump_layout.py` |
| `examples/` | The five runners above |
| `tests/`, [docs/example-validation.md](docs/example-validation.md) | Independent gdstk checks and native contract tests |

Maintainers rebuild every example, run seven output checks and nine native contract tests, and
refresh the images and `assets/manifest.json` with:

```bash
python3 -m pip install numpy pillow matplotlib gdstk
python3 scripts/update_assets.py /tmp/layout-skill-examples
```

## License

[MIT](LICENSE), 2026 laull9.
