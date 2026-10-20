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
    bullets = [l[2:] for l in lines if l.startswith("- ")]
    detail = [l[2:] for l in lines if l.startswith("* ")]
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

SHOTS = {  # (placeholder id, on-slide caption of 6 words or fewer, alt text, EXAMPLE DATA tag)
 2: [("shot-s02-describe", "Describe screen lists gaps · in review", "Describe screen with a pasted homebuilder description and the gaps listed", True)],
 3: [("shot-s03-not-sure", "\u201cNot sure\u201d logged as questions · in review", "Code check cards answered Not sure and logged as open questions", True)],
 4: [("shot-s04-search", "Code search adds window article · in review", "Code search for the bedroom window article, added to the check", True),
     ("shot-s04-benchmark", "Identify output · draft, not in app", "Identify output and benchmark card from the draft build", True)],
 5: [("shot-s05-eval", "Evaluation results per variant · model-checked", "Evaluation results, one labelled line per variant", False)],
 6: [("shot-s06-section-d", "Section D leaves evidence blank · in review", "Alternative path with its fields left empty and the Section D card", True)],
 7: [("shot-s07-officer", "Officer review, open application · in review", "Officer review screen reviews the applicant's open application for administrative completeness", True)],
 8: [("shot-s08-roles", "\u201cWho are you?\u201d role picker · in review", "Role picker: Manufacturer, General contractor, Homebuilder", True)],
 9: [("shot-s09-locked", "Download locked while gaps open · in review", "Application screen: Check completeness opens a review; the official PDF stays locked while blocking gaps remain", True),
     ("shot-s09-scc-form", "Engine-filled SCC form · simulated session", "Downloaded engine-filled SCC variance form PDF, unsigned, officer Part 2 blank", True)],
}
EXAMPLE_SLIDES = {8}
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
