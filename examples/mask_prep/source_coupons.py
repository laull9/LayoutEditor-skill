"""Independent thin-film coupons with intentionally colliding TOP/PAD cell names.

The first source is a Kelvin/contact-resistance pattern; the second is a
line/space process monitor. Dimensions are illustrative, not a foundry deck.
"""
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from le_helpers import LE, rect

LAYERS = {1: ('METAL', (225, 166, 42)), 2: ('CONTACT_OPEN', (80, 160, 220)),
          11: ('DIE_BORDER_REF', (110, 110, 110)), 12: ('NOTE', (70, 70, 70))}


def build(out, kind):
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    le = LE(top='TOP', layers=LAYERS)
    pad = le.cell('PAD')
    le.poly(pad, rect(-70, -70, 70, 70), 1)
    le.poly(pad, rect(-50, -50, 50, 50), 2)
    le.poly(le.top, rect(-700, -500, 700, 500), 11)
    if kind == 'kelvin':
        for x, y in [(-500, 280), (-500, -280), (500, 280), (500, -280)]:
            le.ref(le.top, pad, x, y)
            le.path(le.top, [(x, y), (x / 2, y), (x / 2, 0), (0, 0)], 1, 20)
        le.poly(le.top, rect(-35, -35, 35, 35), 2)
        le.text(le.top, 12, -630, 420, 'KELVIN / 20 um leads')
    else:
        for i, gap in enumerate((4, 8, 12, 20)):
            y = -340 + i * 200
            for j in range(7):
                le.poly(le.top, rect(-250 + j * (20 + gap), y,
                                     -230 + j * (20 + gap), y + 120), 1)
            le.ref(le.top, pad, 480, y + 60)
            le.text(le.top, 12, -630, y + 50, 'SPACE %d um' % gap)
    le.save_gds(str(out / (kind + '.gds')))
    le.dump_flat_json(str(out / (kind + '_polys.json')))
    spec = [{'path': str(out / 'kelvin.gds'), 'cell': 'TOP', 'prefix': 'K_', 'offset': [-850, 0]},
        {'path': str(out / 'line_space.gds'), 'cell': 'TOP', 'prefix': 'LS_', 'offset': [850, 0]}]
    (out / 'merge_spec.json').write_text(json.dumps(spec, indent=2))


if __name__ == '__main__':
    build(sys.argv[1], sys.argv[2])
