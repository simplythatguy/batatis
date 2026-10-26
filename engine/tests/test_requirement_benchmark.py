"""Synthetic-source lifecycle checks, not real applicability answer keys."""
import sqlite3

from engine.identify.config import IdentifyConfig
from engine.identify.pipeline import run
from engine.models_identify import BenchmarkRecord
from engine.tests.test_requirement_identification import database, fact


def initial(tmp_path):
    codes = database(tmp_path, [('B', '9.1.1.1.', 'Egress', ['Egress openings require review.'])])
    result = run('egress', codes=codes, config=IdentifyConfig(screen='requirements'), facts=[fact('storeys', 2)]).result
    row = codes.provision('9.1.1.1.(1)', 'B')
    result.benchmark = BenchmarkRecord(identified=True, basis='applicant', provision='9.1.1.1.',
        provision_id=row['id'], citation=row['citation'], sentence=row['text'],
        departure='Use a different opening arrangement.', departure_status='confirmed')
    return codes, result


def test_unchanged_rerun_keeps_applicant_benchmark_and_departure(tmp_path):
    codes, previous = initial(tmp_path)
    result = run('egress', codes=codes, config=IdentifyConfig(screen='requirements'),
                 facts=[fact('storeys', 2)], previous=previous).result
    assert result.benchmark == previous.benchmark


def test_changed_facts_keep_the_departure_for_review_without_confirming_it(tmp_path):
    codes, previous = initial(tmp_path)
    result = run('egress', codes=codes, config=IdentifyConfig(screen='requirements'),
                 facts=[fact('storeys', 8)], previous=previous).result
    assert result.benchmark.departure == previous.benchmark.departure
    assert result.benchmark.departure_status == 'proposed' and not result.benchmark.identified
    assert result.benchmark.requirement is None and result.benchmark.question


def test_unverified_source_retains_human_prose_without_releasing_old_citations(tmp_path):
    codes, previous = initial(tmp_path)
    with sqlite3.connect(codes.db_path) as con:
        con.execute("UPDATE docs SET label='NBC(AE) 2023 p1' WHERE doc='NBC-AE'")
    result = run('egress', codes=codes, config=IdentifyConfig(screen='requirements'),
                 facts=[fact('storeys', 2)], previous=previous).result
    assert result.benchmark.departure == previous.benchmark.departure
    assert result.benchmark.citation is result.benchmark.sentence is result.benchmark.provision is None
    assert result.benchmark.departure_status == 'proposed' and not result.benchmark.identified
