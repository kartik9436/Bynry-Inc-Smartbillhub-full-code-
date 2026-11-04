// DEF-LED-10076 — every journal SOURCE word reaches a catalogue entry.
//
// The column and the Source filter both pass the raw value as i18next's
// `defaultValue`, so a missing key never fails: it quietly prints `payment`,
// `opening_balance` or `credit_note` to a clerk. This asserts the words
// exist instead of trusting the fallback.
import { describe, expect, it } from "vitest";

import en from "@/i18n/locales/en.json";

import { JOURNAL_SOURCES } from "./JournalView";

/** `ledger/reporting.py` TYPE_* — the words `source_label` can carry. */
const SERVER_SOURCE_WORDS = [
  "bill",
  "payment",
  "adjustment",
  "refund",
  "deposit",
  "write-off",
  "opening",
  "remittance",
  "manual JE",
  "transfer",
] as const;

const catalogue = en as Record<string, string>;

describe("DEF-LED-10076 · journal source words", () => {
  it("every word the SOURCE column can receive has a label", () => {
    const missing = SERVER_SOURCE_WORDS.filter((w) => !catalogue[`finance.journal.source.${w}`]);
    expect(missing).toEqual([]);
  });

  it("every Source filter option has a label, never its raw code", () => {
    const missing = JOURNAL_SOURCES.filter((code) => !catalogue[`finance.journal.sourceCode.${code}`]);
    expect(missing).toEqual([]);
  });
});
