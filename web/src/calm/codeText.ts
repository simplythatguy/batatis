/**
 * Structure for verbatim code text: the code database keeps the PDF's hard line breaks and its
 * markers ("1)", "a)", "i)"). This splits an article into sentences, clauses and subclauses so the
 * reader can show a numbered outline. It never changes a word: only line breaks and repeated
 * spaces are folded, the same as `reflow`.
 */

export interface Clause {
  /** "a", "b"… or "i", "ii"… */
  mark: string;
  text: string;
  sub: Clause[];
}

export interface Sentence {
  /** "1", "2"… as printed. */
  n: string;
  /** The words before the first clause (or the whole sentence when it has none). */
  lead: string;
  clauses: Clause[];
}

export interface ArticleText {
  /** Text before the first sentence marker (an article with no numbered sentences keeps it all here). */
  intro: string;
  sentences: Sentence[];
}

const SENTENCE = /^(\d{1,2})\)\s*(.*)$/;
const LETTER = /^([a-z])\)\s*(.*)$/;
const ROMAN = /^(i|ii|iii|iv|v|vi|vii|viii|ix|x|xi|xii)\)\s*(.*)$/;
const ROMANS = ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii"];

const join = (a: string, b: string) => (a ? (b ? `${a} ${b}` : a) : b);
const nextLetter = (c: string | undefined) => (c ? String.fromCharCode(c.charCodeAt(0) + 1) : "a");

export function parseArticle(raw: string): ArticleText {
  const out: ArticleText = { intro: "", sentences: [] };
  let s: Sentence | null = null;
  let c: Clause | null = null;
  let sub: Clause | null = null;
  const lines = raw.replace(/\r/g, "").split("\n").map((l) => l.replace(/[ \t]+/g, " ").trim()).filter(Boolean);
  for (const line of lines) {
    const sm = line.match(SENTENCE);
    if (sm && Number(sm[1]) === (s ? Number(s.n) + 1 : 1)) {
      s = { n: sm[1], lead: sm[2], clauses: [] };
      out.sentences.push(s);
      c = sub = null;
      continue;
    }
    if (s) {
      const rm = line.match(ROMAN);
      const lm = line.match(LETTER);
      const letterNext = nextLetter(c?.mark);
      // "i)" after "h)" is the ninth clause, not a subclause.
      const romanNext: string | undefined = c ? ROMANS[c.sub.length] : undefined;
      if (rm && c && rm[1] === romanNext && !(rm[1].length === 1 && rm[1] === letterNext)) {
        sub = { mark: rm[1], text: rm[2], sub: [] };
        c.sub.push(sub);
        continue;
      }
      if (lm && lm[1] === letterNext) {
        c = { mark: lm[1], text: lm[2], sub: [] };
        s.clauses.push(c);
        sub = null;
        continue;
      }
      if (sub) sub.text = join(sub.text, line);
      else if (c) c.text = join(c.text, line);
      else s.lead = join(s.lead, line);
      continue;
    }
    out.intro = join(out.intro, line);
  }
  return out;
}

/** One line of a sentence for its collapsed row: the lead, or the first clause when the lead is empty. */
export function previewOf(s: Sentence): string {
  return s.lead || s.clauses[0]?.text || "";
}
