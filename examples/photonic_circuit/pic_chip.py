# -*- coding: utf-8 -*-
"""
pic_chip.py — Silicon Photonics (PIC) test chip with asymmetric MZI, ring resonator,
Euler bend test loop, and fiber array grating couplers.

Run with LayoutEditor's bundled Python:
    <LE_PY> examples/photonic_circuit/pic_chip.py [out_dir]
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for p in [os.path.join(HERE, "..", "scripts"), os.path.join(HERE, "..", "..", "scripts")]:
    if os.path.isdir(p):
        sys.path.insert(0, os.path.abspath(p))
        break

from le_helpers import LE, rect, dot_text
from photonic_helpers import (
    make_mzi, make_ring_resonator, make_grating_coupler,
    euler_bend, straight_waveguide, cosine_s_bend
)

# Layers
# 1: CORE_WG (220nm SOI strip waveguide, drawn = silicon kept)
# 2: ETCH_GRATING (70nm shallow etch for Bragg grating teeth)
# 11: DIE_BORDER (chip edge outline)
# 12: TEXT_LABEL (DRC-safe text)
LAYERS = {
    1: ("CORE_WG", (30, 144, 255)),
    2: ("ETCH_GRATING", (255, 100, 50)),
    11: ("DIE_BORDER", (120, 120, 120)),
    12: ("TEXT_LABEL", (200, 160, 40)),
}


def build_pic_chip(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    le = LE(top="PIC_DEMO_CHIP", layers=LAYERS)
    top = le.top

    # Chip outline: 2000 x 1500 µm
    le.poly(top, rect(0, 0, 2000, 1500), 11)
    le.polys(top, dot_text("PIC TEST CHIP V1", 50, 1420, 5.0), 12)

    # 1. Asymmetric MZI filter (coupler_len = 25 µm, gap = 0.2 µm, delta_L = 40 µm)
    mzi = make_mzi(le, "MZI_FILTER", delta_l=40.0, coupler_len=25.0, gap=0.2, width=0.5, layer=1)
    le.ref(top, mzi, 400, 1000)
    le.polys(top, dot_text("MZI DL=40UM", 400, 1120, 2.0), 12)

    # Input and output grating couplers for MZI
    gc = make_grating_coupler(le, "GC_220", period=0.63, duty_cycle=0.5, n_gratings=25,
                              taper_length=160.0, wg_w=0.5, spot_w=10.0, layer=1)
    # GC ports for MZI
    le.ref(top, gc, 200, 1000 + 15.35, ang=180)
    le.ref(top, gc, 200, 1000 - 15.35, ang=180)
    le.ref(top, gc, 1000, 1000 + 15.35, ang=0)
    le.ref(top, gc, 1000, 1000 - 15.35, ang=0)

    # Routing between GC and MZI inputs/outputs
    le.poly(top, straight_waveguide(200, 1000 + 15.35, 170, 0.0, 0.5), 1)
    le.poly(top, straight_waveguide(200, 1000 - 15.35, 170, 0.0, 0.5), 1)

    for y in (1000 + 15.35, 1000 - 15.35):
        le.poly(top, straight_waveguide(600, y, 400, width=0.5), 1)

    # 2. All-pass Ring Resonator (radius = 30 µm, coupling gap = 0.2 µm)
    ring = make_ring_resonator(le, "RING_30UM", radius=30.0, gap=0.2, bus_length=200.0, width=0.5, layer=1)
    le.ref(top, ring, 500, 500)
    le.polys(top, dot_text("RING R=30UM", 420, 580, 2.0), 12)

    # Grating couplers for Ring
    le.ref(top, gc, 200, 500, ang=180)
    le.ref(top, gc, 1000, 500, ang=0)
    le.poly(top, straight_waveguide(200, 500, 200, 0.0, 0.5), 1)
    le.poly(top, straight_waveguide(600, 500, 400, 0.0, 0.5), 1)

    # 3. Euler Bend test structure (geometric 90-degree turn)
    c_euler = le.cell("EULER_BEND_COUPON")
    le.poly(c_euler, euler_bend(radius_min=15.0, angle_deg=90.0, width=0.5), 1)
    le.ref(top, c_euler, 300, 200)
    le.polys(top, dot_text("EULER BEND", 300, 150, 2.0), 12)

    # Export GDS and JSON dump
    gds_path = os.path.join(out_dir, "pic_chip.gds")
    le.save_gds(gds_path)
    json_path = os.path.join(out_dir, "pic_chip_polys.json")
    le.dump_flat_json(json_path)
    print("Wrote %s and %s" % (gds_path, json_path))
    return gds_path, json_path


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "out")
    build_pic_chip(out)
