"""Read a GDS top and dump preview polygons without modifying the source file.
Usage (LayoutEditor Python): dump_layout.py input.gds TOP output.json [layers.json]
"""
import json
import os
import sys
from le_helpers import LE


def dump_layout(path, top_name, out, layers=None):
    le = LE(layers=layers)
    le.L.open(os.path.abspath(path))
    le.top = le.dr.findCell(top_name)
    if le.top is None:
        raise ValueError('Top cell not found: ' + top_name)
    if abs(le.dr.databaseunits - 1e-9) > 1e-15:
        raise ValueError('Preview dump requires 1 nm DBU')
    return le.dump_flat_json(out)


if __name__ == '__main__':
    styles = {}
    if len(sys.argv) > 4:
        styles = {int(k): (v['name'], v['color']) for k, v in json.load(open(sys.argv[4])).items()}
    dump_layout(sys.argv[1], sys.argv[2], sys.argv[3], styles)
