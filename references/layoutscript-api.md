# LayoutScript Python API — verified notes

The `LayoutScript` SWIG module ships without docstrings. Everything below was verified by experiment
(LayoutEditor release 20260920, macOS universal build, bundled Python 3.14, free license, headless),
cross-checked with the official documentation at <https://layouteditor.org> (LayoutScript → API).
Signatures can be discovered by calling a method with wrong arguments: the SWIG error lists the
C++ prototypes.

## Session

```python
from LayoutScript import *          # project, point, pointArray, strans, layers, ...
L   = project.newLayout()           # headless layout (no GUI); in-GUI macros use project.currentLayout()
dr  = L.drawing                     # drawingField: design-wide operations
top = dr.currentCell                # default cell named "noname"
top.cellName = "MY_TOP"             # rename and reuse it, otherwise an empty "noname" ends up in the GDS
```

| Property | Value | Meaning |
|---|---|---|
| `dr.databaseunits` | `1e-09` | 1 dbu = 1 nm. All integer coordinates are in dbu |
| `dr.userunits` | `0.001` | display unit µm |

Files: `L.open(path)` (gds/oas/dxf/cif/…), `dr.saveFile(path)` (format from the extension).
**Always check that the output exists**: a license refusal writes `<name>.lec` instead and
raises no exception.

## Cells and references

```python
c = dr.addCell().thisCell; c.cellName = "UNIT"     # addCell() returns a cellList node
dr.setCell(c)                                      # current cell (needed by drawingField/boolean/DRC ops)
dr.findCell("UNIT")                                # cell or None
e = parent.addCellref(child, point(x, y))          # returns element
t = strans(); t.rotate(-90); e.setTrans(t)         # rotate(a) is CLOCKWISE  →  -90 means +90° CCW
e.getTrans().getAngle()                            # CCW angle (90.0 here)
parent.addCellrefArray(child, point(x0, y0), point(x0 + dx, y0), nx, 1)   # 2nd point = origin + pitch
```

- `addCellrefArray(cell, point, point, nx, ny)`: with `ny > 1` the second row lands at an absolute
  y equal to the pitch, ignoring the origin. Use `ny = 1` and place rows separately.
- Other overload: `addCellrefArray(cell, pointArray, nx, ny)` (GDS AREF style).
- Mirroring: `strans.setMirror_x()`, `toggleMirror_x()`, `clearMirror_x()`. Unit cells symmetric
  about their own axis avoid the need for mirroring.
- `strans.scale(d)` exists. Avoid scaled refs in mask data.

## Shapes (integer dbu coordinates)

```python
pa = pointArray(); pa.attach(x, y)                 # also: attachPoint(point), size(), point(i)
c.addPolygon(pa, layer)
c.addPath(pa, layer)          ; c.addPath(pa, layer, width)      # flat caps; closed = repeat 1st point
c.addBox(x, y, w, h, layer)                        # (x, y, WIDTH, HEIGHT) — stored as a 2-point box
c.addRoundedBox(x, y, w, h, r, layer)  ; c.addChamferedBox(x, y, w, h, chamfer, layer)
c.addCircle(layer, point(cx, cy), radius[, n])     ; c.addCircle(layer, p_center, p_on_circle[, n])
c.addEllipse(layer, point(cx, cy), rx, ry)
c.addPolygonArc(point(cx, cy), r_in, r_out, a0, a1, layer)
c.addText(layer, point(x, y), "txt").setWidth(height_dbu)
```

- Polygons with holes: one **keyhole** polygon (outer loop → zero-width bridge → inner loop
  reversed → back). It is accepted by LayoutEditor, GDS and mask shops.
- For uniform post-processing, prefer `addPolygon` with your own arc points over
  boxes and circles (boxes dump as 2 points; circles as centre and radius data).
- GDS polygons are limited to 8191 vertices. A 1°-step circle (360 pts) is plenty.

## Selection, conversion and flattening (current cell)

```python
c.selectAll(); c.deselectAll(); c.selectLayer(lay); c.deleteSelect()
dr.flatAll()                     # flatten SELECTED refs and arrays recursively
dr.pathSelect(); dr.toPolygon()  # convert only paths (selectAll + toPolygon would also polygonise text)
dr.activeLayer = 2; dr.clearPoints(); dr.point(x, y); dr.text("ABC")   # drawingField-style drawing
```

`cell.flatSelect()` flattens refs but not arrays. New elements are prepended, so
`cell.firstElement.thisElement` is the newest element.

## Reading geometry

```python
el = c.firstElement
while el:
    e = el.thisElement
    if e is not None:
        e.layerNum, e.isPolygon(), e.isPath(), e.isBox(), e.isText(), e.isCellref(), e.isCellrefArray()
        pa = e.getPoints()               # polygon: closed list; box: 2 corners; path: centre line
        e.getWidth(); e.getName()        # path width / text string
    el = el.nextElement
cl = dr.firstCell                        # iterate cells: cl.thisCell, cl.nextCell
```

## Layers

```python
layers.num(3).name = "SI"
layers.num(3).setColor(40, 140, 230)
layers.findLayer("SI")                   # → number
```

On GDS import (default `setup.gdsAutoMapDatatypes = False`) `e.layerNum` is the GDS layer and
`e.datatype` the datatype (texttype for texts). Both are writable. Cell references also carry a
`layerNum`; ignore it. Layer names, colours, technology layers, DRC and extraction work per layer
number, across all datatypes of that number.

## Units

```python
dr.databaseunits        # metres per dbu, e.g. 1e-9; dr.userunits = dbu / display unit (0.001 for µm)
dr.databaseunits = 1e-9 # reinterprets the integers: geometry scales physically. Do not use alone.
cell.resize(f)          # scales one cell: shapes, path widths, ref origins, array pitches, text size
```

Normalize = `resize(old/new)` on every cell, then set `databaseunits` and `userunits = new·1e6`
(`layout_prep.py normalize-dbu`). `drawingField.scale(...)` is a view zoom, not geometry.

## Extraction and netlists

```python
layers.technologyLayerRemoveAll()
layers.technologyLayerAdd(num, 2)                  # 2 = conductor, 1 = via
layers.technologyLayerSetParameter(num, 0, level)  # 0: level; conductor N, via N+1, conductor N+2
setup.addNetlistNotUseDatatype(22)                 # leave a datatype out of connectivity
c = components.newComponent("nmos", "mylib")       # works headless; addLib()/getLibs() crash
c.extractionMethod = "MOS-default"
c.extractionParameter = "layerPoly=poly\nlayerActive=active\nlayerContact=contact\nports=S,D,G"
L.extractionTool.extractComponent("nmos", "mylib") # replaces devices by <cell>#M1 refs
nt = L.netlistTool; nt.buildConnect(); nt.extractNetList()
n = nt.getExtractedNetList(cellname)               # netList
n.getNodes()                                       # stringList of net names (Node_<i> if unlabelled)
n.getNode(name) -> index; d = n.getDevice(i); d.devicename; d.cellname
d.getConnectionNames(); d.getNode(port) -> net index
e.getPropertyString(10 | 20 | 30)                  # on device refs: device, component, library
nt.extractedNetlistSave(path, 0)                   # LayoutEditor dump format
```

Extraction parameters name layers by `layers.num(n).name`. Text labels on stack conductors name
nets. See [extraction and LVS](extraction-lvs.md) for verified behaviour and limits.

## Sizing and booleans (read-only use only on the free license)

```python
dr.sizeLayer(layer, size_dbu, type=0)               # whole design, in place
dr.copyLayerSized(src, dst, size_dbu, type)         # flattened sized copy; type 0 = miter corners
L.booleanTool.boolOnLayer(layerA, layerB, layerOut, "A-B")   # current cell; results as keyhole polygons
```

They work correctly, but see `free-version-limits.md`: after their use the session can no longer
export GDS on the free license. Use them only in analysis sessions that never save.

## DRC — `L.drcTool` (works on the free license)

```python
dc = L.drcTool
dc.setCheckCell()                                    # whole current cell
dc.ruleName = "R1 metal width"                       # label for the log
dc.minimumSize(size, layer, mergeBefore=False, sharpAngles=True)
dc.minimumElementDistance(dist, layer, mergeBefore=False)
dc.minimumDistance(dist, layer1, layer2)
dc.minimumEnclosure(dist, outer_layer, inner_layer)
dc.inside(dist, insideLayer, layer1, layer2=-1, layer3=-1)
dc.minimumNotchOnLayer(size, layer, mergeBefore=False, testSlots=False)
dc.noSelfintersectionOnLayer(layer)
dc.errorCount                                        # cumulative → diff before/after each rule
dc.result                                            # text log, one line per rule
dc.getViolationPoint1(i), dc.getViolationPoint2(i)   # dbu points of violation i
dc.getViolationValue(i)                              # measured value (µm in the tested version)
```

Run it on a flattened temporary cell with paths converted to polygons. Pass `mergeBefore=True`
whenever a feature is built from overlapping polygons; otherwise every overlap seam is reported.

## Other

- `L.saveScreenshot(f)` / `dr.saveScreenshot(f)`: blank 3×3 PNG when headless.
- `process.isMac()`, `process.getEnv(name)`, `process.startPythonScript(file, args)` exist for
  GUI macro integration.
- Native crashes can exit silently with code 1 and no output. Bisect with prints if a script
  "does nothing".
