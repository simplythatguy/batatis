#!/usr/bin/env python3
"""Check a README against the prettyme rules.

Usage:
    check_readme.py [README.md]

Errors (exit code 1): a local link or image that points at a missing file, an image with no
alt text, or more than one h1. Warnings: code-block lines over 92 characters, dashes,
semicolons, curly quotes, and filler words in prose, Title Case headings, and a missing
horizontal rule between the two halves. Uses only the Python standard library.
"""
import re
import sys
from pathlib import Path
from urllib.parse import unquote

MAX_CODE_LINE = 92
FILLER = ('simply', 'just', 'easy', 'quickly', 'seamless', 'seamlessly', 'robust', 'powerful',
          'leverage', 'leverages', 'utilize', 'utilizes', 'facilitate', 'facilitates', 'delve',
          'crucial', 'showcase', 'showcases', 'cutting-edge', 'state-of-the-art')
SMALL = {'a', 'an', 'and', 'as', 'at', 'by', 'for', 'in', 'of', 'on', 'or', 'the', 'to', 'with'}


def prose_lines(lines):
    """Yield (number, text) for lines outside fenced code, with inline code removed."""
    fenced = False
    for number, line in enumerate(lines, 1):
        if line.lstrip().startswith('```'):
            fenced = not fenced
            continue
        if not fenced:
            yield number, re.sub(r'`[^`]*`', '', line)


def code_lines(lines):
    fenced = False
    for number, line in enumerate(lines, 1):
        if line.lstrip().startswith('```'):
            fenced = not fenced
            continue
        if fenced:
            yield number, line


def check(path):
    readme = Path(path)
    root = readme.parent
    lines = readme.read_text(encoding='utf-8').splitlines()
    errors, warnings = [], []

    for number, text in prose_lines(lines):
        for alt, target in re.findall(r'!\[([^\]]*)\]\(([^)\s]+)\)', text):
            if not alt.strip():
                errors.append(f'{number}: image {target} has no alt text')
        for target in re.findall(r'\]\(([^)\s]+)\)', text):
            if target.startswith(('http://', 'https://', 'mailto:', '#')):
                continue
            local = unquote(target.split('#')[0])
            if local and not (root / local).exists():
                errors.append(f'{number}: link target {target} does not exist')
        if '—' in text or '–' in text:
            warnings.append(f'{number}: dash in prose; use a period or a comma')
        if re.search(r'[‘’“”]', text):
            warnings.append(f'{number}: curly quotes; use straight quotes')
        if ';' in re.sub(r'&\w+;|<[^>]+>|\]\([^)]*\)', '', text) and not text.lstrip().startswith('|'):
            warnings.append(f'{number}: semicolon in prose; start a new sentence')
        for word in FILLER:
            if re.search(rf'\b{re.escape(word)}\b', text, re.IGNORECASE):
                warnings.append(f'{number}: filler word "{word}"')
        heading = re.match(r'#{2,6} (.+)', text)
        if heading:
            words = [w for w in re.findall(r"[A-Za-z][\w'-]*", heading.group(1))[1:] if w.lower() not in SMALL]
            capitalized = [w for w in words if w[0].isupper() and not w.isupper()]
            if len(words) >= 2 and len(capitalized) == len(words):
                warnings.append(f'{number}: heading may be Title Case; use sentence case (proper nouns are fine)')

    h1 = [n for n, t in prose_lines(lines) if re.match(r'# \S', t)]
    if len(h1) > 1:
        errors.append(f'more than one h1 (lines {h1})')
    if not any(t.strip() == '---' for _, t in prose_lines(lines)):
        warnings.append('no "---" line divides the plain half from the technical half')
    for number, line in code_lines(lines):
        if len(line) > MAX_CODE_LINE:
            warnings.append(f'{number}: code line is {len(line)} characters; GitHub will not wrap it')
    return errors, warnings


def main(argv):
    path = argv[0] if argv else 'README.md'
    errors, warnings = check(path)
    for message in errors:
        print(f'error    {message}')
    for message in warnings:
        print(f'warning  {message}')
    print(f'{path}: {len(errors)} errors, {len(warnings)} warnings')
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
