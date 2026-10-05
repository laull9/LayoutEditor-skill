"""Run every example, independently check GDS results, and rebuild all README PNGs.
Usage (analysis Python with numpy/Pillow/matplotlib/gdstk):
  python scripts/update_assets.py /tmp/layout-skill-examples
LE_PY may override the LayoutEditor interpreter. Booleans are not required.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont
from matplotlib.font_manager import findfont
from create_showcase_grid import create_grid

REPO = Path(__file__).resolve().parents[1]


def text_image(text, path):
    font = ImageFont.truetype(findfont('DejaVu Sans Mono'), 17)
    lines = text.splitlines()
    width = max(1100, 24 * 2 + 11 * max(len(line) for line in lines))
    image = Image.new('RGB', (width, len(lines) * 25 + 48), '#f8fafc')
    draw = ImageDraw.Draw(image)
    for i, line in enumerate(lines):
        draw.text((24, 24 + 25 * i), line, font=font, fill='#203447')
    image.save(path, optimize=True)


def update(out):
    out = Path(out).resolve()
    env = dict(os.environ, PYTHON=sys.executable)
    runs = [('mask_prep/run_prep_demo.sh', 'prep'), ('photonic_circuit/run_pic_demo.sh', 'pic'),
            ('wafer_assembly/run_assembly.sh', 'assembly'), ('mems_comb_drive/run_mems.sh', 'mems'),
            ('cmos_lvs/run_lvs_demo.sh', 'lvs')]
    for script, folder in runs:
        subprocess.run(['bash', str(REPO / 'examples' / script), str(out / folder)], env=env, check=True)
    subprocess.run([sys.executable, str(REPO / 'tests/check_example_outputs.py'), str(out)], check=True)
    subprocess.run([sys.executable, str(REPO / 'tests/test_native_contracts.py'), str(out)], check=True)
    assets = REPO / 'assets'
    copies = {
        'prep_coupons.png': 'prep/preview/51_view_coupons.png',
        'pic_overview.png': 'pic/preview/51_view_overview_circuits.png',
        'pic_mzi_filter.png': 'pic/preview/52_view_mzi_filter.png',
        'pic_ring_coupler.png': 'pic/preview/53_view_ring_coupler.png',
        'pic_grating_detail.png': 'pic/preview/54_view_grating_detail.png',
        'wafer_assembly.png': 'assembly/preview/00_overview.png',
        'assembly_die_detail.png': 'assembly/preview/51_view_mixed_dies.png',
        'demo_core_overview.png': 'mems/preview/51_view_core.png',
        'demo_comb_detail.png': 'mems/preview/52_view_comb.png',
        'demo_flexure_fillet.png': 'mems/preview/53_view_flexure_root.png',
        'lvs_nand2.png': 'lvs/preview/51_view_nand2.png',
    }
    for name, source in copies.items():
        shutil.copyfile(out / source, assets / name)
    # Render the current MEMS reports, so the verification image cannot go stale.
    report = (out / 'mems/drc_report.txt').read_text().split('---- raw')[0].strip()
    report += '\n\n' + (out / 'mems/connectivity_report.txt').read_text().strip()
    text_image(report, assets / 'demo_verification.png')
    lvs = '\n\n'.join('[%s]\n' % v + '\n'.join((out / ('lvs/lvs_%s.txt' % v)).read_text().splitlines()[:6])
                       for v in ('good', 'short', 'open'))
    text_image(lvs, assets / 'lvs_verification.png')
    create_grid(assets)
    assembly = json.loads((out / 'assembly/reticle_assembly.report.json').read_text())
    manifest = {'source': 'scripts/update_assets.py', 'layouteditor_tested_release': '20260920',
                'checks': {'independent_gds_tests': 7, 'native_contract_tests': 9, 'pic_drc_violations': 0,
                           'mems_drc_violations': 0, 'mems_connectivity_release': 'PASS',
                           'lvs': {v: json.loads((out / ('lvs/lvs_%s.json' % v)).read_text())['result']
                                   for v in ('good', 'short', 'open')},
                           'boolean_export': 'not exercised; license-dependent'},
                'assembly': {k: assembly[k] for k in ('mode', 'total_dies', 'counts', 'utilization_pct')},
                'images': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(assets.glob('*.png'))},
                'outputs': {str(p.relative_to(out)): hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in sorted(out.rglob('*.gds'))}}
    (assets / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    update(sys.argv[1] if len(sys.argv) > 1 else '/tmp/layout-skill-examples')
