"""Independently read emitted GDS/OASIS with gdstk (verification dependency only).
Usage: python tests/check_example_outputs.py /tmp/layout-skill-v03
"""
import itertools
import json
from pathlib import Path
import sys
import unittest

import gdstk
import numpy as np

ROOT = Path(sys.argv.pop(1)).resolve() if len(sys.argv) > 1 else Path('/tmp/layout-skill-v03')


def cells(path):
    return {c.name: c for c in gdstk.read_gds(str(path)).cells}


def area_by_layer(cell):
    result = {}
    for p in cell.get_polygons():
        key = (p.layer, p.datatype)
        result[key] = result.get(key, 0) + p.area()
    return result


def centerline(points):
    points = np.asarray(points)
    n = len(points) // 2
    return (points[:n] + points[n:][::-1]) / 2


def length(points):
    return np.linalg.norm(np.diff(points, axis=0), axis=1).sum()


class Outputs(unittest.TestCase):
    def test_conversion_roundtrip(self):
        source = cells(ROOT / 'prep/kelvin.gds')['TOP']
        oasis = {c.name: c for c in gdstk.read_oas(str(ROOT / 'prep/converted.oas')).cells}['TOP']
        self.assertEqual(area_by_layer(source), area_by_layer(oasis))
        np.testing.assert_allclose(source.bounding_box(), oasis.bounding_box(), atol=.001)
        self.assertGreater((ROOT / 'prep/converted.dxf').stat().st_size, 100)

    def test_remapping_and_namespaces(self):
        src = area_by_layer(cells(ROOT / 'prep/kelvin.gds')['TOP'])
        remap = area_by_layer(cells(ROOT / 'prep/remapped.gds')['TOP'])
        self.assertEqual({({1: 101, 2: 102}.get(l, l), d): a for (l, d), a in src.items()}, remap)
        merged = cells(ROOT / 'prep/dual_merged.gds')
        self.assertTrue({'K_TOP', 'K_PAD', 'LS_TOP', 'LS_PAD', 'PREP_COUPONS'} <= merged.keys())
        refs = merged['PREP_COUPONS'].references
        self.assertEqual({r.cell_name for r in refs}, {'K_TOP', 'LS_TOP'})
        np.testing.assert_allclose(merged['PREP_COUPONS'].bounding_box(), ((-1550, -500), (1550, 500)))

    def test_reticle_placement_and_streets(self):
        c = cells(ROOT / 'assembly/reticle_assembly.gds')['MIXED_RETICLE']
        refs = [r for r in c.references if r.cell_name in ('RES_DIE', 'FLUID_DIE')]
        self.assertEqual(len(refs), 25)
        self.assertEqual(sum(r.cell_name == 'RES_DIE' for r in refs), 13)
        boxes = [np.array(r.bounding_box()) for r in refs]
        for box in boxes:
            self.assertGreaterEqual(box[0, 0], -7800)
            self.assertLessEqual(box[1, 0], 7800)
            self.assertGreaterEqual(box[0, 1], -5800)
            self.assertLessEqual(box[1, 1], 5800)
        for a, b in itertools.combinations(boxes, 2):
            separation = np.maximum(b[0] - a[1], a[0] - b[1])
            self.assertGreaterEqual(max(separation), 100 - .001)
        street = [p for p in c.get_polygons() if p.layer == 21]
        self.assertTrue(street)
        for r in refs:
            center = tuple(r.origin)
            self.assertFalse(any(gdstk.inside([center], [p])[0] for p in street))
        report = json.loads((ROOT / 'assembly/reticle_assembly.report.json').read_text())
        self.assertEqual(report['total_dies'], len(refs))
        self.assertAlmostEqual(report['utilization_pct'], 78.125)

    def test_pic_continuity_and_gap(self):
        all_cells = cells(ROOT / 'pic/pic_chip.gds')
        full = all_cells['PIC_DEMO_CHIP'].get_polygons()
        for polygon in full:
            if polygon.layer in (1, 2):
                box = polygon.bounding_box()
                self.assertGreaterEqual(min(box[0]), 0)
                self.assertLessEqual(box[1][0], 2000)
                self.assertLessEqual(box[1][1], 1500)
        core = [p for p in full if p.layer == 1]
        joined = gdstk.boolean(core, [], 'or', precision=.001)
        # Upper MZI, lower MZI, ring bus, isolated ring, stand-alone Euler coupon.
        self.assertEqual(len(joined), 5)
        def component(point):
            matches = [i for i, p in enumerate(joined) if gdstk.inside([point], [p])[0]]
            self.assertEqual(len(matches), 1)
            return matches[0]
        upper = component((250, 1015.35))
        lower = component((250, 984.65))
        self.assertEqual(upper, component((950, 1015.35)))
        self.assertEqual(lower, component((950, 984.65)))
        self.assertNotEqual(upper, lower)
        self.assertEqual(component((250, 500)), component((950, 500)))
        ring = all_cells['RING_30UM'].polygons
        bus, loop = sorted(ring, key=lambda p: len(p.points))
        gap = loop.bounding_box()[0][1] - bus.bounding_box()[1][1]
        self.assertAlmostEqual(gap, .2, places=3)
        gc = all_cells['GC_220']
        self.assertEqual(sum(p.layer == 2 for p in gc.polygons), 25)
        core_gc = [p for p in gc.polygons if p.layer == 1]
        for p in gc.polygons:
            if p.layer == 2:
                self.assertFalse(gdstk.boolean([p], core_gc, 'not', precision=.001))

    def test_drawn_mzi_length(self):
        mzi = cells(ROOT / 'pic/pic_chip.gds')['MZI_FILTER']
        curves = [p for p in mzi.polygons if len(p.points) > 4]
        self.assertEqual(len(curves), 2)
        drawn_difference = sum((length(np.vstack([p.points, p.points[0]])) - 1.0) / 2
                               for p in curves) - 50
        self.assertAlmostEqual(drawn_difference, 40, delta=.01)

    def test_euler_drawn_radius(self):
        bend = cells(ROOT / 'pic/pic_chip.gds')['EULER_BEND_COUPON'].polygons[0]
        points = bend.points
        # GDS export removes collinear vertices and rotates vertex order. Measure
        # each offset boundary independently instead of assuming paired indices.
        caps = [i for i in range(len(points))
                if abs(np.linalg.norm(points[(i + 1) % len(points)] - points[i]) - .5) < .002]
        self.assertEqual(len(caps), 2)
        a, b = caps
        sides = [points[a + 1:b + 1], np.vstack([points[b + 1:], points[:a + 1]])]
        radii = []
        for side in sides:
            local = []
            for i in range(3, len(side) - 3):
                q = side[i - 3:i + 4]
                q = q - q.mean(axis=0)
                fit = np.linalg.lstsq(np.column_stack([2 * q[:, 0], 2 * q[:, 1], np.ones(len(q))]),
                                      np.sum(q * q, axis=1), rcond=None)[0]
                local.append(np.sqrt(fit[2] + sum(fit[:2] ** 2)))
            radii.append(min(local))
        self.assertAlmostEqual(sum(radii) / 2, 15, delta=.5)
        # Flat input cap and vertical output cap enforce the 90-degree turn.
        self.assertAlmostEqual(points[0, 0], points[1, 0], places=3)
        self.assertAlmostEqual(points[b, 1], points[b + 1, 1], places=3)

    def test_lvs_example(self):
        lib = gdstk.read_gds(str(ROOT / 'lvs/nand2_good.gds'))
        top = {c.name: c for c in lib.cells}['NAND2']
        labels = {l.text: (l.layer, l.texttype) for l in top.labels if len(l.text) < 5}
        self.assertEqual(labels, {'A': (6, 2), 'B': (6, 2), 'VDD': (6, 2), 'VSS': (6, 2), 'Y': (8, 2)})
        self.assertEqual(sum(p.layer == 7 for p in top.polygons), 2)
        results = {v: json.loads((ROOT / ('lvs/lvs_%s.json' % v)).read_text())['result'] for v in ('good', 'short', 'open')}
        self.assertEqual(results, {'good': 'PASS', 'short': 'FAIL', 'open': 'FAIL'})
        good = json.loads((ROOT / 'lvs/nand2_good_netlist.json').read_text())
        self.assertEqual(sorted(d['component'] for d in good['devices']), ['nmos', 'nmos', 'pmos', 'pmos'])
        self.assertEqual(len(good['nets']), 6)
        short = json.loads((ROOT / 'lvs/nand2_short_netlist.json').read_text())
        self.assertEqual(len(short['nets']), 5)
        opened = gdstk.read_gds(str(ROOT / 'lvs/nand2_open.gds'))
        self.assertEqual(sum(p.layer == 7 for c in opened.cells if c.name == 'NAND2' for p in c.polygons), 1)



if __name__ == '__main__':
    unittest.main()
