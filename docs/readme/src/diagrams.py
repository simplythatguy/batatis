#!/usr/bin/env python3
"""Draw the README diagrams as SVG and render them to PNG with headless Chromium.

Usage:
    .venv/bin/python docs/readme/src/diagrams.py [solution how-it-works path results ...]

With no names it draws all of them. Each diagram is written as docs/readme/src/<name>.html,
rendered at twice its size, then trimmed and given a 32 px white border by the prettyme
skill's finish_image.py. The solution and how-it-works diagrams share one layout, so their
nodes always match. The logos in logos/ are official artwork (see logos/SOURCES.md).
"""
from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from html import escape
from pathlib import Path

SRC = Path(__file__).resolve().parent
ROOT = SRC.parents[2]
FINISH = ROOT / '.agents/skills/prettyme/scripts/finish_image.py'

FONT = "'Helvetica Neue', Helvetica, Arial, sans-serif"
INK, OUTLINE, LINE, MUTED, FAINT = '#111111', '#3A3A3A', '#555555', '#6B6B6B', '#B8B8B8'
TINT = {'blue': '#EAF2FD', 'violet': '#F1ECFB', 'green': '#E8F5EC', 'amber': '#FDF3E0',
        'white': '#FFFFFF', 'gray': '#E5E5E5'}


class Svg:
    def __init__(self, width: int, height: int):
        self.width, self.height, self.parts = width, height, []

    def add(self, part: str) -> None:
        self.parts.append(part)

    def text(self, x, y, lines: str, size=17, weight=400, color=INK, anchor='middle') -> None:
        rows = lines.split('\n')
        step = size * 1.28
        top = y - (len(rows) - 1) * step / 2
        for n, row in enumerate(rows):
            self.add(f'<text x="{x:.1f}" y="{top + n * step:.1f}" font-size="{size}" font-weight="{weight}" '
                     f'fill="{color}" text-anchor="{anchor}" dominant-baseline="central">{escape(row)}</text>')

    def rect(self, x, y, w, h, fill='white', stroke=OUTLINE, width=1.5, radius=6) -> None:
        self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{radius}" '
                 f'fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>')

    def path(self, d: str, color=LINE, width=1.25, arrow=False) -> None:
        marker = f' marker-end="url(#{"arrow" if color == LINE else "arrow-" + color[1:]})"' if arrow else ''
        self.add(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}"{marker}/>')

    def image(self, href: str, x, y, size) -> None:
        self.add(f'<image href="{href}" x="{x:.1f}" y="{y:.1f}" width="{size}" height="{size}" '
                 f'preserveAspectRatio="xMidYMid meet"/>')

    def html(self) -> str:
        defs = ''.join(
            f'<marker id="{name}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
            f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{color}"/></marker>'
            for name, color in (('arrow', LINE),))
        body = '\n'.join(self.parts)
        return (f'<!doctype html><html><head><meta charset="utf-8"><style>html,body{{margin:0;background:#fff}}'
                f'svg{{display:block;font-family:{FONT}}}</style></head><body>'
                f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" height="{self.height}" '
                f'viewBox="0 0 {self.width} {self.height}"><defs>{defs}</defs>'
                f'<rect width="100%" height="100%" fill="#fff"/>{body}</svg></body></html>')


@dataclass
class Node:
    cx: float
    cy: float
    w: float
    h: float
    label: str
    tint: str = 'white'
    diamond: bool = False

    @property
    def top(self): return (self.cx, self.cy - self.h / 2)
    @property
    def bottom(self): return (self.cx, self.cy + self.h / 2)
    @property
    def left(self): return (self.cx - self.w / 2, self.cy)
    @property
    def right(self): return (self.cx + self.w / 2, self.cy)


def draw_node(svg: Svg, node: Node, size=17) -> None:
    fill = TINT[node.tint]
    if node.diamond:
        x, y, w, h = node.cx, node.cy, node.w / 2, node.h / 2
        svg.add(f'<path d="M{x},{y - h} L{x + w},{y} L{x},{y + h} L{x - w},{y} Z" fill="{fill}" '
                f'stroke="{OUTLINE}" stroke-width="1.5" stroke-linejoin="round"/>')
    else:
        svg.rect(node.cx - node.w / 2, node.cy - node.h / 2, node.w, node.h, fill=fill)
    svg.text(node.cx, node.cy, node.label, size=size)


def arrow(svg: Svg, a, b, color=LINE) -> None:
    svg.path(f'M{a[0]:.1f},{a[1]:.1f} L{b[0]:.1f},{b[1]:.1f}', color=color, arrow=True)


def fan(svg: Svg, parent, child) -> None:
    """A smooth curve from a parent's bottom to a child's top, with no arrowhead."""
    (x1, y1), (x2, y2) = parent, child
    mid = (y1 + y2) / 2
    svg.path(f'M{x1:.1f},{y1:.1f} C{x1:.1f},{mid:.1f} {x2:.1f},{mid:.1f} {x2:.1f},{y2:.1f}')


# ---------------------------------------------------------------- solution and how it works

GAP = 50
BOX_W, BOX_H = 148, 70
DIAMOND = 144


@dataclass
class Tech:
    label: str
    logos: tuple[str, ...]


def flow(row1: float, row2: float) -> dict[str, Node]:
    xs, x = [], 268
    for kind in ('box', 'box', 'box', 'box', 'box', 'box', 'diamond', 'box'):
        width = DIAMOND if kind == 'diamond' else BOX_W
        if xs:
            x += GAP + width / 2
        xs.append(x)
        x += width / 2
    n = {
        'describe': Node(xs[0], row1, BOX_W, BOX_H, 'Describe the\nproject', 'blue'),
        'answer': Node(xs[1], row1, BOX_W, BOX_H, 'Answer a few\nquestions', 'blue'),
        'confirm': Node(xs[2], row1, BOX_W, BOX_H, 'Confirm the\ncode articles', 'violet'),
        'sectionc': Node(xs[3], row1, BOX_W, BOX_H, 'Section C\nfills itself in', 'violet'),
        'drafts': Node(xs[4], row1, BOX_W, BOX_H, 'Review the\ndrafted case', 'green'),
        'evidence': Node(xs[5], row1, BOX_W, BOX_H, 'Plan the\nevidence', 'green'),
        'missing': Node(xs[6], row1, DIAMOND, DIAMOND, 'Anything\nmissing?', 'green', diamond=True),
        'submit': Node(xs[7], row1, BOX_W, BOX_H, 'Submit the\nofficial form', 'green'),
    }
    n['pick'] = Node(xs[7], row2, BOX_W, BOX_H, 'Pick it up\nfrom the queue', 'amber')
    n['review'] = Node(xs[7] - 360, row2, BOX_W + 14, BOX_H, 'Review the\napplication', 'amber')
    n['decide'] = Node(xs[7] - 740, row2, DIAMOND + 10, DIAMOND + 10, 'Decide', 'amber', diamond=True)
    n['close'] = Node(xs[1] + 20, row2, BOX_W, BOX_H, 'Close-out', 'amber')
    return n


REVIEW_PARTS = ('Form view', 'Missing items', 'Code checks')
CAPTIONS = {
    'describe': 'Type or drop in PDFs',
    'answer': 'One at a time',
    'confirm': 'Found, ranked, compared',
    'sectionc': 'Looked up from the code',
    'drafts': 'Six statements, one screen',
    'evidence': 'Flags when an engineer\nis needed',
}
TECH = {
    'describe': [Tech('Rules read facts,\nSonnet reviews', ('python', 'claude'))],
    'answer': [Tech('Rules pick up\nto 5 questions', ('python',))],
    'confirm': [Tech('Searches the\ncode text', ('sqlite',)), Tech('Haiku searches\nand ranks', ('claude',))],
    'drafts': [Tech('Sonnet drafts,\nchecks sources', ('claude',))],
    'sectionc': [Tech('Lookup in\nCodeDB', ('sqlite',))],
    'evidence': [Tech('Evidence rules,\nno AI', ('python',))],
    'missing': [Tech('Completeness\nrules', ('python',))],
    'submit': [Tech('Fills the\nCouncil PDF', ('python',))],
    'pick': [Tech('Queue and\nclaims', ('fastapi',))],
    'close': [Tech('Record for\nthe Council', ('python',))],
}
REVIEW_TECH = (('react',), ('python',), ('sqlite',))
LOGO = {'python': 'python.svg', 'react': 'react.svg', 'typescript': 'typescript.svg', 'vite': 'vite.svg',
        'fastapi': 'fastapi.svg', 'sqlite': 'sqlite.svg', 'postgresql': 'postgresql.svg', 'neon': 'neon.png',
        'claude': 'claude.svg', 'vercel': 'vercel.svg', 'xai': 'xai.svg'}


def logos_row(svg: Svg, names, cx, y, size=30, gap=10) -> None:
    total = len(names) * size + (len(names) - 1) * gap
    x = cx - total / 2
    for name in names:
        svg.image(f'logos/{LOGO[name]}', x, y, size)
        x += size + gap


def tech_box(svg: Svg, cx, top, tech: Tech, tint: str, w=96, h=96) -> None:
    w = max(w, 40 * len(tech.logos) + 34)
    svg.rect(cx - w / 2, top, w, h, fill=TINT[tint], width=1.2)
    svg.text(cx, top + 25, tech.label, size=12.5)
    logos_row(svg, tech.logos, cx, top + h - 42)


def loops(svg: Svg, n: dict[str, Node], top_y: float, low_y: float) -> None:
    """The arrows shared by both diagrams: the main flow, the two loops and the officer row."""
    order = ['describe', 'answer', 'confirm', 'sectionc', 'drafts', 'evidence', 'missing']
    for a, b in zip(order, order[1:]):
        arrow(svg, n[a].right, n[b].left)
    arrow(svg, n['missing'].right, n['submit'].left)
    mx, my = n['missing'].right
    svg.text((mx + n['submit'].left[0]) / 2, my - 16, 'No', size=15, color=MUTED)
    # "Yes" loops from the diamond's top back to the questions.
    x1, y1 = n['missing'].top
    x2, y2 = n['answer'].top
    svg.path(f'M{x1},{y1} C{x1},{top_y} {x1 - 30},{top_y} {x1 - 60},{top_y} L{x2 + 40},{top_y} '
             f'C{x2},{top_y} {x2},{top_y + 10} {x2},{y2 - 1}', arrow=True)
    svg.text((x1 + x2) / 2, top_y - 14, 'Yes', size=15, color=MUTED)
    # The officer row runs right to left.
    arrow(svg, n['submit'].bottom, n['pick'].top)
    arrow(svg, n['pick'].left, n['review'].right)
    arrow(svg, n['review'].left, n['decide'].right)
    arrow(svg, n['decide'].left, n['close'].right)
    dx, dy = n['decide'].left
    svg.text((dx + n['close'].right[0]) / 2, dy - 16, 'Accept as complete', size=15, color=MUTED)
    # "Return with a message" runs below the applicant row, then rises between the first two steps.
    x1, y1 = n['decide'].top
    rise = n['describe'].right[0] + 12
    entry_y = n['answer'].cy + 22
    end_x = n['answer'].left[0] - 1
    svg.path(f'M{x1},{y1} C{x1},{low_y + 30} {x1 - 20},{low_y} {x1 - 60},{low_y} L{rise + 30},{low_y} '
             f'C{rise},{low_y} {rise},{low_y - 10} {rise},{low_y - 30} L{rise},{entry_y + 18} '
             f'C{rise},{entry_y} {rise + 8},{entry_y} {end_x},{entry_y}', arrow=True)
    svg.text((x1 + rise) / 2, low_y - 14, 'Return with a message', size=15, color=MUTED)


def solution() -> Svg:
    svg = Svg(1900, 760)
    n = flow(row1=170, row2=520)
    loops(svg, n, top_y=70, low_y=300)
    for node in n.values():
        draw_node(svg, node)
    for key, caption in CAPTIONS.items():
        svg.text(n[key].cx, n[key].bottom[1] + 26 + 9 * caption.count('\n'), caption, size=14, color=MUTED)
    review = n['review']
    for k, part in enumerate(REVIEW_PARTS):
        cx = review.cx + (k - 1) * 150
        fan(svg, review.bottom, (cx, review.bottom[1] + 90))
        svg.rect(cx - 66, review.bottom[1] + 90, 132, 48, fill=TINT['amber'])
        svg.text(cx, review.bottom[1] + 114, part, size=15)
    svg.text(40, n['describe'].cy, 'Applicant', size=24, weight=700, anchor='start')
    svg.text(40, n['close'].cy, 'Safety Codes\nOfficer', size=24, weight=700, anchor='start')
    return svg


def how_it_works() -> Svg:
    svg = Svg(1900, 1180)
    n = flow(row1=360, row2=760)
    # Header: where it runs.
    svg.rect(330, 26, 600, 156, width=1.2, radius=8)
    svg.image('logos/vercel.svg', 352, 40, 26)
    svg.text(388, 54, 'Vercel', size=17, weight=700, anchor='start')
    svg.rect(352, 84, 250, 80, width=1.2)
    svg.text(477, 104, 'Web app', size=15)
    logos_row(svg, ('react', 'typescript', 'vite'), 477, 120, size=32, gap=18)
    svg.rect(660, 84, 250, 80, width=1.2)
    svg.text(785, 104, 'Engine API', size=15)
    logos_row(svg, ('python', 'fastapi'), 785, 120, size=32, gap=18)
    arrow(svg, (602, 124), (659, 124))
    for x, label, logo in ((970, 'Assistant', 'claude'), (1110, 'Voice', 'xai')):
        svg.rect(x, 60, 120, 104, width=1.2)
        svg.text(x + 60, 82, label, size=15)
        svg.image(f'logos/{LOGO[logo]}', x + 42, 100, 36)
    loops(svg, n, top_y=252, low_y=590)
    for node in n.values():
        draw_node(svg, node)
    for key, techs in TECH.items():
        node = n[key]
        top = node.bottom[1] + 46
        offsets = [0] if len(techs) == 1 else [-52, 52]
        for off, tech in zip(offsets, techs):
            fan(svg, node.bottom, (node.cx + off, top))
            tech_box(svg, node.cx + off, top, tech, node.tint)
    review = n['review']
    for k, (part, logos) in enumerate(zip(REVIEW_PARTS, REVIEW_TECH)):
        cx = review.cx + (k - 1) * 120
        top = review.bottom[1] + 46
        fan(svg, review.bottom, (cx, top))
        tech_box(svg, cx, top, Tech(part, logos), 'amber', w=110, h=86)
    # Footer: where the data lives.
    svg.rect(560, 1010, 470, 150, width=1.2, radius=8)
    svg.text(795, 1034, 'Applications and accounts', size=16)
    for x, w, label, logos in ((584, 170, 'Local', ('sqlite',)), (778, 228, 'Hosted', ('postgresql', 'neon'))):
        svg.rect(x, 1056, w, 88, width=1.2)
        logos_row(svg, logos, x + w / 2, 1066, size=40, gap=16)
        svg.text(x + w / 2, 1126, label, size=15)
    svg.text(40, n['describe'].cy, 'Applicant', size=24, weight=700, anchor='start')
    svg.text(40, n['close'].cy, 'Safety Codes\nOfficer', size=24, weight=700, anchor='start')
    return svg


# ---------------------------------------------------------------- which package the applicant prepares

LADDER = ("Manufacturer's literature", 'Existing STANDATA variance', 'Test report (ISO 17025)', 'Evaluation',
          'Evaluation plus testing', 'Qualification', 'Certification (ISO 17065)')        # engine/section_d.py
ALTERNATIVE_EXTRA = ('CCMC evaluation', 'ICC-ES evaluation', 'Registered professional opinion', 'Engineering review')
STATEMENTS = ('Rationale', 'Risk assessment', 'Mitigating measures', 'Assumptions and limits',
              'Maintenance and operation', 'Qualifications')                            # engine/process_fields.py


def list_box(svg: Svg, cx, top, w, title, items, faded=()) -> float:
    """A box with a title and one item per line. Returns its bottom."""
    h = 52 + 22 * len(items)
    svg.rect(cx - w / 2, top, w, h)
    svg.text(cx, top + 22, title, size=16)
    svg.path(f'M{cx - w / 2 + 14},{top + 40} L{cx + w / 2 - 14},{top + 40}', color='#D6D6D6', width=1)
    for k, item in enumerate(items):
        svg.text(cx, top + 56 + 22 * k, item, size=14, color=MUTED if item in faded else '#333333')
    return top + h


def path_decision() -> Svg:
    svg = Svg(1580, 1150)
    row = 110
    design = Node(80, row, 120, 56, 'Your design', 'gray')
    scope = Node(290, row, 176, 136, 'Building-code\nquestion?', diamond=True)
    facts = Node(510, row, 168, 70, 'Use the facts\nalready written')
    rule = Node(750, row, 214, 70, 'One coded rule asks\nonly what it still needs')
    fork = Node(1050, row, 214, 176, 'Meets or exceeds\nthe acceptable\nsolution?', diamond=True)
    other = Node(290, 300, 196, 62, 'Another safety code.\nStop, no package.')
    for a, b in ((design, scope), (scope, facts), (facts, rule), (rule, fork)):
        arrow(svg, a.right, b.left)
    arrow(svg, scope.bottom, other.top, color=FAINT)
    svg.text(scope.cx + 12, (scope.bottom[1] + other.top[1]) / 2, 'No', size=15, color=MUTED, anchor='start')
    svg.text(rule.cx, rule.bottom[1] + 34, "A rule that doesn't apply\nis set aside", size=14, color=MUTED)
    for node in (design, scope, facts, rule, fork):
        draw_node(svg, node, size=16)
    svg.rect(other.cx - other.w / 2, other.cy - other.h / 2, other.w, other.h, stroke=FAINT)
    svg.text(other.cx, other.cy, other.label, size=15, color=MUTED)
    # Three outcomes fan out from the fork.
    top = 330
    left_x, mid_x, right_x = 700, 1050, 1340
    stop = Node(mid_x, top + 44, 200, 88, 'Not decided. Stop\nand name the\nmissing fact.')
    for x, label, dx in ((left_x, 'Yes: acceptable solution', -16), (mid_x, 'Not sure', 10),
                         (right_x, 'No: alternative solution', 16)):
        fx, fy = fork.bottom
        svg.path(f'M{fx},{fy} C{fx},{fy + 70} {x},{top - 80} {x},{top - 2}', arrow=True)
        svg.text(x + dx, top - 26, label, size=15, color=MUTED, anchor='end' if dx < 0 else 'start')
    ladder_bottom = list_box(svg, left_x, top, 300, 'Shared evidence ladder', LADDER)
    permit = Node(left_x, ladder_bottom + 80, 200, 56, 'Permit paperwork')
    arrow(svg, (left_x, ladder_bottom), permit.top)
    draw_node(svg, permit, size=16)
    draw_node(svg, stop, size=15)
    statements_bottom = list_box(svg, right_x, top, 280, 'Six process statements', STATEMENTS)
    evidence_top = statements_bottom + 46
    arrow(svg, (right_x, statements_bottom), (right_x, evidence_top))
    evidence_bottom = list_box(svg, right_x, evidence_top, 280, 'Evidence types to discuss',
                               LADDER + ALTERNATIVE_EXTRA)
    paperwork = Node(right_x, evidence_bottom + 74, 250, 64, 'Paperwork: one site,\nor municipality-wide')
    arrow(svg, (right_x, evidence_bottom), paperwork.top)
    draw_node(svg, paperwork, size=15)
    review = Node(mid_x, paperwork.cy + 120, 300, 70, 'Administrative review only.\nNot a technical decision.', 'gray')
    for node in (permit, paperwork):
        x, y = node.bottom
        svg.path(f'M{x},{y} C{x},{review.cy - 10} {x},{review.cy} '
                 f'{review.left[0] - 1 if x < mid_x else review.right[0] + 1},{review.cy}', arrow=True)
    draw_node(svg, review, size=16)
    svg.height = int(review.bottom[1] + 30)
    return svg


# ---------------------------------------------------------------- results chart

# experiments/workflow-bakeoff-v2/RESULTS.md: estimated minutes and the blind grade out of 10.
RESULTS = [
    # label, (first-time minutes, grade), (expert minutes, grade), winner
    ('Official flowchart, asked as a form', (24.2, 2.0), (50.5, 4.9), False),
    ('Our earlier flow', (29.0, 3.4), (38.1, 5.9), False),
    ("App does the flowchart's steps", (16.4, 4.4), (18.8, 5.8), False),
    ('App drafts, at most 3 questions', (12.1, 5.2), (15.6, 6.4), False),
    ('App analyses and drafts, you review', (20.6, 5.6), (27.3, 7.5), True),
]
HIGHLIGHT, OTHER = '#1F5FCC', '#A3A3A3'

# Where each label sits relative to its dot, per panel: (dx, dy, anchor).
LABEL_AT = [
    {0: (16, 0, 'start'), 1: (16, 0, 'start'), 2: (16, 6, 'start'), 3: (16, 12, 'start'), 4: (16, -8, 'start')},
    {0: (-16, 0, 'end'), 1: (16, 0, 'start'), 2: (16, 14, 'start'), 3: (16, -10, 'start'), 4: (16, -4, 'start')},
]


def results() -> Svg:
    """Two panels stacked, so each gets the full width and its labels stay readable in a README."""
    svg = Svg(1400, 1200)
    panels = (('First-time applicant', 1), ('Expert with the code book', 2))
    left, w, h = 130, 1220, 420
    for p, (title, k) in enumerate(panels):
        top = 70 + p * 590
        x = lambda minutes: left + minutes / 60 * w
        y = lambda grade: top + h - grade / 10 * h
        svg.text(left, top - 40, title, size=26, weight=700, anchor='start')
        for g in range(0, 11, 2):
            svg.path(f'M{left},{y(g):.1f} L{left + w},{y(g):.1f}', color='#ECECEC', width=1)
            svg.text(left - 16, y(g), str(g), size=18, color=MUTED, anchor='end')
        for m in range(0, 61, 10):
            svg.text(x(m), top + h + 26, str(m), size=18, color=MUTED)
        svg.path(f'M{left},{top + h} L{left + w},{top + h}', color='#8A8A8A', width=1)
        svg.text(left + w / 2, top + h + 62, 'Applicant time, minutes (estimated)', size=19, color=MUTED)
        svg.add(f'<text transform="translate(52,{top + h / 2}) rotate(-90)" font-size="19" fill="{MUTED}" '
                f'text-anchor="middle" dominant-baseline="central">Grade out of 10</text>')
        svg.text(left + 16, top + 18, '↖ better: higher grade, less time', size=17, color=MUTED, anchor='start')
        for i, row in enumerate(RESULTS):
            minutes, grade = row[k]
            winner = row[3]
            dx, dy, anchor = LABEL_AT[p][i]
            color = HIGHLIGHT if winner else OTHER
            radius = 11 if winner else 9
            svg.add(f'<circle cx="{x(minutes):.1f}" cy="{y(grade):.1f}" r="{radius}" fill="{color}" '
                    f'stroke="#fff" stroke-width="2"/>')
            svg.text(x(minutes) + dx, y(grade) + dy, f'{row[0]}  {grade:.1f}', size=21,
                     weight=700 if winner else 400, color=INK if winner else '#4A4A4A', anchor=anchor)
    return svg


# ---------------------------------------------------------------- render

DIAGRAMS = {'solution': (solution, ROOT / 'docs/readme/solution.png'),
            'how-it-works': (how_it_works, ROOT / 'docs/readme/how-it-works.png'),
            'path': (path_decision, ROOT / 'docs/diagrams/applicant-path-decision.png'),
            'results': (results, ROOT / 'docs/readme/workflow-results.png')}


def render(names: list[str]) -> None:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for name in names:
            build, out = DIAGRAMS[name]
            svg = build()
            page_file = SRC / f'{name}.html'
            page_file.write_text(svg.html())
            page = browser.new_page(viewport={'width': svg.width, 'height': svg.height}, device_scale_factor=2)
            page.goto(page_file.as_uri())
            page.wait_for_load_state('networkidle')
            raw = SRC / f'{name}.raw.png'
            page.locator('svg').screenshot(path=str(raw))
            page.close()
            subprocess.run([sys.executable, str(FINISH), str(raw), str(out)], check=True)
            raw.unlink()
            print('drew', out.relative_to(ROOT))
        browser.close()


if __name__ == '__main__':
    render(sys.argv[1:] or list(DIAGRAMS))
