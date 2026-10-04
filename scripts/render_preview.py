# -*- coding: utf-8 -*-
"""
Render layout previews (PNG) from a flattened polygon dump — replaces LayoutEditor's headless
screenshot, which is blank.

Run with any CPython that has matplotlib:
    python3 render_preview.py <polys.json> <out_dir> [views.json]

Always writes:  00_overview.png (all layers) and one <NN>_layer_<num>.png per layer.
views.json (optional) adds zoomed views:
    {
      "title": "My chip",
      "order": ["4", "3", "2", "1"],                 # draw order, bottom → top (default: sorted)
      "hide_in_overview": ["31", "32"],               # e.g. reference-only layers
      "views": [
        {"name": "comb", "title": "Comb detail", "window": [x0, x1, y0, y1], "layers": ["3", "1"],
         "notes": true}
      ]
    }
Layer names/colours come from the dump ("layers" written by LE(layers=...)); unknown layers get a
default palette. Layers named *REF* or *NOTE* are drawn as dashed outlines.
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PatchCollection
from matplotlib.patches import Polygon, Rectangle

PALETTE = ["#3d8fe0", "#e5503c", "#f2bd2a", "#9b6fd1", "#4caf50", "#ff9800", "#00bcd4", "#795548"]


def style_for(data, lay, i):
    info = data.get("layers", {}).get(lay, {})
    name = info.get("name", "layer %s" % lay)
    col = info.get("color")
    face = "#%02x%02x%02x" % tuple(col) if col else PALETTE[i % len(PALETTE)]
    outline = any(k in name.upper() for k in ("REF", "NOTE", "DIE", "EDGE", "BOUNDARY", "BORDER"))
    return name, face, outline


def draw(ax, data, layers, window, lw=0.4):
    for i, lay in enumerate(layers):
        polys = data["polys"].get(lay, [])
        if not polys:
            continue
        name, face, outline = style_for(data, lay, i)
        pc = PatchCollection([Polygon(p, closed=True) for p in polys],
                             facecolor="none" if outline else face, edgecolor=face if outline else "#333333",
                             alpha=0.9 if outline else 0.55, linewidths=lw, zorder=i + 1)
        if outline:
            pc.set_linestyle((0, (4, 3)))
        ax.add_collection(pc)
    ax.set_xlim(window[0], window[1]); ax.set_ylim(window[2], window[3])
    ax.set_aspect("equal"); ax.set_facecolor("white")
    ax.tick_params(labelsize=7); ax.set_xlabel("x (µm)", fontsize=8); ax.set_ylabel("y (µm)", fontsize=8)


def legend(ax, data, layers):
    hs, labels = [], []
    for i, lay in enumerate(layers):
        if data["polys"].get(lay):
            name, face, outline = style_for(data, lay, i)
            hs.append(Rectangle((0, 0), 1, 1, facecolor="white" if outline else face, edgecolor=face))
            labels.append("%s (%s)" % (name, lay))
    ax.legend(hs, labels, loc="upper right", fontsize=7, framealpha=0.9)


def notes(ax, data, window, size=6):
    for lay, x, y, s in data.get("texts", []):
        if window[0] <= x <= window[1] and window[2] <= y <= window[3]:
            ax.text(x, y, s, fontsize=size, color="#222222", zorder=100)


def figure_for(window, base=9.0):
    w, h = window[1] - window[0], window[3] - window[2]
    return plt.subplots(figsize=(base, max(3.0, min(14.0, base * h / w))))


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    data = json.load(open(argv[1]))
    out = argv[2]
    os.makedirs(out, exist_ok=True)
    cfg = json.load(open(argv[3])) if len(argv) > 3 else {}
    order = cfg.get("order") or sorted(data["polys"], key=lambda k: int(k))
    order = [l for l in order if l in data["polys"]] + [l for l in sorted(data["polys"], key=int) if l not in order]
    x0, y0, x1, y1 = data["bbox"]
    m = 0.02 * max(x1 - x0, y1 - y0)
    full = (x0 - m, x1 + m, y0 - m, y1 + m)
    title = cfg.get("title", data.get("top", "layout"))
    written = []

    ov_layers = [l for l in order if l not in cfg.get("hide_in_overview", [])]
    fig, ax = figure_for(full, 10)
    draw(ax, data, ov_layers, full); legend(ax, data, ov_layers)
    ax.set_title("%s — all layers" % title, fontsize=11)
    p = os.path.join(out, "00_overview.png"); fig.savefig(p, dpi=200, bbox_inches="tight"); plt.close(fig)
    written.append(p)

    for k, lay in enumerate(order, 1):
        fig, ax = figure_for(full, 8)
        draw(ax, data, [lay], full)
        ax.set_title("%s — %s (layer %s)" % (title, style_for(data, lay, 0)[0], lay), fontsize=10)
        p = os.path.join(out, "%02d_layer_%s.png" % (k, lay)); fig.savefig(p, dpi=200, bbox_inches="tight"); plt.close(fig)
        written.append(p)

    for k, v in enumerate(cfg.get("views", []), 1):
        layers = [l for l in order if l in v.get("layers", order)]
        fig, ax = figure_for(v["window"])
        draw(ax, data, layers, v["window"], lw=0.6)
        if v.get("notes", True):
            notes(ax, data, v["window"], 7)
        ax.set_title(v.get("title", v["name"]), fontsize=10)
        p = os.path.join(out, "%02d_view_%s.png" % (50 + k, v["name"]))
        fig.savefig(p, dpi=200, bbox_inches="tight"); plt.close(fig)
        written.append(p)
    print("\n".join(written))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
