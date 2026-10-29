#!/usr/bin/env python3
"""Build alberta-jurisdictions.csv, one row per Alberta jurisdiction that Batatis could be asked about.

Reads (nothing else, no network):
  - Data Prompts/Alberta Jurisdiction Sources.json   (A16 inventory, 2026-10-25: 330 municipal rows, 8 Metis settlements)
  - reference/text/NBC-AE-2023-2nd-printing-FULL-Vol1+Vol2.jsonl   (Table C-2 on PDF pages 667 to 670)
  - alberta-scc-snapshot.json            (Safety Codes Council Accreditation Search, read 2026-10-29)
  - alberta-mapl-2025.json               (Municipal Affairs population list 2025: First Nation, Metis and stakeholder rows)
  - alberta-jurisdiction-overrides.json  (hand-checked national park, Lloydminster, airport, First Nation and top-20 facts)
  - alberta-unaccredited-routing.json    (per-municipality SCC queries for the 75 municipalities not accredited for Building)

Run:  python3 -I alberta_jurisdictions_build.py [--a16 PATH] [--nbc PATH] [--out PATH]
It prints counts. It never writes anywhere except the CSV path.
"""
import argparse
import csv
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]

COLUMNS = [
    "lg_code", "legal_name", "type", "population_2025", "building_accredited", "building_ahj", "building_ahj_kind",
    "service_provider", "fire_accredited", "plumbing_accredited", "gas_accredited", "electrical_accredited",
    "psds_accredited", "table_c2_location", "notes", "source",
]

PREFIXES = [
    "regional municipality of ", "specialized municipality of ", "municipal district of ", "summer village of ",
    "municipality of ", "village of ", "town of ", "city of ", "county of ", "m d of ", "md of ",
]


def norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = s.replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def core(name):
    n = norm(name)
    for p in PREFIXES:
        if n.startswith(p):
            n = n[len(p):]
            break
    n = re.sub(r"\bno \d+$", "", n).strip()
    n = re.sub(r"\bcounty$", "", n).strip()
    return n


def read_table_c2(nbc_path):
    """Return list of (name, elevation_m, heating_degree_days) from NBC(AE) Table C-2 on PDF pages 667 to 670."""
    pages = {}
    with open(nbc_path, encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            if 667 <= r["page"] <= 670:
                pages[r["page"]] = r["text"]
    named = re.compile(r"^(?P<name>[A-Za-z][A-Za-z .'’\-/()]*?)\s+(?P<elev>\d{2,4})\s+(?P<t1>[−\-]?\d+)\s+(?P<t2>[−\-]?\d+)\s+(?P<dry>\d+)\s+(?P<wet>\d+)\s+(?P<hdd>\d{4})\b")
    bare = re.compile(r"^(?P<elev>\d{2,4})\s+(?P<t1>[−\-]?\d+)\s+(?P<t2>[−\-]?\d+)\s+(?P<dry>\d+)\s+(?P<wet>\d+)\s+(?P<hdd>\d{4})\b")
    alpha = re.compile(r"^[A-Za-z][A-Za-z .'’\-]*$")
    out = []
    for pg in sorted(pages):
        pending = []
        for raw in pages[pg].splitlines():
            line = raw.strip()
            m = named.match(line)
            if m:
                out.append((m.group("name").strip(), int(m.group("elev")), int(m.group("hdd"))))
                pending = []
                continue
            m = bare.match(line)
            if m and pending:
                out.append((" ".join(pending[-2:]), int(m.group("elev")), int(m.group("hdd"))))
                pending = []
                continue
            if alpha.match(line) and len(line) <= 24:
                pending.append(line)
            else:
                pending = []
    return out


def zone_of(hdd):
    if hdd < 3000:
        return "4"
    if hdd < 4000:
        return "5"
    if hdd < 5000:
        return "6"
    if hdd < 6000:
        return "7A"
    if hdd < 7000:
        return "7B"
    return "8"


def yn(v):
    return "true" if v else "false"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a16", default=str(REPO / "Data Prompts" / "Alberta Jurisdiction Sources.json"))
    ap.add_argument("--nbc", default=str(REPO / "reference" / "text" / "NBC-AE-2023-2nd-printing-FULL-Vol1+Vol2.jsonl"))
    ap.add_argument("--out", default=str(HERE / "alberta-jurisdictions.csv"))
    args = ap.parse_args()

    a16 = json.loads(Path(args.a16).read_text(encoding="utf-8"))
    snap = json.loads((HERE / "alberta-scc-snapshot.json").read_text(encoding="utf-8"))
    mapl = json.loads((HERE / "alberta-mapl-2025.json").read_text(encoding="utf-8"))
    ov = json.loads((HERE / "alberta-jurisdiction-overrides.json").read_text(encoding="utf-8"))
    routing = json.loads((HERE / "alberta-unaccredited-routing.json").read_text(encoding="utf-8"))

    c2 = read_table_c2(args.nbc)
    c2_names = {norm(n): n for n, _, _ in c2}
    zones = Counter(zone_of(h) for _, _, h in c2)

    scc = {norm(o["organization"]): o for o in snap["municipalities"]}
    joint_building = [j for j in snap["joint_municipalities"] if "Building" in j["disciplines"]]
    office_city = {norm(o["organization"]): o["city_listed"] for o in snap["municipalities"]}

    rows = []
    diffs_vs_a16 = []
    c2_exact = {}
    joint_hits = defaultdict(list)

    def joint_membership(legal_name, mtype):
        """Names of joint building accreditations whose name lists this municipality (name match only)."""
        c = core(legal_name)
        rural = mtype in ("Municipal District", "Specialized Municipality") and ("county" in norm(legal_name) or "district" in norm(legal_name))
        hits = []
        for j in joint_building:
            for seg in re.split(r"[/,]|\s-\s", j["organization"]):
                s = norm(seg)
                if not s:
                    continue
                seg_rural = bool(re.search(r"\b(county|m d|md|municipal district|no \d+)\b", s))
                if core(seg) == c and seg_rural == rural:
                    hits.append(j["accreditation_number"])
                    break
        return hits

    def disciplines_for(names):
        d = {}
        for n in names:
            o = scc.get(norm(n))
            if o:
                d.update(o["disciplines"])
        return d

    def scc_ref(names):
        """SCC accreditation number and Building order number for the organization names (from the 2026-10-29 snapshot)."""
        parts = []
        for n in names:
            o = scc.get(norm(n))
            if o:
                b = o["disciplines"].get("Building")
                parts.append(o["accreditation_number"] + (f", Building order {b}" if b else ""))
        return "; ".join(parts)

    # 1. Municipal-type rows
    for r in a16["accredited_municipal_roster_all_330"]:
        code, name, mtype, pop = r["lg_code"], r["legal_name"], r["type"], r["population_2025"]
        names = r["scc_organization_names"] or []
        d = disciplines_for(names)
        if sorted(d) != sorted(r["scc_disciplines"]):
            diffs_vs_a16.append((code, name, sorted(r["scc_disciplines"]), sorted(d)))
        accredited = "Building" in d
        notes, sources = [], ["MAPL 2025 (open.alberta.ca) for type and population", "SCC Accreditation Search read 2026-10-29"]
        provider = ""
        kind = "accredited_municipality" if accredited else "asca"
        ahj = name if accredited else ov["default_building_ahj_asca"]
        if code in ov["national_park_improvement_districts"]:
            o = ov["national_park_improvement_districts"][code]
            kind, ahj = "federal", o["ahj"]
            notes.append(f"{o['note']} [{o['status']}]")
            sources.append(o["source"])
        elif code == "0418":
            o = ov["special_rows"]["0418"]
            kind, ahj = "federal", o["ahj"]
            notes.append(f"{o['note']} [{o['status']}]")
            sources.append(o["source"])
        elif code == "0206":
            o = ov["special_rows"]["0206"]
            kind, ahj = "other", o["ahj"]
            notes.append(f"{o['note']} [{o['status']}]")
            sources.append(o["source"])
        elif code == "0479":
            o = ov["special_rows"]["0479"]
            notes.append(f"{o['note']} [{o['status']}]")
            sources.append(o["source"])
        elif code in ("0387", "0373"):
            o = ov["special_rows"][code]
            notes.append(f"{o['note']} [{o['status']}]")
            sources.append(o["source"])
        if kind == "asca":
            provider = "owner chooses an ASCA-contracted agency"
        if not accredited and code not in ov["national_park_improvement_districts"] and code != "0418":
            fire = "Fire" in d
            notes.append("Fire: " + ("own SCC accreditation" if fire else "no SCC fire accreditation found; STANDATA 23-BCI-030 says the building SCO accepts fire safety plans in areas unaccredited for fire"))
        if accredited:
            hits = joint_membership(name, mtype)
            if hits:
                joint_hits[code] = hits
                notes.append("Named in joint accreditation(s) with Building " + ", ".join(hits) + " (name match, not a membership list)")
        t = ov["top20"].get(code)
        if t:
            if not t["service_provider"].startswith("not "):
                provider = t["service_provider"]
            notes.append(f"Variance evidence: {t['note']} [{t['status']}]")
            sources.append(t["source"])
        if kind == "accredited_municipality":
            notes.insert(0, f"[basis: SCC listing {scc_ref(names)}, VERIFIED]")
        elif kind == "asca":
            notes.insert(0, ov["asca_basis"])
            sources.append("https://www.qp.alberta.ca/documents/Regs/2016_029.pdf")
        # Table C-2
        c = core(name)
        exact = ""
        urban = mtype in ("City", "Town", "Village", "Summer Village", "Specialized Municipality")
        if c in c2_names and urban:
            exact = c2_names[c]
            if mtype == "Specialized Municipality" and ("county" in norm(name)):
                notes.append("Table C-2 location is the community of the same name; the municipality is a county")
        elif c in c2_names:
            notes.append(f"Table C-2 has a location named {c2_names[c]}; it is the town or city, not this rural municipality, so it is not counted as an exact match")
        else:
            oc = office_city.get(norm(names[0])) if names else None
            if oc and norm(oc) in c2_names and norm(oc) != c:
                notes.append(f"Inference only: the municipal office city {oc} is a Table C-2 location")
        c2_exact[code] = bool(exact)
        rows.append({
            "lg_code": code, "legal_name": name, "type": mtype, "population_2025": pop,
            "building_accredited": yn(accredited), "building_ahj": ahj, "building_ahj_kind": kind, "service_provider": provider,
            "fire_accredited": yn("Fire" in d), "plumbing_accredited": yn("Plumbing" in d), "gas_accredited": yn("Gas" in d),
            "electrical_accredited": yn("Electrical" in d), "psds_accredited": "unknown",
            "table_c2_location": exact, "notes": " | ".join(notes), "source": " ; ".join(dict.fromkeys(sources)),
        })

    # 2. Metis settlements
    mpop = {m["lg_code"]: m["population_2025"] for m in mapl["metis_settlements"]}
    for m in a16["accredited_metis_settlements"]:
        code, name = m["lg_code"], m["legal_name"]
        d = disciplines_for([name])
        accredited = "Building" in d
        mo = ov["metis_settlements"]
        e = mo["evidence"].get(code, {})
        if accredited:
            basis = f"[basis: SCC listing {scc_ref([name])}, VERIFIED; name query {e.get('raw_file','')} sha256 {e.get('sha256','')}]"
        else:
            basis = (f"[basis: SCC name query {e.get('raw_file','')} returned {e.get('rows_returned','?')} rows on {e.get('retrieved','')} (sha256 {e.get('sha256','')}), VERIFIED; "
                     "AR 29/2016 s.4(1) gives areas without an accredited organization to ASCA, VERIFIED; applying both to this settlement is an inference]")
        rows.append({
            "lg_code": code, "legal_name": name, "type": "Metis Settlement", "population_2025": mpop.get(code, ""),
            "building_accredited": yn(accredited),
            "building_ahj": name if accredited else ov["default_building_ahj_asca"],
            "building_ahj_kind": "metis_settlement" if accredited else "asca",
            "service_provider": "" if accredited else "owner chooses an ASCA-contracted agency",
            "fire_accredited": yn("Fire" in d), "plumbing_accredited": yn("Plumbing" in d), "gas_accredited": yn("Gas" in d),
            "electrical_accredited": yn("Electrical" in d), "psds_accredited": "unknown", "table_c2_location": "",
            "notes": basis + " " + (mo["note_accredited"] if accredited else mo["note_unaccredited"]) + " " + mo["legal_basis"],
            "source": "MAPL 2025 ; SCC Accreditation Search read 2026-10-29 ; " + mo["source"],
        })

    # 3. First Nations
    fno = ov["first_nations"]
    for f in mapl["first_nations"]:
        code = f["lg_code"]
        ex = fno["examples"].get(code)
        notes = fno["default_note"] + f" [{fno['default_status']}]"
        sources = ["MAPL 2025 (population is the federal figure)", fno["default_source"]]
        provider = ""
        if ex:
            notes += " | Example: " + ex["note"] + f" [{ex['status']}]"
            sources.append(ex["source"])
            provider = ex.get("service_provider", "")
        rows.append({
            "lg_code": code, "legal_name": f["legal_name"], "type": "First Nation", "population_2025": f["population_2025"] if f["population_2025"] is not None else "",
            "building_accredited": "false", "building_ahj": fno["default_ahj"], "building_ahj_kind": "first_nation", "service_provider": provider,
            "fire_accredited": "false", "plumbing_accredited": "false", "gas_accredited": "false", "electrical_accredited": "false",
            "psds_accredited": "unknown", "table_c2_location": "", "notes": notes, "source": " ; ".join(sources),
        })

    # 4. Other categories from primary sources
    for o in mapl["other_rows"]:
        rows.append({
            "lg_code": o["lg_code"], "legal_name": o["legal_name"], "type": o["mapl_type"], "population_2025": o["population_2025"] or "",
            "building_accredited": "unknown", "building_ahj": "not determined", "building_ahj_kind": "other", "service_provider": "",
            "fire_accredited": "unknown", "plumbing_accredited": "unknown", "gas_accredited": "unknown", "electrical_accredited": "unknown",
            "psds_accredited": "unknown", "table_c2_location": "",
            "notes": ov["ais_stakeholder"]["note"] + f" [{ov['ais_stakeholder']['status']}]", "source": "MAPL 2025",
        })
    for e in ov["extra_rows"]:
        rows.append({
            "lg_code": e["lg_code"], "legal_name": e["legal_name"], "type": e["type"], "population_2025": e["population_2025"],
            "building_accredited": "false", "building_ahj": e["building_ahj"], "building_ahj_kind": e["kind"], "service_provider": "",
            "fire_accredited": "unknown", "plumbing_accredited": "unknown", "gas_accredited": "unknown", "electrical_accredited": "unknown",
            "psds_accredited": "unknown", "table_c2_location": "", "notes": e["note"] + f" [{e['status']}]", "source": e["source"],
        })

    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS, quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        w.writerows(rows)

    muni = [r for r in rows if r["type"] in ("City", "Town", "Village", "Summer Village", "Municipal District", "Specialized Municipality", "Improvement District", "Special Areas")]
    metis = [r for r in rows if r["type"] == "Metis Settlement"]
    print(f"wrote {args.out}")
    print(f"rows total: {len(rows)}  (municipal-type {len(muni)}, Metis settlements {len(metis)}, First Nations {sum(1 for r in rows if r['type']=='First Nation')}, other {len(rows)-len(muni)-len(metis)-sum(1 for r in rows if r['type']=='First Nation')})")
    print("rows by building_ahj_kind:", dict(sorted(Counter(r["building_ahj_kind"] for r in rows).items())))
    print("rows by type:", dict(sorted(Counter(r["type"] for r in rows).items())))
    print("building accredited: municipal-type", sum(1 for r in muni if r["building_accredited"] == "true"), "of", len(muni), "; Metis", sum(1 for r in metis if r["building_accredited"] == "true"), "of", len(metis))
    print("municipal-type rows routed to ASCA:", sum(1 for r in muni if r["building_ahj_kind"] == "asca"),
          "| in the 75-municipality routing file:", len(routing["municipalities"]))
    print("differences between A16 (2026-10-25) and the 2026-10-29 SCC snapshot for municipal rows:", len(diffs_vs_a16), diffs_vs_a16[:5])
    print("Table C-2 locations parsed:", len(c2), "| by NBC(AE) 9.36 climate zone (from degree-days):", dict(sorted(zones.items())))
    n_exact = sum(1 for r in muni if r["table_c2_location"])
    print(f"municipal-type rows with an exact Table C-2 location: {n_exact}; without: {len(muni)-n_exact}")
    acc = [r for r in muni if r["building_accredited"] == "true"]
    print(f"  of the {len(acc)} building-accredited municipal-type rows: exact {sum(1 for r in acc if r['table_c2_location'])}, without {sum(1 for r in acc if not r['table_c2_location'])}")
    asca = [r for r in muni if r["building_ahj_kind"] == "asca"]
    print(f"  of the {len(asca)} ASCA municipal-type rows: exact {sum(1 for r in asca if r['table_c2_location'])}, without {sum(1 for r in asca if not r['table_c2_location'])}")
    unmatched = sorted(n for k, n in c2_names.items() if k not in {norm(r['table_c2_location']) for r in muni if r['table_c2_location']})
    print(f"Table C-2 locations with no exact municipality row ({len(unmatched)}): {unmatched[:25]}{' ...' if len(unmatched) > 25 else ''}")
    print("municipal rows named in a joint Building accreditation (name match only):", len(joint_hits))
    print("distinct joint accreditations with Building:", len(joint_building))


if __name__ == "__main__":
    sys.exit(main())
