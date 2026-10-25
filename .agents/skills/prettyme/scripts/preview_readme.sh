#!/bin/bash
# Show a README the way GitHub renders it: GitHub's Markdown API, GitHub's stylesheet, and a
# full-page screenshot.
# Usage: preview_readme.sh [README.md] [out.png] [owner/repo]
# Needs: gh (signed in), Chrome or Chromium, and a network connection. Set CHROME to choose
# a browser. Pillow, when installed, trims the empty space under the page.
set -euo pipefail

readme=${1:-README.md}
out=${2:-readme-preview.png}
repo=${3:-}
root=$(cd "$(dirname "$readme")" && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

find_chrome() {
  if [ -n "${CHROME:-}" ]; then echo "$CHROME"; return; fi
  for name in google-chrome google-chrome-stable chromium chromium-browser chrome; do
    if command -v "$name" >/dev/null 2>&1; then command -v "$name"; return; fi
  done
  for path in "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
              "/Applications/Chromium.app/Contents/MacOS/Chromium" \
              "$HOME"/Library/Caches/ms-playwright/chromium_headless_shell-*/*/chrome-headless-shell \
              "$HOME"/.cache/ms-playwright/chromium_headless_shell-*/*/chrome-headless-shell; do
    if [ -x "$path" ]; then echo "$path"; return; fi
  done
}

chrome=$(find_chrome || true)
if [ -z "$chrome" ]; then
  echo "preview: no Chrome or Chromium found; set CHROME=/path/to/chrome" >&2
  exit 1
fi

set -- -F "text=@$readme" -f mode=gfm
if [ -n "$repo" ]; then set -- "$@" -f "context=$repo"; fi
gh api markdown "$@" > "$work/body.html"
curl -fsSL https://cdn.jsdelivr.net/npm/github-markdown-css@5/github-markdown-light.css -o "$work/github.css"

python3 - "$work" "$root" <<'PY'
import pathlib, re, sys
work, root = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
body = (work / 'body.html').read_text()
def local(match):
    src = match.group(1)
    if src.startswith(('http://', 'https://', 'data:')):
        return match.group(0)
    return f'src="{(root / src).resolve().as_uri()}"'
body = re.sub(r'src="([^"]+)"', local, body)
(work / 'page.html').write_text(
    '<!doctype html><html><head><meta charset="utf-8">'
    f'<link rel="stylesheet" href="{(work / "github.css").as_uri()}">'
    '<style>body{margin:0;background:#fff}.markdown-body{box-sizing:border-box;'
    'max-width:1012px;margin:0 auto;padding:45px}</style></head>'
    f'<body><article class="markdown-body">{body}</article></body></html>')
PY

"$chrome" --headless --disable-gpu --hide-scrollbars --allow-file-access-from-files \
  --window-size=1100,20000 --screenshot="$out" "file://$work/page.html" >/dev/null 2>&1

python3 - "$out" <<'PY' || true
import sys
try:
    from PIL import Image
except ImportError:
    sys.exit(0)
image = Image.open(sys.argv[1]).convert('RGB')
box = image.convert('L').point(lambda v: 255 if v < 250 else 0).getbbox()
if box:
    image.crop((0, 0, image.width, min(image.height, box[3] + 40))).save(sys.argv[1])
PY
echo "preview: saved $out"
