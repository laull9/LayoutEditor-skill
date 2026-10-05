"""Two independent MPW dies: thin-film resistor monitors and microfluidic mixers.
Illustrative mask geometry; no process, resistance or fluidic performance sign-off.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from le_helpers import LE, rect, rrect

LAYERS = {1: ('METAL', (220, 165, 40)), 2: ('CONTACT_OPEN', (40, 140, 210)),
          3: ('CHANNEL', (40, 175, 150)), 4: ('PORT_OPEN', (160, 90, 185)),
          11: ('DIE_BORDER_REF', (100, 100, 100)), 12: ('NOTE', (70, 70, 70))}


def build(out, kind):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    le = LE(top='DIE', layers=LAYERS)
    le.poly(le.top, rect(-1500, -1000, 1500, 1000), 11)
    if kind == 'resistor':
        pad = le.cell('PAD')
        le.poly(pad, rect(-90, -90, 90, 90), 1)
        le.poly(pad, rect(-65, -65, 65, 65), 2)
        for i, width in enumerate((10, 20, 40)):
            y = -550 + i * 500
            le.ref(le.top, pad, -1150, y)
            le.ref(le.top, pad, 1150, y)
            pts = [(-1150, y), (-750, y)]
            for j in range(6):
                x = -750 + j * 300
                pts.extend([(x, y + (160 if j % 2 == 0 else -160)),
                            (x + 300, y + (160 if j % 2 == 0 else -160))])
            pts.extend([(1050, y), (1150, y)])
            le.path(le.top, pts, 1, width)
            le.text(le.top, 12, -900, y + 230, 'RESISTOR W=%d um' % width)
    else:
        # Two inlet paths meet at the same junction, followed by a serpentine.
        for sign in (-1, 1):
            le.path(le.top, [(-1200, sign * 550), (-650, sign * 550), (-350, 0)], 3, 80)
            le.poly(le.top, rrect(-1350, sign * 550 - 150, -1050, sign * 550 + 150, 120), 4)
        pts = [(-350, 0), (-100, 0), (-100, 450), (250, 450), (250, -450),
               (600, -450), (600, 450), (950, 450), (950, 0), (1200, 0)]
        le.path(le.top, pts, 3, 80)
        le.poly(le.top, rrect(1050, -150, 1350, 150, 120), 4)
        le.text(le.top, 12, -1000, 780, 'Y MIXER / 80 um channel')
    le.save_gds(str(out / (kind + '.gds')))
    le.dump_flat_json(str(out / (kind + '_polys.json')))


if __name__ == '__main__':
    build(sys.argv[1], sys.argv[2])
