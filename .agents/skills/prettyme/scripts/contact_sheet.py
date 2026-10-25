#!/usr/bin/env python3
"""Put every generated image on one labeled sheet, so the user can see all of them at once.

Usage:
    contact_sheet.py OUT.png "Label=path.png" ["Label=path.png:used" ...] [--cols 3]

Add :used to the images that went into the README; their labels are drawn darker.
Needs Pillow (pip install pillow).
"""
import sys

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    sys.exit('contact_sheet.py: needs Pillow. Install it with: python3 -m pip install pillow')

CELL_W, CELL_H, LABEL_H, PAD = 520, 400, 34, 16
FONTS = ('/System/Library/Fonts/Helvetica.ttc', '/Library/Fonts/Arial.ttf',
         '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'C:/Windows/Fonts/arial.ttf')


def font(size):
    for path in FONTS:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def main(argv):
    cols = 3
    if '--cols' in argv:
        index = argv.index('--cols')
        cols = int(argv[index + 1])
        del argv[index:index + 2]
    if len(argv) < 2:
        print(__doc__.strip())
        return 2
    items = []
    for spec in argv[1:]:
        label, _, rest = spec.partition('=')
        used = rest.endswith(':used')
        items.append((label, rest[:-5] if used else rest, used))
    rows = (len(items) + cols - 1) // cols
    sheet = Image.new('RGB', (PAD + cols * (CELL_W + PAD), PAD + rows * (LABEL_H + CELL_H + PAD)), 'white')
    draw = ImageDraw.Draw(sheet)
    label_font = font(20)
    for index, (label, path, used) in enumerate(items):
        x = PAD + (index % cols) * (CELL_W + PAD)
        y = PAD + (index // cols) * (LABEL_H + CELL_H + PAD)
        image = Image.open(path).convert('RGB')
        image.thumbnail((CELL_W, CELL_H), Image.LANCZOS)
        sheet.paste(image, (x + (CELL_W - image.width) // 2, y + LABEL_H + (CELL_H - image.height) // 2))
        draw.text((x, y + 6), label + ('  (used)' if used else ''), fill=(17, 17, 17) if used else (110, 110, 110), font=label_font)
        draw.rectangle((x, y + LABEL_H, x + CELL_W - 1, y + LABEL_H + CELL_H - 1), outline=(220, 220, 220))
    sheet.save(argv[0], optimize=True)
    print(f'saved {argv[0]} with {len(items)} images')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
