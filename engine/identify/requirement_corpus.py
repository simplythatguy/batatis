"""Verified, read-only NBC(AE) corpus for requirement discovery.

The scratch FTS index includes complete extracted passages, independently of the
persisted search index. Query chunking changes request size, never the hit set.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections import defaultdict
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from codedb import store
from engine.models_identify import RequirementEvidence, RequirementSource, Term

LABEL = 'NBC(AE) 2023 p2'
DOC = 'NBC-AE'
Key = tuple[str, str]
_SHA = re.compile(r'[0-9a-f]{64}')
_WORD = re.compile(r'[^\W_]+', re.UNICODE)
_STOP = frozenset('''a an and are as at be been being but by can could for from had has have if in into is it
its may might must not of on or our shall should than that the their them then there these they this those to
under was were what when where which while who will with within without would your you we all any each other
also only per via such some same more most no yes unknown confirmed unconfirmed proposed facts fact documents
document answers answer description project source field value status kind ref text file page id title user
building buildings requirement requirements code codes article articles sentence sentences division div
design proposed proposal request application alternative solution solutions acceptable include information
provided provide required applies apply'''.split())
LIMITS = [
    'Lexical matches and reference traversal are discovery methods, not proof that every applicable requirement was found.',
    'Applicability, departures, technical equivalence, safety and professional approval require human review.',
    'The scan covers extracted CodeDB provisions and notes; it does not establish that the extraction contains every PDF requirement.',
    'Notes are explanatory context. Table cells, appendices and referenced standards are not fully represented as searchable requirements.',
    'Reference parsing covers explicit numeric and local sentence/clause references; ranges, implicit exceptions and prose-only dependencies may need manual review.',
    'Registry metadata verifies edition and source identity, not a fresh PDF-to-extraction audit.',
]


class SourceUnavailable(ValueError):
    """A public, content-free reason the source cannot be used for citations."""


def words(text: str) -> list[str]:
    return list(dict.fromkeys(w.lower() for w in _WORD.findall(text)
                              if len(w) > 1 and not w.isdecimal() and w.lower() not in _STOP))


def qualified(key: Key) -> str:
    return f'{DOC}:{key[0]}:{key[1]}'


@dataclass
class Corpus:
    source: RequirementSource
    rows: dict[Key, dict]
    articles: dict[Key, dict]
    passages: list[dict]
    notes: list[dict]
    note_articles: dict[Key, list[Key]]
    by_article: dict[Key, list[dict]]
    attributions: dict[str, list[dict]]
    definitions: dict[str, dict]

    def article_key(self, division: str, pid: str) -> Key | None:
        row = self.rows.get((division, pid))
        if row is None:
            return None
        key = (division, row['article'] or row['id'])
        return key if key in self.articles else None

    def targets(self, division: str, pid: str) -> list[Key]:
        row = self.rows.get((division, pid))
        if row is None:
            return []
        key = self.article_key(division, pid)
        if key:
            return [key]
        return [k for k in self.articles if k[0] == division and k[1].startswith(pid)]

    def evidence(self, row: dict) -> RequirementEvidence:
        note = 'note_id' in row
        pid = row['note_id'] if note else row['id']
        heading = row.get('level') in ('article', 'section', 'subsection')
        kind = 'note' if note else 'heading' if heading else 'provision'
        quote = row.get(row.get('_matched_field', 'title' if heading else 'text')) or ''
        identity = json.dumps([self.source.text_sha256, row['division'], pid, kind, quote], ensure_ascii=False)
        return RequirementEvidence(
            id='e_' + hashlib.sha256(identity.encode()).hexdigest()[:24],
            division=row['division'], provision_id=pid, kind=kind,
            quote=quote,
            citation=self.citation(row), pdf_page=row.get('pdf_page'), pdf_page_end=row.get('pdf_page_end'),
            source_sha256=self.source.text_sha256, contextual=note)

    def citation(self, row: dict) -> str:
        note = 'note_id' in row
        return (f'{self.source.label}, Div {row["division"]}, '
                f'{"Note" if note else row["level"].title()} {row["note_id"] if note else row["id"]}'
                + (f' [PDF p.{row["pdf_page"]}]' if row.get('pdf_page') is not None else ''))

    def terms(self, article: str, pid: str | None = None) -> tuple[list[Term], list[Term], bool]:
        rows = self.attributions.get(article, [])
        if pid:
            rows = [r for r in rows if r['provision_id'] == pid or r['provision_id'].startswith(pid + '(')]
        def terms(field):
            codes = dict.fromkeys(code for row in rows for code in json.loads(row[field] or '[]'))
            return [Term(id=code, label=self.definitions.get(code, {}).get('title') or None) for code in codes]
        return terms('objectives'), terms('fs'), not rows

    def search(self, text: str) -> tuple[list[dict], int]:
        terms = words(text)
        if not terms:
            return [], 0
        # A connection belongs to this run; no cross-thread SQLite state is shared.
        with closing(sqlite3.connect(':memory:')) as con:
            con.execute("CREATE VIRTUAL TABLE fulltext USING fts5(i UNINDEXED, text, tokenize='porter unicode61')")
            searchable = [{**row, '_matched_field': field} for row in [*self.passages, *self.notes]
                          for field in ('title', 'text') if row.get(field)]
            con.executemany('INSERT INTO fulltext VALUES (?,?)',
                            ((i, row[row['_matched_field']])
                             for i, row in enumerate(searchable)))
            found = set()
            chunks = 0
            for start in range(0, len(terms), 64):
                chunks += 1
                query = ' OR '.join('"' + term.replace('"', '""') + '"' for term in terms[start:start + 64])
                found.update(r[0] for r in con.execute('SELECT i FROM fulltext WHERE fulltext MATCH ?', (query,)))
        return [searchable[i] for i in sorted(found)], chunks


def load(db_path: Path | str) -> Corpus:
    """Read a consistent snapshot. Never create, update or repair the supplied database."""
    try:
        with closing(store.connect(Path(db_path))) as con:
            con.execute('BEGIN')
            doc = con.execute('SELECT * FROM docs WHERE doc=?', (DOC,)).fetchone()
            metadata = dict(con.execute('SELECT key,value FROM meta'))
            stats = json.loads(metadata.get('stats', '{}'))
            src = stats.get('sources', {}).get(DOC, {})
            if (doc is None or doc['label'] != LABEL or doc['kind'] != 'code' or doc['citable'] != 1
                    or not _SHA.fullmatch(doc['sha256'] or '') or src.get('label') != LABEL
                    or src.get('text_sha256') != doc['sha256']
                    or not _SHA.fullmatch(src.get('pdf_sha256') or '')
                    or src.get('citable_as_alberta_law') is not True
                    or metadata.get('build_version') != '2' or stats.get('build_version') != '2'):
                raise SourceUnavailable('NBC(AE) 2023 second-printing provenance is absent or inconsistent.')
            rows = [dict(r) for r in con.execute(
                "SELECT * FROM provisions WHERE doc=? AND division IN ('A','B','C') ORDER BY division,sort_key,id", (DOC,))]
            notes = [dict(r) for r in con.execute(
                "SELECT * FROM notes WHERE doc=? AND division IN ('A','B','C') ORDER BY division,note_id", (DOC,))]
            links = [dict(r) for r in con.execute('SELECT * FROM note_links WHERE doc=?', (DOC,))]
            tables = [dict(r) for r in con.execute('SELECT * FROM code_tables WHERE doc=? ORDER BY division,table_id', (DOC,))]
            attributions = [dict(r) for r in con.execute('SELECT * FROM attributions WHERE doc=? ORDER BY article_id,seq,provision_id', (DOC,))]
            definitions = [dict(r) for r in con.execute('SELECT * FROM definitions WHERE doc=? ORDER BY code', (DOC,))]
        if not rows:
            raise SourceUnavailable('The verified source contains no extracted provisions.')
        digest = hashlib.sha256(json.dumps([rows, notes, links, tables, attributions, definitions], sort_keys=True,
                                           ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
        source = RequirementSource(text_sha256=doc['sha256'], pdf_sha256=src['pdf_sha256'],
                                   build_version=metadata['build_version'], corpus_sha256=digest)
    except SourceUnavailable:
        raise
    except (OSError, sqlite3.Error, ValueError, TypeError, KeyError, AttributeError) as exc:
        raise SourceUnavailable('The code source or its edition metadata could not be read.') from exc
    indexed = {(r['division'], r['id']): r for r in rows}
    arts = {k: r for k, r in indexed.items() if r['level'] == 'article'}
    by_article: dict[Key, list[dict]] = defaultdict(list)
    passages = []
    for row in rows:
        key = (row['division'], row['article'] or row['id'])
        if key in arts:
            by_article[key].append(row)
        if row['level'] in ('section', 'subsection', 'article', 'sentence'):
            passages.append(row)
        elif row['text']:
            # Parent sentences normally contain their clauses; retain orphan/additional text too.
            parent = indexed.get((row['division'], row['id'].split(')')[0] + ')'), {})
            flat = lambda text: ' '.join((text or '').split())
            if flat(row['text']) not in flat(parent.get('text')):
                passages.append(row)
    note_articles: dict[Key, list[Key]] = defaultdict(list)
    attrs: dict[str, list[dict]] = defaultdict(list)
    for row in attributions:
        attrs[row['article_id']].append(row)
    corpus = Corpus(source, indexed, arts, passages, notes, note_articles, dict(by_article),
                    dict(attrs), {r['code']: r for r in definitions})
    for link in links:
        for target in corpus.targets(link['division'], link['provision_id']):
            bucket = note_articles[(link['division'], link['note_id'])]
            if target not in bucket:
                bucket.append(target)
    # An unlinked note is retained by search, with a gap rather than a guessed normative target.
    return corpus
