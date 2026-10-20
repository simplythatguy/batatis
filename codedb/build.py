"""One-command rebuild: parse sources -> codedb/build/codedb.sqlite + codedb/build/export/*.jsonl + stats.json.

Deterministic: same inputs give the same rows (no timestamps in the data).
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter, defaultdict

from . import attributions as attr_mod
from . import ids, intents as intent_mod, objectives, provisions, store, textnorm
from .sources import BUILD_DIR, DOCS, load_pages, volume_of

BUILD_VERSION = "2"
# code doc -> intent supplement for the same code family
INTENT_FOR = {"NBC-AE": "NBC-2020-IS", "NFC-AE": "NFC-2020-IS"}
_NOTE_REF = re.compile(r"\bA-(?:Table )?\d+(?:\.\d+)*\.(?:\(\d+\))*(?:\([a-z]{1,2}\))*")


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build(keys=("NBC-AE",), log=print) -> dict:
    keys = tuple(keys)
    if keys != ("NBC-AE",):
        raise ValueError("Only NBC-AE is verified; NFC parsing is outside this build's supported scope")
    for source in ("NBC-AE", "NBC-2020-IS"):
        for path in (DOCS[source].jsonl, DOCS[source].pdf):
            if not path.is_file():
                raise FileNotFoundError(f"Required source missing: {path}; existing build was not replaced")
    con = store.create()
    stats: dict = {"build_version": BUILD_VERSION, "sources": {}}
    for key in keys:
        if not DOCS[key].jsonl.exists():
            log(f"skip {key}: {DOCS[key].jsonl} missing")
            continue
        log(f"[{key}] parsing")
        stats[key] = build_code(con, key, log)
        for source in (key, INTENT_FOR[key]):
            d = DOCS[source]
            stats["sources"][source] = {
                "label": d.label, "text_sha256": _sha(d.jsonl),
                "pdf_sha256": _sha(d.pdf), "pdf_pages": len(load_pages(source)),
                "citable_as_alberta_law": d.citable,
            }
    for key, d in DOCS.items():
        con.execute("INSERT INTO docs VALUES (?,?,?,?,?,?,?)",
                    (key, d.label, d.kind, int(d.citable), str(d.pdf.relative_to(d.pdf.parents[2])),
                     str(d.jsonl.relative_to(d.jsonl.parents[2])), _sha(d.jsonl) if d.jsonl.exists() else None))
    con.execute("INSERT INTO meta VALUES ('build_version', ?)", (BUILD_VERSION,))
    con.execute("INSERT INTO meta VALUES ('stats', ?)", (json.dumps(stats),))
    export(con)
    store.finalize(con)
    (BUILD_DIR / "stats.json").write_text(json.dumps(stats, indent=2) + "\n")
    log(f"wrote {store.DB_PATH}")
    return stats


def build_code(con, key: str, log) -> dict:
    pages = load_pages(key)
    seg = textnorm.Segmenter(" ".join(p.lines) for p in pages)
    repair = lambda t: textnorm.repair(t, seg)  # noqa: E731

    rows, problems, tables = attr_mod.parse_all(key)
    pc = provisions.parse_code(key, {t for t, _, _ in tables})
    log(f"[{key}] {len(pc.nodes)} provisions, {len(pc.notes)} notes, {len(rows)} attribution rows")

    # ---- provisions
    clauses_of: dict = defaultdict(list)
    for (div, pid) in pc.nodes:
        if pid.level == "clause":
            clauses_of[(div, pid.sentence_id())].append(pid.clause)
    titles = {(d, p): n.title for (d, p), n in pc.nodes.items() if p.level == "article"}
    prov_rows = []
    for (div, pid), n in sorted(pc.nodes.items(), key=lambda kv: (kv[0][0], kv[0][1].sort_key())):
        nums = pid.nums
        art = ids.Pid(nums) if len(nums) == 4 else None
        raw = n.text
        prov_rows.append((
            key, div, str(pid), pid.level, pid.part,
            str(ids.Pid(nums[:2])) if len(nums) >= 2 else None,
            str(ids.Pid(nums[:3])) if len(nums) >= 3 else None,
            str(art) if art else None,
            pid.sentence, pid.clause, pid.subclause,
            str(pid.parent()) if pid.parent() else None,
            titles.get((div, art), "") if art else "",
            n.title, repair(raw), raw,
            json.dumps(clauses_of.get((div, pid), [])) if pid.level == "sentence" else None,
            n.page, n.page_end, volume_of(key, n.page), _sort_text(pid),
        ))
    con.executemany(f"INSERT INTO provisions VALUES ({','.join('?' * 21)})", prov_rows)
    con.executemany("INSERT INTO provisions_fts VALUES (?,?,?,?,?)",
                    [(r[0], r[1], r[2], r[12] if r[3] != "article" else r[13], r[14]) for r in prov_rows
                     if r[3] in ("article", "sentence", "section", "subsection")])
    existing = {(r[1], r[2]) for r in prov_rows}

    # ---- notes
    note_ids = set()
    for nt in pc.notes:
        if (nt.division, nt.note_id) in note_ids:
            continue
        note_ids.add((nt.division, nt.note_id))
        txt = repair(nt.text)
        con.execute("INSERT INTO notes VALUES (?,?,?,?,?,?,?,?,?)",
                    (key, nt.division, nt.note_id, repair(nt.title), txt, nt.text, nt.page, nt.page_end,
                     volume_of(key, nt.page)))
        con.execute("INSERT INTO notes_fts VALUES (?,?,?,?,?)", (key, nt.division, nt.note_id, nt.title, txt))
        for t in provisions.note_targets(nt.note_id):
            con.execute("INSERT INTO note_links VALUES (?,?,?,?,?)", (key, nt.division, nt.note_id, t, "note_id"))
    for r in prov_rows:
        if r[3] in ("article", "sentence"):
            for m in sorted(set(_NOTE_REF.findall(r[14].replace("\n", " ")))):
                if (r[1], m) in note_ids:
                    con.execute("INSERT INTO note_links VALUES (?,?,?,?,?)", (key, r[1], m, r[2], "see_reference"))
    for (div, t), pg in pc.tables.items():
        con.execute("INSERT OR IGNORE INTO code_tables VALUES (?,?,?,?)", (key, div, "Table " + t, pg))

    # ---- definitions (Division A objectives / functional statements)
    defs = []
    if ("A", ids.parse("2.2.1.1.(1)")) in pc.nodes and ("A", ids.parse("3.2.1.1.(1)")) in pc.nodes:
        defs = objectives.parse_definitions(pc.nodes, repair)
        con.executemany("INSERT INTO definitions VALUES (?,?,?,?,?,?,?)",
                        [(key, d.code, d.kind, d.title, d.text, d.parent, d.page) for d in defs])
    defined = {d.code for d in defs}

    # ---- attributions
    by_prov: dict[str, set] = defaultdict(set)      # provision id -> expanded (F, O) pairs
    undefined = Counter()
    att_rows = []
    for seq, r in enumerate(rows):
        targets = [r.provision] if len(r.clauses) <= 1 else [
            f"{r.article}({r.sentence})" + "".join(f"({x})" for x in re.findall(r"[a-z]+", c)) for c in r.clauses]
        for b in r.brackets:
            for code in b.fs + b.objectives:
                if defined and code not in defined:
                    undefined[code] += 1
            for t in targets:
                att_rows.append((key, "Table " + r.table, t, r.article, r.sentence, json.dumps(r.clauses), seq,
                                 b.raw, json.dumps(b.fs), json.dumps(b.objectives), repair(r.note) or None, r.page))
                by_prov[t] |= set(b.pairs)
    con.executemany(f"INSERT INTO attributions VALUES ({','.join('?' * 12)})", att_rows)

    # ---- attribution status for every Div B sentence/clause in a Part that has an attribution table
    attributed_parts = {int(t.split(".")[0]) for t, _, _ in tables}
    status_rows, st_count = attribution_status(key, pc, by_prov, attributed_parts)
    con.executemany("INSERT INTO attribution_status VALUES (?,?,?,?,?)", status_rows)

    # ---- intents
    ist = {}
    ikey = INTENT_FOR.get(key)
    if ikey and DOCS[ikey].jsonl.exists():
        ist = build_intents(con, key, ikey, existing, by_prov, repair, log)

    # ---- stats
    per_part = Counter()
    for (div, pid) in pc.nodes:
        per_part[f"Div {div} Part {pid.part} {pid.level}"] += 1
    sentences_b = [s for s in status_rows if s[1].count("(") == 1]
    covered = sum(1 for s in sentences_b if s[2] in ("direct", "clause_level"))
    return {
        "provisions_total": len(pc.nodes),
        "provisions_by_part_level": dict(sorted(per_part.items())),
        "notes": len(note_ids),
        "attribution_tables": [{"table": t, "pdf_pages": [a, b]} for t, a, b in tables],
        "attribution_rows": len(rows),
        "attribution_brackets": len(att_rows),
        "attribution_parse_problems": problems,
        "attribution_rows_unmatched_to_provision": sorted({r[2] for r in att_rows if ("B", r[2]) not in existing}),
        "undefined_codes_in_tables": dict(undefined),
        "definitions": len(defs),
        "divB_sentences_in_attributed_parts": len(sentences_b),
        "divB_sentences_with_attribution": covered,
        "divB_sentence_attribution_pct": round(100 * covered / max(1, len(sentences_b)), 1),
        "attribution_status_counts": dict(st_count),
        "parser_anomalies": pc.anomalies,
        "intents": ist,
    }


def _sort_text(pid: ids.Pid) -> str:
    k = pid.sort_key()
    return ".".join(f"{n:03d}" for n in k[0]) + f"|{k[1]:02d}|{k[2]:02d}|{k[3]:02d}"


_REF_SENT = re.compile(r"Sentences? \((\d+)\)")
_REF_EXT = re.compile(r"Sentences? (\d+\.\d+\.\d+\.\d+\.)\((\d+)\)")
_REF_ART = re.compile(r"Articles? (\d+\.\d+\.\d+\.\d+\.)(?!\()")


def attribution_status(key, pc, by_prov, attributed_parts):
    """Status per Div B sentence and clause. For unattributed sentences, prefer an attributed
    same-article sentence reference, then an external sentence, then an article reference.
    This is a heuristic and is labelled as such (root_method); it is never direct attribution."""
    rows, count = [], Counter()
    sent_status = {}
    sentences = sorted((p for (d, p) in pc.nodes if d == "B" and p.level == "sentence" and p.part in attributed_parts),
                       key=lambda p: p.sort_key())
    has_clause_rows = defaultdict(bool)
    for prov in by_prov:
        try:
            pid = ids.parse(prov)
        except ValueError:
            continue
        if pid.clause:
            has_clause_rows[str(pid.sentence_id())] = True

    def attributed(sid: str) -> bool:
        return bool(by_prov.get(sid)) or has_clause_rows[sid]

    for p in sentences:
        sid = str(p)
        if by_prov.get(sid):
            st, root, how = "direct", None, None
        elif has_clause_rows[sid]:
            st, root, how = "clause_level", None, None
        else:
            st, root, how = "none", None, None
            text = " ".join(pc.nodes[("B", p)].text.split())
            art = str(ids.Pid(p.nums))
            cands = []
            for m in re.finditer(r"Sentences? (\d+\.\d+\.\d+\.\d+\.)\((\d+)\)|Sentences? \((\d+)\)|Articles? "
                                 r"(\d+\.\d+\.\d+\.\d+\.)(?!\()", text):
                if m.group(1):
                    cands.append((f"{m.group(1)}({m.group(2)})", "referenced_sentence"))
                elif m.group(3):
                    cands.append((f"{art}({m.group(3)})", "referenced_sentence_same_article"))
                else:
                    a = m.group(4)
                    sents = [str(q) for (d, q) in pc.nodes if d == "B" and q.level == "sentence" and str(ids.Pid(q.nums)) == a]
                    for s in sorted(sents):
                        if attributed(s):
                            cands.append((s, "referenced_article"))
                            break
            # A same-article requirement is a stronger root candidate than an
            # earlier "Except as permitted by Article ..." reference.
            priority = {"referenced_sentence_same_article": 0, "referenced_sentence": 1, "referenced_article": 2}
            for c, how_ in sorted(cands, key=lambda item: priority[item[1]]):
                if c != sid and attributed(c):
                    root, how = c, how_
                    break
            if root is None:
                how = "not_determined"
        sent_status[sid] = (st, root)
        count[f"sentence:{st}"] += 1
        rows.append((key, sid, st, root, how))
    for (d, p) in pc.nodes:
        if d != "B" or p.level not in ("clause", "subclause") or p.part not in attributed_parts:
            continue
        cid = str(p)
        sid = str(p.sentence_id())
        if by_prov.get(cid):
            st, root, how = "direct", None, None
        else:
            parent_sub = str(ids.Pid(p.nums, p.sentence, p.clause)) if p.subclause else None
            sst, sroot = sent_status.get(sid, ("none", None))
            if parent_sub and by_prov.get(parent_sub):
                st, root, how = "inherits", parent_sub, "parent_clause"
            elif by_prov.get(sid):
                st, root, how = "inherits", sid, "parent_sentence"
            elif sroot:
                st, root, how = "none", sroot, "via_sentence_root"
            else:
                st, root, how = "none", None, "not_determined"
        count[f"{p.level}:{st}"] += 1
        rows.append((key, cid, st, root, how))
    return rows, count


def build_intents(con, key, ikey, existing, by_prov, repair, log):
    entries = intent_mod.parse_intents(ikey)
    log(f"[{ikey}] {len(entries)} intent entries")
    status = Counter()
    seen = set()
    for e in entries:
        intent_pairs = set()
        for i, b in enumerate(e.blocks):
            for br in b.brackets:
                intent_pairs |= set(br.pairs)
            con.execute("INSERT INTO intents VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (ikey, key, e.provision, i, b.objective, json.dumps([x.raw for x in b.brackets]),
                         json.dumps([repair(n) for n in b.attribution_notes]),
                         json.dumps([_dehyphen(t, repair) for t in b.intents(repair)]), b.page or e.page, e.page_end))
        if e.provision in seen:
            continue
        seen.add(e.provision)
        exists = ("B", e.provision) in existing
        ae_pairs = set(by_prov.get(e.provision, set()))
        try:
            pid = ids.parse(e.provision)
        except ValueError:
            pid = None
        if pid is not None and pid.level == "sentence":
            prefix = e.provision + "("
            for prov, pairs in by_prov.items():
                if prov.startswith(prefix):
                    ae_pairs |= pairs
        if not exists:
            st = "provision_missing_in_ae"
        elif not intent_pairs and not ae_pairs:
            st = "none_both"
        elif intent_pairs == ae_pairs:
            st = "match"
        elif not ae_pairs:
            st = "missing_in_ae"
        elif not intent_pairs:
            st = "missing_in_intent"
        else:
            st = "differs"
        status[st] += 1
        fmt = lambda s: sorted(f"[{f}-{o}]" for f, o in s)  # noqa: E731
        con.execute("INSERT INTO intent_comparison VALUES (?,?,?,?,?,?,?)",
                    (ikey, key, e.provision, int(exists), st,
                     json.dumps(fmt(intent_pairs - ae_pairs)) if exists else None,
                     json.dumps(fmt(ae_pairs - intent_pairs)) if exists else None))
    total = len(seen)
    exist_n = total - status["provision_missing_in_ae"]
    with_pairs = status["match"] + status["differs"] + status["missing_in_ae"] + status["missing_in_intent"]
    return {
        "entries": len(entries), "distinct_provisions": total,
        "exist_in_ae": exist_n, "exist_in_ae_pct": round(100 * exist_n / max(1, total), 1),
        "status_counts": dict(status),
        "attribution_match_pct_of_comparable": round(100 * status["match"] / max(1, with_pairs), 1),
    }


def _dehyphen(t: str, repair) -> str:
    # "in- adequate" -> "inadequate" (line-break hyphenation in the supplement PDFs)
    return re.sub(r"\b([a-z]+)- ([a-z]+)\b", lambda m: m.group(1) + m.group(2)
                  if m.group(1) not in ("non", "self", "fire", "low", "high", "well", "semi", "multi") else m.group(0), t)


def export(con):
    out = BUILD_DIR / "export"
    out.mkdir(parents=True, exist_ok=True)
    for table in ("provisions", "notes", "note_links", "code_tables", "definitions", "attributions",
                  "attribution_status", "intents", "intent_comparison"):
        cur = con.execute(f"SELECT * FROM {table}")
        cols = [c[0] for c in cur.description]
        with open(out / f"{table}.jsonl", "w", encoding="utf8") as f:
            for row in cur:
                rec = dict(zip(cols, row))
                for k in ("clauses", "fs", "objectives", "brackets", "attribution_notes", "intents",
                          "only_in_intent", "only_in_ae"):
                    if isinstance(rec.get(k), str):
                        rec[k] = json.loads(rec[k])
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    build(tuple(sys.argv[1:]) or ("NBC-AE",))
