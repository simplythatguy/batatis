"""Package findings retain all applicant quotes, including those without a source record."""

def test_saved_review_keeps_all_quotes_without_sources(monkeypatch):
    from engine.codes import Codes
    from engine.completeness_report import QuoteModel, saved_case_response
    from engine.review.package import review_case
    from engine.tests.case_builder_fixtures import complete_case
    case = complete_case()
    case.facts = [f for f in case.facts if f.field != 'rationale']
    report = saved_case_response(case, Codes(), 'B')
    element = next(e for r in report.reviews for s in r.sections for e in s.elements if e.field == 'rationale')
    passages = ['SYNTHETIC first complete source passage. ' * 30, 'SYNTHETIC second complete passage. ' * 30]
    element.quotes = [QuoteModel(text=text, kind='exact', source_ref='synthetic-record', source={}) for text in passages]
    monkeypatch.setattr('engine.completeness_report.saved_case_response', lambda *args: report)
    result = review_case(case, Codes())
    found = next(f for f in result.findings if f.field == 'rationale')
    assert [pointer.quote for pointer in found.pointers if pointer.quote in passages] == passages
    assert all(pointer.file == 'case:' + case.id for pointer in found.pointers)


def test_upload_review_keeps_all_source_less_quotes_at_the_field(monkeypatch):
    from engine.completeness_variants import QuoteSpan
    from engine.review import package as package_review
    from engine.tests.package_review_fixtures import CLEAN_FORM, package
    original = package_review.run_variant
    passages = ['SYNTHETIC first upload quote. ' * 30, 'SYNTHETIC second upload quote. ' * 30]

    def quoted(*args):
        result = original(*args)
        element = next(e for e in result.elements if e.field == 'owner_name')
        element.quotes = [QuoteSpan(text=text, kind='exact', source_ref='form.pdf') for text in passages]
        return result

    monkeypatch.setattr(package_review, 'run_variant', quoted)
    result = package_review.review_uploads(package(dict(CLEAN_FORM, Owner='')), None)
    found = next(f for f in result.findings if f.field == 'owner_name')
    quoted = [pointer for pointer in found.pointers if pointer.quote in passages]
    assert [pointer.quote for pointer in quoted] == passages
    assert all(pointer.file == 'scc-form.pdf' and pointer.page == 1 for pointer in quoted)

