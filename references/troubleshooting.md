# Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: LayoutScript` | running system Python | use LayoutEditor's bundled interpreter (`scripts/find_layouteditor.sh`) |
| `ModuleNotFoundError: numpy/matplotlib/PIL` | running analysis scripts with LayoutEditor's Python | use a normal CPython with those packages |
| `.gds` missing, `.lec` written, console says "Feature disabled by license" | free-license export gate (booleans used, or > ~8–10k elements) | remove boolean/sizing calls from the generator; use hierarchy; see `free-version-limits.md` |
| geometry rotated the wrong way | `strans.rotate()` is clockwise | `t.rotate(-ang)` or `LE.ref(..., ang)` |
| second row of an array misplaced | `addCellrefArray` with `ny > 1` | 1-D arrays only |
| arrays missing after flattening | `cell.flatSelect()` skips arrays | `drawing.flatAll()` |
| text turned into polygons on note layers | `selectAll(); toPolygon()` | `drawing.pathSelect(); drawing.toPolygon()` |
| `saveScreenshot` produces a 3×3 image | headless rendering unsupported | `render_preview.py` |
| empty `noname` cell in GDS | default cell left unused | rename `drawing.currentCell` and use it as top |
| script prints nothing and exits 1 | native crash (bad argument types, wrong cell) | add prints and bisect; check that types are ints in dbu |
| `TypeError` / "Wrong number or type of arguments" | SWIG overload mismatch | the error lists the valid C++ prototypes; pass ints (dbu) and `point`/`pointArray` objects |
| loop variable overwrote a cell handle (e.g. `top`) | Python name reuse in long generators | use distinct names (`upper`, `side`) for loop variables |
| DRC flags every overlap | `mergeBefore=False` | merge before checking |
| DRC metal width failures at text | vector font spikes | `dot_text`, pitch ≥ min_width / 0.42 |
| DRC trench sliver at a ring end | ring clipped through a rounded corner | extend the island ≥ 2× corner radius into the open region |
| connectivity says everything is one net | raster bug or real short | Pillow bool arrays store True as 255: use `.astype(np.int8)`; then zoom on suspects |
| connectivity says a probe is `NOT_ON_CONDUCTOR` | probe placed in a gap | put probes at finger centres; compute positions from parameters |
| release check fails | a part sits entirely over the backside opening without a mechanical path to the substrate | add a tether/beam, or shrink the opening |
| design 10× smaller or larger after a unit change | `databaseunits` set without rescaling | `layout_prep.py normalize-dbu` |
| merge/DRC/dump says "requires 1 nm DBU" | source uses another database unit | `normalize-dbu` into a copy first |
| remap changed pins or fill too | bare layer key maps every datatype of that layer | use `"L/D"` pair keys |
| extraction merges every net | diffusion listed as a conductor, or fill datatype not ignored | stack poly/contact/metal only; add `ignore_datatypes` |
| extraction finds no devices | device layer names do not match, wells missing | `pdk_tool.py check`; names come from the technology file |
| `components.addLib` exits with a crash | not supported headless in the tested build | define devices in the technology file (`newComponent`) |
| frequency estimate far from FEM | wrong thickness, drawn instead of fabricated width, missing inertia (fingers, frame), wrong axis assignment | back-fit thickness; use target widths; integrate all moving parts; check which dimension is perpendicular to each axis |

## Multiple native sessions crash on macOS

In the tested 20260920 build, calling `project.newLayout()` a second time in a process crashes
in native initialization. Run one native session per process. `layout_prep.py` stages namespace
renaming in a subprocess, then imports into the single destination session.
