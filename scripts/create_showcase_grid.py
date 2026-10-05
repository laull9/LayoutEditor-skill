"""Build the README contact sheet from reproducible example previews."""
from pathlib import Path
import sys
from PIL import Image, ImageDraw, ImageFont, ImageOps
from matplotlib.font_manager import findfont


def create_grid(asset_dir):
    asset_dir = Path(asset_dir)
    items = [('prep_coupons.png', 'Data prep', 'Kelvin contacts + line/space monitor'),
             ('pic_ring_coupler.png', 'Photonics', 'Ring resonator / 200 nm coupling gap'),
             ('wafer_assembly.png', 'Mixed reticle', 'Resistor monitors + microfluidic mixers'),
             ('demo_core_overview.png', 'SOI MEMS', 'Comb actuator + isolation + release checks'),
             ('lvs_nand2.png', 'Extraction / LVS', 'CMOS NAND2 from a technology file'),
             ('lvs_verification.png', 'LVS results', 'Good layout passes; short and open fail')]
    cols, width, height, pad, head = 3, 600, 520, 24, 70
    rows = (len(items) + cols - 1) // cols
    canvas = Image.new('RGB', (cols * width + (cols + 1) * pad, rows * (height + head) + (rows + 1) * pad), '#eef1f5')
    draw = ImageDraw.Draw(canvas)
    title_font = ImageFont.truetype(findfont('DejaVu Sans'), 24)
    detail_font = ImageFont.truetype(findfont('DejaVu Sans'), 17)
    for i, (name, title, detail) in enumerate(items):
        x, y = pad + (i % cols) * (width + pad), pad + (i // cols) * (height + head + pad)
        draw.rectangle((x, y, x + width, y + head + height), fill='white')
        draw.text((x + 18, y + 9), title, font=title_font, fill='#1b293a')
        draw.text((x + 18, y + 41), detail, font=detail_font, fill='#526173')
        with Image.open(asset_dir / name) as source:
            fit = ImageOps.contain(source.convert('RGB'), (width, height), Image.Resampling.LANCZOS)
        canvas.paste(fit, (x + (width - fit.width) // 2, y + head + (height - fit.height) // 2))
    out = asset_dir / 'showcase_grid.png'
    canvas.save(out, optimize=True)
    print(out)


if __name__ == '__main__':
    create_grid(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / 'assets')
