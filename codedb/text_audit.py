"""Conservative, corpus-trained extraction warnings (not automatic corrections).

Run ``python -m codedb.text_audit --json --output codedb/build/text-audit.json``.
Use ``--dictionary-db codedb/build/before.sqlite`` for a fixed before/after
vocabulary. Counts are distinct flagged fragments per field, including repeated sentence/clause text;
warnings can be legitimate typography and require a source check.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from . import store

WORD = re.compile(r"[A-Za-z]+")
CATEGORIES = ("split_words", "glued_defined_terms", "broken_units", "hyphen_remnants")


@dataclass(frozen=True)
class Text:
    table: str
    identifier: str
    field: str
    page: int
    text: str


def read_texts(path=None) -> list[Text]:
    con = store.connect(path)
    out = []
    try:
        for table, identifier in (("provisions", "id"), ("notes", "note_id")):
            for r in con.execute(f"SELECT * FROM {table} ORDER BY doc,division,{identifier}"):
                for field in ("title", "text"):
                    out.append(Text(table, f"{r['doc']}/{r['division']}/{r[identifier]}",
                                    field, r['pdf_page'], r[field] or ""))
        for r in con.execute("SELECT * FROM intents ORDER BY source,provision_id,block_seq"):
            for field in ("intents", "attribution_notes"):
                for i, value in enumerate(json.loads(r[field])):
                    out.append(Text("intents", f"{r['source']}/{r['provision_id']}/{r['block_seq']}",
                                    f"{field}[{i}]", r['pdf_page'], value))
    finally:
        con.close()
    return out


class Detector:
    def __init__(self, texts):
        texts = list(texts)
        self.words = Counter(w.lower() for t in texts for w in WORD.findall(t))
        # Singletons are not reliable evidence that an extraction fragment is a word.
        self.dictionary = {w for w, n in self.words.items() if n >= 2 and len(w) > 1} | {'a', 'i'}
        terms = set()
        for t in texts:
            for m in re.finditer(r"(?m)^([A-Z][A-Za-z -]+?)(?: \([^\n)]*\))? means\b", t):
                terms.add(m[1].lower())
        self.terms = sorted(terms, key=lambda s: (-len(s), s))
        corpus = ' '.join(' '.join(t.split()) for t in texts)
        self.followers = {t: {m[1].lower() for m in re.finditer(
            r'\b' + re.escape(t) + r'\s+([a-z]+)\b', corpus, re.I)} for t in self.terms}
        self.glued = [(t, re.compile(r"\b" + re.escape(t) + r"([a-z]{2,})\b", re.I)) for t in self.terms]

    def scan(self, text):
        found = set()
        for line in text.splitlines():
            tokens = list(WORD.finditer(line))
            for i, start in enumerate(tokens):
                for n in (2, 3, 4):
                    group = tokens[i:i+n]
                    if len(group) != n or any(not line[a.end():b.start()].isspace()
                                              for a, b in zip(group, group[1:])):
                        continue
                    parts = [m[0].lower() for m in group]
                    if any(m[0].isupper() and len(m[0]) == 1 for m in group):
                        continue  # Division B, objective codes, and formula variables
                    joined = ''.join(parts)
                    if len(joined) >= 3 and joined in self.dictionary and any(
                            p not in self.dictionary for p in parts):
                        found.add(("split_words", line[start.start():group[-1].end()]))
            for term, rx in self.glued:
                for m in rx.finditer(line):
                    tail = m[0].split()[-1].lower()
                    usual = term.split()[-1]
                    known_word = tail in self.dictionary and self.words[tail] >= max(2, self.words[usual] / 10)
                    if not known_word and m[1].lower() in self.followers[term] and m[1].lower() in self.dictionary:
                        found.add(("glued_defined_terms", m[0]))
        for m in re.finditer(r"\b(?:m|mm|cm|km)\s*[23]\b|\bP\s+a\b|\b\d(?:\s+\d)+\s*P\s*a\b", text):
            found.add(("broken_units", m[0]))
        for m in re.finditer(r"\b([A-Za-z]{2,})-\s*([a-z]{2,})\b", text):
            a, b = m[1].lower(), m[2].lower()
            if a+b in self.dictionary and (a not in self.dictionary or b not in self.dictionary):
                found.add(("hyphen_remnants", m[0]))
        return sorted(found)


def audit(path=None, dictionary_path=None, examples=5):
    texts = read_texts(path)
    detector = Detector(t.text for t in (read_texts(dictionary_path) if dictionary_path else texts))
    counts = Counter({c: 0 for c in CATEGORIES})
    samples = defaultdict(list)
    for t in texts:
        for category, fragment in detector.scan(t.text):
            counts[category] += 1
            if examples < 0 or len(samples[category]) < examples:
                at = t.text.find(fragment)
                samples[category].append({'table': t.table, 'id': t.identifier, 'field': t.field,
                                          'pdf_page': t.page, 'fragment': fragment,
                                          'context': t.text[max(0, at-45):at+len(fragment)+65]})
    return {'counts': dict(counts), 'text_fields_scanned': len(texts),
            'dictionary_words': len(detector.dictionary), 'defined_terms': len(detector.terms),
            'examples': {c: samples[c] for c in CATEGORIES},
            'scope': 'Distinct flagged fragments per field, not confirmed errors; hierarchy text repeats.'}


def unaligned_sources(path=None):
    """List every body/intent line deliberately left unreconstructed.

    Full source text belongs only in ignored local outputs. This is separate from
    the heuristic warnings: a formula can be unalignable without looking like a
    broken word, and an unusual but correct word can trigger a heuristic warning.
    """
    from . import intents, textnorm
    con = store.connect(path)
    records = []
    source_keys = []
    try:
        for table, identifier in (("provisions", "id"), ("notes", "note_id")):
            for r in con.execute(f"SELECT * FROM {table} ORDER BY pdf_page,{identifier}"):
                value = textnorm.source_text(r['text_raw'], r['doc'], r['pdf_page'], r['pdf_page_end'])
                records.append((table, f"{r['doc']}/{r['division']}/{r[identifier]}",
                                r['pdf_page'], r['pdf_page_end'], value))
        source_keys = [r[0] for r in con.execute('SELECT DISTINCT source FROM intents ORDER BY source')]
    finally:
        con.close()
    for key in source_keys:
        for entry in intents.parse_intents(key):
            for i, block in enumerate(entry.blocks):
                value = textnorm.source_text('\n'.join(block.intent_lines), key, block.page, block.page_end)
                records.append(('intents', f'{key}/{entry.provision}/{i}', block.page, block.page_end, value))
                for note in block.attribution_notes:
                    records.append(('intent_notes', f'{key}/{entry.provision}/{i}', block.page, block.page_end, note))
    issues = []
    counts = Counter()
    for table, identifier, first, last, value in records:
        for line in value.unmatched:
            counts[table] += 1
            issues.append({'table': table, 'id': identifier, 'pdf_pages': [first, last], 'raw_line': line})
    return {'unreconstructed_lines': len(issues), 'by_table': dict(counts), 'lines': issues}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path)
    parser.add_argument('--dictionary-db', type=Path)
    parser.add_argument('--examples', type=int, default=5, help='-1 includes every warning')
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--unaligned-output', type=Path, help='Also list all unchanged, unalignable source lines')
    args = parser.parse_args()
    result = audit(args.db, args.dictionary_db, args.examples)
    if args.unaligned_output:
        unaligned = unaligned_sources(args.db)
        args.unaligned_output.write_text(json.dumps(unaligned, indent=2, ensure_ascii=False)+'\n', encoding='utf8')
        result['unreconstructed_source_lines'] = unaligned['unreconstructed_lines']
    payload = json.dumps(result, indent=2, ensure_ascii=False) + '\n'
    if args.output:
        args.output.write_text(payload, encoding='utf8')
    if args.json:
        print(payload, end='')
    else:
        print(f"Scanned {result['text_fields_scanned']} text fields; {result['dictionary_words']} corpus words")
        for category, count in result['counts'].items():
            print(f'{category}: {count}')
            for example in result['examples'][category]:
                print(f"  {example['id']} p.{example['pdf_page']}: {example['fragment']!r}")


if __name__ == '__main__':
    main()
