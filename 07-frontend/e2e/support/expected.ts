// FI-06 support — expectation-CSV loader (B12 r3 §5: journeys assert against
// the machine-computed expectation dataset, never hand math — docs and tests
// physically cannot drift; the 04-e2e-expected-gen.py harness regenerates the
// CSV in CI, so a rule change that shifts any figure fails loudly).
//
// Money figures stay EXACT DECIMAL STRINGS end-to-end (CLAUDE.md rule 2):
// assertions compare "97.41" === "97.41" — parseFloat never appears here or
// in any journey spec.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

// e2e/support → 07-frontend → repo root.
const REPO_ROOT = resolve(fileURLToPath(new URL(".", import.meta.url)), "../../..");
export const MONEY_TRIPLES_CSV = resolve(REPO_ROOT, "08-qa/01-e2e/expected/money-triples.csv");
// ❄️ FROZEN, finance-signed 2026-08-08. The SAME file `10-scripts/03-golden-verify.py`
// Part 2 parses (see `goldenCalc` below for why a browser spec reads it directly).
export const GOLDEN_TESTS_MD = resolve(REPO_ROOT, "04-docs/02-decisions/05-golden-tests.md");

// One row of the FULL A×D×E money-triple dataset (00-e2e-design.md §2 T3):
// key = (shape, bill_type, payment); everything else is the frozen expectation.
export interface MoneyTriple {
  shape: string; // plan/tariff shape (axis A)
  bill_type: string; // bill type (axis D)
  payment: string; // payment outcome (axis E)
  taxable: string; // money — exact decimal strings, never floats
  tax: string;
  total: string;
  paid: string;
  outstanding: string;
  credit: string;
  next_late_fee: string;
  notes: string;
}

const HEADER = [
  "shape",
  "bill_type",
  "payment",
  "taxable",
  "tax",
  "total",
  "paid",
  "outstanding",
  "credit",
  "next_late_fee",
  "notes",
];

// Minimal RFC-4180 field split: the dataset quotes only fields containing
// commas (see the backbill rows' notes); doubled quotes inside quoted fields
// unescape to one.
function splitCsvLine(line: string): string[] {
  const fields: string[] = [];
  let current = "";
  let quoted = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (quoted) {
      if (ch === '"' && line[i + 1] === '"') {
        current += '"';
        i++;
      } else if (ch === '"') {
        quoted = false;
      } else {
        current += ch;
      }
    } else if (ch === '"') {
      quoted = true;
    } else if (ch === ",") {
      fields.push(current);
      current = "";
    } else {
      current += ch;
    }
  }
  fields.push(current);
  return fields;
}

let cache: MoneyTriple[] | null = null;

export function loadMoneyTriples(): MoneyTriple[] {
  if (cache !== null) {
    return cache;
  }
  // The generator writes CRLF line endings — split on either.
  const lines = readFileSync(MONEY_TRIPLES_CSV, "utf-8").trim().split(/\r?\n/);
  const header = splitCsvLine(lines[0]);
  if (header.join(",") !== HEADER.join(",")) {
    // The dataset's shape is a contract — a silently changed header must fail
    // every money assertion loudly, not misalign columns.
    throw new Error(`money-triples.csv header changed: got [${header.join(", ")}]`);
  }
  cache = lines.slice(1).map((line) => {
    const cells = splitCsvLine(line);
    return {
      shape: cells[0],
      bill_type: cells[1],
      payment: cells[2],
      taxable: cells[3],
      tax: cells[4],
      total: cells[5],
      paid: cells[6],
      outstanding: cells[7],
      credit: cells[8],
      next_late_fee: cells[9],
      notes: cells[10] ?? "",
    };
  });
  return cache;
}

// The lookup journeys use for money assertions, e.g.
//   moneyTriple("flat", "cycle", "full").total === "97.41"
export function moneyTriple(shape: string, billType: string, payment: string): MoneyTriple {
  const row = loadMoneyTriples().find(
    (r) => r.shape === shape && r.bill_type === billType && r.payment === payment,
  );
  if (row === undefined) {
    throw new Error(
      `no money-triples.csv row for (${shape}, ${billType}, ${payment}) — ` +
        "the journey cites an expectation the dataset does not carry",
    );
  }
  return row;
}

// ══════════════════════════════════════════════════════════════════════════
// B5 ❄️ — the FINANCE-SIGNED figures, read from the document finance signed
// ══════════════════════════════════════════════════════════════════════════
//
// WHY A SECOND SOURCE EXISTS BESIDE money-triples.csv, and when to use which.
//
//   · `moneyTriple(...)` serves the 245 MACHINE-COMPUTED rows of the A×D×E
//     dataset — the generator (`10-scripts/04-e2e-expected-gen.py`) derives
//     them from the frozen B4 RULES. That is the right source for any journey
//     whose combination the dataset carries.
//   · `goldenCalc(...)` serves the GT-1..GT-16 prose fixtures, which are
//     figures a human at a finance sitting SIGNED, one at a time, and which no
//     generator produces. `10-scripts/03-golden-verify.py` Part 2 parses this
//     same file for the same reason: *"there is no raw-input workbook to
//     recompute them from"*.
//
// The PO's 2026-08-11 ruling is what makes the second one matter to a BROWSER
// spec: *"we ahve to prove against human clicking"* — the thing no check
// proved was that **the figure a human SEES equals the figure finance signed**.
// Retyping "108.88" into a spec would make a second copy of a signed figure,
// which is the drift CLAUDE.md forbids and which DEF-028 already cost this
// repo once. So the spec reads B5, and a finance re-sign (HUMAN-GUIDE §6) that
// moves a figure moves the browser assertion in the same commit.
//
// THIS MODULE NEVER COMPUTES. It parses, and it throws when the text does not
// say what it expects — a loader that guessed would be a third opinion on a
// frozen number.

export interface GoldenCalc {
  id: string; // "GT-1"
  heading: string; // the `## GT-n — …` line, verbatim
  input: string; // the "Input: …" line, verbatim
  calc: string; // the "…calc: …" line, verbatim
  steps: readonly string[]; // the trailing figure of each `;`-separated clause
  total: string; // the `**total N**` marker — the signed headline figure
}

let goldenCache: Map<string, GoldenCalc> | null = null;

// `## GT-1 — Simple flat residential (single service)` … up to the next heading.
function loadGoldenSections(): Map<string, string[]> {
  const sections = new Map<string, string[]>();
  let current: string | null = null;
  for (const line of readFileSync(GOLDEN_TESTS_MD, "utf-8").split(/\r?\n/)) {
    if (line.startsWith("#")) {
      const match = /^##\s+(GT-\d+)\b/.exec(line);
      current = match === null ? null : match[1];
      if (current !== null) {
        sections.set(current, [line]);
      }
      continue;
    }
    if (current !== null) {
      sections.get(current)?.push(line);
    }
  }
  return sections;
}

// B5 writes its worked sums out longhand and separates the steps with `;`:
//
//   Assumed calc: 684×0.12 = 82.08; +18.50 = 100.58; tax 8.2979 → 8.30; **total 108.88**.
//
// so the trailing figure of each clause IS the step's result, in order — usage,
// taxable subtotal, tax, total. Extracting them this way (rather than four
// hand-written regexes) is what `03-golden-verify.py`'s scanner does in spirit:
// no per-GT knowledge, and a clause that states no figure is dropped rather
// than guessed at.
const TRAILING_FIGURE = /(\d+(?:,\d{3})*(?:\.\d+)?)[^\d]*$/;
const TOTAL_MARKER = /\*\*total\s+([\d,]+(?:\.\d+)?)\*\*/i;

export function loadGoldenCalcs(): Map<string, GoldenCalc> {
  if (goldenCache !== null) {
    return goldenCache;
  }
  const parsed = new Map<string, GoldenCalc>();
  for (const [id, lines] of loadGoldenSections()) {
    const heading = lines[0];
    const input = lines.find((line) => /^Input:/.test(line)) ?? "";
    const calc = lines.find((line) => /calc:/i.test(line)) ?? "";
    if (calc === "") {
      // Not every GT states a longhand sum (GT-3 pins one figure in prose).
      // A fixture that says too little is SKIPPED here, never faked — the same
      // posture as 03-golden-verify.py's NOT-CHECKABLE.
      continue;
    }
    // Everything after "calc:" up to the closing full stop, minus the
    // SUPERSEDED stamp that DEF-023 appends to every line in this file.
    const body = calc.slice(calc.toLowerCase().indexOf("calc:") + 5).split(" — **SUPERSEDED**")[0];
    const steps: string[] = [];
    for (const clause of body.split(";")) {
      const match = TRAILING_FIGURE.exec(clause.replace(/\*\*/g, "").trim());
      if (match !== null) {
        steps.push(match[1].replace(/,/g, ""));
      }
    }
    const totalMatch = TOTAL_MARKER.exec(calc);
    parsed.set(id, {
      id,
      heading,
      input,
      calc,
      steps,
      total: totalMatch === null ? "" : totalMatch[1].replace(/,/g, ""),
    });
  }
  goldenCache = parsed;
  return parsed;
}

// The lookup a browser journey uses, e.g.
//   goldenCalc("GT-1").total === "108.88"
export function goldenCalc(id: string): GoldenCalc {
  const found = loadGoldenCalcs().get(id);
  if (found === undefined) {
    throw new Error(
      `no ${id} worked calculation in 05-golden-tests.md — the journey cites a ` +
        "frozen fixture the signed document does not state longhand",
    );
  }
  if (found.total === "") {
    throw new Error(
      `${id} states no **total N** figure in 05-golden-tests.md — a journey may ` +
        "not assume one; report it rather than choosing a number",
    );
  }
  return found;
}
