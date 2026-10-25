"""Gate G3 checks for the official SCC form export (AC9.1): coverage, citations, render and appendix content.

Each check returns a list of problems (empty means it passed), so `scripts/gate_g3.py` can print a summary and
`engine/tests/test_export_g3.py` can assert on the same functions. Nothing here changes a case or an export.
"""
from __future__ import annotations

import re
import tempfile
from pathlib import Path

from ..copyright import NRC_PUBLICATION_URL
from ..models import Case
from ..not_applicable import LABEL as NA_LABEL
from ..process_fields import process_fields
from .appendix import _reflow
from .scc import ExportResult, confirmed_values, load_field_map

# Words Batatis-authored export text must never use about the design (organizers' deck; AGENTS.md).
BANNED = re.compile(r'\b(?:complies|comply|compliant|safe|approved|approval|adequate|adequacy)\b', re.I)
FOOTER = re.compile(r'Batatis appendix to SCC variance form - case \S+\s+Appendix page \d+')


def norm(text: str) -> str:
    return ' '.join(str(text).split())


def applicant_fields(fmap: dict | None = None) -> list[str]:
    """Applicant fields for this template/layout; signatures and consent are excluded."""
    fmap = fmap or load_field_map()
    return [*fmap['text_fields'], *fmap['checkboxes'], *[f for r in fmap['section_c_rows'] for f in r.values()],
            *[f for r in fmap['section_d_rows'] for f in r.values()],
            *([fmap['supporting_document_field']] if fmap.get('supporting_document_field') else [])]


def coverage(case: Case, result: ExportResult, fmap: dict | None = None) -> dict[str, list[str]]:
    """Each applicant field is filled, N/A (from an applicant fact) or missing. A checkbox is filled when the
    applicant confirmed a yes or a no for it."""
    if fmap is None:
        fmap = load_field_map(result.field_map)
        if fmap.get('dynamic_attributions'):
            from .challenge_form import row_fields
            count = len(case.section_c)
            fmap['section_c_rows'] = [row_fields(i) for i in range(max(1, count))]
    values = confirmed_values(case)
    drawn = {p.field for p in result.placements}
    answered_boxes = {name for name, spec in fmap['checkboxes'].items()
                      if (values.get(spec['fact']) in spec['answers'] if 'answers' in spec
                          else isinstance(values.get(spec['fact']), bool))}
    out = {'filled': [], 'na': [], 'missing': []}
    for name in applicant_fields(fmap):
        if name in result.not_applicable:
            out['na'].append(name)
        elif name in drawn or name in answered_boxes:
            out['filled'].append(name)
        else:
            out['missing'].append(name)
    return out


def coverage_problems(case: Case, result: ExportResult, fmap: dict | None = None) -> list[str]:
    cov = coverage(case, result, fmap)
    problems = [f'{name} is blank' for name in cov['missing']]
    shown_na = {p.field for p in result.placements if p.lines == [NA_LABEL]}
    problems += [f'{name} shows N/A without an applicant fact' for name in shown_na - set(result.not_applicable)]
    return problems


def citation_report(result: ExportResult, *, db_path=None) -> dict:
    """Run the code-database validator (the same function as `python -m codedb validate`) over the exported text,
    written as Markdown with one paragraph per form value or appendix paragraph."""
    from codedb import validate
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'export.md'
        path.write_text('\n\n'.join(result.text) + '\n', encoding='utf-8')
        report = validate([path], db_path=db_path)
    return report


def citation_problems(result: ExportResult, *, db_path=None) -> list[str]:
    report = citation_report(result, db_path=db_path)
    return [f'{e["code"]} {e["citation"]}: {e["message"]}' for e in report['errors']]


def page_texts(pdf: bytes) -> list[str]:
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(pdf)
    return [doc[i].get_textpage().get_text_range() for i in range(len(doc))]


def appendix_text(result: ExportResult) -> str:
    return norm(' '.join(FOOTER.sub(' ', t) for t in page_texts(result.pdf)[result.form_pages:]))


def render_problems(result: ExportResult) -> list[str]:
    """Every shown line of every filled field is drawn on its page with each character inside the field box,
    and every value shown only as a reference is carried in full by the appendix."""
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(result.pdf)
    appendix = appendix_text(result)
    problems = []
    for pl in result.placements:
        tp = doc[pl.page].get_textpage()
        x0, y0, x1, y1 = pl.rect
        for line in pl.lines:
            searcher = tp.search(line, match_case=True)
            hits = []
            while (hit := searcher.get_next()) is not None:
                hits.append(hit)
            inside = [all(x0 - 0.5 <= b[0] and b[2] <= x1 + 0.5 and y0 - 0.5 <= b[1] and b[3] <= y1 + 0.5
                          for b in (tp.get_charbox(i) for i in range(start, start + count)) if b[2] > b[0])
                      for start, count in hits]
            if not any(inside):
                problems.append(f'{pl.field}: "{line}" is not drawn inside its box on page {pl.page + 1}')
        if norm(' '.join(pl.lines)) != norm(pl.value) and not (pl.ref and norm(pl.value) in appendix):
            problems.append(f'{pl.field}: the full value is not in the appendix')
    return problems


def appendix_problems(case: Case, result: ExportResult, codes) -> list[str]:
    """Section C rows (provision, lookup objectives and functions, quoted sentence, how identified) and the six
    process rows (answer, applicant source, provenance) are in the rendered appendix; every appendix paragraph
    the validator checked is the text the PDF shows."""
    text = appendix_text(result)
    problems = []
    for k, row in enumerate(case.section_c, start=1):
        if f'C-{k} {row.provision_id}' not in text:
            problems.append(f'Section C row C-{k} {row.provision_id} is not in the appendix')
        for p in row.pairs:
            for code in (p.objective, p.function):
                if code not in text:
                    problems.append(f'C-{k}: {code} is not in the appendix')
        rec = codes.provision(row.provision_id, 'B')
        if rec and rec.get('text') and norm(_reflow(rec['text'])) not in text:
            problems.append(f'C-{k}: the quoted sentence of {row.provision_id} is not in the appendix')
        if 'How this row was identified:' not in text:
            problems.append('Section C rows do not say how they were identified')
    for n, field in enumerate(process_fields(case, codes), start=1):
        if field.answer is None:
            problems.append(f'process field {field.id} has no applicant answer')
            continue
        block = f'P-{n} {field.label} {norm(field.answer.value)} Applicant source: {field.answer.source.ref}'
        if block not in text:
            problems.append(f'process row P-{n} {field.label} with its source is not in the appendix')
    if 'Provenance:' not in text:
        problems.append('process rows carry no provenance')
    for paragraph in result.appendix_text:
        if paragraph.startswith('|'):
            continue                                          # table cells wrap independently; rows checked above
        if norm(paragraph) not in text:
            problems.append(f'appendix paragraph not rendered as validated: {paragraph[:80]}')
    return problems


def wording_problems(case: Case, result: ExportResult) -> list[str]:
    """Batatis-authored text never says complies, safe, approved or adequate. Quoted code text (it carries the
    NRC link) is the code's own wording, and applicant passages are the applicant's; neither is checked."""
    applicant = [norm(v) for v in confirmed_values(case).values() if isinstance(v, str) and len(v) > 12]
    out = []
    for paragraph in result.text:
        flat = norm(paragraph)
        if NRC_PUBLICATION_URL in paragraph or any(v in flat for v in applicant):
            continue
        hit = BANNED.search(paragraph)
        if hit:
            out.append(f'"{hit.group()}" in: {paragraph[:100]}')
    return out


def check_case(case: Case, result: ExportResult, codes) -> dict[str, list[str]]:
    return {'fields': coverage_problems(case, result), 'citations': citation_problems(result, db_path=codes.db_path),
            'render': render_problems(result), 'appendix': appendix_problems(case, result, codes),
            'wording': wording_problems(case, result)}
