"""Character inventory supplements source typography tests; it cannot prove formula recovery."""
import json
import re
import unicodedata

from codedb import store
from codedb.intents import parse_intents
from codedb.sources import BUILD_DIR


def digits(value):
    return ''.join(re.findall(r'\d', unicodedata.normalize('NFKC', value)))


def test_all_numeric_characters_survive_reading_text_reconstruction():
    con = store.connect()
    counts = {}
    mismatches = []
    try:
        for table, identifier in (('provisions', 'id'), ('notes', 'note_id')):
            rows = list(con.execute(f'SELECT division,{identifier},text_raw,text FROM {table}'))
            counts[table] = len(rows)
            mismatches.extend((table, r['division'], r[identifier]) for r in rows
                              if digits(r['text_raw']) != digits(r['text']))
        stored = {(r['source'], r['provision_id'], r['block_seq']): json.loads(r['intents'])
                  for r in con.execute('SELECT * FROM intents')}
    finally:
        con.close()
    counts['intents'] = 0
    # Heading numbers identify list entries, not numerical content. Decode the
    # JSON first and remove only the source's line-leading Intent N. headings.
    heading = re.compile(r'(?m)^[ \t]*I[ \t]*n[ \t]*t[ \t]*e[ \t]*n[ \t]*t[ \t]*(?:[0-9][ \t]*)+\.[ \t]*')
    for source in sorted({key[0] for key in stored}):
        for entry in parse_intents(source):
            for i, block in enumerate(entry.blocks):
                raw = heading.sub('', '\n'.join(block.intent_lines))
                reading = ' '.join(stored[(source, entry.provision, i)])
                counts['intents'] += 1
                if digits(raw) != digits(reading):
                    mismatches.append(('intents', source, entry.provision, i))
    assert counts['intents'] == len(stored)
    (BUILD_DIR / 'numerical-content.json').write_text(json.dumps({'checked': counts, 'mismatches': mismatches}, indent=2)+'\n')
    assert not mismatches, mismatches
