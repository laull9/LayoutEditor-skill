"""Assemble mixed dies on a circular wafer or rectangular reticle without overlaps.
Run with LayoutEditor Python: wafer_assembly.py config.json output.gds [report.txt]
Paths in the config are relative to the config file. Die coordinates are centered.
"""
import json
import math
from pathlib import Path
import sys

from le_helpers import LE, rect
from layout_prep import import_namespaced


def plan_placements(cfg):
    """Use a common slot size and a cyclic die pattern; reserve complete street margins."""
    dies = cfg.get('dies') or ([cfg['die']] if 'die' in cfg else [])
    if not dies:
        raise ValueError('At least one die is required')
    names = [d['name'] for d in dies]
    if len(set(names)) != len(names):
        raise ValueError('Die names must be unique')
    for d in dies:
        if min(float(d['width_um']), float(d['height_um'])) <= 0:
            raise ValueError('Die dimensions must be positive')
    street = float(cfg.get('dicing_street_width_um', 80))
    edge = float(cfg.get('edge_exclusion_mm', 3)) * 1000
    if street <= 0 or edge < 0:
        raise ValueError('Street must be positive; edge exclusion must be nonnegative')
    w = max(float(d['width_um']) for d in dies)
    h = max(float(d['height_um']) for d in dies)
    px, py = w + street, h + street
    mode = cfg.get('mode', 'wafer')
    if mode == 'reticle':
        fw, fh = [float(v) * 1000 for v in cfg['field_size_mm']]
        if min(fw, fh) <= 2 * edge:
            raise ValueError('Edge exclusion leaves no usable reticle area')
        bounds = [-fw / 2, -fh / 2, fw / 2, fh / 2]
        area = fw * fh
        usable = (fw - 2 * edge) * (fh - 2 * edge)
        def fits(x, y):
            return abs(x) + px / 2 <= fw / 2 - edge and abs(y) + py / 2 <= fh / 2 - edge
    elif mode == 'wafer':
        radius = float(cfg.get('wafer_diameter_mm', 100)) * 500
        if radius <= edge:
            raise ValueError('Edge exclusion leaves no usable wafer area')
        bounds = [-radius, -radius, radius, radius]
        area, usable = math.pi * radius ** 2, math.pi * (radius - edge) ** 2
        def fits(x, y):
            return all((x + sx * px / 2) ** 2 + (y + sy * py / 2) ** 2 <= (radius - edge) ** 2
                       for sx in (-1, 1) for sy in (-1, 1))
    else:
        raise ValueError('mode must be wafer or reticle')
    pattern = cfg.get('pattern', names)
    if not pattern or any(n not in names for n in pattern):
        raise ValueError('pattern must contain known die names')
    placements = []
    nx, ny = int(bounds[2] / px), int(bounds[3] / py)
    for iy in range(-ny, ny + 1):
        for ix in range(-nx, nx + 1):
            x, y = ix * px, iy * py
            if fits(x, y):
                placements.append({'die': pattern[(ix + iy) % len(pattern)], 'center_um': [x, y]})
    if not placements:
        raise ValueError('No die fits with the requested margins')
    return {'placements': placements, 'slot_um': [w, h], 'pitch_um': [px, py],
            'bounds_um': bounds, 'gross_area_um2': area, 'usable_area_um2': usable}


def assemble_wafer(config_path, out_gds, report_path=None):
    config_path = Path(config_path).resolve()
    cfg = json.loads(config_path.read_text())
    plan = plan_placements(cfg)
    dies = cfg.get('dies') or [cfg['die']]
    le = LE(top=cfg.get('title', 'ASSEMBLY'), layers={
        11: ('FIELD_BOUNDARY_REF', (100, 100, 100)),
        21: ('DICING_STREET', (200, 205, 210)),
        22: ('ALIGNMENT', (215, 65, 65)),
        1: ('METAL', (220, 165, 40)), 2: ('CONTACT_OPEN', (40, 140, 210)),
        3: ('CHANNEL', (40, 175, 150)), 4: ('PORT_OPEN', (160, 90, 185)),
        12: ('NOTE', (70, 70, 70))})
    top = le.top
    x0, y0, x1, y1 = plan['bounds_um']
    boundary_layer = int(cfg.get('wafer_boundary_layer', 11))
    if cfg.get('mode', 'wafer') == 'reticle':
        le.poly(top, rect(x0, y0, x1, y1), boundary_layer)
    else:
        r = x1
        le.poly(top, [(r * math.cos(i * 2 * math.pi / 360), r * math.sin(i * 2 * math.pi / 360))
                      for i in range(360)], boundary_layer)
    cells = {}
    for d in dies:
        path = d.get('gds_path')
        if not path:
            raise ValueError('Provide an actual GDS source for ' + d['name'])
        path = (config_path.parent / path).resolve()
        c = import_namespaced(le.dr, str(path), d['name'] + '_', d.get('cell_name'))
        # Measure the selected hierarchy at the origin, before any placement.
        probe = le.cell('_FIT_' + d['name'])
        ref = le.ref(probe, c, 0, 0)
        b = ref.getBoundingBox()
        hw, hh = float(d['width_um']) / 2, float(d['height_um']) / 2
        if b.left() / 1000 < -hw - .001 or b.right() / 1000 > hw + .001 or \
                b.bottom() / 1000 < -hh - .001 or b.top() / 1000 > hh + .001:
            raise ValueError('Source geometry exceeds centered die dimensions: ' + d['name'])
        le.dr.deleteCell(probe)
        cells[d['name']] = c
    w, h = plan['slot_um']
    px, py = plan['pitch_um']
    street_layer = int(cfg.get('street_layer', 21))
    mark_layer = int(cfg.get('mark_layer', 22))
    streets = le.cell('SLOT_STREETS')
    for box in [rect(-px / 2, -py / 2, -w / 2, py / 2),
                rect(w / 2, -py / 2, px / 2, py / 2),
                rect(-w / 2, -py / 2, w / 2, -h / 2),
                rect(-w / 2, h / 2, w / 2, py / 2)]:
        le.poly(streets, box, street_layer)
    marks = set()
    for p in plan['placements']:
        x, y = p['center_um']
        le.ref(top, cells[p['die']], x, y)
        le.ref(top, streets, x, y)
        le.text(top, 12, x - w / 2 + 40, y + h / 2 - 100, p['die'])
        for sx in (-1, 1):
            for sy in (-1, 1):
                marks.add((round(x + sx * px / 2, 6), round(y + sy * py / 2, 6)))
    span = min(40, float(cfg.get('dicing_street_width_um', 80)) * .6)
    for x, y in sorted(marks):
        le.poly(top, rect(x - span / 2, y - 1.5, x + span / 2, y + 1.5), mark_layer)
        le.poly(top, rect(x - 1.5, y - span / 2, x + 1.5, y + span / 2), mark_layer)
    out = Path(out_gds).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    le.save_gds(str(out))
    counts = {d['name']: sum(p['die'] == d['name'] for p in plan['placements']) for d in dies}
    die_area = sum(counts[d['name']] * d['width_um'] * d['height_um'] for d in dies)
    report = dict(plan, title=top.cellName, mode=cfg.get('mode', 'wafer'), counts=counts,
                  total_dies=len(plan['placements']), utilization_pct=100 * die_area / plan['gross_area_um2'])
    out.with_suffix('.report.json').write_text(json.dumps(report, indent=2))
    le.dump_flat_json(str(out.with_suffix('.polys.json')), meta=report)
    text = '%s assembly: %s\nPlaced dies: %d\nCounts: %s\nDie area / gross field area: %.2f%%\n' % (
        report['mode'], report['title'], report['total_dies'], counts, report['utilization_pct'])
    if report_path:
        Path(report_path).write_text(text)
    print(text)
    return report


if __name__ == '__main__':
    assemble_wafer(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
