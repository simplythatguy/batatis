# Code database and citation gate

Local, read-only queries over **NBC(AE) 2023, second printing**, Volumes 1 and 2, plus explicitly explanatory NBC 2020 intent statements. Run commands from the repository root. Source text, SQLite, exports, and audit page captures remain inside this repository under the ignored `codedb/build/` directory.

## Start and rebuild

```sh
.venv/bin/python -m pip install -r codedb/requirements.txt
.venv/bin/python -m codedb build
.venv/bin/python -m pytest codedb/tests -q
.venv/bin/python -m codedb.audit
```

The standalone requirements include `pypdfium2>=5.14.0,<6` for glyph positions,
effective font sizes and baselines during text reconstruction (verified with 5.14.0).
Install `codedb/requirements.txt` to rebuild; the engine requirements are not needed.
Reading an existing database does not require PDFium.

Rebuild requires both PDFs and their per-page JSONL extracts at the paths registered in `codedb/sources.py`. It parses attribution tables using PDF coordinates, preserves source page numbers, and writes:

- `codedb/build/codedb.sqlite`: schema/build version 2, replaced atomically after a successful build.
- `codedb/build/export/*.jsonl`: one export per domain table; JSON columns become native arrays.
- `codedb/build/stats.json`: coverage and parse diagnostics, with PDF and extracted-text SHA-256 fingerprints.

The same sources and implementation produce identical data. Rebuilds have no timestamps or network calls. Builds replace their outputs; do not run concurrent builds. Queries can continue reading the previous SQLite file until replacement. Exports are local generated outputs, not an atomic multi-file publication. Missing required inputs fail before replacing the existing database. NFC is registered as a source but **not built or certified**; its citations fail with `unsupported_document` rather than being checked against NBC.

## CLI

```sh
.venv/bin/python -m codedb lookup '9.9.10.1.(1)'
.venv/bin/python -m codedb lookup '2.3.1.1.' --division C
.venv/bin/python -m codedb search egress bedrooms --limit 10
.venv/bin/python -m codedb children '9.9.10.1.'
.venv/bin/python -m codedb validate research/facts/example.md --json
.venv/bin/python -m codedb validate path/to/one.md path/to/two.yaml
.venv/bin/python -m codedb --db codedb/build/codedb.sqlite lookup '9.9.10.1.(1)'
```

Queries return JSON (the optional `--json` flag is accepted). Identifiers accept a missing dot before parentheses and spaces between groups, but reject trailing junk. `children` returns immediate children in code order. `search` uses FTS5 BM25, weights titles, stems English words, and treats input as literal search words joined with OR. `lookup` returns `null`/exit 1 when absent. An identifier shared by divisions requires `--division A|B|C`; the implementation never silently chooses Division B. Parts are fields, not provision nodes; use section/subsection/article/sentence/clause ids for hierarchy queries.

## Citation gate

Use `validate` before accepting generated knowledge. Supported inputs: Markdown, JSON, JSONL and YAML. Directory arguments recurse over those extensions. The scanner reads text; it does not execute YAML or certify JSON/YAML syntax.

```text
NBC(AE) 2023 p2, Div B, Sentence 9.9.10.1.(1) [PDF p.873].
[F10-OS3.7] (Div B Table attribution, PDF p.1126)
```

The body, attribution table, notes and intent supplement have different page locations. An intent citation must name its source explicitly, for example `NBC 2020 Intent Statements, 9.9.10.1.(1) [PDF p.1333]`. That supplement is explanatory, not Alberta law. These examples were checked using `tools/codesearch.py page`.

The report contains `ok`, `files_checked`, `citations_checked`, `errors`, and `warnings`. Every issue includes `path`, 1-based `line`/`column`, a stable `code`, the citation token, and an actionable message. Exit codes: **0** no errors, **1** citation/file errors, **2** command/setup errors. The token count includes ids, pairs, and page references, not complete citation records.

Checks include:

- Nonexistent or malformed article/sentence/clause ids; explicitly labelled sections/subsections; note and table ids.
- Ambiguous division, wrong explicitly named division, and unsupported documents.
- `[Fxx-Oxx]` pairs, including grouped functional/objective codes, against the cited provision's table rows. Parent sentence/clause attribution may apply to a child; heuristic exception roots never become direct attribution.
- `PDF p.N`/`PDF pp.N–M` against body, note, attribution or intent pages, with ±1 tolerance. Continued attribution tables accept pages throughout their span.
- Superseded Alberta/national editions and first-printing references, plus national 2020/2025 codes presented without an explanatory label. Explicit historical/explanatory or “never cite” mentions are distinguished from law citations.

Place each id before its page/pair and keep related tokens on the same line or consecutive lines in one paragraph. A pair/page without a linked id is checked for existence/range and produces an **unbound warning**; it does not establish provision-specific correctness. Blank lines and headings reset context. Markdown tables and JSON/YAML lines are scanned, but arbitrary prose, nested structured records, a division stated only in a remote heading, shorthand `(2)` references, and complicated interleaved citations may require explicit complete citations. The scanner deliberately avoids interpreting dates, STANDATA numbers, standards and labelled version numbers as provisions. A clean report proves recognized citation syntax and links; it cannot prove article relevance, interpretation, application completeness or technical correctness.

## Python interface

```python
from codedb import lookup, search, children, validate, validate_text

provision = lookup('9.9.10.1.(1)')
results = search('egress bedrooms', limit=10)
sentences = children('2.3.1.1.', division='C')
report = validate(['research/facts/example.md'])
assert report['ok'], report['errors']
```

All functions accept `db_path=` for an alternate read-only SQLite file; query functions accept `doc='NBC-AE'` and `division=`. `lookup` raises `AmbiguousProvisionError` on a shared unqualified id and returns `None` when absent. It includes body text (assembled from sentences for articles), immediate children, linked notes, attribution rows with application notes, attribution status/root provenance, intent blocks, edition comparisons, and a formatted citation. National intent blocks are returned only for Division B. JSON columns are decoded to lists. An exception's root is only a suggestion in `attribution_status`, never an assertion of an attribution absent from the source table.

## Schema

The authoritative SQL is `codedb/store.py`.

| Table | Identity and contents |
|---|---|
| `meta` | Build version and full stats JSON. |
| `docs` | Document key/label, code vs intent, Alberta-law status, source paths, extracted-text SHA-256. Registration does not mean that a document was built. |
| `provisions` | PK `(doc, division, id)`. Hierarchy level/parent, numeric part, section/subsection/article, sentence/clause/subclause, titles, normalized/raw body text, clause list, 1-based PDF start/end, volume, sortable key. |
| `notes`, `note_links` | Notes scoped by document/division, original note ids, titles/text/pages, and links from note identifiers or explicit see-note references. |
| `code_tables` | Document/division/table id and first PDF page. Cell values are not reconstructed. |
| `definitions` | PK `(doc, code)`. Objective hierarchy and functional statements, title, full definition text, parent code, PDF page. |
| `attributions` | One bracket per expanded target. Table id, actual provision target, sequence, FS/objective arrays, application note and source page. Multiple brackets/rows may apply to one target. |
| `attribution_status` | Div B sentences/clauses in parts with attribution tables: `direct`, `clause_level`, `inherits` or `none`; optional root and explicitly labelled heuristic method. |
| `intents` | National supplement blocks: source/code document, provision, objective, brackets, notes, intent array and PDF span. One provision can have several objective blocks. |
| `intent_comparison` | Per national intent provision, whether it exists in AE and pair-set differences/status. Clause rows are included when comparing a sentence. |
| `provisions_fts`, `notes_fts` | Local FTS5 indexes; public ranked search currently searches provisions. |

SQLite JSON columns are stored as text arrays. Article rows store their own preamble; sentence rows contain their clause text; clause rows contain their subclauses. Public article lookup assembles sentence text. All source references use **1-based PDF pages**, never printed page numbers.

## Verified coverage

Build version 2 contains **13,743 provision nodes**, **2,177 articles**, **5,493 sentences**, **774 notes**, **148 definitions**, **9,810 attribution source rows / 11,501 expanded bracket rows**, and **10,122 intent objective blocks for 5,026 distinct provision entries**.

| Division | Part | Nodes | Articles | Sentences |
|---|---:|---:|---:|---:|
| A | 1 | 148 | 25 | 48 |
| A | 2 | 26 | 3 | 8 |
| A | 3 | 21 | 3 | 6 |
| B | 1 | 39 | 11 | 17 |
| B | 3 | 4,521 | 555 | 1,614 |
| B | 4 | 1,068 | 147 | 448 |
| B | 5 | 350 | 49 | 117 |
| B | 6 | 397 | 73 | 163 |
| B | 7 | 479 | 92 | 248 |
| B | 8 | 116 | 27 | 35 |
| B | 9 | 5,887 | 1,055 | 2,535 |
| B | 10 | 280 | 64 | 120 |
| B | 11 | 37 | 7 | 11 |
| C | 1 | 17 | 4 | 8 |
| C | 2 | 357 | 62 | 115 |

Div B attribution coverage is **3,817 / 5,291 = 72.1%** of sentences in parts with attribution tables; across all 5,308 Div B sentences, it is **71.9%**. Lack of attribution is recorded, not automatically called a parse error. Div B has no Part 2 body in this source.

Of 5,026 national intent entries, **4,805 (95.6%) exist in AE**. Pair comparison: **3,414 match**, **64 differ**, **29 lack AE pairs**, **14 lack intent pairs**, **1,284 have no pairs on either side**, and **221 provisions are absent in AE**. The match rate among 3,521 comparable pair-bearing entries is **97.0%**. This is pair equality, not textual or technical equivalence between editions.

`python -m codedb.audit` selects 30 provisions with a fixed seed, randomly within strata covering A/B/C, every Div B part, and article/sentence levels. It invokes `tools/codesearch.py page`, compares ordered raw lines/title and start/end pages, and saves `build/spot-check.json` plus ignored page captures. The final audit found **0/30 mismatches**. Tests include independently checked literal receipts for bedroom egress (body p.873 / attribution p.1126), Part 3 (body p.179 / attribution p.326), Div C documentation (p.739), and a sentence with no direct attribution. This sample supports extraction quality; it is not exhaustive PDF proofreading.

## Known source and extraction limits

- The printed Part 4 attribution table at PDF p.514 names clauses `(c)` and `(d)` under its serviceability sentence `(5)`; the corresponding body at p.428 contains only `(a)` and `(b)`. Both unmatched table targets remain in the export and diagnostics. The validator rejects a nonexistent body clause instead of inventing it.
- Quoted application notes can contain editorial square brackets (for example at p.333). They are preserved as application text and are not interpreted as attribution pairs.
- Attribution application notes constrain scope; the gate checks pair membership, not whether a proposed use satisfies that application note. Root inference follows explicit references and can be uncertain; `root_method` distinguishes those suggestions from parent inheritance.
- Raw PDF extraction can split letters, formulas and layout. `text_raw` preserves body extraction; `text` applies a document-trained word-segmentation repair that is convenient for search, not an authoritative transcription. Tables/figures and their notes are separated from sentence prose; table locations are indexed, but table cell/formula/diagram semantics are not parsed. Continue consulting the source PDF for engineering content.
- Note range/compound-id linking and uncommon layout can require a manual source check. The source parser's heading inventory and 30-item audit are bounded checks, not a claim of perfect clause/note extraction.
- National intent comparison checks provision presence and expanded attribution pair sets only. It neither adapts 2020 intent language to Alberta amendments nor makes the national edition citable as Alberta law.
- No NFC extraction/intent matching, external MCP server, web UI or production deployment is included. CLI/API output and automated source checks are the verification surface; there is no meaningful screenshot/demo surface.
