"""Applicant oracle and the real engine calls a workflow is allowed to make.

Hidden rule-vector inputs are returned only when a workflow asks that field.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.intake.fork import assess
from engine.intake.questions import plan_questions
from engine.intake.scope import classify
from engine.rules.evaluator import evaluate, load_index, load_rule

from prompts import Prompt

PID = re.compile(r"\d+\.\d+\.\d+\.\d+\.(?:\(\d+\)(?:\([a-z]\))?)?")
STANDATA = re.compile(r"\b\d{2}-[A-Z]{3}-\d{3}[A-Z]?\b")
CCMC = re.compile(r"\bCCMC\s*\d{4,}\b", re.I)

OFFICE = {"fire_response_over_10_min"}
DESIGNER = {
    "part4_design", "assembly.description", "industrial_hazard", "fire_resistance_rating",
    "fire_resistance_rating_minutes", "duct_penetrates_rated_separation",
    "max_suite_houses_between_firewalls", "appendix_d_conforms", "riser_negative_pressure",
    "duct_melting_point_c",
}
PROCESS_CITES = {
    "rationale": "2.3.1.1.(2)(a)",
    "risk_assessment": "2.3.1.1.(3)",
    "mitigating_measures": "2.3.1.1.(3)",
    "assumptions_and_limits": "2.3.1.1.(3)",
    "maintenance_operation": "2.3.1.1.(2)(b)",
    "qualifications": "2.3.1.1.(4)",
}
WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
}


@dataclass
class Answer:
    status: str
    value: object
    text: str


@dataclass
class Session:
    prompt: Prompt
    _hidden: dict
    questions: list[dict] = field(default_factory=list)
    stages: list[str] = field(default_factory=list)
    obtained: dict = field(default_factory=dict)
    allowed_ids: set[str] = field(default_factory=set)
    process_asked: list[str] = field(default_factory=list)
    evaluations: list[dict] = field(default_factory=list)
    silent_fills: list[str] = field(default_factory=list)
    _stated: dict | None = None

    def __post_init__(self) -> None:
        self._index = load_index()
        self.allowed_ids.update(PID.findall(self.prompt.text))
        self.allowed_ids.update(STANDATA.findall(self.prompt.text))
        self.allowed_ids.update(CCMC.findall(self.prompt.text))

    def stage(self, name: str) -> None:
        if name not in self.stages:
            self.stages.append(name)

    def facts(self) -> str:
        return self.prompt.fact_text or self.prompt.text

    def stated(self) -> dict:
        if self._stated is None:
            self._stated = _stated(self.facts(), self._hidden, self._index)
        return dict(self._stated)

    def take(self, name: str):
        value = self.stated().get(name)
        if value is not None:
            self.obtained[name] = value
        return value

    def ask(self, *, stage: str, field: str, text: str, answerer: str | None = None, kind: str = "other") -> Answer:
        self.stage(stage)
        who = answerer or ("office" if field in OFFICE else "designer" if field in DESIGNER else "applicant")
        answer = self._answer(field)
        if answer.status == "answered":
            self.obtained[field] = answer.value
        self.questions.append({
            "n": len(self.questions) + 1,
            "stage": stage,
            "field": field,
            "answerer": who,
            "kind": kind,
            "text": text,
            "answer": answer.text,
            "status": answer.status,
        })
        return answer

    def confirm_reading(self) -> None:
        rows = self.stated()
        if not rows:
            return
        self.stage("understand")
        self.obtained.update(rows)
        preview = "; ".join(f"{k}: {v}" for k, v in list(rows.items())[:6])
        self.questions.append({
            "n": len(self.questions) + 1,
            "stage": "understand",
            "field": "understood",
            "answerer": "applicant",
            "text": f"Here’s what I understood. {preview}",
            "answer": "Looks right",
            "status": "answered",
            "kind": "confirm",
        })

    def classify(self):
        self.stage("scope")
        return classify(self.prompt.text)

    def assess(self):
        self.stage("route")
        return assess(self.prompt.text)

    def plan(self, known: set[str], departure_known: bool):
        return plan_questions(
            known=known, prose=self.prompt.text, candidates=[], conflicts=[], not_sure=set(),
            role=None, departure_known=departure_known,
        )

    def evaluate_rule(self, rule_id: str, facts: dict) -> dict:
        for key in facts:
            if key not in self.obtained and key not in self.stated():
                self.silent_fills.append(key)
        rule = load_rule(rule_id)
        result = evaluate(rule, facts)
        blob = " ".join([
            result.get("message") or "",
            result["provision"]["id"],
            result["provision"].get("citation") or "",
            " ".join(result.get("assumptions") or []),
        ])
        self.allowed_ids.update(PID.findall(blob))
        self.evaluations.append({"rule_id": rule_id, "state": result["state"], "provision": result["provision"]["id"]})
        return result

    def allow_process_cites(self) -> None:
        for fid in self.process_asked:
            cite = PROCESS_CITES.get(fid)
            if cite:
                self.allowed_ids.add(cite)

    def _answer(self, field: str) -> Answer:
        if field in self._hidden:
            value = self._hidden[field]
            return Answer("answered", value, _show(value))
        if field in self.stated():
            value = self.stated()[field]
            return Answer("answered", value, _show(value))
        special = _special(field, self.prompt.text)
        if special is not None:
            return special
        parsed = _parse_field(field, self.facts())
        if parsed is not None:
            return Answer("answered", parsed, _show(parsed))
        return Answer("not_sure", None, "Not sure")


def _show(value: object) -> str:
    if value is True:
        return "Yes"
    if value is False:
        return "No"
    return str(value)


def _numbers(text: str) -> list[float]:
    return [float(token) for token in re.findall(r"\d+(?:\.\d+)?", text)]


def _stated(text: str, hidden: dict, index: dict) -> dict:
    found = {"alternative_description": text.strip()} if text.strip() else {}
    specs = index["inputs"]
    for key, value in hidden.items():
        spec = specs.get(key)
        if spec and _evidenced(text, key, value, spec):
            found[key] = value
    for key, value in _parsed_facts(text).items():
        found.setdefault(key, value)
    return found


def _evidenced(text: str, field: str, value, spec: dict) -> bool:
    if spec["type"] in ("number", "int"):
        try:
            target = float(value)
        except (TypeError, ValueError):
            return False
        return any(abs(number - target) < 1e-9 for number in _numbers(text))
    if field == "sprinklered":
        return _sprinkler_phrase(text) == value
    if field == "occupancy":
        return _occupancy_phrase(text) == value
    if spec["type"] == "bool":
        return False
    return False


def _sprinkler_phrase(text: str) -> str | None:
    if re.search(r"unsprinklered|no sprinklers?|not sprinklered", text, re.I):
        return "no"
    if re.search(r"partial(?:ly)? sprinklered|partly sprinklered", text, re.I):
        return "partial"
    if re.search(r"\bsprinklered\b", text, re.I):
        return "yes"
    return None


def _occupancy_phrase(text: str) -> str | None:
    if re.search(r"townhouses?|row houses?|apartments?|dwelling units", text, re.I):
        return "multi_family"
    if re.search(r"single[-\s]family|detached", text, re.I):
        return "single_family"
    return None


def _parsed_facts(text: str) -> dict:
    out: dict = {}
    storeys = _storeys(text)
    if storeys is not None:
        out["storeys"] = storeys
    area = _building_area(text)
    if area is not None:
        out["building_area_m2"] = area
    sprinkler = _sprinkler_phrase(text)
    if sprinkler:
        out["sprinklered"] = sprinkler
    occupancy = _occupancy_phrase(text)
    if occupancy:
        out["occupancy"] = occupancy
    houses = _count_before(text, r"townhouses?|houses")
    if houses is not None:
        out["houses_in_building"] = houses
    if houses is not None and re.search(r"\b(?:each|every)\b.{0,50}\bsuites?\b", text, re.I):
        out["houses_with_secondary_suite"] = houses
    soffit = _soffit_projects(text)
    if soffit is not None:
        out["soffit_projects"] = soffit
    limiting = _limiting_distance(text)
    if limiting is not None:
        out["limiting_distance_m"] = limiting
    public = _public_way(text)
    if public is not None:
        out["faces_public_way"] = public
    for label, field in (
        ("Owner", "owner"),
        ("Address", "municipal_address"),
        ("Legal", "legal_description"),
        ("Building permit", "permit"),
    ):
        value = _table(text, label)
        if value and not re.search(r"don'?t have|not decided|not applied|placeholder|0000 Example|Lot 0", value, re.I):
            out[field] = value
    return out


def _building_area(text: str) -> float | None:
    match = re.search(r"building area(?:[^\d]{0,40})(\d+(?:\.\d+)?)\s*m(?:2|²)", text, re.I)
    if match:
        return float(match.group(1))
    match = re.search(r"\|\s*Building\s*\|[^|\n]*?(\d+(?:\.\d+)?)\s*m(?:2|²)", text, re.I)
    if match:
        return float(match.group(1))
    return None


def _storeys(text: str) -> int | None:
    if re.search(r"single-storey|one-storey|1-storey", text, re.I):
        return 1
    word = re.search(r"\b(one|two|three|four|five|six|seven|eight|nine|\d+)\s*-?\s*storeys?\b", text, re.I)
    if not word:
        return None
    token = word.group(1).lower()
    return WORDS.get(token, int(token) if token.isdigit() else None)


def _soffit_projects(text: str) -> bool | None:
    if re.search(r"no projecting soffit|soffit does not project", text, re.I):
        return False
    if re.search(r"projecting soffit|soffit (?:would|will) project|roof overhang|eave overhang", text, re.I):
        return True
    return None


def _limiting_distance(text: str) -> float | None:
    match = re.search(
        r"limiting distance(?:\s+\w+){0,4}\s+(\d+(?:\.\d+)?)\s*m\b",
        text, re.I,
    )
    if not match:
        match = re.search(r"(\d+(?:\.\d+)?)\s*m from the (?:property|lot) line", text, re.I)
    if not match:
        return None
    return float(match.group(1))


def _public_way(text: str) -> bool | None:
    if re.search(r"faces a public way|faces (?:a|the) street", text, re.I):
        return True
    if re.search(r"not a (?:street|lane|public way)", text, re.I):
        return False
    return None


def _count_before(text: str, noun: str) -> int | None:
    match = re.search(
        rf"(?<![\d.])\b(one|two|three|four|five|six|seven|eight|nine|\d+)\b(?![\d.])(?:\W+\w+){{0,3}}\W+(?:{noun})\b",
        text, re.I,
    )
    if not match:
        return None
    token = match.group(1).lower()
    return WORDS.get(token, int(token) if token.isdigit() else None)


def _table(text: str, label: str) -> str | None:
    match = re.search(rf"\|\s*{label}[^|\n]*\|\s*([^|\n]+)", text, re.I)
    if not match:
        return None
    return re.sub(r"\s+", " ", match.group(1)).strip(" *")


def _parse_field(field: str, text: str):
    return _parsed_facts(text).get(field)


def _special(field: str, text: str) -> Answer | None:
    if field == "applicable_solution":
        match = PID.search(text)
        if match:
            return Answer("answered", match.group(0), match.group(0))
        return Answer("not_sure", None, "Not sure")
    if field == "add_rule":
        return Answer("answered", "yes", "Yes, add it")
    if field == "diamond":
        needed = assess(text).variance_needed
        if needed == "likely":
            return Answer("answered", "no", "No. What I want to build is not the usual code requirement.")
        if needed == "not_indicated":
            return Answer("answered", "yes", "Yes. I am following the usual code requirement.")
        return Answer("not_sure", None, "Not sure")
    if field == "route":
        needed = assess(text).variance_needed
        if needed == "not_indicated":
            return Answer("answered", "standard", "Use the standard way")
        if needed == "likely":
            return Answer("answered", "variance", "Continue")
        return Answer("not_sure", None, "Not sure")
    if field == "product_scope":
        if re.search(r"across alberta", text, re.I) and re.search(r"house|pilot|building|site", text, re.I):
            return Answer("answered", "both", "Both: across Alberta, and one pilot building.")
        if re.search(r"across alberta", text, re.I):
            return Answer("answered", "product_acceptance", "Across Alberta")
        return Answer("answered", "site", "One building or site")
    if field == "rationale":
        sentence = re.split(r"(?<=[.!?])\s+", text.strip())[0][:400]
        if sentence:
            return Answer("answered", sentence, sentence)
        return None
    if field in {"compare", "gaps", "equivalent_performance", "detailed_code_analysis", "division_b"}:
        return Answer("not_sure", None, "Not sure")
    if field in {"objectives", "functional_statements", "intent_statements", "minimum_performance"}:
        return Answer("not_sure", None, "Not sure")
    return None
