# Photonic geometry

`scripts/photonic_helpers.py` supplies polygon geometry in µm. The example uses illustrative
220 nm SOI conventions. It has no foundry PDK, optical mode solver or measured transfer response.

| Function | Geometry and limits |
|---|---|
| `straight_waveguide` | Constant-width strip at an angle |
| `arc_bend` | Circular strip sampled by angle; a full ring uses a keyhole seam |
| `cosine_s_bend` | Cosine centerline with horizontal endpoint tangents; endpoint curvature is nonzero |
| `euler_bend` | Symmetric triangular curvature; `radius_min` sets peak centerline curvature |
| `linear_taper` | Linear width transition; adiabaticity is not checked |
| `make_directional_coupler` | Parallel strips and S-bend port separation; no coupling ratio guarantee |
| `make_ring_resonator` | Separate ring and bus with a specified edge gap |
| `make_mzi` | Two couplers with a solved geometric arm length difference |
| `make_grating_coupler` | Continuous core taper/slab on `layer`, shallow-etch slots on `etch_layer` |

For `cosine_s_bend(x0,y0,dx,dy,...)`,
`y=y0+dy/2*(1-cos(pi*(x-x0)/dx))`. Its slope vanishes at both ends; its second derivative does
not. A straight-to-cosine joint therefore retains a curvature discontinuity.

For the symmetric Euler bend, length `L=2*radius_min*abs(theta)` gives peak curvature
`1/radius_min`. Midpoint integration constructs the centerline and normal offsets construct the
strip. Sampling and 1 nm quantization affect the final polygon. Review the chosen tolerance
against minimum feature size; optical loss requires separate validation.

`make_mzi` keeps a 60 µm arm span. Two 25 µm S-bends create a detour; bisection solves their
sampled centerline length to match `delta_l`. External ports are at
`x=-s_dx` and `x=2*coupler_len+4*s_dx+60`, with
`y=+/-(s_dy+(gap+width)/2)`. Route from those coordinates. Geometric ΔL does not determine an
optical phase or spectral response without effective/group index and wavelength.

Grating coupler port `(0,0)` faces a grating extending along +x. Rotate by 180° for a left-facing
coupler. The core slab remains connected; `etch_layer` cuts shallow slots. Separate fully etched
islands on the core layer would not describe this shallow-etch device. Etch depth, period, duty
cycle, polarization and coupling angle must come from the process model for a real design.

Example layers: 1 kept core silicon, 2 shallow etch, 11 die reference, 12 note polygons.
`pic_drc_rules.json` checks core width ≥450 nm, core spacing ≥180 nm and etch slots ≥300 nm.
These three illustrative rules do not form a foundry deck. Independent output checks verify
input/output continuity, ring-bus separation, mask containment, drawn ΔL and bend radius.
