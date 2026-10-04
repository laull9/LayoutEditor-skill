#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
from PIL import Image, ImageDraw, ImageFont

# Load images
img1_path = "assets/demo_core_overview.png"
img2_path = "assets/pic_ring_coupler.png"
img3_path = "assets/wafer_assembly.png"
img4_path = "assets/prep_dual_chip.png"

im1 = Image.open(img1_path).convert("RGBA")
im2 = Image.open(img2_path).convert("RGBA")
im3 = Image.open(img3_path).convert("RGBA")
im4 = Image.open(img4_path).convert("RGBA")

# Cell size (width x height)
cell_w, cell_h = 800, 560
pad = 16
title_h = 36

# Overall grid: 2 cols x 2 rows
total_w = cell_w * 2 + pad * 3
total_h = (cell_h + title_h) * 2 + pad * 3

grid = Image.new("RGBA", (total_w, total_h), (255, 255, 255, 255))
draw = ImageDraw.Draw(grid)

# Try loading font, fallback to default
try:
    font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 20)
except Exception:
    font = ImageFont.load_default()

items = [
    (im4, "1. Mask Data Prep (Multi-GDS Merging & Booleans)", 0, 0),
    (im2, "2. Silicon Photonics (Ring Resonator 200 nm Gap)", 1, 0),
    (im3, "3. Wafer & Reticle Assembly (89-Die Array & Streets)", 0, 1),
    (im1, "4. MEMS & Micromachined Masks (Comb-Drive & Flexures)", 1, 1),
]

def fit_image(im, target_w, target_h):
    # Fit inside target_w x target_h with white background
    ratio = min(target_w / im.width, target_h / im.height)
    new_w = int(im.width * ratio)
    new_h = int(im.height * ratio)
    resized = im.resize((new_w, new_h), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (target_w, target_h), (250, 250, 252, 255))
    offset_x = (target_w - new_w) // 2
    offset_y = (target_h - new_h) // 2
    canvas.paste(resized, (offset_x, offset_y), resized)
    return canvas

for im, label, col, row in items:
    x = pad + col * (cell_w + pad)
    y = pad + row * (cell_h + title_h + pad)
    
    # Draw label
    draw.rectangle([x, y, x + cell_w, y + title_h], fill=(240, 243, 246, 255))
    draw.text((x + 12, y + 8), label, fill=(33, 37, 41, 255), font=font)
    
    # Draw fitted image
    fitted = fit_image(im, cell_w, cell_h)
    grid.paste(fitted, (x, y + title_h), fitted)
    
    # Border around the whole cell
    draw.rectangle([x, y, x + cell_w, y + title_h + cell_h], outline=(209, 213, 218, 255), width=1)

# Save as optimized PNG with adaptive palette
out_path = "assets/v0.2_showcase_grid.png"
rgb_grid = grid.convert("RGB")
im_q = rgb_grid.convert("P", palette=Image.Palette.ADAPTIVE, colors=256)
im_q.save(out_path, format="PNG", optimize=True)

size_kb = os.path.getsize(out_path) / 1024
print(f"Generated {out_path}: {size_kb:.1f} KB, size: {grid.size}")
