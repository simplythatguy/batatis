import re, html, pathlib, json
HERE = pathlib.Path(__file__).resolve()
OUT = HERE.parents[1]    # the deck folder (docs/pitch-deck/)
DOCS = HERE.parents[2]   # the folder holding pitch-slides.md and pitch-narration.md (docs/)
slides_md = (DOCS / "pitch-slides.md").read_text()
narr_md = (DOCS / "pitch-narration.md").read_text()

def inline(s):
    out, pos = [], 0
    for m in re.finditer(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", s):
        out.append(fmt(s[pos:m.start()]))
        out.append(f'<a href="{html.escape(m.group(2), quote=True)}">{fmt(m.group(1))}</a>')
        pos = m.end()
    out.append(fmt(s[pos:]))
    return "".join(out)

def fmt(s):
    s = html.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\w)\*([^*]+)\*(?!\w)", r"<em>\1</em>", s)
    return s

def chips(s):
    # wrap bracketed status labels in a styled span; text is unchanged
    return re.sub(r"(\[(?:if merged|case files)[^\]]*\])", r'<span class="status">\1</span>', s)

slides = []
for blk in re.split(r"^### Slide ", slides_md, flags=re.M)[1:]:
    lines = blk.strip().splitlines()
    num, title = re.match(r"(\d+): (.*)", lines[0]).groups()
    hero = next((l[len("**Hero:** "):] for l in lines if l.startswith("**Hero:** ")), None)
    if hero:
        hv, hl = [x.strip() for x in hero.split("|", 1)]
        hero = dict(value=hv, label=hl)
    # On-slide bullets come before the "Full slide detail" label; detail items come after it.
    bullets, detail, in_detail = [], [], False
    for l in lines:
        if l.startswith("**Full slide detail"):
            in_detail = True
        elif l.startswith("**Speaker notes:**"):
            in_detail = False
        elif l.startswith(("- ", "* ")):
            (detail if in_detail else bullets).append(l[2:])
    notes = next(l for l in lines if l.startswith("**Speaker notes:**"))[len("**Speaker notes:** "):]
    src = next(l for l in lines if l.startswith("*Sources:*"))[len("*Sources:* "):]
    slides.append(dict(n=int(num), title=title, hero=hero, bullets=bullets, detail=detail, notes=notes, sources=src))
assert len(slides) == 12

narr = {}
for blk in re.split(r"^### Slide ", narr_md, flags=re.M)[1:]:
    lines = blk.strip().splitlines()
    num, ntitle = re.match(r"(\d+): (.*)", lines[0]).groups()
    para = " ".join(l[2:] for l in lines if l.startswith("> "))
    timing = next((l for l in lines if l.startswith("**Time")), "")
    narr[int(num)] = dict(title=ntitle, text=para, timing=timing)
assert len(narr) == 12

SHOTS = {  # (placeholder id, on-slide caption of 6 words or fewer, alt text, EXAMPLE DATA tag). Built screens only.
 2: [("shot-s02-describe", "Describe: one box, one question", "Start screen with the headline and the description box", False),
     ("shot-s02-read", "Facts beside their source words", "A Check what we read card with the applicant's words marked and the Yes and No choices", True),
     ("shot-s02-planner", "Planner question and the fork note", "The first planner question with the fork note and the two halves of a variance", True),
     ("shot-s02-question", "One question at a time", "A question card with its reason under Why we ask", True)],
 4: [("shot-s04-progress", "Four stages while it checks", "The four stages of the code check with their counts", True),
     ("shot-s04-code-check", "A quoted choice, code shown", "A code check card with the verbatim sentence open under Show the code", True)],
 5: [("shot-s05-library", "Code library with relevance rings", "Code library reader with the relevance ring on an article", False)],
 6: [("shot-s06-engineer", "Engineer callout on the review", "Review screen with the engineer callout and Sections A to D", True)],
 7: [("shot-s07-queue", "Officer queue with claim", "Review queue with tabs and Start reviewing", True),
     ("shot-s07-sheet", "Paper sheet with completeness list", "An application as a paper sheet beside its completeness list", True)],
 8: [("shot-s08-onboarding", "Onboarding sets the applicant type", "Onboarding question: manufacturer, general contractor or homebuilder", False)],
 9: [("shot-s09-before-submit", "Before you submit, from the pack", "The review screen with the Before you submit disclosures open", True),
     ("shot-s09-application", "Draft or official PDF, gated", "Application screen with the download panel", True),
     ("shot-s09-scc-form", "Council form, officer part blank", "Downloaded SCC variance form, unsigned, officer Part 2 blank", True)],
}
EXAMPLE_SLIDES = set()
DENSE = set()

def title_html(t):
    m = re.match(r"(.*?)( \[[^\]]+\])$", t)
    if m:
        return f'{fmt(m.group(1))}<span class="rubric">{fmt(m.group(2))}</span>'
    return fmt(t)

def shot_html(sid, caption, alt, example):
    ex = '<span class="example-badge">EXAMPLE DATA</span>' if example else ""
    return f'''<figure class="shot" id="{sid}" data-shot="{sid}">
        <div class="shot-frame">
          <img class="shot-img" src="img/{sid}.png" alt="{html.escape(alt, quote=True)}" onload="this.closest('.shot').classList.add('has-img')" onerror="this.remove()">
          <div class="shot-placeholder" aria-hidden="true">
            <div class="shot-icon"></div>
            <div class="shot-pending">Screenshot pending</div>
          </div>
          {ex}
        </div>
        <figcaption class="shot-caption">{fmt(caption)}</figcaption>
      </figure>'''

def public_sources(src):
    links = [m for m in re.finditer(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", src) if "github.com" not in m.group(2)]
    if not links:
        return "in speaker notes"
    return "; ".join(f'<a href="{html.escape(m.group(2), quote=True)}">{fmt(m.group(1))}</a>' for m in links) + "; full list in speaker notes"

sec = []
for s in slides:
    n = s["n"]; shots = SHOTS.get(n, [])
    lay = ("layout-shot" + (" has-hero" if s["hero"] else "") + (" shots-2" if len(shots) > 1 else "") + (" dense" if n in DENSE else "")) if shots else "layout-text"
    lis = "\n".join(f"          <li>{chips(inline(b))}</li>" for b in s["bullets"])
    figs = "\n".join(shot_html(*x) for x in shots)
    ex = '<span class="example-badge slide-badge">EXAMPLE DATA</span>' if n in EXAMPLE_SLIDES else ""
    nr = narr[n]
    h = s["hero"]
    hero_html = f'<div class="hero"><span class="hero-num">{fmt(h["value"])}</span><span class="hero-label">{fmt(h["label"])}</span></div>' if h else ""
    det = ("<h3>Slide detail</h3><ul>" + "".join(f"<li>{inline(d)}</li>" for d in s["detail"]) + "</ul>") if s["detail"] else ""
    sec.append(f'''  <section class="slide {lay}" id="s{n:02d}" data-index="{n}">
    <header class="slide-head">
      <span class="brand">Batatis</span>{ex}
      <span class="slide-num">{n} / 12</span>
    </header>
    <h2 class="slide-title">{title_html(s["title"])}</h2>
    <div class="slide-body">
      <div class="bullets-wrap">
        {hero_html}
        <ul class="bullets">
{lis}
        </ul>
      </div>
      {('<div class="shots">' + figs + '</div>') if shots else ''}
    </div>
    <footer class="sources"><span class="sources-label">Sources:</span> {public_sources(s["sources"])}</footer>
    <aside class="notes" hidden>
      <h3>Narration</h3>
      <p class="narration">{fmt(nr["text"])}</p>
      <p class="timing">{fmt(nr["timing"])}</p>
      {det}
      <h3>Background</h3>
      <p>{inline(s["notes"])}</p>
      <h3>Sources</h3>
      <p>{inline(s["sources"])}</p>
    </aside>
  </section>''')

tpl = (OUT / ".build/template.html").read_text()
(OUT / "index.html").write_text(tpl.replace("<!--SLIDES-->", "\n".join(sec)))
print("ok")
