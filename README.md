# layout-skill

**English** | [简体中文](README.zh-CN.md)

An [Agent Skill](https://agentskills.io) for **headless mask-layout generation with
[juspertor LayoutEditor](https://layouteditor.com)** through its LayoutScript Python API. Your
coding agent writes a parametric Python generator, exports GDSII, verifies the result (design
rules, electrical connectivity and isolation, mechanical release, physics sanity) and shows you
rendered previews.

It packages what was learned by actually doing it: verified API signatures and quirks, the free
license's export limits and compliant ways around them, boolean-free geometry techniques, SOI-MEMS
mask conventions, and generic verification tools.

- Agent-agnostic: follows the open [Agent Skills specification](https://agentskills.io/specification),
  so it works with Claude Code, Cursor, Codex, OpenCode, GitHub Copilot, Cline and other compatible
  agents.
- Installable with `npx skills`, or by copying one folder.

> Not affiliated with juspertor GmbH. LayoutEditor is proprietary software; download and license
> it from the vendor. This skill only automates it.

---

## 1. Install the skill

### Option A — `npx skills` (any supported agent)

Requires Node.js. Uses the open-source [skills CLI](https://github.com/vercel-labs/skills):

```bash
npx skills add laull9/layout-skill
```

This installs into the current project; add `-g` for a global (user-level) install:

```bash
npx skills add laull9/layout-skill -g
```

Choose agents explicitly, non-interactively:

```bash
npx skills add laull9/layout-skill -g -a claude-code -a cursor -y
```

The CLI detects the repository-root `SKILL.md` and links (or copies) the skill into each agent's
skills directory.

### Option B — manual copy

The whole repository is the skill folder. Clone it into your agent's skills directory, keeping
the folder name `layout-skill` (it must match the `name` field in `SKILL.md`):

| Agent | User-level location | Project-level location |
|---|---|---|
| Claude Code | `~/.claude/skills/layout-skill` | `<project>/.claude/skills/layout-skill` |
| Agents following the shared convention | `~/.agents/skills/layout-skill` | `<project>/.agents/skills/layout-skill` |
| Others | see your agent's documentation for its skills directory | |

```bash
git clone https://github.com/laull9/layout-skill ~/.claude/skills/layout-skill
```

Agents without native skill support can still use it: point the agent at `SKILL.md` (for example,
"read layout-skill/SKILL.md and follow it"), and the scripts run from any shell.

## 2. Install LayoutEditor

LayoutEditor is made by juspertor GmbH. Official site: <https://layouteditor.com>.

1. Open the official download page: **<https://layouteditor.com/download.html>**. The package list
   is at <http://www.layouteditor.net/download.html>, and older releases are linked from there.
   You must confirm the export-control statement before downloading.
2. Pick the package for your platform (release 20260920 shown; newer releases have the same pattern):

   | OS | Package |
   |---|---|
   | macOS (Apple Silicon and Intel) | `layout-<release>-macOS-universal.dmg`: drag `layout.app` to `/Applications` |
   | Windows 64-bit | `layout-<release>-win-64bit-installer.msi` (or the portable `.zip`) |
   | Linux | `layout-<release>-Linux.x86_64.AppImage`, or `.deb` (Ubuntu 22.04/24.04/26.04) / `.rpm` (RHEL 8/9/10) |

3. macOS only: if Gatekeeper blocks the first launch, right-click `layout.app` → *Open* once.
   Alternatively run `xattr -d com.apple.quarantine /Applications/layout.app`.
4. Editions: **free** (0 €) is enough for this skill: scripting, GDS export of designs within the
   free limits, and DRC. Paid *reduced* and *full* editions remove export limits. See the vendor
   site for current terms, and `references/free-version-limits.md` for what was measured.
5. Check that the bundled Python is found:

   ```bash
   scripts/find_layouteditor.sh
   ```

   It prints e.g. `/Applications/layout.app/Contents/MacOS/Frameworks/Python.framework/Versions/3.14/bin/python3.14`.
   If it is not found, set `LE_PY=/path/to/that/python` or `LAYOUTEDITOR_HOME=/install/dir`
   (`find / -name LayoutScript.py` shows where the module lives).

## 3. Other requirements

The analysis and preview scripts need Python 3.8+ with numpy, Pillow and matplotlib
(LayoutEditor's bundled Python does not include them):

```bash
python3 -m pip install numpy pillow matplotlib
```

## 4. Try it

From the skill folder:

```bash
examples/run_demo.sh /tmp/le_demo
```

This runs generate → DRC → connectivity → previews on a 2×2 mm SOI comb-actuator test chip.
Expected: `demo_chip.gds`, a DRC report with 0 violations, a connectivity report ending in
`RESULT: ALL PASS`, and PNGs in `/tmp/le_demo/preview/`.

Then just ask your agent, for example: *"Use LayoutEditor to lay out a 4-mask SOI comb-drive
resonator from these dimensions, run DRC and show me the previews."*

Using the tools directly:

```bash
LE_PY="$(scripts/find_layouteditor.sh)"
"$LE_PY" my_generator.py                                         # your generator (see examples/demo_chip.py)
"$LE_PY" scripts/drc_check.py out.gds MY_TOP rules.json drc.txt  # LayoutEditor drcTool
python3 scripts/check_connectivity.py out_polys.json probes.json nets.txt
python3 scripts/render_preview.py out_polys.json preview/ views.json
```

## 5. What's inside

```
layout-skill/
├── SKILL.md                     # entry point for the agent (workflow + rules)
├── scripts/
│   ├── le_helpers.py            # geometry helpers + LayoutEditor session wrapper + JSON dump
│   ├── drc_check.py             # DRC with LayoutEditor's drcTool from a JSON rule list
│   ├── check_connectivity.py    # raster netlist / isolation / release check (numpy + Pillow)
│   ├── render_preview.py        # PNG previews (matplotlib); headless screenshots are blank
│   └── find_layouteditor.sh     # locate LayoutEditor's bundled Python
├── examples/
│   ├── demo_chip.py             # SOI comb-actuator test chip using every technique
│   ├── demo_drc_rules.json      # starter SOI-MEMS rule set
│   ├── demo_probes.json         # pads + probe points for the demo
│   ├── demo_views.json          # zoom windows for the demo previews
│   └── run_demo.sh              # end-to-end pipeline
└── references/                  # loaded by the agent on demand
    ├── layoutscript-api.md      # verified API signatures and quirks
    ├── free-version-limits.md   # export gate measurements + compliant workarounds
    ├── geometry-techniques.md   # fillets, rings, holes, combs, text without booleans
    ├── mems-soi-process.md      # 4-mask SOI-MEMS conventions and default rules
    ├── verification.md          # DRC, connectivity, analytic checks, visual review
    └── troubleshooting.md       # symptom → cause → fix
```

## 6. Key facts (details in `references/`)

- 1 database unit = 1 nm. The helpers take µm.
- `strans.rotate()` is **clockwise**. `addCellrefArray` is reliable only for 1-D arrays.
- Headless screenshots are blank, so previews are rendered from a polygon dump.
- **Free license**: GDS export is refused (a cloud-only `.lec` is written instead) above roughly
  8–10k elements, **or after the boolean engine has been used in the session**. The skill draws
  final mask geometry without booleans ("drawn = kept" structural layer, keyhole field polygons,
  offset+clip trench rings). Please respect the license; do not launder boolean results into a
  fresh session.

## 7. Compatibility

| Item | Status |
|---|---|
| LayoutEditor 20260920, macOS universal (Apple Silicon), bundled Python 3.14 | fully verified |
| Linux / Windows | same LayoutScript API, expected to work; install paths unverified (use `LE_PY`) |
| Agents | any [Agent Skills](https://agentskills.io)-compatible agent; manual use via `SKILL.md` otherwise |

## Contributing

Measurements on other LayoutEditor versions and platforms are especially welcome (API behaviour,
install paths, license limits). Please include the release number and OS. Keep scripts
dependency-light and project-agnostic, and make sure `examples/run_demo.sh` still passes.

## License

[MIT](LICENSE) © 2026 laull9
