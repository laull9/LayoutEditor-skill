"""Exercise negative cases and transforms against the installed native API.
Usage: python tests/test_native_contracts.py /tmp/layout-skill-examples
"""
import copy
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import gdstk
import numpy as np

REPO = Path(__file__).resolve().parents[1]
ROOT = Path(sys.argv.pop(1)).resolve()
LE_PY = os.environ.get('LE_PY') or subprocess.check_output([str(REPO / 'scripts/find_layouteditor.sh')], text=True).strip()
sys.path.insert(0, str(REPO / 'scripts'))
from wafer_assembly import plan_placements


class NativeContracts(unittest.TestCase):
    def run_tool(self, script, args):
        return subprocess.run([LE_PY, str(REPO / 'scripts' / script)] + [str(a) for a in args],
                              text=True, capture_output=True)

    def test_rotation_and_inspection(self):
        with tempfile.TemporaryDirectory() as out:
            out = Path(out)
            spec = out / 'merge.json'
            spec.write_text(json.dumps([{'path': str(ROOT / 'prep/kelvin.gds'), 'cell': 'TOP',
                                         'prefix': 'ROT_', 'offset': [2000, 1000], 'angle': 90}]))
            result = self.run_tool('layout_prep.py', ['merge', spec, out / 'rot.gds', 'ROTATED'])
            self.assertEqual(result.returncode, 0, result.stderr)
            cell = gdstk.read_gds(str(out / 'rot.gds')).top_level()[0]
            np.testing.assert_allclose(cell.bounding_box(), ((1500, 300), (2500, 1700)), atol=.001)
            result = self.run_tool('layout_prep.py', ['inspect', out / 'rot.gds', '--json'])
            self.assertEqual(result.returncode, 0, result.stderr)
            np.testing.assert_allclose(json.loads(result.stdout)['bbox_um'], (1500, 300, 2500, 1700), atol=.001)

    def test_collision_and_missing_top_fail(self):
        with tempfile.TemporaryDirectory() as out:
            out = Path(out)
            item = {'path': str(ROOT / 'prep/kelvin.gds'), 'cell': 'TOP', 'prefix': 'X_'}
            for spec in ([item, item], [dict(item, cell='MISSING')]):
                (out / 'spec.json').write_text(json.dumps(spec))
                result = self.run_tool('layout_prep.py', ['merge', out / 'spec.json', out / 'bad.gds'])
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((out / 'bad.gds').exists())

    def test_missing_source_and_oversize_fail(self):
        cfg = json.loads((REPO / 'examples/wafer_assembly/wafer_config.json').read_text())
        for d, kind in zip(cfg['dies'], ('resistor', 'mixer')):
            d['gds_path'] = str(ROOT / 'assembly/inputs' / (kind + '.gds'))
        bad_configs = [copy.deepcopy(cfg), copy.deepcopy(cfg)]
        bad_configs[0]['dies'][0]['gds_path'] = '/missing/source.gds'
        bad_configs[1]['dies'][0]['width_um'] = 2000
        with tempfile.TemporaryDirectory() as out:
            out = Path(out)
            for bad in bad_configs:
                (out / 'config.json').write_text(json.dumps(bad))
                result = self.run_tool('wafer_assembly.py', [out / 'config.json', out / 'bad.gds'])
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((out / 'bad.gds').exists())

    def test_circular_wafer_and_mixed_sizes(self):
        cfg = {'mode': 'wafer', 'wafer_diameter_mm': 26, 'edge_exclusion_mm': 1,
               'dicing_street_width_um': 100, 'dies': [
                   {'name': 'A', 'width_um': 3000, 'height_um': 2000},
                   {'name': 'B', 'width_um': 1800, 'height_um': 1600}]}
        plan = plan_placements(cfg)
        self.assertGreater(len(plan['placements']), 1)
        self.assertEqual(set(p['die'] for p in plan['placements']), {'A', 'B'})
        for p in plan['placements']:
            x, y = p['center_um']
            for sx in (-1, 1):
                for sy in (-1, 1):
                    self.assertLessEqual(math.hypot(x + sx * 1550, y + sy * 1050), 12000)
        for patch in ({'dicing_street_width_um': -1}, {'edge_exclusion_mm': 14}, {'pattern': ['UNKNOWN']}):
            with self.assertRaises(ValueError):
                plan_placements(dict(cfg, **patch))

    def test_layer_datatype_inspect_and_pair_remap(self):
        with tempfile.TemporaryDirectory() as out:
            out = Path(out)
            lib = gdstk.Library(unit=1e-6, precision=1e-9)
            top, sub = lib.new_cell('TOP'), lib.new_cell('SUB')
            sub.add(gdstk.rectangle((0, 0), (10, 10), layer=5))
            top.add(gdstk.rectangle((0, 0), (100, 10), layer=1, datatype=0),
                    gdstk.rectangle((0, 20), (100, 30), layer=1, datatype=2),
                    gdstk.rectangle((0, 40), (100, 50), layer=2, datatype=7),
                    gdstk.Label('PIN', (5, 5), layer=1, texttype=3), gdstk.Reference(sub, (200, 0)))
            lib.write_gds(str(out / 'src.gds'))
            result = self.run_tool('layout_prep.py', ['inspect', out / 'src.gds', '--json'])
            self.assertEqual(result.returncode, 0, result.stderr)
            info = json.loads(result.stdout)
            self.assertEqual({k: v['total'] for k, v in info['layer_datatypes'].items()},
                             {'1/0': 1, '1/2': 1, '1/3': 1, '2/7': 1, '5/0': 1})
            self.assertEqual(info['references']['cellrefs'], 1)
            self.assertEqual(info['top_cells'], ['TOP'])
            (out / 'map.json').write_text(json.dumps({'1/2': '11/0', '2': 20}))
            result = self.run_tool('layout_prep.py', ['remap', out / 'src.gds', out / 'src.gds', out / 'map.json',
                                                      '--drop-unmapped'])
            self.assertEqual(result.returncode, 0, result.stderr)
            cells = {c.name: c for c in gdstk.read_gds(str(out / 'src.gds')).cells}
            pairs = sorted((p.layer, p.datatype) for p in cells['TOP'].polygons)
            self.assertEqual(pairs, [(11, 0), (20, 7)])
            self.assertEqual([r.cell_name for r in cells['TOP'].references], ['SUB'])
            self.assertFalse(list(out.glob('.*tmp*')))

    def test_normalize_dbu(self):
        with tempfile.TemporaryDirectory() as out:
            out = Path(out)
            lib = gdstk.Library(unit=1e-6, precision=1e-8)
            top, sub = lib.new_cell('TOP'), lib.new_cell('SUB')
            sub.add(gdstk.rectangle((0, 0), (10, 10), layer=5))
            top.add(gdstk.rectangle((0, 0), (100, 10), layer=1),
                    gdstk.FlexPath([(0, 60), (100, 60)], 2, layer=1, simple_path=True),
                    gdstk.Reference(sub, (200, 0), columns=3, rows=2, spacing=(20, 30)))
            lib.write_gds(str(out / 'coarse.gds'))
            result = self.run_tool('layout_prep.py', ['normalize-dbu', out / 'coarse.gds', out / 'fine.gds'])
            self.assertEqual(result.returncode, 0, result.stderr)
            fine = gdstk.read_gds(str(out / 'fine.gds'))
            self.assertAlmostEqual(fine.precision, 1e-9)
            a = [c for c in lib.cells if c.name == 'TOP'][0]
            b = [c for c in fine.cells if c.name == 'TOP'][0]
            np.testing.assert_allclose(a.bounding_box(), b.bounding_box(), atol=.001)
            self.assertAlmostEqual(b.paths[0].widths()[0][0], 2, places=3)
            result = self.run_tool('layout_prep.py', ['normalize-dbu', out / 'fine.gds', out / 'bad.gds', '--dbu', '1e-8'])
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((out / 'bad.gds').exists())

    def test_audit_against_technology(self):
        tech = REPO / 'examples/cmos_lvs/cmos_tech.json'
        with tempfile.TemporaryDirectory() as out:
            out = Path(out)
            lib = gdstk.Library(unit=1e-6, precision=1e-9)
            top = lib.new_cell('TOP')
            top.add(gdstk.rectangle((0, 0), (10, 10), layer=6), gdstk.rectangle((0, 0), (10.25, 10), layer=6),
                    gdstk.rectangle((0, 0), (5, 5), layer=9, datatype=1))
            lib.write_gds(str(out / 'a.gds'))
            result = self.run_tool('layout_prep.py', ['audit', out / 'a.gds', tech, '--json'])
            self.assertEqual(result.returncode, 1)
            res = json.loads(result.stdout)
            self.assertEqual(res['undeclared_pairs'], {'9/1': 1})
            self.assertEqual(res['off_grid_points'], 2)

    def test_extraction_ignores_fill_datatype(self):
        tech = json.loads((REPO / 'examples/cmos_lvs/cmos_tech.json').read_text())
        with tempfile.TemporaryDirectory() as out:
            out = Path(out)
            lib = gdstk.Library(unit=1e-6, precision=1e-9)
            top = lib.new_cell('TOP')
            top.add(gdstk.rectangle((0, 0), (100, 10), layer=6), gdstk.rectangle((0, 30), (100, 40), layer=6),
                    gdstk.rectangle((40, 0), (50, 40), layer=6, datatype=22),
                    gdstk.Label('A', (5, 5), layer=6, texttype=2), gdstk.Label('B', (5, 35), layer=6, texttype=2))
            lib.write_gds(str(out / 'fill.gds'))
            nets = {}
            for name, ignore in (('ignored', [22]), ('connected', [])):
                tech['connectivity']['ignore_datatypes'] = ignore
                (out / (name + '.json')).write_text(json.dumps(tech))
                result = self.run_tool('extract_netlist.py', [out / 'fill.gds', out / (name + '.json'), out / (name + '_n.json')])
                self.assertEqual(result.returncode, 0, result.stderr)
                nets[name] = sorted(json.loads((out / (name + '_n.json')).read_text())['nets'])
            self.assertEqual(nets['ignored'], ['A', 'B'])
            self.assertEqual(len(nets['connected']), 1)

    def test_lvs_compare_reference_forms(self):
        sys.path.insert(0, str(REPO / 'scripts'))
        from tech import Tech
        import lvs_compare
        tech = Tech.load(REPO / 'examples/cmos_lvs/cmos_tech.json')
        layout = lvs_compare.Circuit('INV', [
            {'name': 'M7', 'component': 'pmos', 'pins': {'G': 'IN', 'D': 'VDD', 'S': 'OUT'}},
            {'name': 'M9', 'component': 'nmos', 'pins': {'G': 'IN', 'D': 'OUT', 'S': 'VSS'}}],
            unnamed=__import__('re').compile(r'^Node_-?\d+$'))
        spice = """* hierarchical reference with bulk pins and a continuation line
.subckt half a y s b
MX y a s b
+ nmos W=1u L=1u
.ends
.subckt INV IN OUT VDD VSS
MP OUT IN VDD VDD pmos
XN IN OUT VSS VSS half
.ends
"""
        ref, _ = lvs_compare.parse_spice(spice, tech, 'INV')
        self.assertEqual(len(ref.devices), 2)
        passed, lines, _ = lvs_compare.compare(layout, ref, tech)
        self.assertTrue(passed, lines)
        swapped = spice.replace('MP OUT IN VDD VDD pmos', 'MP OUT VDD IN VDD pmos')
        ref, _ = lvs_compare.parse_spice(swapped, tech, 'INV')
        self.assertFalse(lvs_compare.compare(layout, ref, tech)[0])


if __name__ == '__main__':
    unittest.main()
