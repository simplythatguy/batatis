"""Package findings retain all applicant quotes, including those without a source record."""
from engine import completeness_policy
from engine.completeness_rules import QuoteSpan


def _quoting(monkeypatch, field, passages):
    original = completeness_policy._one

    def quoted(doc, spec, *args, **kwargs):
        element = original(doc, spec, *args, **kwargs)
        if element.field == field:
            element.quotes = [QuoteSpan(text=text, kind='exact', source_ref='synthetic-record') for text in passages]
        return element

    monkeypatch.setattr(completeness_policy, '_one', quoted)


def test_saved_review_keeps_all_quotes_without_sources(monkeypatch):
    from engine.codes import Codes
    from engine.review.package import review_case
    from engine.tests.case_builder_fixtures import complete_case
    case = complete_case()
    case.facts = [f for f in case.facts if f.field != 'rationale']
    passages = ['SYNTHETIC first complete source passage. ' * 30, 'SYNTHETIC second complete passage. ' * 30]
    _quoting(monkeypatch, 'rationale', passages)
    result = review_case(case, Codes())
    found = next(f for f in result.findings if f.field == 'rationale')
    quoted = [pointer for pointer in found.pointers if pointer.quote in passages]
    assert [pointer.quote for pointer in quoted] == passages
    assert {pointer.file for pointer in quoted} == {found.pointers[0].file}


def test_upload_review_keeps_all_source_less_quotes_at_the_field(monkeypatch):
    from engine.review.package import review_uploads
    from engine.tests.package_review_fixtures import CLEAN_FORM, package
    passages = ['SYNTHETIC first upload quote. ' * 30, 'SYNTHETIC second upload quote. ' * 30]
    _quoting(monkeypatch, 'owner_name', passages)
    result = review_uploads(package(dict(CLEAN_FORM, Owner='')), None)
    found = next(f for f in result.findings if f.field == 'owner_name')
    quoted = [pointer for pointer in found.pointers if pointer.quote in passages]
    assert [pointer.quote for pointer in quoted] == passages
    assert all(pointer.file == 'scc-form.pdf' and pointer.page == 1 for pointer in quoted)
