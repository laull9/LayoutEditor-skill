# SOI-MEMS mask conventions (4-mask reference flow)

A generic guide for bulk-micromachined SOI devices (scanning micromirrors, comb actuators,
resonators, inertial sensors). Treat every number as a **default to be replaced by your foundry's
design rules**. Public references: the MEMSCAP SOIMUMPs Design Handbook and published SOI-MEMS
design rules (for example, science.xyz "SOI MEMS design rules").

## Reference process

| Step | Mask | Purpose |
|---|---|---|
| 1 | **M1 isolation trench** | DRIE narrow trenches through the device layer, line with thermal oxide, refill with polysilicon, planarise. Gives electrical isolation **with** mechanical continuity |
| 2 | **M2 metal** | Cr/Au (lift-off): bond pads, low-resistance leads, reflective coating, marks |
| 3 | **M3 front structure** | DRIE through the device layer down to the buried oxide: all mechanical structures |
| 4 | **M4 backside cavity** | DRIE through the handle wafer under moving parts, then remove the buried oxide (HF) to release |

Typical stack: device 10–75 µm, buried oxide 1–2 µm, handle 400 µm. Many teaching flows insert an
insulator deposition between M1 and M2. Decide early whether metal contacts the silicon directly
(no contact mask: isolation must come from trenches and air gaps, and **metal must never cross a
trench**) or sits on an insulator (then a contact-opening mask is needed).

## Layer table template

| GDS | Name | Polarity (state it to the mask shop) | Notes |
|---|---|---|---|
| 1 | TRENCH | drawn = etched (dark field) | width 3–5 µm, rounded corners |
| 2 | METAL | drawn = metal kept | pads, leads, mirror coating |
| 3 | SI | **drawn = silicon kept** (light field) — boolean-free; or drawn = etched | the structural layer |
| 4 | BACK | drawn = opened (dark field) | ≥ 200 µm features |
| 11 | DIE_EDGE | non-mask | die outline / street centre |
| 12 | NOTE | non-mask | text annotations |
| 31/32 | *_REF | non-mask | open-region outline, electrode-island outlines |

## Default design rules (replace with foundry values)

| Rule | Typical value |
|---|---|
| Device-layer min line / min gap | 2 µm / 2 µm (2.5 µm on diagonals) |
| Metal min width / space | 3 µm / 3 µm |
| Device silicon encloses metal | ≥ 3 µm (keep ≥ 10–20 µm from trenches and etched edges in practice) |
| Trench width | 3–5 µm (set by refill capability); corner radius ≥ 2× width |
| Backside min feature / space | 200 µm / 200 µm |
| Backside opening encloses released structures | ≥ 5 µm + backside alignment tolerance |
| Anchors | ≥ 50 µm of overlap with unreleased substrate; ≥ 10 µm features (HF undercut 2–5 µm per side) |
| Released features | everything narrower than about 2× the HF undercut is released, so isolated narrow posts on oxide will float away |
| No "donut" islands on the backside layer | they fall out |
| Dicing street | 100–200 µm, keep 500 µm clear in production |

## Process-bias compensation

DRIE removes material laterally: drawn ≠ fabricated.
- Lines (beams, fingers): draw `target + 2·bias`.
- Gaps (comb gaps, beam clearances): draw `target − 2·bias`.
- Bias is often 0.5–1.5 µm per side and **must be calibrated with the foundry**.
- Keep critical gaps uniform. Etch lag makes narrow and wide openings etch at different rates.
- Report the frequency or stiffness sensitivity to ±1 µm bias. For torsion beams it is often
  ±5–10% in frequency.

## Structures

**Torsion and flexure beams**: one polygon with integral root fillets (`dogbone`). Use the radius
from the FEM stress study. Keep paired beams identical, because dual-axis devices are sensitive to
asymmetry. A beam may be recessed into a slot in the frame to gain length. Give the slot ≥ 50 µm of
clearance beyond the fillets.

**Comb drives**: equal gaps on both sides of every moving finger (n moving, n+1 fixed). Leave a tip
clearance of ≥ 10–30 µm. For vertical (out-of-plane) combs the vertical offset is not created by a
single-layer layout: it comes from residual-stress curling, a second etch depth, or assembly. Say
which one is assumed.

**Gimbals / multi-net moving frames**: a moving frame often has to carry more nets than it has
suspension beams. Partition it with trenches:
- A single trench path from an inner edge to an outer edge never disconnects the rest of an annular
  frame. A band (strip) between two trenches can therefore carry a second net around the frame to
  a beam.
- Isolate the root of every beam whose net differs from the surrounding frame with a U-trench
  "island" that starts and ends inside an etched edge.
- Count nets per beam and verify with the connectivity check. Topology mistakes are easy to make
  and invisible in a picture.

**Electrode islands in the field**: anchor + lead + pad as one rounded polygon, surrounded by a
trench ring that terminates inside the etched region (`trench_ring`). Put metal on the island
(inset ≥ 15–20 µm). Routing in doped device silicon is acceptable (sheet resistance of tens of
Ω/sq at 50 µm thickness and 0.01 Ω·cm); metal on top lowers it.

**Pads**: 100–200 µm square metal on 150–260 µm silicon blocks, at least 5 pads for a 2-axis
device (2 drives per axis or a shared drive + ground + shield/test). Group them on one or two sides
for wire bonding.

## Alignment marks and test structures

- M1 carries the primary marks. M2 and M3 align optically to M1. M4 aligns from the back
  (IR or double-side aligner) to M1 marks.
- M2→M1: trench cross plus metal squares with 3–5 µm clearance, and a vernier (main pitch p,
  vernier pitch p + 0.5 µm → 0.5 µm resolution).
- M3→M1: put marks inside an etched window, and keep the M1 cross embedded in a silicon pedestal so
  that the refilled trench is not left free-standing after the structural etch. Anchor narrow
  vernier bars to a wide base bar so that they survive release.
- M4: a large window (≥ 200 µm features) over an M1 outline target.
- Test structures: line/space combs (anchored to a base), gap blocks, and an isolated pad ring
  (trench leakage test against the field).
- Mask text in metal uses a DRC-safe font (`dot_text`).

## Things to pin down before drawing (ask the user)

1. Wafer stack (device, oxide and handle thickness) and doping.
2. Bias per side, trench width/refill limits, min features per layer.
3. Mask polarity convention expected by the mask shop.
4. Whether metal contacts silicon directly.
5. The verified mechanical model: plate/frame sizes, beam length/width/fillet, finger geometry,
   and target frequencies or angles. **Use it; do not invent dimensions.** If something is missing,
   back-fit it from verified results and flag it.
