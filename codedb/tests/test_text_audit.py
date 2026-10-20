from codedb.text_audit import Detector


def test_detector_learns_from_the_corpus_and_reports_each_artifact_class():
    corpus = ('Exposing building face means a wall.\n'
              'characteristic liquid compartments shall the characteristic liquid compartments shall the')
    detector = Detector([corpus])
    findings = detector.scan('characteri stic of t he liq-uid exposing building faceshall 0.1 L/(s×m 2)')
    assert ('split_words', 'characteri stic') in findings
    assert ('split_words', 't he') in findings
    assert ('glued_defined_terms', 'Exposing building faceshall'.lower()) in findings
    assert ('broken_units', 'm 2') in findings
    assert ('hyphen_remnants', 'liq-uid') in findings


def test_detector_does_not_treat_supported_words_or_native_units_as_repairs():
    detector = Detector(['a long fire resistance along long fire resistance along'])
    assert detector.scan('a long fire-resistance rating of 75 Pa and 60 ng/(Pa×s×m²)') == []
