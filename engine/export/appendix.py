"""Generated appendix pages (reportlab, BSD licence) and the DRAFT stamp.

Sections: X (form values too long for their cell), C (one entry per Section C row: citation, attribution
pairs with their Division A text and table source, provision text, NBC 2020 intent statements labelled as
explanatory only), D (every supporting document) and, for drafts, the open items that block a final export.
"""
from __future__ import annotations

import io
import re
from datetime import date
from xml.sax.saxutils import escape

from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ..models import INTENT_LABEL, Case, SectionCRow
from ..process_fields import process_fields
from ..section_d import applicant_statements, section_d_plan, supporting_documents
from .article_notes import notes_for
from .edition import edition_label
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


def _row_story(k: int, row: SectionCRow, codes, in_form: bool, case: Case | None = None) -> list:
    out = [Paragraph(f'C-{k}&nbsp;&nbsp;{escape(row.provision_id)}', H3),
           _kv('Citation', row.citation),
           _kv('On the form', f'row {k}' if in_form else 'appendix only (more than five rows)')]
    status = row.attribution_status
    if row.attributed_via:
        status += f' ({row.attributed_via})'
    out.append(_kv('Attribution status', status))
    if row.pairs:
        out.append(_table(['Function', 'Objective', 'Source'],
                          [[f'{p.function} {p.function_text or ""}'.strip(), f'{p.objective} {p.objective_text or ""}'.strip(),
                            f'{p.table}, NBC(AE) 2023 PDF p. {p.pdf_page}'
                            + (f'; clauses {", ".join(p.clauses)}' if p.clauses else '')
                            + (f'; {p.application_note}' if p.application_note else '')]
                           for p in row.pairs], [2.3 * inch, 2.3 * inch, 2.4 * inch]))
    else:
        out.append(_p('The NBC(AE) 2023 attribution table has no row for this provision, so no objective or '
                      'functional statement is attributed to it here.'))
    note = notes_for(case, row, codes) if case is not None else None
    if note is not None:
        out.append(_kv('Explainer', note.explainer))
        out.append(_kv('Benchmark acceptable solution', note.benchmark))
        if note.citation:
            out.append(_kv('Code database citation', note.citation))
        if note.source_url:
            out.append(_kv('NRC source', note.source_url))
    if codes is not None:
        rec = codes.provision(row.provision_id, 'B')
        if rec and rec.get('text'):
            out.append(_kv('Provision text', f'Article {rec["article"]} {rec["article_title"] or ""}'.strip()))
            out.append(_p(_reflow(rec['text']), CODE))
    out.append(Paragraph(f'<b>{escape(INTENT_LABEL)}</b>', BODY))
    if row.differs:
        out.append(_p('The national 2020 intent statement is attributed differently from NBC(AE) 2023.'
                      + (f' Only in the intent statement: {", ".join(row.only_in_intent)}.' if row.only_in_intent else '')
                      + (f' Only in NBC(AE) 2023: {", ".join(row.only_in_ae)}.' if row.only_in_ae else '')))
    if not row.intents:
        out.append(_p('No NBC 2020 intent statement was found for this provision.', SMALL))
    for blk in row.intents:
        head = f'{blk.provision_id}' + (f', objective {blk.objective}' if blk.objective else '') \
            + (f', attribution {"; ".join(blk.brackets)}' if blk.brackets else '') + f' (intent PDF p. {blk.pdf_page})'
        out.append(_p(head, SMALL))
        out += [_p(t, CODE) for t in blk.intents]
        out += [_p(f'Note: {n}', SMALL) for n in blk.notes]
    return out


def build_appendix(case: Case, plan, values: dict, fmap: dict, *, codes=None, open_items: list[str]) -> bytes:
    story: list = [Paragraph('Appendix to the Variance Form for Proposed Alternative Solution', H1),
                   _p(f'Case {case.title or ""} ({case.id}). Generated {date.today().isoformat()} by Batatis with '
                      f'field map {fmap["version"]}. Code references are to {edition_label(codes)}. '
                      'This appendix lists what the application cites; it does not state that the proposed design complies.',
                      SMALL)]

    if open_items:
        story += [Paragraph('Open items (draft export)', H2),
                  _p('This draft was exported before these items were resolved. Unconfirmed values are not shown '
                     'on the form.')]
        story += [_p(f'- {r}') for r in open_items]
        story.append(_p('Section C below was rebuilt from verified confirmed provisions. Unverified or changed '
                        'source text has been excluded; rebuilding does not resolve the listed open items.', SMALL))

    if plan.overflow:
        story.append(Paragraph('X. Form values continued', H2))
        for ref, label, value in plan.overflow:
            story.append(KeepTogether([Paragraph(f'{escape(ref)}&nbsp;&nbsp;{escape(label)}', H3), _p(value)]))

    story.append(Paragraph('B. Proposed alternative and scope', H2))
    for label, key in (('Proposed alternative', 'alternative_description'), ('Scope', 'scope')):
        story.append(_kv(label, str(values.get(key, '(not provided or not confirmed)'))))
    if case.jurisdiction:
        story.append(_kv('Reviewing jurisdiction', case.jurisdiction.name))
    if codes is not None:
        story.append(Paragraph('P. Applicant-written process fields', H2))
        story.append(_p('The following passages were supplied and confirmed by the applicant. Batatis supplies '
                        'prompts and checks presence; it does not author or validate the technical analysis.', SMALL))
        for n, field in enumerate(process_fields(case, codes), start=1):
            block = [Paragraph(f'P-{n}&nbsp;&nbsp;{escape(field.label)}', H3)]
            if field.answer:
                block.append(_p(field.answer.value))
                source = field.answer.source
                block.append(_kv('Applicant source', source.ref + (f', page {source.page}' if source.page else '')))
            else:
                block.append(_p('(Not provided or not confirmed. No answer has been supplied by Batatis.)'))
            block.append(_p(field.citation, SMALL))
            story.append(KeepTogether(block))

    story.append(Paragraph('C. Attributions to acceptable solutions', H2))
    if not case.section_c:
        story.append(_p('No provisions identified.'))
    for k, row in enumerate(case.section_c, start=1):
        story += _row_story(k, row, codes, k <= plan.rows_in_form, case)

    docs = supporting_documents(case)
    statements = applicant_statements(case)
    story.append(Paragraph('D. Supporting documentation', H2))
    if docs or statements:
        rows = [[f'D-{n}', d.title, d.responsible_party or '(not given)',
                 f'row {n}' if n <= plan.docs_in_form else 'appendix only']
                for n, d in enumerate(docs, start=1)]
        rows += [[f'D-{n}', f'{s.title} ({s.label})', s.responsible_party or '(not given)',
                  f'row {n}' if n <= plan.docs_in_form else 'appendix only']
                 for n, s in enumerate(statements, start=len(docs) + 1)]
        story.append(_table(['Ref', 'Name of supporting documentation', 'Responsible', 'On the form'],
                            rows, [0.5 * inch, 3.1 * inch, 2.4 * inch, 1.0 * inch]))
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
        for n, statement in enumerate(statements, start=len(docs) + 1):
            linked = list(dict.fromkeys(labels[key] for key in statement.item_ids if key in labels))
            story.append(KeepTogether([
                Paragraph(f'D-{n}&nbsp;&nbsp;Applicant-typed statement', H3),
                _kv('Label', statement.label),
                _p(statement.text),
                _kv('Source', statement.source_ref),
                _kv('Section C performance issues addressed', '; '.join(linked) or '(no matched issue link)'),
            ]))
        story.append(_p('An attachment and its links record what the applicant supplied. A statement labelled '
                        'stated by applicant, not verified is not a verified document and is not professional evidence. '
                        'The responsible designer and authority must review authenticity, scope, limitations and technical adequacy.',
                        SMALL))
    else:
        story.append(_p('No supporting documents listed.'))

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
