"""Generated appendix pages (reportlab, BSD licence) and the DRAFT stamp.

Sections, each only when it has real content: the pack's notices and officer-routed open items, X (form values
too long for their cell), N (the applicant's N/A reasons), B (the confirmed proposed alternative and scope),
P (confirmed applicant passages), C (one entry per Section C row: citation, attribution pairs with their
Division A text and table source, provision text, NBC 2020 intent statements labelled as explanatory only)
and D (every listed document). NRC prose in section C is the full provision text, with its citation and the
NRC publication link. A draft's to-do list and unanswered placeholders are not printed: they belong to the
questions and Review, and `ExportResult.open_items` keeps the list. With no real content there is no appendix.
"""
from __future__ import annotations

import io
import re
from datetime import date
from html import unescape
from xml.sax.saxutils import escape

from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ..copyright import NRC_PUBLICATION_URL
from ..jurisdictions import notices_for
from ..models import INTENT_LABEL, Case, SectionCRow
from ..process_fields import process_fields
from ..section_d import section_d_plan, supporting_documents, text_evidence
from .article_notes import benchmark, identify_quote, row_basis
from .edition import second_printing_proven
from .text import faithful_font_text

INK = colors.HexColor('#1f2328')
MUTED = colors.HexColor('#59636e')
RULE = colors.HexColor('#d0d7de')

H1 = ParagraphStyle('h1', fontName='Helvetica-Bold', fontSize=14, leading=18, textColor=INK, spaceAfter=4)
H2 = ParagraphStyle('h2', fontName='Helvetica-Bold', fontSize=11.5, leading=15, textColor=INK, spaceBefore=12,
                    spaceAfter=4, keepWithNext=True)
H3 = ParagraphStyle('h3', fontName='Helvetica-Bold', fontSize=10, leading=13, textColor=INK, spaceBefore=9,
                    spaceAfter=2, keepWithNext=True)
BODY = ParagraphStyle('body', fontName='Helvetica', fontSize=9, leading=12, textColor=INK, spaceAfter=3)
SMALL = ParagraphStyle('small', parent=BODY, fontSize=8, leading=10.5, textColor=MUTED)
CELL = ParagraphStyle('cell', parent=BODY, fontSize=8.5, leading=11, spaceAfter=0)
CODE = ParagraphStyle('code', parent=BODY, leftIndent=10, textColor=INK)


_CLAUSE_START = re.compile(r'\n(?=\s*(?:\d+\)|[a-z]{1,2}\)|[ivx]+\)|\(See ))')


def _reflow(text: str) -> str:
    """Join the PDF's hard line breaks, keeping a break before each sentence, clause or Note reference."""
    return _CLAUSE_START.sub('\x00', text).replace('\n', ' ').replace('\x00', '\n')


def _safe(text) -> str:
    """Keep numerical meaning when the official form's font lacks a scientific character."""
    return faithful_font_text(text)


def _p(text, style=BODY) -> Paragraph:
    return Paragraph(escape(_safe(text)).replace('\n', '<br/>'), style)


def _kv(label: str, value: str) -> Paragraph:
    return Paragraph(f'<b>{escape(label)}:</b> {escape(_safe(value))}', BODY)


def _table(header: list[str], rows: list[list[str]], widths: list[float]) -> Table:
    data = [[Paragraph(f'<b>{escape(h)}</b>', CELL) for h in header]]
    data += [[_p(c, CELL) for c in r] for r in rows]
    t = Table(data, colWidths=widths, repeatRows=1, hAlign='LEFT')
    t.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 0.5, RULE), ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f6f8fa')),
                           ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 4),
                           ('RIGHTPADDING', (0, 0), (-1, -1), 4), ('TOPPADDING', (0, 0), (-1, -1), 3),
                           ('BOTTOMPADDING', (0, 0), (-1, -1), 3)]))
    return t


def _nrc(text, citation: str) -> str:
    """Full code text, its citation, and the NRC publication link."""
    if not text:
        return ''
    body = str(text)
    parts = [body]
    if citation and citation not in body:
        parts.append(citation)
    if NRC_PUBLICATION_URL not in body:
        parts.append(NRC_PUBLICATION_URL)
    return ' '.join(parts)


_SOURCE_KIND = {'user_text': 'typed by the applicant', 'user_click': 'chosen by the applicant',
                'file': "a passage from the applicant's file"}


def _field_labels(fmap: dict) -> dict[str, str]:
    labels = {name: spec['label'] for name, spec in fmap.get('text_fields', {}).items()}
    for table, rows in (('Section C', fmap.get('section_c_rows', [])), ('Section D', fmap.get('section_d_rows', []))):
        for k, slot in enumerate(rows, start=1):
            labels.update({name: f'{table} row {k}' for name in slot.values()})
    return labels


def _row_story(k: int, row: SectionCRow, codes, in_form: bool, case: Case | None = None) -> list:
    out = [Paragraph(f'C-{k}&nbsp;&nbsp;{escape(row.provision_id)}', H3),
           _kv('Citation', row.citation),
           _kv('On the form', f'row {k}' if in_form else 'appendix only (more than five rows)')]
    if case is not None:
        out.append(_kv('How this row was identified', row_basis(case, row.provision_id)))
        quote = identify_quote(case, row.provision_id, codes)
        if quote:
            out.append(_kv('Identification quote (word for word in the code database)', _nrc(quote, row.citation)))
    status = row.attribution_status
    if row.attributed_via:
        status += f' ({row.attributed_via})'
    out.append(_kv('Attribution status', status))
    def statement(code: str, text) -> str:
        # Objectives and functional statements are Division A text: cite their own Division A sentence.
        own = codes.definition(code) if codes is not None else None
        return f'{code} {_nrc(text, (own or {}).get("citation") or row.citation)}'.strip()

    if row.pairs:
        out.append(_table(['Function', 'Objective', 'Source'],
                          [[statement(p.function, p.function_text),
                            statement(p.objective, p.objective_text),
                            f'NBC(AE) 2023 Div B {p.table}, PDF p. {p.pdf_page}'
                            + (f'; clauses {", ".join(p.clauses)}' if p.clauses else '')
                            + (f'; {_nrc(p.application_note, row.citation)}' if p.application_note else '')]
                           for p in row.pairs], [2.3 * inch, 2.3 * inch, 2.4 * inch]))
    else:
        out.append(_p('The NBC(AE) 2023 attribution table has no row for this provision, so no objective or '
                      'functional statement is attributed to it here.'))
    if codes is not None:
        rec = codes.provision(row.provision_id, 'B')
        if rec and rec.get('text'):
            out.append(_kv('Provision text', f'Article {rec["article"]} {rec["article_title"] or ""}'.strip()))
            out.append(_p(_nrc(_reflow(rec['text']), row.citation), CODE))
    out.append(Paragraph(f'<b>{escape(INTENT_LABEL)}</b>', BODY))
    if row.differs:
        out.append(_p('The national 2020 intent statement is attributed differently from NBC(AE) 2023.'
                      + (f' Only in the NBC 2020 Intent Statements entry for {row.provision_id}: '
                         f'{", ".join(row.only_in_intent)}.' if row.only_in_intent else '')
                      + (f' Only in NBC(AE) 2023, {row.provision_id}: {", ".join(row.only_in_ae)}.'
                         if row.only_in_ae else '')))
    if not row.intents:
        out.append(_p('No NBC 2020 intent statement was found for this provision.', SMALL))
    for blk in row.intents:
        head = f'{INTENT_LABEL}: {blk.provision_id}' + (f', objective {blk.objective}' if blk.objective else '') \
            + (f', attribution {"; ".join(blk.brackets)}' if blk.brackets else '') + f' (PDF p. {blk.pdf_page})'
        out.append(_p(head, SMALL))
        out += [_p(_nrc(t, row.citation), CODE) for t in blk.intents]
        out += [_p(f'Note: {_nrc(n, row.citation)}', SMALL) for n in blk.notes]
    return out


# The organizers' two names and the equivalence test (Div A 1.2.1.1.(1)(b)); no finding about the design.
PACKAGE_NOTE = ('This package has two parts. The request for variance is the application under section 38 of the '
                'Safety Codes Act; a Safety Codes Officer decides whether to issue a variance. The alternative '
                'solution (NBC(AE) 2023 Division C 2.3.1) is the evidence the proponent supplies to show that the '
                'proposed design achieves at least the level of performance of the acceptable solution it replaces, '
                'in the areas defined by the objectives and functional statements attributed to it (Division A '
                '1.2.1.1.(1)(b)). This appendix lists what the application cites and what the applicant wrote. It '
                'makes no finding about the design; the officer reviews it.')


def story_text(story: list) -> list[str]:
    """The appendix as plain text, one entry per paragraph and one ``| a | b |`` entry per table row, in reading
    order. This is the exported narrative the citation validator checks (paragraph-level, so a PDF line break
    never separates a citation from its document label)."""
    out: list[str] = []

    def plain(par: Paragraph) -> str:
        # A line break is a space in the rendered text; markup and entities are not text.
        markup = re.sub(r'<br\s*/?>', ' ', par.text)
        return ' '.join(unescape(re.sub(r'<[^>]+>', '', markup).replace('&nbsp;', ' ')).split())

    def walk(item):
        if isinstance(item, Paragraph):
            text = plain(item)
            if text:
                out.append(text)
        elif isinstance(item, Table):
            for row in item._cellvalues:
                cells = [plain(c) if isinstance(c, Paragraph) else str(c) for c in row]
                out.append('| ' + ' | '.join(cells) + ' |')
        elif isinstance(item, KeepTogether):
            for sub in item._content:
                walk(sub)
        elif isinstance(item, (list, tuple)):
            for sub in item:
                walk(sub)
    walk(story)
    return out


def build_appendix(case: Case, plan, values: dict, fmap: dict, *, codes=None,
                   package_notes: list[str] | None = None, text: list[str] | None = None) -> bytes | None:
    """Render the appendix PDF, or None when nothing real belongs in it. When ``text`` is a list, the
    appendix's plain text is appended to it."""
    story: list = []

    # Draft and final both carry the pack's notices. They inform; they never block an export.
    for notice in notices_for(case, 'export_appendix'):
        story += [Paragraph(escape(notice.heading), H2), _p(notice.message)]

    if package_notes:
        story += [Paragraph('Open items', H2),
                  _p('These items remain open. The officer decides them. This export does not close them.')]
        story += [_p(f'- {note}') for note in package_notes]

    if plan.overflow:
        story.append(Paragraph('X. Form values continued', H2))
        for ref, label, value in plan.overflow:
            story.append(KeepTogether([Paragraph(f'{escape(ref)}&nbsp;&nbsp;{escape(label)}', H3), _p(value)]))

    na = getattr(plan, 'na', {})
    if na:
        labels, groups = _field_labels(fmap), {}
        for name, entry in na.items():
            groups.setdefault(entry.fact_id, (entry, []))[1].append(labels.get(name, name))
        story += [Paragraph('N. Fields marked not applicable', H2),
                  _p('The applicant confirmed that these fields do not apply, so the form shows N/A. Batatis never '
                     'marks a field not applicable on its own, and a blank field is never shown as N/A.', SMALL),
                  _table(['Form field', "Applicant's reason", 'Source'],
                         [['; '.join(dict.fromkeys(names)), entry.reason, f'{entry.via} ({entry.source_ref})']
                          for entry, names in groups.values()], [2.2 * inch, 3.0 * inch, 1.8 * inch])]

    request = [_kv(label, str(values[key])) for label, key in
               (('Proposed alternative', 'alternative_description'), ('Scope', 'scope')) if key in values]
    if case.jurisdiction:
        request.append(_kv('Reviewing jurisdiction', case.jurisdiction.name))
    if request:
        story += [Paragraph('B. Request for variance: proposed alternative and scope', H2), *request]
    # Only confirmed passages, each under its own P-number; an unanswered field stays a question, not a page.
    answered = [(n, field) for n, field in enumerate(process_fields(case, codes), start=1)
                if field.answer] if codes is not None else []
    if answered:
        story.append(Paragraph('P. Alternative solution (Div C 2.3.1): applicant-written documentation', H2))
        story.append(_p('The following passages were supplied and confirmed by the applicant, each with its source. '
                        'Batatis supplies prompts and checks that each item is present; it does not write, assess or '
                        'validate the analysis.', SMALL))
        for n, field in answered:
            source = field.answer.source
            story.append(KeepTogether([
                Paragraph(f'P-{n}&nbsp;&nbsp;{escape(field.label)}', H3), _p(field.answer.value),
                _kv('Applicant source', source.ref + (f', page {source.page}' if source.page else '')),
                _kv('Provenance', f'{_SOURCE_KIND.get(source.type, source.type)}; confirmed by the '
                                  'applicant; not written by Batatis'),
                _p(field.citation, SMALL)]))

    bench = benchmark(case, codes)
    if case.section_c or bench:
        story.append(Paragraph('C. Attributions to acceptable solutions', H2))
    if case.section_c:
        story.append(_p('Each row is a Division B acceptable solution the proposal departs from. Its objectives and '
                        'functional statements come from the NBC(AE) 2023 attribution tables by lookup, not from a '
                        'model.', SMALL))
        story.append(_table(['Ref', 'Provision', 'How identified', 'Objectives', 'Functions'],
                            [[f'C-{k}', row.provision_id, row_basis(case, row.provision_id),
                              ', '.join(dict.fromkeys(p.objective for p in row.pairs)) or 'no table row',
                              ', '.join(dict.fromkeys(p.function for p in row.pairs)) or 'no table row']
                             for k, row in enumerate(case.section_c, start=1)],
                            [0.5 * inch, 1.1 * inch, 2.6 * inch, 1.4 * inch, 1.4 * inch]))
    if bench:
        story.append(Paragraph('Benchmark acceptable solution', H3))
        story.append(_kv('Benchmark', bench['citation']))
        story.append(_kv('Quoted sentence', _nrc(_reflow(bench['sentence']), bench['citation'])))
        story.append(_kv('Departure', bench['departure'] + ' (confirmed by the applicant)' if bench['departure']
                         else 'not yet confirmed by the applicant'))
    for k, row in enumerate(case.section_c, start=1):
        story += _row_story(k, row, codes, k <= plan.rows_in_form, case)

    docs = supporting_documents(case)
    attached = {doc.id for doc in docs}
    # A text listing is not a file. It is not reviewed, and it is not a file_ref document.
    # Typed listings use the form's own helper and numbering (files first, then typed text),
    # so every form row and every "see Appendix D" overflow reference has its entry here.
    typed = text_evidence(case)
    typed_titles = {title for title, _ in typed}
    text_items = [item for item in case.evidence if item.kind == 'text' and item.id not in attached
                  and item.description.strip() not in typed_titles]
    if docs or typed or text_items:
        story.append(Paragraph('D. Supporting documentation', H2))
    if docs or typed:
        on_form = lambda n: f'row {n}' if n <= plan.docs_in_form else 'appendix only'  # noqa: E731
        story.append(_table(['Ref', 'Name of supporting documentation', 'Responsible', 'On the form'],
                            [[f'D-{n}', d.title, d.responsible_party or '(not given)', on_form(n)]
                             for n, d in enumerate(docs, start=1)]
                            + [[f'D-{n}', title, who or '(not given)', f'{on_form(n)}; no file']
                               for n, (title, who) in enumerate(typed, start=len(docs) + 1)],
                            [0.5 * inch, 3.1 * inch, 2.4 * inch, 1.0 * inch]))
    if typed:
        first, last = len(docs) + 1, len(docs) + len(typed)
        refs = f'D-{first}' if first == last else f'D-{first} to D-{last}'
        story.append(_p(f'{refs}: listed by applicant, no file attached, not reviewed.', SMALL))
    if docs:
        evidence = section_d_plan(case, codes, docs) if codes is not None else None
        labels = {item.id: f'{item.provision_id}, {item.function or "no table function"} / '
                           f'{item.objective or "no table objective"}' for item in evidence.items} if evidence else {}
        for n, doc in enumerate(docs, start=1):
            block = [Paragraph(f'D-{n}&nbsp;&nbsp;Attachment and performance links', H3)]
            block += [_kv('File reference', doc.file.ref + (f', page {doc.file.page}' if doc.file.page else '')),
                      _kv('Issue/revision date', doc.date or '(not given)'), _kv('Issuer', doc.issuer or '(not given)')]
            if doc.professional_seal:
                block.append(_kv('Applicant-reported authentication', doc.professional_seal))
            linked = list(dict.fromkeys(labels[key] for key in doc.item_ids if key in labels))
            block.append(_kv('Section C performance issues addressed', '; '.join(linked) or '(no matched issue link)'))
            story.append(KeepTogether(block))
        story.append(_p('An attachment and its links record what the applicant supplied. The responsible designer '
                        'and the authority review its authenticity, scope, limitations and technical content.', SMALL))
    for item in text_items:
        story.append(KeepTogether([
            Paragraph(escape(item.description), H3),
            _p('listed by applicant, no file attached, not reviewed'),
        ]))
    if not story:
        return None
    printing = ', 2nd printing' if codes is not None and second_printing_proven(codes) else ''
    story[:0] = [Paragraph('Appendix to the Variance Form for Proposed Alternative Solution', H1),
                 _p(f'Case {case.title or ""} ({case.id}). Generated {date.today().isoformat()} by Batatis with '
                    f'field map {fmap["version"]}. Code references are to the National Building Code - 2023 '
                    f'Alberta Edition{printing} (NBC(AE) 2023).', SMALL),
                 _p(PACKAGE_NOTE, SMALL)]
    if text is not None:
        text.extend(story_text(story))
    buf = io.BytesIO()

    def footer(c: canvas.Canvas, doc):
        c.saveState()
        c.setFont('Helvetica', 7.5)
        c.setFillColor(MUTED)
        c.drawString(0.75 * inch, 0.5 * inch, f'Batatis appendix to SCC variance form - case {case.id}')
        c.drawRightString(letter[0] - 0.75 * inch, 0.5 * inch, f'Appendix page {doc.page}')
        c.restoreState()

    SimpleDocTemplate(buf, pagesize=letter, leftMargin=0.75 * inch, rightMargin=0.75 * inch, topMargin=0.75 * inch,
                      bottomMargin=0.8 * inch, title='Appendix', author='Batatis').build(
        story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()


def _draft_page(width: float, height: float):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(width, height))
    c.saveState()
    c.setFillColor(colors.Color(0.8, 0.1, 0.1, alpha=0.18))
    c.setFont('Helvetica-Bold', 120)
    c.translate(width / 2, height / 2)
    c.rotate(45)
    c.drawCentredString(0, -40, 'DRAFT')
    c.restoreState()
    c.setFillColor(colors.Color(0.7, 0.1, 0.1))
    c.setFont('Helvetica-Bold', 8)
    c.drawCentredString(width / 2, height - 22, 'DRAFT - not for submission; see appendix for review status')
    c.save()
    return PdfReader(io.BytesIO(buf.getvalue())).pages[0]


def stamp_draft(writer: PdfWriter) -> None:
    for page in writer.pages:
        page.merge_page(_draft_page(float(page.mediabox.width), float(page.mediabox.height)), over=True)
