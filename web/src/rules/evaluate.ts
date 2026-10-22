/**
 * Coded rules: the live evaluator for the browser (what-if as the applicant types).
 *
 * The authoritative evaluator is engine/rules/evaluator.py; this file implements the same semantics line for
 * line over the same rule data (served by `GET /rules`). Both run evals_dev/rules/vectors.json, and the full
 * outputs must equal evals_dev/rules/outputs.json (web/src/rules/rules.test.ts). Change both or neither.
 *
 * A result says the design "follows" or "departs from" the acceptable solution; it is a departure flag,
 * never a finding about the design as a whole.
 */

export type RuleState = "follows" | "departs" | "needs_info" | "not_applicable";
export type Value = string | number | boolean;
export type Expr =
  | Value
  | { var: string }
  | { op: "table"; table: string; row: Expr; col: Expr; mode: "lesser" | "interpolate" }
  | { op: "in"; args: [Expr, Value[]] }
  | { op: string; args: Expr[] };

export interface InputSpec {
  field: string;
  label: string;
  type: "number" | "int" | "bool" | "enum";
  unit?: string;
  min?: number;
  choices?: { value: string; label: string }[];
  question: string;
  why: string;
}

export interface RuleProvision { id: string; division: string; pdf_page: number; citation: string }
export interface RuleTable {
  id: string;
  group?: string;
  pdf_page: number;
  columns: number[];
  rows: { max_area: number | null; values: (number | null)[] }[];
}
export interface Derived { name: string; label: string; unit?: string; expr: Expr }
export interface Outcome {
  id: string;
  state: Exclude<RuleState, "needs_info">;
  provision: string;
  when: Expr;
  message: string;
  if_unknown?: "ask" | "assume";
  assumption?: string;
}
export interface RuleDef {
  id: string;
  title: string;
  article: string;
  reviewed?: boolean;
  provisions: RuleProvision[];
  tables: RuleTable[];
  inputs: string[];
  derived: Derived[];
  outcomes: Outcome[];
  not_checked: string[];
}
export interface RuleIndex {
  rules: string[];
  departs_next_step: string;
  needs_info_message: string;
  states: Record<RuleState, string>;
  inputs: Record<string, InputSpec>;
}

export interface RuleResult {
  rule_id: string;
  title: string;
  article: string;
  state: RuleState;
  state_label: string;
  outcome_id: string | null;
  provision: { id: string; division: string; citation: string; pdf_page: number };
  message: string;
  next_step: string | null;
  missing: { field: string; label: string; question: string; why: string }[];
  inputs: { field: string; label: string; unit: string | null; value: Value | null }[];
  ignored_inputs: string[];
  computed: { name: string; label: string; unit: string | null; value: Value | null }[];
  assumptions: string[];
  not_checked: string[];
  reviewed: boolean;
}

export const EPS = 1e-9;
const MAX_SPLIT = 64;
const PLACEHOLDER = /\{([a-z0-9_]+)\}/g;

type Got = [Value | null, Set<string>];
const NONE = (): Set<string> => new Set();

function isNum(v: unknown): v is number {
  return typeof v === "number" && Number.isFinite(v);
}

/** The value if it is valid for the input's type, else null (treated as missing). */
export function normalize(spec: InputSpec, value: unknown): Value | null {
  if (spec.type === "bool") return typeof value === "boolean" ? value : null;
  if (spec.type === "enum") {
    return typeof value === "string" && (spec.choices ?? []).some((c) => c.value === value) ? value : null;
  }
  if (!isNum(value)) return null;
  if (spec.type === "int" && !Number.isInteger(value)) return null;
  if (spec.min !== undefined && value < spec.min) return null;
  return value;
}

/** Numbers to at most 2 decimals, half up, trailing zeros dropped. Same digits as the Python fmt. */
export function fmt(value: Value): string {
  if (typeof value === "boolean") return value ? "yes" : "no";
  if (isNum(value)) {
    const negative = value < 0;
    const hundredths = Math.floor(Math.abs(value) * 100 + 0.5);
    const whole = Math.floor(hundredths / 100);
    const frac = hundredths % 100;
    const text = frac === 0 ? `${whole}` : frac % 10 === 0 ? `${whole}.${frac / 10}` : `${whole}.${String(frac).padStart(2, "0")}`;
    return negative && hundredths ? `-${text}` : text;
  }
  return String(value);
}

/** '2.1' + 'm²' -> '2.1 m²'; '7' + '%' -> '7%'. */
export function withUnit(text: string, unit: string | null | undefined): string {
  return !unit ? text : unit === "%" ? `${text}%` : `${text} ${unit}`;
}

class Env {
  readonly rule: RuleDef;
  readonly inputs: Record<string, Value>;
  readonly specs: Record<string, InputSpec>;
  readonly tables: Record<string, RuleTable>;
  readonly derived: Map<string, Derived>;
  readonly memo = new Map<string, Got>();
  constructor(rule: RuleDef, inputs: Record<string, Value>, specs: Record<string, InputSpec>, tables: Record<string, RuleTable>) {
    this.rule = rule;
    this.inputs = inputs;
    this.specs = specs;
    this.tables = tables;
    this.derived = new Map(rule.derived.map((d) => [d.name, d]));
  }
  withInputs(overrides: Record<string, Value>): Env {
    return new Env(this.rule, { ...this.inputs, ...overrides }, this.specs, this.tables);
  }
}

function equal(a: Value, b: Value): boolean {
  if (isNum(a) && isNum(b)) return Math.abs(a - b) <= EPS;
  return typeof a === typeof b && a === b;
}

function union(sets: Set<string>[]): Set<string> {
  const out = new Set<string>();
  for (const s of sets) for (const f of s) out.add(f);
  return out;
}

function table(env: Env, expr: { table: string; mode: string }, row: number, col: number): number {
  const t = env.tables[expr.table];
  const picked =
    t.rows.find((r) => r.max_area !== null && row <= r.max_area + EPS) ?? t.rows.find((r) => r.max_area === null)!;
  const values = picked.values.map((v) => (v === null ? 100 : v));
  const cols = t.columns;
  let index = 0;
  cols.forEach((c, i) => {
    if (i === 0 || col >= c - EPS) index = i;
  });
  const lesser = values[index];
  if (expr.mode === "lesser" || col <= 1.2 + EPS || index === cols.length - 1) return lesser;
  if (expr.mode !== "interpolate") throw new Error(`unknown table mode ${expr.mode}`);
  const [c0, c1, v0, v1] = [cols[index], cols[index + 1], values[index], values[index + 1]];
  return v0 + (v1 - v0) * (col - c0) / (c1 - c0);
}

/** [value, missing inputs that made it unknown]. value null means unknown. */
export function ev(expr: Expr, env: Env): Got {
  if (typeof expr === "boolean" || isNum(expr) || typeof expr === "string") return [expr, NONE()];
  if (typeof expr !== "object" || expr === null) throw new Error(`bad expression ${JSON.stringify(expr)}`);
  if ("var" in expr) {
    const name = expr.var;
    if (name in env.specs) {
      const value = env.inputs[name];
      return value !== undefined ? [value, NONE()] : [null, new Set([name])];
    }
    const derived = env.derived.get(name);
    if (derived) {
      if (!env.memo.has(name)) env.memo.set(name, ev(derived.expr, env));
      return env.memo.get(name)!;
    }
    throw new Error(`unknown name ${name}`);
  }
  if (expr.op === "table") {
    const t = expr as { table: string; row: Expr; col: Expr; mode: string };
    const [row, m1] = ev(t.row, env);
    const [col, m2] = ev(t.col, env);
    if (row === null || col === null) return [null, union([m1, m2])];
    return [table(env, t, row as number, col as number), NONE()];
  }
  const op = expr.op;
  if (op === "in") {
    const [first, list] = (expr as { args: [Expr, Value[]] }).args;
    const [value, missing] = ev(first, env);
    return value === null ? [null, missing] : [list.includes(value), NONE()];
  }
  const args = (expr as { args: Expr[] }).args.map((a) => ev(a, env));
  const unknown = union(args.filter(([v]) => v === null).map(([, m]) => m));
  const values = args.map(([v]) => v);
  if (op === "and") {
    if (values.some((v) => v === false)) return [false, NONE()];
    return values.some((v) => v === null) ? [null, unknown] : [true, NONE()];
  }
  if (op === "or") {
    if (values.some((v) => v === true)) return [true, NONE()];
    return values.some((v) => v === null) ? [null, unknown] : [false, NONE()];
  }
  if (op === "if") {
    const [[cond, mc], [a, ma], [b, mb]] = args;
    if (cond === null) {
      if (a !== null && b !== null && equal(a, b)) return [a, NONE()];
      return [null, union([mc, ma, mb])];
    }
    return cond ? [a, ma] : [b, mb];
  }
  if (values.some((v) => v === null)) return [null, unknown];
  const vs = values as Value[];
  switch (op) {
    case "not":
      return [!vs[0], NONE()];
    case "lt":
    case "le":
    case "gt":
    case "ge": {
      const [a, b] = vs;
      if (!isNum(a) || !isNum(b)) throw new Error(`${op} needs numbers`);
      const r = op === "lt" ? a < b - EPS : op === "le" ? a <= b + EPS : op === "gt" ? a > b + EPS : a >= b - EPS;
      return [r, NONE()];
    }
    case "eq":
      return [equal(vs[0], vs[1]), NONE()];
    case "ne":
      return [!equal(vs[0], vs[1]), NONE()];
    case "add":
      return [(vs[0] as number) + (vs[1] as number), NONE()];
    case "sub":
      return [(vs[0] as number) - (vs[1] as number), NONE()];
    case "mul":
      return [(vs[0] as number) * (vs[1] as number), NONE()];
    case "div":
      return [(vs[0] as number) / (vs[1] as number), NONE()];
    case "min":
      return [Math.min(...(vs as number[])), NONE()];
    case "max":
      return [Math.max(...(vs as number[])), NONE()];
  }
  throw new Error(`unknown op ${op}`);
}

function domain(spec: InputSpec): Value[] | null {
  if (spec.type === "bool") return [true, false];
  if (spec.type === "enum") return (spec.choices ?? []).map((c) => c.value);
  return null;
}

/** Every combination, first field varying slowest (Python itertools.product order). */
function product(domains: Value[][]): Value[][] {
  return domains.reduce<Value[][]>((acc, d) => acc.flatMap((prefix) => d.map((v) => [...prefix, v])), [[]]);
}

function zip(fields: string[], combo: Value[]): Record<string, Value> {
  return Object.fromEntries(fields.map((f, i) => [f, combo[i]]));
}

function decide(when: Expr, env: Env, order: string[]): [boolean | null, string[]] {
  const [value, missing] = ev(when, env);
  if (value !== null) return [Boolean(value), []];
  const fields = order.filter((f) => missing.has(f));
  const finite = fields.filter((f) => domain(env.specs[f]) !== null);
  const domains = finite.map((f) => domain(env.specs[f])!);
  if (!finite.length || domains.reduce((n, d) => n * d.length, 1) > MAX_SPLIT) return [null, fields];
  const results: (Value | null)[] = [];
  const still = new Set<string>();
  for (const combo of product(domains)) {
    const [result, left] = ev(when, env.withInputs(zip(finite, combo)));
    results.push(result);
    for (const f of left) still.add(f);
  }
  if (results.every((r) => r === null)) return [null, order.filter((f) => still.has(f))];
  if (results.every((r) => r !== null) && new Set(results).size === 1) return [Boolean(results[0]), []];
  return [null, fields];
}

function unitOf(env: Env, name: string): string | undefined {
  return name in env.specs ? env.specs[name].unit : env.derived.get(name)?.unit;
}

function render(template: string, env: Env): string {
  return template.replace(PLACEHOLDER, (_m, name: string) => {
    const [found, missing] = ev({ var: name }, env);
    if (found !== null) return withUnit(fmt(found), unitOf(env, name));
    if (name in env.specs) return "not stated";
    const finite = env.rule.inputs.filter((f) => missing.has(f) && domain(env.specs[f]) !== null);
    if (finite.length !== missing.size) return "not determined";
    const shown: string[] = [];
    for (const combo of product(finite.map((f) => domain(env.specs[f])!))) {
      const [value] = ev({ var: name }, env.withInputs(zip(finite, combo)));
      if (value === null) return "not determined";
      if (!shown.includes(fmt(value))) shown.push(fmt(value));
    }
    return withUnit(shown.join(" or "), unitOf(env, name));
  });
}

function tablesOf(rule: RuleDef): Record<string, RuleTable> {
  return Object.fromEntries(rule.tables.map((t) => [t.id + (t.group ? `|${t.group}` : ""), t]));
}

/** Evaluate one rule over raw input values (field -> value). Pure: no case, no network. */
export function evaluate(rule: RuleDef, given: Record<string, unknown>, index: RuleIndex): RuleResult {
  const specs = Object.fromEntries(rule.inputs.map((f) => [f, index.inputs[f]]));
  const inputs: Record<string, Value> = {};
  const ignored: string[] = [];
  for (const field of rule.inputs) {
    const raw = given[field];
    if (raw === undefined || raw === null) continue;
    const value = normalize(specs[field], raw);
    if (value === null) ignored.push(field);
    else inputs[field] = value;
  }
  const env = new Env(rule, inputs, specs, tablesOf(rule));
  const provisions = new Map(rule.provisions.map((p) => [p.id, p]));
  const assumptions: string[] = [];
  let chosen: Outcome | null = null;
  let missing: string[] = [];
  for (const outcome of rule.outcomes) {
    let decided: boolean | null;
    [decided, missing] = decide(outcome.when, env, rule.inputs);
    if (decided === null && outcome.if_unknown === "assume") {
      assumptions.push(outcome.assumption ?? "");
      continue;
    }
    if (decided === null || decided) {
      chosen = outcome;
      break;
    }
  }
  if (!chosen) throw new Error(`no outcome matched in rule ${rule.id}`);
  const needsInfo = missing.length > 0;
  const state: RuleState = needsInfo ? "needs_info" : chosen.state;
  const provisionId = needsInfo ? rule.provisions[0].id : chosen.provision;
  const provision = provisions.get(provisionId)!;
  const message = needsInfo ? index.needs_info_message.replace("{provision}", provisionId) : render(chosen.message, env);
  return {
    rule_id: rule.id,
    title: rule.title,
    article: rule.article,
    state,
    state_label: index.states[state],
    outcome_id: needsInfo ? null : chosen.id,
    provision: { id: provision.id, division: provision.division, citation: provision.citation, pdf_page: provision.pdf_page },
    message,
    next_step: state === "departs" ? index.departs_next_step : null,
    missing: missing.map((f) => ({ field: f, label: specs[f].label, question: specs[f].question, why: specs[f].why })),
    inputs: rule.inputs.map((f) => ({ field: f, label: specs[f].label, unit: specs[f].unit ?? null, value: inputs[f] ?? null })),
    ignored_inputs: ignored,
    computed: rule.derived.map((d) => ({ name: d.name, label: d.label, unit: d.unit ?? null, value: ev({ var: d.name }, env)[0] })),
    assumptions,
    not_checked: [...rule.not_checked],
    reviewed: Boolean(rule.reviewed),
  };
}

/** Every rule in index order. `rules` maps rule id to its definition (from `GET /rules`). */
export function evaluateAll(rules: Record<string, RuleDef>, index: RuleIndex, given: Record<string, unknown>): RuleResult[] {
  return index.rules.map((id) => evaluate(rules[id], given, index));
}
