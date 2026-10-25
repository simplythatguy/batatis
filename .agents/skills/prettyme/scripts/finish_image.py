#!/usr/bin/env python3
"""Clean up a generated diagram for a README.

Usage:
    finish_image.py IN.png OUT.png [--margin 32] [--gray]

Turns near-white specks pure white, trims the empty margins, and adds an even white border.
Use --gray only for a diagram that must be strictly black, white, and gray: it erases red,
stage tints, and logo colors. Needs Pillow (pip install pillow).
"""
import argparse
import sys

try:
    from PIL import Image, ImageChops
except ImportError:
    sys.exit('finish_image.py: needs Pillow. Install it with: python3 -m pip install pillow')

NEAR_WHITE = 246   # every channel at or above this becomes pure white
INK = 240          # anything darker than this counts as content when trimming


def finish(src, out, margin, gray):
    image = Image.open(src).convert('RGB')
    if gray:
        image = image.convert('L').convert('RGB')
    channels = [band.point(lambda value: 255 if value >= NEAR_WHITE else 0) for band in image.split()]
    near_white = ImageChops.multiply(ImageChops.multiply(channels[0], channels[1]), channels[2])
    image.paste((255, 255, 255), mask=near_white)
    ink = image.convert('L').point(lambda value: 255 if value < INK else 0)
    box = ink.getbbox()
    if box is None:
        raise SystemExit(f'{src} looks blank; nothing to keep.')
    content = image.crop(box)
    canvas = Image.new('RGB', (content.width + 2 * margin, content.height + 2 * margin), (255, 255, 255))
    canvas.paste(content, (margin, margin))
    canvas.save(out, optimize=True)
    return box, canvas.size


def main():
    parser = argparse.ArgumentParser(description='Clean up a generated README diagram.')
    parser.add_argument('src')
    parser.add_argument('out')
    parser.add_argument('--margin', type=int, default=32, help='white border in pixels (default 32)')
    parser.add_argument('--gray', action='store_true', help='make the image strictly grayscale')
    args = parser.parse_args()
    box, size = finish(args.src, args.out, args.margin, args.gray)
    print(f'{args.out}: kept {box}, saved at {size[0]} x {size[1]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
