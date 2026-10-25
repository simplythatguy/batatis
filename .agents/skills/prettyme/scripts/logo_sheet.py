#!/usr/bin/env python3
"""Build a labeled logo sheet for the image model to copy from.

Usage:
    logo_sheet.py OUT.png "Label=path/to/logo.svg" ["Label=path/to/logo.png" ...] [--cols N]

Every logo is drawn the same size, with its label under it, on a white page. The sheet is
rendered with headless Chrome or Chromium. Set CHROME=/path/to/chrome to choose one. If no
browser is found, the HTML page is written next to OUT.png so that you can screenshot it.
"""
import glob
import html
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

CELL_W, LOGO, GAP_X, GAP_Y, PAD = 240, 120, 12, 28, 40


def find_chrome():
    if os.environ.get('CHROME'):
        return os.environ['CHROME']
    for name in ('google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser', 'chrome'):
        found = shutil.which(name)
        if found:
            return found
    home = Path.home()
    candidates = [
        '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        '/Applications/Chromium.app/Contents/MacOS/Chromium',
        *glob.glob(str(home / 'Library/Caches/ms-playwright/chromium_headless_shell-*/*/chrome-headless-shell')),
        *glob.glob(str(home / 'Library/Caches/ms-playwright/chromium-*/*/*.app/Contents/MacOS/*')),
        *glob.glob(str(home / '.cache/ms-playwright/chromium_headless_shell-*/*/chrome-headless-shell')),
        *glob.glob(str(home / '.cache/ms-playwright/chromium-*/chrome-linux*/chrome')),
    ]
    for candidate in candidates:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def page(items, cols):
    cells = ''.join(
        f'<div class="c"><div class="l"><img src="{Path(path).resolve().as_uri()}"></div>'
        f'<div class="t">{html.escape(label)}</div></div>'
        for label, path in items)
    return f'''<!doctype html><html><head><meta charset="utf-8"><style>
html,body{{margin:0;background:#fff}}
.g{{display:grid;grid-template-columns:repeat({cols},{CELL_W}px);gap:{GAP_Y}px {GAP_X}px;padding:{PAD}px}}
.c{{display:flex;flex-direction:column;align-items:center}}
.l{{width:{LOGO + 12}px;height:{LOGO + 12}px;display:flex;align-items:center;justify-content:center}}
.l img{{width:{LOGO}px;height:{LOGO}px;object-fit:contain}}
.t{{margin-top:14px;font:600 22px Helvetica,Arial,sans-serif;color:#111;text-align:center}}
</style></head><body><div class="g">{cells}</div></body></html>'''


def main(argv):
    cols = None
    if '--cols' in argv:
        index = argv.index('--cols')
        cols = int(argv[index + 1])
        del argv[index:index + 2]
    if len(argv) < 2:
        print(__doc__.strip())
        return 2
    out = Path(argv[0]).resolve()
    items = []
    for spec in argv[1:]:
        label, _, path = spec.partition('=')
        if not label or not Path(path).is_file():
            print(f'not a Label=existing-file pair: {spec!r}', file=sys.stderr)
            return 2
        items.append((label, path))
    cols = cols or min(6, len(items))
    rows = math.ceil(len(items) / cols)
    width = PAD * 2 + cols * CELL_W + (cols - 1) * GAP_X
    height = PAD * 2 + rows * (LOGO + 12 + 14 + 30) + (rows - 1) * GAP_Y
    html_path = out.with_suffix('.html')
    html_path.write_text(page(items, cols), encoding='utf-8')
    chrome = find_chrome()
    if not chrome:
        print(f'No Chrome or Chromium found. Open {html_path} and take a screenshot.', file=sys.stderr)
        return 1
    subprocess.run([chrome, '--headless', '--disable-gpu', '--hide-scrollbars', '--allow-file-access-from-files',
                    f'--window-size={width},{height}', f'--screenshot={out}', html_path.as_uri()],
                   check=True, capture_output=True)
    html_path.unlink()
    print(f'saved {out} ({len(items)} logos, {cols} per row). Look at it before you use it.')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
