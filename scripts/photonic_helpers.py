# -*- coding: utf-8 -*-
"""
photonic_helpers — silicon photonics (PIC) waveguide primitives and devices for LayoutEditor.

Provides:
  - Waveguide geometry: straight, arc bends, cosine S-bends, Euler bends, linear tapers.
  - PIC components: directional couplers, ring resonators, Mach-Zehnder interferometers (MZI),
    and fiber grating couplers.

All geometry is calculated in micrometres (float) and returns closed polygons compatible with
`le_helpers.LE` or pure polygon renderers.
"""
import math


def straight_waveguide(x0, y0, length, angle_deg=0.0, width=0.5):
    """Straight waveguide polygon of specified length and width starting at (x0, y0)."""
    th = math.radians(angle_deg)
    dx = math.cos(th)
    dy = math.sin(th)
    nx = -dy
    ny = dx
    hw = width / 2.0

    p0 = (x0 + nx * hw, y0 + ny * hw)
    p1 = (x0 + dx * length + nx * hw, y0 + dy * length + ny * hw)
    p2 = (x0 + dx * length - nx * hw, y0 + dy * length - ny * hw)
    p3 = (x0 - nx * hw, y0 - ny * hw)
    return [p0, p1, p2, p3]


def arc_bend(cx, cy, radius, a0_deg, a1_deg, width=0.5, step_deg=2.0):
    """Circular arc bend centered at (cx, cy) from angle a0 to a1."""
    da = a1_deg - a0_deg
    n = max(3, int(abs(da) / step_deg) + 1)
    angles = [a0_deg + da * i / (n - 1) for i in range(n)]

    r_outer = radius + width / 2.0
    r_inner = radius - width / 2.0

    outer = [(cx + r_outer * math.cos(math.radians(a)), cy + r_outer * math.sin(math.radians(a))) for a in angles]
    inner = [(cx + r_inner * math.cos(math.radians(a)), cy + r_inner * math.sin(math.radians(a))) for a in reversed(angles)]
    return outer + inner


def cosine_s_bend(x0, y0, dx, dy, width=0.5, n=80):
    """Cosine S-bend waveguide starting at (x0, y0) with span (dx, dy).

    Transitions laterally with horizontal endpoint tangents.
    Endpoint curvature is nonzero for nonzero dy; this is not a clothoid.
    """
    if dx <= 0 or width <= 0 or n < 3:
        raise ValueError("S-bend needs dx > 0, width > 0 and n >= 3")
    center = []
    for i in range(n):
        t = i / float(n - 1)
        x = x0 + t * dx
        y = y0 + (dy / 2.0) * (1.0 - math.cos(math.pi * t))
        dydx = (dy * math.pi / (2.0 * dx)) * math.sin(math.pi * t)
        angle = math.atan2(dydx, 1.0)
        nx = -math.sin(angle)
        ny = math.cos(angle)
        center.append((x, y, nx, ny))

    top = [(x + nx * width / 2.0, y + ny * width / 2.0) for x, y, nx, ny in center]
    bot = [(x - nx * width / 2.0, y - ny * width / 2.0) for x, y, nx, ny in reversed(center)]
    return top + bot


def euler_bend(radius_min, angle_deg=90.0, width=0.5, n=100):
    """90-degree Euler bend starting horizontally at (0, 0).

    Curvature ramps linearly from zero to peak and symmetrically back to zero,
    This defines geometry only; propagation loss requires an optical model.
    """
    if radius_min <= width / 2 or width <= 0 or n < 3 or angle_deg == 0:
        raise ValueError("Invalid Euler bend dimensions")
    theta_total = math.radians(angle_deg)
    # Triangular curvature integrates to theta; peak |kappa| = 1 / radius_min.
    L = 2.0 * radius_min * abs(theta_total)
    ds = L / float(n - 1)
    def theta(s):
        if s <= L / 2:
            return theta_total * 2 * (s / L) ** 2
        return theta_total - theta_total * 2 * ((L - s) / L) ** 2
    center = []
    cur_x, cur_y = 0.0, 0.0
    for i in range(n):
        th = theta(i * ds)
        center.append((cur_x, cur_y, -math.sin(th), math.cos(th)))
        mid = theta((i + .5) * ds)
        if i < n - 1:
            cur_x += ds * math.cos(mid)
            cur_y += ds * math.sin(mid)

    top = [(x + nx * width / 2.0, y + ny * width / 2.0) for x, y, nx, ny in center]
    bot = [(x - nx * width / 2.0, y - ny * width / 2.0) for x, y, nx, ny in reversed(center)]
    return top + bot


def linear_taper(x0, y0, w_start, w_end, length, angle_deg=0.0):
    """Linear waveguide taper from w_start to w_end."""
    th = math.radians(angle_deg)
    dx = math.cos(th)
    dy = math.sin(th)
    nx = -dy
    ny = dx

    p0 = (x0 + nx * (w_start / 2.0), y0 + ny * (w_start / 2.0))
    p1 = (x0 + dx * length + nx * (w_end / 2.0), y0 + dy * length + ny * (w_end / 2.0))
    p2 = (x0 + dx * length - nx * (w_end / 2.0), y0 + dy * length - ny * (w_end / 2.0))
    p3 = (x0 - nx * (w_start / 2.0), y0 - ny * (w_start / 2.0))
    return [p0, p1, p2, p3]


# -- Higher-level PIC devices (requires LE session) ---------------------------

def make_directional_coupler(le, name, length=20.0, gap=0.2, width=0.5, s_dx=30.0, s_dy=10.0, layer=1):
    """Directional coupler with coupling section and S-bend port separation.

    Ports:
      Port 1 (Input 1): (-s_dx, s_dy + gap/2 + width/2)
      Port 2 (Input 2): (-s_dx, -(s_dy + gap/2 + width/2))
      Port 3 (Through): (length + s_dx, gap/2 + width/2 + s_dy)
      Port 4 (Cross):   (length + s_dx, -(gap/2 + width/2 + s_dy))
    """
    c = le.cell(name)
    y_top = (gap + width) / 2.0
    y_bot = -y_top

    # Coupling straight sections
    le.poly(c, straight_waveguide(0, y_top, length, 0.0, width), layer)
    le.poly(c, straight_waveguide(0, y_bot, length, 0.0, width), layer)

    # Input S-bends
    le.poly(c, cosine_s_bend(-s_dx, y_top + s_dy, s_dx, -s_dy, width), layer)
    le.poly(c, cosine_s_bend(-s_dx, y_bot - s_dy, s_dx, s_dy, width), layer)

    # Output S-bends
    le.poly(c, cosine_s_bend(length, y_top, s_dx, s_dy, width), layer)
    le.poly(c, cosine_s_bend(length, y_bot, s_dx, -s_dy, width), layer)
    return c


def make_ring_resonator(le, name, radius=20.0, gap=0.2, bus_length=80.0, width=0.5, layer=1):
    """All-pass ring resonator coupled to a bus waveguide."""
    c = le.cell(name)
    # Bus waveguide along y = 0
    le.poly(c, straight_waveguide(-bus_length / 2.0, 0, bus_length, 0.0, width), layer)

    # Ring centered at (0, radius + gap + width)
    cy = radius + gap + width
    ring_poly = arc_bend(0, cy, radius, 0.0, 360.0, width=width, step_deg=2.0)
    le.poly(c, ring_poly, layer)
    return c


def mzi_arm_geometry(delta_l, span=25.0, n=80):
    """Solve detour height for a requested geometric centerline length difference."""
    if delta_l < 0:
        raise ValueError("delta_l must be nonnegative")
    def length(h):
        pts = [(span * i / (n - 1), h / 2 * (1 - math.cos(math.pi * i / (n - 1))))
               for i in range(n)]
        return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:]))
    lo, hi = 0.0, max(span, delta_l)
    while 2 * (length(hi) - span) < delta_l:
        hi *= 2
    for _ in range(70):
        mid = (lo + hi) / 2
        if 2 * (length(mid) - span) < delta_l:
            lo = mid
        else:
            hi = mid
    height = (lo + hi) / 2
    return height, 2 * (length(height) - span)


def make_mzi(le, name, delta_l=50.0, coupler_len=20.0, gap=0.2, width=0.5, s_dx=30.0, s_dy=15.0, layer=1):
    """Two directional couplers joined by arms with geometric length difference delta_l.

    External x ports: -s_dx and 2*coupler_len + 4*s_dx + 60.
    External y ports: +/-(s_dy + (gap + width)/2). No optical response is implied.
    """
    c = le.cell(name)
    dc = make_directional_coupler(le, name + "_DC", length=coupler_len, gap=gap,
                                  width=width, s_dx=s_dx, s_dy=s_dy, layer=layer)
    y = (gap + width) / 2 + s_dy
    x0 = coupler_len + s_dx
    arm_len, span = 60.0, 25.0
    height, _ = mzi_arm_geometry(delta_l, span)
    le.ref(c, dc, 0, 0)
    le.poly(c, cosine_s_bend(x0, y, span, height, width), layer)
    le.poly(c, straight_waveguide(x0 + span, y + height, arm_len - 2 * span, width=width), layer)
    le.poly(c, cosine_s_bend(x0 + arm_len - span, y + height, span, -height, width), layer)
    le.poly(c, straight_waveguide(x0, -y, arm_len, width=width), layer)
    le.ref(c, dc, x0 + arm_len + s_dx, 0)
    return c


def make_grating_coupler(le, name, period=0.63, duty_cycle=0.5, n_gratings=25,
                          taper_length=150.0, wg_w=0.5, spot_w=10.0, layer=1, etch_layer=2):
    """Continuous silicon taper/slab plus shallow-etch slots on a separate layer.

    Waveguide port is (0, 0); grating extends along +x. Dimensions are illustrative.
    """
    if period <= 0 or not 0 < duty_cycle < 1 or n_gratings < 1 or etch_layer == layer:
        raise ValueError("Invalid grating parameters or layer polarity")
    c = le.cell(name)
    le.poly(c, linear_taper(0, 0, wg_w, spot_w, taper_length), layer)
    end = taper_length + n_gratings * period
    le.poly(c, [(taper_length, -spot_w / 2), (end, -spot_w / 2),
                (end, spot_w / 2), (taper_length, spot_w / 2)], layer)
    for i in range(n_gratings):
        x = taper_length + (i + duty_cycle) * period
        le.poly(c, [(x, -spot_w / 2), (taper_length + (i + 1) * period, -spot_w / 2),
                    (taper_length + (i + 1) * period, spot_w / 2), (x, spot_w / 2)], etch_layer)
    return c
