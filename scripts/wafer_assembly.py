# -*- coding: utf-8 -*-
"""
wafer_assembly — wafer-level and reticle-level multi-die layout assembly with dicing streets and alignment marks.

Usage from shell with LayoutEditor's Python:
    <LE_PY> wafer_assembly.py <config.json> <out.gds> [report.txt]

Functions can also be imported in Python:
    from wafer_assembly import assemble_wafer, WaferConfig
"""
import json
import math
import os
import sys

try:
    from LayoutScript import project, point, pointArray, strans
except ImportError:
    project = None

UM = 1000  # 1 µm = 1000 dbu


def _ensure_le():
    if project is None:
        sys.exit("wafer_assembly requires LayoutEditor's bundled Python (LayoutScript module).")


def make_cross_mark(le, cell, cx, cy, span_um=60, width_um=4, layer=11):
    """Draw a cross alignment mark centered at (cx, cy)."""
    h_span = span_um / 2.0
    h_w = width_um / 2.0
    # Horizontal bar
    le.poly(cell, [
        (cx - h_span, cy - h_w), (cx + h_span, cy - h_w),
        (cx + h_span, cy + h_w), (cx - h_span, cy + h_w)
    ], layer)
    # Vertical bar
    le.poly(cell, [
        (cx - h_w, cy - h_span), (cx + h_w, cy - h_span),
        (cx + h_w, cy + h_span), (cx - h_w, cy + h_span)
    ], layer)


def assemble_wafer(config_path, out_gds, report_path=None):
    """Assemble a wafer or reticle layout according to config_path."""
    _ensure_le()
    cfg = json.load(open(config_path))
    out_gds = os.path.abspath(out_gds)

    title = cfg.get("title", "WAFER_ASSEMBLY")
    wafer_diam_mm = cfg.get("wafer_diameter_mm", 100.0)  # default 4-inch (100 mm)
    edge_excl_mm = cfg.get("edge_exclusion_mm", 3.0)
    street_w_um = cfg.get("dicing_street_width_um", 80.0)
    street_layer = cfg.get("street_layer", 11)
    wafer_layer = cfg.get("wafer_boundary_layer", 11)
    mark_layer = cfg.get("mark_layer", 11)

    r_wafer_um = (wafer_diam_mm / 2.0) * 1000.0
    r_eff_um = r_wafer_um - (edge_excl_mm * 1000.0)

    dies = cfg.get("dies", [])
    # Default to single die array if "die" object given
    if "die" in cfg and not dies:
        dies = [cfg["die"]]

    master_L = project.newLayout()
    master_dr = master_L.drawing
    top = master_dr.currentCell
    top.cellName = title

    # Draw wafer circular boundary
    n_wafer_pts = 360
    wafer_poly = []
    for i in range(n_wafer_pts):
        th = 2.0 * math.pi * i / n_wafer_pts
        wafer_poly.append((r_wafer_um * math.cos(th), r_wafer_um * math.sin(th)))

    pa_wafer = pointArray()
    for x, y in wafer_poly:
        pa_wafer.attach(int(round(x * UM)), int(round(y * UM)))
    top.addPath(pa_wafer, wafer_layer, int(round(10.0 * UM)))

    # Process each die definition
    total_placed_dies = 0
    die_reports = []

    for die_idx, dcfg in enumerate(dies):
        die_name = dcfg.get("name", "DIE_%d" % die_idx)
        w_um = float(dcfg.get("width_um", 2000.0))
        h_um = float(dcfg.get("height_um", 2000.0))
        gds_path = dcfg.get("gds_path", None)
        target_cell_name = dcfg.get("cell_name", None)

        pitch_x = w_um + street_w_um
        pitch_y = h_um + street_w_um

        # Import cell if gds_path is given
        die_cell = None
        if gds_path and os.path.exists(gds_path):
            abs_gds = os.path.abspath(gds_path)
            master_dr.importFile(abs_gds)
            if target_cell_name:
                die_cell = master_dr.findCell(target_cell_name)
            if die_cell is None:
                # Find cell by checking existing
                cl = master_dr.firstCell
                while cl:
                    if cl.thisCell and cl.thisCell.cellName != title:
                        die_cell = cl.thisCell
                    cl = cl.nextCell
        else:
            # Create a placeholder box die cell
            die_cell = master_dr.addCell().thisCell
            die_cell.cellName = die_name
            # Outline
            pa_box = pointArray()
            hw, hh = w_um / 2.0, h_um / 2.0
            for bx, by in [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]:
                pa_box.attach(int(round(bx * UM)), int(round(by * UM)))
            die_cell.addPolygon(pa_box, street_layer)

        # Compute grid bounds
        nx_max = int(r_eff_um // pitch_x) + 1
        ny_max = int(r_eff_um // pitch_y) + 1

        placed_coords = []
        for ix in range(-nx_max, nx_max + 1):
            cx = ix * pitch_x
            for iy in range(-ny_max, ny_max + 1):
                cy = iy * pitch_y
                # Check 4 corners of the die against effective wafer radius
                hw, hh = w_um / 2.0, h_um / 2.0
                corners = [
                    (cx - hw, cy - hh), (cx + hw, cy - hh),
                    (cx + hw, cy + hh), (cx - hw, cy + hh)
                ]
                if all(x*x + y*y <= r_eff_um * r_eff_um for x, y in corners):
                    # Die fits inside effective radius
                    top.addCellref(die_cell, point(int(round(cx * UM)), int(round(cy * UM))))
                    placed_coords.append((cx, cy))

        total_placed_dies += len(placed_coords)
        die_reports.append({
            "die_name": die_name,
            "dimensions_um": [w_um, h_um],
            "count": len(placed_coords)
        })

        # Add cross marks at dicing street intersections for placed dies
        for cx, cy in placed_coords:
            # Place mark at top-right street intersection
            mx = cx + (w_um / 2.0) + (street_w_um / 2.0)
            my = cy + (h_um / 2.0) + (street_w_um / 2.0)
            if mx*mx + my*my <= r_eff_um * r_eff_um:
                # Add cross
                cpa1 = pointArray()
                cpa1.attach(int(round((mx - 20) * UM)), int(round(my * UM)))
                cpa1.attach(int(round((mx + 20) * UM)), int(round(my * UM)))
                top.addPath(cpa1, mark_layer, int(round(3.0 * UM)))

                cpa2 = pointArray()
                cpa2.attach(int(round(mx * UM)), int(round((my - 20) * UM)))
                cpa2.attach(int(round(mx * UM)), int(round((my + 20) * UM)))
                top.addPath(cpa2, mark_layer, int(round(3.0 * UM)))

    master_dr.setCell(top)
    if os.path.exists(out_gds):
        os.remove(out_gds)
    master_dr.saveFile(out_gds)

    wafer_area_mm2 = math.pi * (wafer_diam_mm / 2.0) ** 2
    eff_area_mm2 = math.pi * (r_eff_um / 1000.0) ** 2
    die_area_total_mm2 = sum(d["count"] * (d["dimensions_um"][0] * d["dimensions_um"][1] / 1e6) for d in die_reports)
    utilization_pct = (die_area_total_mm2 / wafer_area_mm2) * 100.0 if wafer_area_mm2 else 0.0

    lines = [
        "Wafer assembly report: %s" % title,
        "=" * 60,
        "Wafer diameter:        %.1f mm (%.1f inch)" % (wafer_diam_mm, wafer_diam_mm / 25.4),
        "Edge exclusion:        %.1f mm" % edge_excl_mm,
        "Effective diameter:    %.1f mm" % (2.0 * r_eff_um / 1000.0),
        "Dicing street width:   %.1f µm" % street_w_um,
        "-" * 60,
        "Total placed dies:     %d" % total_placed_dies,
    ]
    for d in die_reports:
        lines.append("  * %s (%.0f x %.0f µm): %d dies" % (
            d["die_name"], d["dimensions_um"][0], d["dimensions_um"][1], d["count"]
        ))
    lines += [
        "-" * 60,
        "Wafer gross area:      %.1f mm²" % wafer_area_mm2,
        "Effective usable area: %.1f mm²" % eff_area_mm2,
        "Silicon utilization:   %.1f%%" % utilization_pct,
        "Exported GDS:          %s" % out_gds,
    ]
    report_text = "\n".join(lines)
    if report_path:
        with open(report_path, "w") as f:
            f.write(report_text + "\n")
    print(report_text)
    return {
        "title": title,
        "total_dies": total_placed_dies,
        "utilization_pct": utilization_pct,
        "out_gds": out_gds
    }


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    cfg_path = argv[1]
    out_gds = argv[2]
    rep_path = argv[3] if len(argv) > 3 else None
    assemble_wafer(cfg_path, out_gds, rep_path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
