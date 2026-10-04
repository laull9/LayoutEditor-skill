# -*- coding: utf-8 -*-
"""
Demo: a 2 × 2 mm SOI-MEMS electrostatic comb-actuator test chip, generated headlessly.

Run with LayoutEditor's bundled Python (see scripts/find_layouteditor.sh):
    <LE_PYTHON> examples/demo_chip.py [out_dir]

It exercises every technique in this skill:
  * parameter dict in µm, drawn = target ± process bias
  * hierarchy: finger cells → 1-D arrays → comb row → top; rotated references
  * torsion/flexure beams drawn as one polygon with integral root fillets (dogbone)
  * "drawn = kept" structural layer: field silicon as two keyhole halves around the open region,
    plus an etch window punched through a zero-width bridge (no boolean engine needed)
  * an electrically isolated electrode island bounded by a trench ring whose ends stop 5 µm inside
    the etched region (offset + clip, no booleans)
  * metal pads/leads inset from trenches, DRC-safe dot-matrix mask text, alignment marks
  * GDS export with license check, then flattened JSON dump for verification/preview

Layers (layer/datatype 0):
  1 TRENCH (isolation trench, drawn = etched)   2 METAL (drawn = metal)
  3 SI (device layer, drawn = KEPT)              4 BACK (backside cavity, drawn = opened)
  11 DIE_EDGE, 12 NOTE, 31 OPEN_REF, 32 ISLAND_REF — not masks
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
from le_helpers import (LE, rect, rrect, tr, rot, mirx, ccw, round_poly, round_by_turn, offset_poly,
                        dogbone, field_halves, insert_windows, trench_ring, dot_text, comb_row)

OUT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "out"))
os.makedirs(OUT, exist_ok=True)

# ----------------------------------------------------------------------------- parameters (µm)
P = dict(
    bias=1.0,                          # lateral etch loss per side (calibrate with the foundry)
    die=2000.0, street=100.0,
    plate=(400.0, 300.0),              # moving shuttle plate (w, h)
    beam_w=10.0, beam_L=300.0, beam_R=15.0,
    finger_w=5.0, gap=5.0, finger_L=60.0, tip=10.0, n_fingers=18,
    clr=60.0, open_R=30.0, cavity_margin=10.0, channel_h=100.0,   # channel half-height: cavity >= 200 um
    trench_w=4.0, trench_stub=5.0, island_R=25.0,
    pad=160.0, pad_block=200.0, lead_w=60.0, metal_inset=15.0,
)
b = P["bias"]
W_BEAM = P["beam_w"] + 2 * b               # lines drawn wider ...
W_F, GAP = P["finger_w"] + 2 * b, P["gap"] - 2 * b   # ... gaps drawn narrower
PW, PH = P["plate"][0] / 2, P["plate"][1] / 2
XA = PW + P["beam_L"]                       # anchor face x
YE = PH + P["finger_L"] + P["tip"]          # open-region half height = fixed-finger root
H = P["die"] / 2
HF = H - P["street"]                        # field extent (street is etched)

le = LE(top="DEMO_CHIP", layers={
    1: ("TRENCH", (230, 80, 60)), 2: ("METAL", (240, 190, 40)), 3: ("SI_KEPT", (40, 140, 230)),
    4: ("BACK_CAVITY", (150, 90, 200)), 11: ("DIE_EDGE", (120, 120, 120)), 12: ("NOTE", (60, 60, 60)),
    31: ("OPEN_REF", (90, 90, 200)), 32: ("ISLAND_REF", (200, 120, 60)),
})
TRENCH, METAL, SI, BACK, DIE, NOTE, OPEN_REF, ISL_REF = 1, 2, 3, 4, 11, 12, 31, 32
top = le.top

# ----------------------------------------------------------------------------- unit cells
comb, xc, xf = comb_row(le, "COMB", W_F, GAP, P["finger_L"], P["tip"], P["n_fingers"], SI)
beam = le.cell("FLEXURE")
le.poly(beam, dogbone(W_BEAM, 0, P["beam_L"], P["beam_R"], P["beam_R"]), SI)
le.text(beam, NOTE, W_BEAM, P["beam_L"] / 2, "W%g R%g" % (W_BEAM, P["beam_R"]), 8)

# ----------------------------------------------------------------------------- moving structure
le.poly(top, rect(-PW, -PH, PW, PH), SI)                    # shuttle plate
le.ref(top, beam, PW, 0, -90)                               # beam along +x (cell is along +y)
le.ref(top, beam, -PW, 0, 90)                               # beam along -x
le.ref(top, comb, 0, PH, 0)                                 # comb on the top edge

# ----------------------------------------------------------------------------- open region, cavity, field
CH = P["channel_h"]

def open_outline(m=0.0):
    return [(XA + m, -CH - m), (XA + m, CH + m), (PW + P["clr"] + m, CH + m), (PW + P["clr"] + m, YE + m),
            (-PW - P["clr"] - m, YE + m), (-PW - P["clr"] - m, CH + m), (-XA - m, CH + m), (-XA - m, -CH - m),
            (-PW - P["clr"] - m, -CH - m), (-PW - P["clr"] - m, -PH - P["clr"] - m),
            (PW + P["clr"] + m, -PH - P["clr"] - m), (PW + P["clr"] + m, -CH - m)]

def open_region(m=0.0):
    return round_by_turn(open_outline(m), P["open_R"], 0.0)   # round convex corners only

le.poly(top, open_region(0), OPEN_REF)
le.poly(top, open_region(P["cavity_margin"]), BACK)          # backside cavity = open region + margin

XO = PW + P["clr"]
hole_left = [(5.0, -PH - P["clr"]), (-XO, -PH - P["clr"]), (-XO, -CH), (-XA, -CH), (-XA, CH), (-XO, CH),
             (-XO, YE), (5.0, YE)]
left, right = field_halves(hole_left, HF, overlap=5.0, hole_round=P["open_R"])
CD_WIN = (-850, 600, -500, 850)                               # etch window for the CD test structure
le.poly(top, insert_windows(left, [CD_WIN], HF), SI)
le.poly(top, right, SI)

# ----------------------------------------------------------------------------- electrode island + trench ring
PB, LW = P["pad_block"] / 2, P["lead_w"] / 2
PAD_DRIVE, PAD_GND = (0.0, 650.0), (500.0, 650.0)
# island sides sit IN the open region by more than the open-region corner radius, so the trench
# crosses the etched edge on a straight segment (not through a rounded corner)
IX = XO - P["open_R"] - 10
island = [(-IX, YE - 50), (IX, YE - 50), (IX, YE + 180), (LW, YE + 180),
          (LW, PAD_DRIVE[1] - PB), (PB, PAD_DRIVE[1] - PB), (PB, PAD_DRIVE[1] + PB), (-PB, PAD_DRIVE[1] + PB),
          (-PB, PAD_DRIVE[1] - PB), (-LW, PAD_DRIVE[1] - PB), (-LW, YE + 180), (-IX, YE + 180)]
island = round_poly(ccw(island), P["island_R"])
le.poly(top, island, ISL_REF)
for run in trench_ring(island, P["trench_w"], open_region(0), open_region(-P["trench_stub"])):
    le.path(top, run, TRENCH, P["trench_w"])

# ----------------------------------------------------------------------------- metal
mi = P["metal_inset"]
for r in [rect(-IX + mi, YE + mi, IX - mi, YE + 180 - mi),                 # electrode bus
          rect(-LW + mi, YE + 180 - 2 * mi, LW - mi, PAD_DRIVE[1]),                  # lead
          rect(-PB + mi, PAD_DRIVE[1] - PB + mi, PB - mi, PAD_DRIVE[1] + PB - mi),   # DRIVE pad
          rect(PAD_GND[0] - P["pad"] / 2, PAD_GND[1] - P["pad"] / 2,
               PAD_GND[0] + P["pad"] / 2, PAD_GND[1] + P["pad"] / 2)]:              # GND pad on field
    le.poly(top, r, METAL)
le.polys(top, dot_text("DEMO CHIP V1", -600, -800, 8), METAL)
le.polys(top, dot_text("DRIVE", PAD_DRIVE[0], PAD_DRIVE[1] + PB + 30, 8, center=True), METAL)
le.polys(top, dot_text("GND", PAD_GND[0], PAD_GND[1] + PB + 30, 8, center=True), METAL)

# ----------------------------------------------------------------------------- marks and test structure
mark = le.cell("ALIGN_M1_M2")
le.poly(mark, rect(-90, -3, 90, 3), TRENCH); le.poly(mark, rect(-3, -90, 3, 90), TRENCH)
for sx in (1, -1):
    for sy in (1, -1):
        le.poly(mark, rect(sx * 7, sy * 7, sx * 47, sy * 47), METAL)   # 4 µm clearance to the cross
le.ref(top, mark, 650, -650)

cd = le.cell("CD_TEST")
le.poly(cd, rect(0, 0, 300, 40), SI)                                   # anchor bar (survives HF undercut)
x = 15.0
for w in (3, 5, 8, 12):
    for _ in range(3):
        le.poly(cd, rect(x, 39, x + w, 160), SI)
        x += 2 * w
    x += 20
le.ref(top, cd, CD_WIN[0] + 25, CD_WIN[1] + 30)

le.path(top, [(-H, -H), (H, -H), (H, H), (-H, H), (-H, -H)], DIE, 2)
le.text(top, NOTE, -950, 950, "DEMO: comb actuator test chip, SI layer drawn = kept", 20)

# ----------------------------------------------------------------------------- export + dump
gds = le.save_gds(os.path.join(OUT, "demo_chip.gds"))
le.dump_flat_json(os.path.join(OUT, "demo_chip_polys.json"),
                  meta={"params": P, "pads": {"DRIVE": PAD_DRIVE, "GND": PAD_GND}})
print("wrote", gds)
