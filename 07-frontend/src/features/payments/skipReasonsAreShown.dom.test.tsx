// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   `CR-138-BRC07` `P4.16` — *"**Every skip is recorded and shown** —
//           five reasons. **No silent exclusion: the one thing a collections
//           trail may not contain.**"* This is the SHOWN half; the RECORDED
//           half is `06-backend/tests/test_cr138_p4_16_every_skip_is_recorded.py`.
// Rules:    B14 rule 31 (no internal code is the visible value of a field) ·
//           rule 33 (a FACT ≤ 6 words) · BR-PAY-017 (the stop conditions) ·
//           J4 step 2 (*a silent exclusion is the one thing a collections
//           trail may not contain*)
// Defects:  `DEF-PAY-6281` — `payments.skip.already_noticed_today` was in NO
//           catalogue, so the same-day guard's reason rendered as SILENCE.
//           Fixed in `fb3526105`; this file is the check that keeps it fixed
//           **and extends to every reason, including ones not minted yet.**
// Screens:  7·3a Ladder (PAY-06) · 7·3d Notice, step 3's per-row table
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// A SKIP THAT IS RECORDED AND NOT SHOWN IS STILL A SILENT EXCLUSION
// ══════════════════════════════════════════════════════════════════════════
// `ladderSkipLabel` is one line — `t("payments.skip." + reason)` — and
// **i18next renders a key it does not know as NOTHING**. So a reason the server
// can emit with no catalogue sentence reaches a clerk as an EMPTY CELL, which
// reads exactly like an account nobody excluded. That is `DEF-PAY-6281`, filed
// 2026-09-23: `already_noticed_today` had been emitted since `CR-059` CS-10 and
// had a sentence in none of the eleven catalogues.
//
// ⚠ **`G15` COULD NOT SEE IT AND STILL CANNOT.** It checks PARITY across the
// eleven — that they carry the same keys as each other — and **a key absent
// from all eleven is parity-perfect.** The defect row's own prevention line
// says what is needed instead: *"a check that walks the SOURCE constants, not
// the catalogues."* This file is that check.
//
// ══════════════════════════════════════════════════════════════════════════
// SO IT READS THE BACKEND'S OWN MODULE, AS TEXT
// ══════════════════════════════════════════════════════════════════════════
// `apps/payments/ladder.py` is imported through Vite's `?raw` — the idiom
// `sendNoticeWizard.dom.test.tsx` already uses on `OutstandingsTab.tsx?raw`,
// because this app's `src` tsconfig carries no node types and `node:fs` is a
// red typecheck. The `SKIP_* = "…"` lines are the vocabulary, and a ninth
// reason minted in Python arrives in this file the moment it is written.
//
// ⚠ **THAT CROSSES A LANGUAGE BOUNDARY ON PURPOSE, AND IT IS THE ONLY WAY.**
// A list of reasons typed out in TypeScript would be a second copy of the
// vocabulary — and the day the two disagree is exactly the day this check
// needs to fire. There is one source and it is the Python module.
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { LadderBoardResponse, LadderBoardRow } from "@/api/bankRecEndpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";
import { CollectionsPage, collectionsQueryKey } from "./CollectionsPage";
import { PAYMENTS_PERMISSION, ladderSkipLabel } from "./paymentsShared";
import type { Translator } from "@/features/tenancy/settingsShared";

// The backend's vocabulary, as text. Relative because `@` is `src/`.
import LADDER_PY from "../../../../06-backend/apps/payments/ladder.py?raw";
// All eleven, imported so a twelfth added to the folder must be added here too
// — an omission is the failure this whole file is about.
import de from "@/i18n/locales/de.json";
import en from "@/i18n/locales/en.json";
import esMX from "@/i18n/locales/es-MX.json";
import es from "@/i18n/locales/es.json";
import frFR from "@/i18n/locales/fr-FR.json";
import hi from "@/i18n/locales/hi.json";
import idID from "@/i18n/locales/id-ID.json";
import itIT from "@/i18n/locales/it-IT.json";
import jaJP from "@/i18n/locales/ja-JP.json";
import koKR from "@/i18n/locales/ko-KR.json";
import ptBR from "@/i18n/locales/pt-BR.json";

afterEach(cleanup);

const CATALOGUES: Record<string, Record<string, string>> = {
  de,
  en,
  "es-MX": esMX,
  es,
  "fr-FR": frFR,
  hi,
  "id-ID": idID,
  "it-IT": itIT,
  "ja-JP": jaJP,
  "ko-KR": koKR,
  "pt-BR": ptBR,
} as never;

const TENANT = "brazosbend";
const AS_OF = "2026-09-23";
const t: Translator = (key, params) => i18n.t(key, params);

/** Every `SKIP_* = "value"` the ladder declares, read off the module.
 *
 *  ⚠ `SKIP_MEDICAL_HOLD = notices.SKIP_MEDICAL_HOLD` is an ALIAS and carries no
 *  literal here, so it is picked up from `notices.py`'s own line instead. A
 *  regex that silently dropped it would under-report the vocabulary, which is
 *  the same shape of blind spot as the defect being checked. */
function declaredSkipReasons(source: string): string[] {
  const found = new Set<string>();
  for (const match of source.matchAll(/^SKIP_[A-Z_]+\s*=\s*"([a-z_]+)"/gm)) {
    found.add(match[1]);
  }
  return [...found].sort();
}

/** The aliased one, named explicitly rather than inferred, so its absence from
 *  the regex above is a stated fact and not a silent hole. */
const ALIASED = ["medical_hold"];

function skipReasons(): string[] {
  return [...new Set([...declaredSkipReasons(LADDER_PY), ...ALIASED])].sort();
}

function boardRow(index: number, skip: string | null): LadderBoardRow {
  return {
    account_id: `01a046dd-d809-7e20-81a3-87b1eddc1b6${index}`,
    account_no: `AC-2026-0000${index + 1}`,
    balance: "948.200000",
    currency: "USD",
    oldest_due_on: "2026-06-24",
    current_tier: "friendly",
    tier_sent_on: "2026-09-08",
    last_notice_on: "2026-09-08",
    plan_paused: skip === "payment_plan_pause",
    plan_pause_reason: skip === "payment_plan_pause" ? "active_and_current" : "",
    plan_id: null,
    medical_hold: skip === "medical_hold",
    runs: skip === null ? true : false,
    next_rung: skip === null ? "first_10_day" : null,
    next_step_on: skip === null ? "2026-09-24" : null,
    skip_reason: skip,
    days_late: 91,
    detail_code: "",
  } as unknown as LadderBoardRow;
}

/** 7·3a with one row per skip reason, so the board has to render every one. */
function openLadderShowingEverySkip() {
  const rows = skipReasons().map((reason, index) => boardRow(index, reason));
  const body: LadderBoardResponse = {
    as_of: AS_OF,
    rows,
    rungs: ["friendly", "first_10_day", "second_5_day", "final_48_hour"],
    next_step_available: true,
    intervals: { reminder_days: 3, tier_days: [10, 5], final_hours: 48 },
    tiles: {
      accounts: rows.length,
      at_tier: { friendly: rows.length },
      not_started: 0,
      paused: 1,
      due_today: 0,
    },
    problems: [],
  } as unknown as LadderBoardResponse;

  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  client.setQueryData(collectionsQueryKey(AS_OF), body);
  client.setQueryData(queryKeys.myPermissions, {
    role: "billing_clerk",
    role_name: "Billing Clerk",
    permissions: [{ code: PAYMENTS_PERMISSION, access: "write" }],
  });
  render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/payments/collections`]}>
          <Routes>
            <Route
              path="/:tenant/payments/collections"
              element={
                <CollectionsPage
                  today={AS_OF}
                  client={
                    {
                      get: async () => ({ status: 200, data: body, headers: {} }),
                    } as never
                  }
                />
              }
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return rows;
}

describe("P4.16 · every reason the server can emit has WORDS, in all eleven", () => {
  it("the vocabulary is read off `ladder.py`, and it is not empty", () => {
    // ⚠ **A CHECK THAT LOOPS OVER NOTHING PASSES.** `G32` reported *0
    // unresolved* over 21 live refusals it could not see; the same shape here
    // would be a regex that matched no line. The count is asserted as a FIGURE.
    const reasons = skipReasons();
    expect(reasons.length).toBe(8);
    expect(reasons).toContain("already_noticed_today"); // DEF-PAY-6281's own
    expect(reasons).toContain("medical_hold"); // the aliased one
  });

  it("each one resolves to a SENTENCE in every one of the eleven catalogues", () => {
    const missing: string[] = [];
    for (const [language, catalogue] of Object.entries(CATALOGUES)) {
      for (const reason of skipReasons()) {
        const key = `payments.skip.${reason}`;
        const sentence = catalogue[key];
        if (typeof sentence !== "string" || sentence.trim() === "") {
          missing.push(`${language}:${key}`);
        }
      }
    }
    expect(missing).toEqual([]);
    // …and the loop really ran over eleven × eight.
    expect(Object.keys(CATALOGUES).length).toBe(11);
  });

  it("`ladderSkipLabel` never hands back the KEY — the exact `DEF-PAY-6281` shape", () => {
    for (const reason of skipReasons()) {
      const label = ladderSkipLabel(reason, t);
      // ⚠ **`not.toContain` ON THE PREFIX IS THE ASSERTION THAT BITES.** A
      // missing key renders as the key itself or as nothing at all, and both
      // satisfy "a string came back". Three fixtures on this feature landed
      // today rendering their own raw keys with every assertion green.
      expect(label).not.toContain("payments.skip.");
      expect(label.trim()).not.toBe("");
    }
  });

  it("⚠ one sentence is TWELVE words against B14 rule 33's six — `DEF-PAY-6299`", () => {
    // ⚠ **THIS PINS TODAY'S BREACH RATHER THAN HIDING IT BEHIND A LOOSE CAP.**
    // The first draft asserted `≤ 10 words` over all eight, which passed seven
    // and failed one — and the honest response to that is to name the one
    // rather than to raise the cap until it fits. Measured, English:
    //
    //     2  nothing_overdue         Nothing overdue
    //     5  already_noticed_today   A letter already went today
    //     6  ladder_complete         Every step has already been sent
    //     6  partial_payment_pause   Part-paid enough to pause the chase
    //     7  next_step_not_due       The next step is not due yet
    //     8  payment_plan_pause      On a payment plan and up to date
    //     9  medical_hold            Medical hold — left out of every collection step
    //    12  below_ladder_floor      Too small to chase — the letter costs more than the debt
    //
    // B14 rule 33 caps a FACT at six words. **Four of the eight are over it and
    // one is at double**, in a `StatusPill` on a list row. Filed as
    // `DEF-PAY-6299` rather than rewritten here: eleven catalogues' copy is not
    // a test lane's to change, and a shorter sentence is a copy decision.
    // **The day it is shortened this case goes RED and names the defect.**
    const words = (reason: string) => ladderSkipLabel(reason, t).split(/\s+/).length;
    expect(words("below_ladder_floor")).toBe(12);
    expect(words("nothing_overdue")).toBe(2);
    const overTheCap = skipReasons().filter((reason) => words(reason) > 6);
    expect(overTheCap.sort()).toEqual([
      "below_ladder_floor",
      "medical_hold",
      "next_step_not_due",
      "payment_plan_pause",
    ]);
  });
});

describe("P4.16 · and the board actually PUTS them on screen", () => {
  it("renders one readable reason per skipped row, never a code and never a blank", () => {
    // ⚠ **THE CATALOGUE HAVING THE KEY IS NOT THE SAME FACT AS THE SCREEN
    // DRAWING IT.** `ladderSkipLabel` could be correct beside a cell that
    // renders `row.skip_reason` directly, which is what `DEF-1122` was one
    // column over. So the board is mounted and read.
    const rows = openLadderShowingEverySkip();
    expect(rows.length).toBe(8);
    for (const row of rows) {
      // ⚠ **SEVEN READ THEIR SKIP SENTENCE AND ONE READS *Paused*, BECAUSE THE
      // CELL TESTS `plan_paused` FIRST.** `collections_read` sets `plan_paused`
      // and `skip_reason: payment_plan_pause` TOGETHER — they always co-occur —
      // so that reason's sentence never renders on THIS board. It is not a
      // silent exclusion (the row says *Paused*, which is words a clerk reads)
      // and it is not a bug; it is two vocabularies for one fact, and the next
      // case pins it so nobody "fixes" one half into disagreeing with the other.
      const expected =
        row.skip_reason === "payment_plan_pause"
          ? i18n.t("payments.collections.paused")
          : i18n.t(`payments.skip.${row.skip_reason}`);
      expect(screen.getAllByText(expected).length).toBeGreaterThan(0);
    }
  });

  it("the plan-pause row says *Paused* on the board and keeps its own sentence elsewhere", () => {
    openLadderShowingEverySkip();
    const paused = i18n.t("payments.collections.paused");
    expect(paused.trim()).not.toBe("");
    expect(screen.getAllByText(paused).length).toBeGreaterThan(0);
    // …and the reason's own sentence is still a real one, because `P4.14`'s
    // wizard renders it through `ladderSkipLabel` on its per-row result table.
    expect(ladderSkipLabel("payment_plan_pause", t)).not.toContain("payments.skip.");
  });

  it("no raw skip CODE reaches the screen (B14 rule 31)", () => {
    openLadderShowingEverySkip();
    const text = document.body.textContent ?? "";
    for (const reason of skipReasons()) {
      expect(text).not.toContain(reason);
      expect(text).not.toContain(`payments.skip.${reason}`);
    }
  });

  it("a skip and an account nobody chased do NOT read the same — J4 step 2", () => {
    // The whole point, stated as an assertion: a row that WILL step says one
    // thing, a row that was stopped says another, and neither is blank.
    const rows = openLadderShowingEverySkip();
    const first = rows.find((row) => row.skip_reason !== "payment_plan_pause");
    const skipped = i18n.t(`payments.skip.${first?.skip_reason}`);
    expect(screen.getAllByText(skipped).length).toBeGreaterThan(0);
    expect(skipped).not.toBe("");
    // And the three-valued `runs` still has its own third word for *cannot say*
    // — a deployment that could read no balance floor, which is neither a send
    // nor a skip and must not be drawn as either.
    expect(i18n.t("payments.collections.cannotSay").trim()).not.toBe("");
    expect(i18n.t("payments.collections.cannotSay")).not.toContain(
      "payments.collections.",
    );
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-138-BRC07 `P4.16` · `DEF-PAY-6281` · blueprint p022 (the task
//         row) · p085 (7·3a) · J4 step 2 · B14 rules 31 and 33
// generated: 2026-09-23 by LANE P4-TESTS
// checklist: A=n/a B✔ C✔ D=n/a E✔ F✔ G✔ H=n/a
// gates: RED PROVED FIRST, through `vitest` — `payments.skip.already_noticed
//         _today` deleted from `en.json` alone failed the catalogue case with
//         `["en:payments.skip.already_noticed_today"]`, which is `DEF-PAY-6281`
//         reproduced; deleting it from ALL ELEVEN failed the same case with
//         eleven entries AND the `ladderSkipLabel` case, which is the state
//         the defect was actually filed in and which `G15`'s parity check
//         passes over.
// exceptions: (1) `medical_hold` IS NAMED IN `ALIASED` RATHER THAN MATCHED.
//         `ladder.SKIP_MEDICAL_HOLD = notices.SKIP_MEDICAL_HOLD` carries no
//         string literal, so the regex cannot see it. Declaring it is honest;
//         widening the regex to follow an alias would be a parser.
//         (2) THE WORD CAP IS PINNED, NOT ENFORCED. Four of the eight English
//         sentences are over B14 rule 33's six-word FACT cap and one is at
//         twelve. That is `DEF-PAY-6299` and it is asserted BY VALUE, so the
//         day the copy is shortened this file goes red and names the row —
//         rather than a loose cap quietly accommodating the breach.
//         (3) THE CAP IS NOT APPLIED TO THE OTHER TEN CATALOGUES AT ALL. Rule
//         33 counts words, and a correct translation of a six-word English
//         fact can take more; counting them here would fail good copy.
// status: VERIFIED-UNRATIFIED
