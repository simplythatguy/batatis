#!/usr/bin/env python3
"""Download official logo artwork for a logo sheet.

Usage:
    fetch_logos.py OUT_DIR SPEC [SPEC ...]

Each SPEC is Label=source:name, with an optional :#RRGGBB color for single-color icons.

    Python=devicon:python                 devicon's full-color "original" SVG
    OpenAI=simpleicons:openai             Simple Icons' single-color SVG
    Claude=simpleicons:claude:#D97757     the same, recolored to the brand color
    Baseten=github:basetenlabs            a GitHub organization's avatar, as PNG
    Chrome=url:https://upload.wikimedia.org/wikipedia/commons/e/e1/Google_Chrome_icon_%28February_2022%29.svg

Each file is saved as OUT_DIR/<label>.svg or OUT_DIR/<label>.png. Look at every logo you
download. Some sources still ship old versions, such as Chrome's logo from before 2022.
"""
import os
import re
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

DEVICON = 'https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons/{0}/{0}-{1}.svg'
SIMPLE_ICONS = 'https://cdn.jsdelivr.net/npm/simple-icons@latest/icons/{0}.svg'
GITHUB_AVATAR = 'https://github.com/{0}.png?size=400'
AGENT = 'prettyme-fetch-logos/1.0 (+https://github.com/simplythatguy/prettyme.md)'


def tls_context():
    """Some Python builds, such as python.org's on macOS, ship without certificates."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        pass
    for bundle in ('/etc/ssl/cert.pem', '/etc/ssl/certs/ca-certificates.crt'):
        if os.path.isfile(bundle):
            return ssl.create_default_context(cafile=bundle)
    return ssl.create_default_context()


CONTEXT = tls_context()


def download(url):
    request = urllib.request.Request(url, headers={'User-Agent': AGENT})
    with urllib.request.urlopen(request, timeout=30, context=CONTEXT) as response:
        return response.read()


def slug(label):
    return re.sub(r'[^a-z0-9]+', '-', label.lower()).strip('-') or 'logo'


def fetch(spec):
    label, _, rest = spec.partition('=')
    source, _, name = rest.partition(':')
    if not label or not source or not name:
        raise ValueError(f'expected Label=source:name, got {spec!r}')
    if source == 'devicon':
        for variant in ('original', 'plain'):
            try:
                return label, download(DEVICON.format(name, variant)), 'svg'
            except urllib.error.HTTPError as error:
                if error.code not in (403, 404):
                    raise
        raise OSError(f'devicon has no original or plain icon named {name!r}')
    if source == 'simpleicons':
        name, _, color = name.partition(':')
        svg = download(SIMPLE_ICONS.format(name)).decode('utf-8')
        if color:
            if not re.fullmatch(r'#[0-9A-Fa-f]{6}', color):
                raise ValueError(f'color must look like #RRGGBB, got {color!r}')
            svg = svg.replace('<svg ', f'<svg fill="{color}" ', 1)
        return label, svg.encode('utf-8'), 'svg'
    if source == 'github':
        return label, download(GITHUB_AVATAR.format(name)), 'png'
    if source == 'url':
        data = download(name)
        kind = 'svg' if data.lstrip()[:5] in (b'<svg ', b'<?xml') or name.lower().split('?')[0].endswith('.svg') else 'png'
        return label, data, kind
    raise ValueError(f'unknown source {source!r}; use devicon, simpleicons, github, or url')


def main(argv):
    if len(argv) < 2:
        print(__doc__.strip())
        return 2
    out = Path(argv[0])
    out.mkdir(parents=True, exist_ok=True)
    failed = 0
    for spec in argv[1:]:
        try:
            label, data, kind = fetch(spec)
        except (OSError, ValueError) as error:
            print(f'failed  {spec}: {error}', file=sys.stderr)
            failed += 1
            continue
        path = out / f'{slug(label)}.{kind}'
        path.write_bytes(data)
        print(f'saved   {label} -> {path}')
    print('Next: compare every logo with the brand\'s current one before you use it.\n'
          '      Some sources still ship old versions. See references/diagram-style.md,\n'
          '      "Make sure every logo is current".')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
