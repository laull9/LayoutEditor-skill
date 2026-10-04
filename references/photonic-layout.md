# Silicon Photonics (PIC) layout guide

Design and generate integrated photonics mask layouts with LayoutScript and `photonic_helpers.py`.

## 1. Waveguide primitives

All primitives are generated in micrometres (µm) as closed polygon loops.

### Straight waveguide
`straight_waveguide(x0, y0, length, angle_deg=0.0, width=0.5)`
Generates a strip waveguide polygon extending from `(x0, y0)` at angle `angle_deg` with specified width.

### Cosine S-bend
`cosine_s_bend(x0, y0, dx, dy, width=0.5, n=80)`
Centerline profile:
$$y(x) = y_0 + \frac{dy}{2} \left(1 - \cos\left(\frac{\pi (x - x_0)}{dx}\right)\right)$$
Zero curvature at both endpoints ($d^2y/dx^2 = 0$), eliminating curvature discontinuity and transition loss when joining straight waveguides.

### Euler bend (clothoid curve)
`euler_bend(radius_min, angle_deg=90.0, width=0.5, n=100)`
In an Euler bend, curvature $\kappa(s)$ ramps linearly from zero to peak and returns symmetrically to zero:
$$\kappa(s) \propto s$$
This suppresses fundamental-to-higher-order mode conversion, reduces radiation loss, and minimises back-reflection compared to circular bends of the same footprint.

### Linear taper
`linear_taper(x0, y0, w_start, w_end, length, angle_deg=0.0)`
Smooth adiabatic transition between single-mode strip waveguide (e.g. 0.5 µm) and multi-mode or grating coupler region (e.g. 10.0–12.0 µm).

---

## 2. Integrated components

### Directional coupler
`make_directional_coupler(le, name, length=20.0, gap=0.2, width=0.5, s_dx=30.0, s_dy=10.0, layer=1)`
Constructs a symmetric 2×2 directional coupler cell with parallel coupling length `length` and sub-micron coupling gap `gap`. Ports are separated smoothly using cosine S-bends.

### Ring resonator
`make_ring_resonator(le, name, radius=20.0, gap=0.2, bus_length=80.0, width=0.5, layer=1)`
Creates an all-pass ring resonator coupled to a straight bus waveguide. Coupling gap is defined from waveguide edge to ring edge.

### Asymmetric Mach-Zehnder Interferometer (MZI)
`make_mzi(le, name, delta_l=50.0, coupler_len=20.0, gap=0.2, width=0.5, s_dx=30.0, s_dy=15.0, layer=1)`
Combines two directional couplers with unequal optical path lengths in the upper and lower arms to construct optical bandpass / interleaver filters.

### Grating coupler
`make_grating_coupler(le, name, period=0.63, duty_cycle=0.5, n_gratings=25, taper_length=150.0, wg_w=0.5, spot_w=10.0, layer=1)`
Diffraction grating for vertical or near-vertical (8°–10°) optical fiber array coupling. Uses a linear expansion taper and sub-micron grating teeth.

---

## 3. Recommended layer convention (220 nm SOI)

| Layer | Name | Polarity | Purpose |
|---|---|---|---|
| 1 | `CORE_WG` | Drawn = kept silicon | Full-etch (220 nm) strip waveguides, couplers, ring resonators |
| 2 | `ETCH_GRATING` | Drawn = etched | Shallow-etch (70 nm) Bragg grating teeth |
| 3 | `SLAB_RIB` | Drawn = etched | Medium-etch (150 nm) rib waveguides / modulators |
| 4 | `METAL_HEATER` | Drawn = metal | Ti/W/Pt thermo-optic phase shifters |
| 5 | `PAD_CONTACT` | Drawn = metal | Al/Au contact pads for heater driving |
| 11 | `DIE_BORDER` | Non-mask | Chip edge boundary (rendered as dashed outline) |
| 12 | `TEXT_LABEL` | Non-mask | DRC-safe dot font labels |
