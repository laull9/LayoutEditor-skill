"""Two-input CMOS NAND gate drawn from the demo technology file.

Usage (LayoutEditor Python): nand2.py <out_dir> [good|short|open]

  good   matches nand2.sp
  short  a METAL1 bridge joins inputs A and B
  open   the NMOS-side VIA1 of output Y is missing

Layers come from cmos_tech.json by name. Pin labels sit on METAL1.PIN / METAL2.PIN
(datatype 2) and name the nets during extraction. Dimensions are illustrative.
"""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'scripts'))
from le_helpers import LE, rect  # noqa: E402


def box(le, layer, x0, y0, x1, y1):
    le.poly(le.top, rect(x0, y0, x1, y1), layer)


def build(out, variant='good'):
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    le = LE(top='NAND2', tech=str(HERE / 'cmos_tech.json'))
    box(le, 'BOUNDARY', -10, -20, 58, 80)
    box(le, 'PWELL', -4, -4, 52, 14)
    box(le, 'NWELL', -4, 36, 52, 56)
    box(le, 'ACTIVE', 0, 0, 48, 10)            # series NMOS
    box(le, 'ACTIVE', 0, 40, 48, 52)           # parallel PMOS
    for x, pin in ((14, 'A'), (32, 'B')):      # gates run through both devices to a pad
        box(le, 'POLY', x, -4, x + 2, 60)
        box(le, 'POLY', x - 3, 58, x + 5, 64)
        box(le, 'CONTACT', x - 1, 59, x + 3, 63)
        box(le, 'METAL1', x - 2, 58, x + 4, 64)
        le.text(le.top, 'METAL1.PIN', x + 1, 61, pin)
    # PMOS: VDD | Y | VDD ; NMOS: VSS | internal node | Y
    for x in (3, 22, 41):
        box(le, 'CONTACT', x, 44, x + 4, 48)
        box(le, 'METAL1', x - 1, 43, x + 5, 49)
    for x in (3, 41):
        box(le, 'CONTACT', x, 3, x + 4, 7)
        box(le, 'METAL1', x - 1, 2, x + 5, 8)
    box(le, 'METAL1', 2, 43, 8, 76); box(le, 'METAL1', 40, 43, 46, 76)
    box(le, 'METAL1', -6, 70, 54, 76); le.text(le.top, 'METAL1.PIN', 0, 73, 'VDD')
    box(le, 'METAL1', 2, -16, 8, 8)
    box(le, 'METAL1', -6, -16, 54, -10); le.text(le.top, 'METAL1.PIN', 0, -13, 'VSS')
    # Output Y on METAL2 joins the PMOS middle contact and the NMOS right contact.
    box(le, 'VIA1', 22, 44, 26, 48)
    if variant != 'open':
        box(le, 'VIA1', 41, 3, 45, 7)
    box(le, 'METAL2', 21, 22, 27, 49); box(le, 'METAL2', 21, 22, 46, 28); box(le, 'METAL2', 40, 2, 46, 28)
    le.text(le.top, 'METAL2.PIN', 24, 25, 'Y')
    if variant == 'short':
        box(le, 'METAL1', 18, 59, 30, 63)
    gds = out / ('nand2_%s.gds' % variant)
    le.save_gds(str(gds))
    le.dump_flat_json(str(out / ('nand2_%s_polys.json' % variant)), meta={'variant': variant})
    print('wrote', gds)


if __name__ == '__main__':
    build(sys.argv[1] if len(sys.argv) > 1 else HERE / 'out', sys.argv[2] if len(sys.argv) > 2 else 'good')
