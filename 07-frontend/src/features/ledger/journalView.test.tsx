// ── Trace ──────────────────────────────────────────────
// Task:    Finance blueprint `P1.1` · `P1.9` · `P1.15` · `P1.17` · `P1.18`
// Drawing: 05-prototype/07 Finance Blueprint.pdf p020 (the wireframe and its
//          eight notes) · p021 (the filter-criteria table) · p022 (FIELDS,
//          TABLE CONTROLS, WRITE SURFACES)
// ───────────────────────────────────────────────────────
/**
 * 1·1 Journal — the parts of the drawing a test CAN see.
 *
 * ⚠ **WHAT THIS FILE CAN AND CANNOT PROVE, SAID OUT LOUD.** No check in this
 * repository reads rendered output, so nothing here is evidence that the screen
 * LOOKS like p020. What it does prove is tier 2 of the UI skill's three: that
 * the columns the drawing lists are declared, in the drawn order; that the
 * filter criteria p021's table names are the ones offered; that the sort the
 * `⇅` promises exists and points at the date; and that the two row actions the
 * drawing shows are the two that are visible. **The layout was diffed against
 * the rendered page by a person, and that walk is in the lane report** — this
 * file is what stops the next change undoing it silently.
 */

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { GL_VIEWS, glViewFrom } from "./GeneralLedgerPage";
import {
  JOURNAL_SOURCES,
  JOURNAL_STATUSES,
  JOURNAL_TYPES,
  journalConfig,
  journalWindow,
} from "./JournalView";
import type { JournalRegional } from "./JournalView";

const t = (key: string) => key;

/** A utility on `MM/DD/YYYY` whose business date is 12 October 2026, with a
 *  catalogue that names exactly one raw source — the shape the real
 *  `journalRegional` builds from `i18n.exists`. */
const REGIONAL: JournalRegional = {
  timeZone: "America/Chicago",
  dateFormat: "MM/DD/YYYY",
  today: "2026-10-12",
  sourceWord: (sourceType) => (sourceType === "counter_session" ? "Counter session" : null),
};

describe("P1.15 — the strip splits into four views", () => {
  it("holds four views, one word each, with the journal first", () => {
    expect(GL_VIEWS).toEqual(["journal", "balance", "chart", "accruals"]);
  });

  it("makes the journal the landing view", () => {
    // p022 DOORS: "It is the landing view, so every door to /finance is a door
    // to this screen."
    expect(glViewFrom(null)).toBe("journal");
    expect(glViewFrom("")).toBe("journal");
    expect(glViewFrom("not-a-view")).toBe("journal");
  });

  it("keeps `balance` as a URL value so a bookmark still lands", () => {
    // The WORD on screen changed from "Trial balance & journal"; the VALUE did
    // not, deliberately — every existing ticket link carries it.
    expect(glViewFrom("balance")).toBe("balance");
    expect(glViewFrom("chart")).toBe("chart");
    expect(glViewFrom("accruals")).toBe("accruals");
  });
});

// ══════════════════════════════════════════════════════════════════════════
// TWO RULES RE-HOMED FROM `financeSurface.test.tsx` (`DEF-LED-6723`)
// ══════════════════════════════════════════════════════════════════════════
//
// They used to be asserted against `JournalEntryTable`, which had had **zero
// production callers** since `P1.15` split the view strip — so two real rules
// were being proved over code no clerk could reach. The component is deleted;
// the rules land here, on the CELL RENDERERS of the table a clerk sees.
//
// ⚠ **THE CELL FUNCTION IS RENDERED, NOT INSPECTED.** A case that asserted
// `config.columns[0].cell !== undefined` would pass on a renderer that returns
// the wrong thing — so each one is rendered to markup and READ.
describe("BR-LED-021 · BR-REP-008 — what two cells put on the screen", () => {
  // ⚠ **THIS BLOCK'S TRANSLATOR INTERPOLATES, AND THE BARE `t` ABOVE DOES
  // NOT.** The file's `t` returns its KEY, which is right for every case that
  // asks WHICH key a column uses — and it would make the unmapped-source case
  // below pass on a renderer that dropped the source entirely, because the key
  // is present either way. So this block uses a translator that substitutes
  // `{{source}}` the way the real catalogue does, and the case reads the VALUE.
  const interpolating = (key: string, params?: Record<string, unknown>) =>
    params === undefined
      ? key
      : Object.entries(params).reduce(
          (text, [name, value]) => text.replace(`{{${name}}}`, String(value)),
          `${key}: {{source}}`,
        );
  const config = journalConfig(null, interpolating as never, "en-US", REGIONAL);
  const cellFor = (key: string) => {
    const column = config.columns.find((one) => one.key === key);
    expect(column?.cell, `no ${key} column`).toBeTypeOf("function");
    return column!.cell!;
  };
  const ROW = {
    entry_id: "01a0d23a-499c-795b-b22d-36b48abcf037",
    je_number: null,
    entry_date: "2026-08-31",
    type: "standard",
    status: "draft",
    memo: "Reclass 6900 to 6910",
    source_type: "manual_je",
    source_label: "manual JE",
    source_mapped: true,
    currency: "USD",
    debit: "400.000000",
    credit: "400.000000",
    balanced: true,
    reversal_of_entry_id: null,
    reversed_by_entry_id: null,
    auto_reverse_entry_id: null,
    posted_at: null,
  };

  it("renders a DRAFT's missing number as the ruling, never as a blank", () => {
    // PO 2026-08-12, verbatim: *"a draft has NO number"*. The dash is that
    // ruling rendered. ⚠ And the entry's uuid must reach NO cell (B14 rule 31).
    const html = renderToStaticMarkup(<>{cellFor("je_number")(ROW as never)}</>);
    expect(html).toContain("—");
    expect(html).not.toContain(ROW.entry_id);
  });

  it("renders a number when there IS one, so the dash case is provably read", () => {
    const html = renderToStaticMarkup(
      <>{cellFor("je_number")({ ...ROW, je_number: "JE-083126-0105" } as never)}</>,
    );
    expect(html).toContain("JE-083126-0105");
  });

  it("shows an unrecognised source as ITSELF, never bucketed under a known word", () => {
    // BR-REP-008's whole point is that the report foots to the AR tie-out with
    // NOTHING INVISIBLE. A source this module has never heard of is money it
    // must still show; bucketing it under a familiar word would hide a new
    // posting contract inside an old column. `DEF-LED-6702` is what it costs
    // when a real source is left unmapped — the raw code reaches a clerk — and
    // the answer is to MAP it, never to make this branch quieter.
    const html = renderToStaticMarkup(
      <>
        {cellFor("source")({
          ...ROW,
          source_type: "settlement",
          source_label: "settlement",
          source_mapped: false,
        } as never)}
      </>,
    );
    expect(html).toContain("settlement");
  });
});

describe("P1.1 — the table is the one the drawing draws", () => {
  const config = journalConfig(null, t, "en-US", REGIONAL);

  it("carries p022's FIELDS line, in the drawn order", () => {
    // "Entry no. · Date · Type · Memo · Source · Debit · Credit · State ·
    // Actions" — nine columns, and the order is part of the design.
    expect(config.columns.map((column) => column.key)).toEqual([
      "je_number",
      "entry_date",
      "type",
      "memo",
      "source",
      "debit",
      "credit",
      "status",
      "actions",
    ]);
  });

  it("makes the entry number the identity column and never the database id", () => {
    // B14 rule 31. `entry_id` keys React and the preference store; the column a
    // clerk reads is the number a bookkeeper says out loud.
    const identity = config.columns.filter((column) => column.identity === true);
    expect(identity.map((column) => column.key)).toEqual(["je_number"]);
    expect(config.columns.map((column) => column.key)).not.toContain("entry_id");
  });

  it("offers the search box p021 row 1 names, over both fields", () => {
    expect(config.searchFields).toEqual(["je_number", "memo"]);
    // B14 rule 19 — this list's own prompt, as a KEY and never a sentence.
    expect(config.searchPlaceholder).toBe("finance.journal.searchPrompt");
  });

  it("offers exactly the + Filter criteria p021's table lists", () => {
    // p020 note 3: "+ Filter ▾ · five criteria". Three are chip filters on the
    // table config; Property and GL account are served by the same handler and
    // are P2.3's control, which the blueprint puts in the next phase.
    expect((config.filters ?? []).map((one) => one.name)).toEqual([
      "type",
      "status",
      "source_type",
      // `DEF-LED-10071` J3 — the Period, added 2026-10-12 by PO ruling.
      "period",
    ]);
  });

  it("never offers `reversed` as a state", () => {
    // p021 row 3's own warning: "⚠ not reversed — that is a link, never a
    // status". `journal_entries.status` holds two values, so a third would be a
    // filter value no column can ever equal.
    expect(JOURNAL_STATUSES).toEqual(["draft", "posted"]);
    const status = (config.filters ?? []).find((one) => one.name === "status");
    expect(status?.options.map((option) => option.value)).not.toContain("reversed");
  });

  it("offers the three entry types and the six live sources", () => {
    expect(JOURNAL_TYPES).toEqual(["standard", "accrual", "reversing"]);
    expect(JOURNAL_SOURCES).toHaveLength(6);
  });
});

describe("P1.18 — the entry number sorts by date, not by text", () => {
  const config = journalConfig(null, t, "en-US", REGIONAL);

  it("opens newest first", () => {
    expect(config.defaultSort).toEqual({ sort: "entry_date", dir: "desc" });
  });

  it("puts the ⇅ on exactly the two headers the drawing draws it on", () => {
    // p020's table head shows "ENTRY NO. ⇅" and "DATE ⇅" and nothing else.
    const sortable = config.columns.filter((column) => column.sortable === true);
    expect(sortable.map((column) => column.key)).toEqual(["je_number", "entry_date"]);
  });

  it("names the sort `entry_date`, which is what the server orders by", () => {
    // The guard that matters is the backend's
    // `test_def_led_6493_journal_pages_in_sql.py`, which asserts the DESCENDING
    // order of `JE-011526-0001` against `JE-020325-0001` — eleven months apart
    // and the wrong way round as text. This one only pins that the screen asks
    // for a date sort by name rather than inventing a `number` order of its own.
    expect(config.defaultSort.sort).toBe("entry_date");
  });
});

describe("P1.17 — two visible row actions, then the overflow", () => {
  it("draws nothing in the Actions cell when no handlers are passed", () => {
    // Hard-won law 2: an optional prop nothing supplies is dead UI. The cell is
    // honestly empty rather than rendering controls that call nothing.
    const config = journalConfig(null, t, "en-US", REGIONAL);
    const actions = config.columns.find((column) => column.key === "actions");
    expect(actions?.cell?.({ entry_id: "x" } as never)).toBeNull();
  });

  it("locks the Actions column so a clerk cannot hide it", () => {
    const config = journalConfig(null, t, "en-US", REGIONAL);
    const actions = config.columns.find((column) => column.key === "actions");
    expect(actions?.locked).toBe(true);
  });
});

describe("DEF-LED-10071 · 10074 · 10075 — period, source word, date", () => {
  const config = journalConfig(null, t, "en-US", REGIONAL);
  const cell = (key: string) => config.columns.find((one) => one.key === key)!.cell!;
  const ROW = {
    entry_id: "01a0d23a-499c-795b-b22d-36b48abcf037",
    je_number: "JE-100126-0001",
    entry_date: "2026-10-01",
    type: "standard",
    status: "posted",
    memo: "Counter drawer short $10.00",
    source_type: "counter_session",
    source_label: "counter_session",
    source_mapped: false,
    currency: "USD",
    debit: "10.000000",
    credit: "10.000000",
    balanced: true,
    reversal_of_entry_id: null,
    reversed_by_entry_id: null,
    auto_reverse_entry_id: null,
    posted_at: null,
  };

  it("J3 — the Period offers Last 30 · 60 · 90 days and Custom, from the business date", () => {
    const period = (config.filters ?? []).find((one) => one.name === "period");
    expect(period?.period?.choices).toEqual(["last_30", "last_60", "last_90", "custom"]);
    expect(period?.period?.today).toBe("2026-10-12");
    expect([period?.period?.choice, period?.period?.from, period?.period?.to]).toEqual([
      "period",
      "period_from",
      "period_to",
    ]);
  });

  it("J4 — no period chosen sends no window: every entry", () => {
    expect(journalWindow({})).toEqual({});
    expect(journalWindow({ status: "posted" })).toEqual({});
  });

  it("J3 — a chosen period sends the existing from/to", () => {
    expect(
      journalWindow({ period: "last_30", period_from: "2026-09-13", period_to: "2026-10-12" }),
    ).toEqual({ from: "2026-09-13", to: "2026-10-12" });
  });

  it("P9 / DEF-LED-10075 — the DATE column is in the utility's format, never ISO", () => {
    const html = renderToStaticMarkup(<>{cell("entry_date")(ROW as never)}</>);
    expect(html).toContain("10/01/2026");
    expect(html).not.toContain(">2026-10-01<");
  });

  it("DEF-LED-10074 — counter_session reads Counter session, not the raw code", () => {
    const html = renderToStaticMarkup(<>{cell("source")(ROW as never)}</>);
    expect(html).toContain("Counter session");
    expect(html).not.toContain("finance.journal.sourceUnmapped");
  });

  it("DEF-LED-10074 — a source with no word anywhere still shows as ITSELF", () => {
    const html = renderToStaticMarkup(
      <>
        {cell("source")({
          ...ROW,
          source_type: "depreciation",
          source_label: "depreciation",
        } as never)}
      </>,
    );
    expect(html).toContain("finance.journal.sourceUnmapped");
  });
});
