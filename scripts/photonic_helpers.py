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

    Smoothly transitions waveguide laterally with zero curvature at both endpoints.
    """
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
    suppressing radiation loss and higher-order mode excitation.
    """
    theta_total = math.radians(angle_deg)
    L = radius_min * theta_total * 1.5
    ds = L / float(n - 1)

    center = []
    cur_x, cur_y = 0.0, 0.0
    for i in range(n):
        s = i * ds
        if s <= L / 2.0:
            th = theta_total * 2.0 * (s / L) ** 2
        else:
            th = theta_total - theta_total * 2.0 * ((L - s) / L) ** 2
        nx = -math.sin(th)
        ny = math.cos(th)
        center.append((cur_x, cur_y, nx, ny))
        cur_x += ds * math.cos(th)
        cur_y += ds * math.sin(th)

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


def make_mzi(le, name, delta_l=50.0, coupler_len=20.0, gap=0.2, width=0.5, s_dx=30.0, s_dy=15.0, layer=1):
    """Asymmetric Mach-Zehnder Interferometer (MZI) filter.

    delta_l adds extra optical path length to the top arm.
    """
    c = le.cell(name)
    dc1 = make_directional_coupler(le, name + "_DC1", length=coupler_len, gap=gap, width=width, s_dx=s_dx, s_dy=s_dy, layer=layer)
    dc2 = make_directional_coupler(le, name + "_DC2", length=coupler_len, gap=gap, width=width, s_dx=s_dx, s_dy=s_dy, layer=layer)

    y_top = (gap + width) / 2.0 + s_dy
    y_bot = -y_top

    # Place DC1 at origin
    le.ref(c, dc1, 0, 0)

    # Arms
    arm_x0 = coupler_len + s_dx
    arm_base_len = 60.0

    # Top arm (longer by delta_l via double S-bend detour)
    if delta_l > 0:
        detour_h = math.sqrt(max(1.0, (delta_l / 2.0) ** 2))
        le.poly(c, cosine_s_bend(arm_x0, y_top, 25.0, detour_h, width), layer)
        le.poly(c, straight_waveguide(arm_x0 + 25.0, y_top + detour_h, arm_base_len - 50.0 + delta_l * 0.4, 0.0, width), layer)
        arm_x_mid = arm_x0 + arm_base_len - 25.0 + delta_l * 0.4
        le.poly(c, cosine_s_bend(arm_x_mid, y_top + detour_h, 25.0, -detour_h, width), layer)
        dc2_x = arm_x_mid + 25.0 + s_dx
    else:
        le.poly(c, straight_waveguide(arm_x0, y_top, arm_base_len, 0.0, width), layer)
        dc2_x = arm_x0 + arm_base_len + s_dx

    # Bottom arm (straight reference)
    bot_len = dc2_x - s_dx - arm_x0
    le.poly(c, straight_waveguide(arm_x0, y_bot, bot_len, 0.0, width), layer)

    # Place DC2
    le.ref(c, dc2, dc2_x, 0)
    return c


def make_grating_coupler(le, name, period=0.63, duty_cycle=0.5, n_gratings=25,
                          taper_length=150.0, wg_w=0.5, spot_w=10.0, layer=1):
    """Uniform fiber grating coupler with linear focus taper."""
    c = le.cell(name)
    # Taper from single-mode waveguide to wide grating area
    le.poly(c, linear_taper(0, 0, wg_w, spot_w, taper_length, 0.0), layer)

    # Grating teeth
    x_cur = taper_length
    tooth_w = period * duty_cycle
    for i in range(n_gratings):
        # Tooth box
        pts = [
            (x_cur, -spot_w / 2.0), (x_cur + tooth_w, -spot_w / 2.0),
            (x_cur + tooth_w, spot_w / 2.0), (x_cur, spot_w / 2.0)
        ]
        le.poly(c, pts, layer)
        x_cur += period

    return c
