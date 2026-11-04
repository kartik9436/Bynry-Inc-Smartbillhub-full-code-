// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  `DEF-CUS-7692` — the `Created` screen printed 86 words of the
//          SERVER's own English rationale, measured in a browser on
//          2026-09-28 after a build was committed end to end. It rendered
//          `{absence.detail}`, which is prose authored in
//          `apps/metering/connections.py`.
//          `DEF-CUS-9174` — then it printed RAW CODES: twelve snake_case
//          tokens on one real commit (2026-10-02, PO screenshot, *"do not
//          show databse id on this screen"*), because a payment taken at step
//          4 forwards payments' and notifications' problem codes onto the same
//          list and the fallback printed any code it did not know. And
//          *"2 document filed."*.
//          `DEF-CUS-9175` — *Open the connection* opened the owner's ACCOUNT;
//          the PO: *"it should go to new connect request link"*.
// Rules:   B14 rule 31 (nothing internal on screen) · rule 33 (RATIONALE is
//          ZERO WORDS ON SCREEN; a fact is six words) · `BR-SHL-020 r2` ·
//          CLAUDE.md hard-won law 2 (assert the destination by ADDRESS and by
//          the screen id it opens) · law 6
// Tests:   this file IS the test
// ───────────────────────────────────────────────────────
//
// ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY, ASKED BEFORE IT WAS TRUSTED**
// (law 7, habit 2):
//
//   1. **The note could simply vanish.** A screen that says nothing passes
//      every *"no code on screen"* assertion trivially. So the facts a clerk
//      acts on are asserted PRESENT, by their words.
//   2. **A shortened rationale reads like a fact.** So the cases assert the
//      SHAPE a rationale has and a six-word cap.
//   3. **A new code could arrive and render as a token.** The no-code case
//      feeds an INVENTED code as well as the real ones, so it is a property of
//      the renderer, not of a list somebody has to keep current.
//   4. **A link that "works" in a bare router.** The Open case mounts under
//      the real `/:tenant/…` pattern and resolves the landing address through
//      `resolveScreen`, so a `//connections/…` or an account address fails.
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";
import { resolveScreen } from "@/routing/screenIds";

import { NewConnectDone } from "./NewConnectDone";
import { COMMIT_ABSENCE_FACT, COMMIT_NOTES_NOT_FOR_A_CLERK } from "./newConnectShared";
import type { CommitResult } from "./newConnectEndpoints";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

const TENANT = "brazosbend";
const BUILD_ID = "01a0fdb8-7057-7954-ac75-31e494109131";

afterEach(cleanup);

/** The six `unavailable[]` codes `apps/metering/connections.py` can answer a
 *  successful commit with, WITH THE SERVER'S REAL PROSE, so a case that reads
 *  the rendered text can tell the two apart. */
const SERVER_ABSENCES = [
  {
    field: "one_time_charges",
    code: "build_names_no_charge",
    tracks: "BR-MET-1178",
    detail:
      "Nobody put a charge on this build, so there is nothing to raise. A build prices " +
      "itself from the charge codes a clerk picks and the quantities step 4 counts; none " +
      "was sent. Reported rather than counted as $0.00 - a zero would read as 'this build " +
      "was free'.",
  },
  {
    field: "one_time_charges",
    code: "quote_has_no_chargeable_line",
    tracks: "BR-CUS-090",
    detail: "The request's quote has no chargeable line, so there is nothing to raise.",
  },
  {
    field: "sub_meter_links",
    code: "no_door_from_metering",
    tracks: "OQ-379",
    detail:
      "A sub-meter link is an assets relationship and this module has no seam that writes " +
      "one. Reported rather than counted as 0 — a zero would read as 'we made none' where " +
      "the truth is 'we cannot make them from here'.",
  },
  {
    field: "connection_services",
    code: "unmetered_services_are_not_on_the_payload",
    tracks: "DEF-MET-6119",
    detail:
      "A service that takes no meter is mapped to its units by step 4 and travels on no " +
      "key of this payload, so this commit cannot record where it is provided.",
  },
  {
    field: "work_orders",
    code: "template_republished_since_proposal",
    tracks: "BR-WRK-008",
    detail:
      "A template was published again between step 6's proposal and this commit. The order " +
      "copies the version it was raised from.",
  },
  {
    field: "premises",
    code: "premises_created_at_step_1_not_at_commit",
    tracks: "DEF-2961",
    detail:
      "connections.premises_id is NOT NULL, so the address exists before this draft does " +
      "and the commit creates none.",
  },
];

/** `DEF-CUS-9174` — the `unavailable[]` of a REAL commit with a cash payment
 *  taken at step 4, in the order the server sent it (Chromium, 2026-10-02,
 *  CON-26-0130), plus `invoice_composition_unavailable` from the PO's own
 *  screenshot and an INVENTED code no list names. */
const PAYMENT_RIDERS = [
  "account_balance_cache_not_updated",
  "not_cleared_so_not_allocated",
  "receipt_queued",
  "channel_has_no_rule_toggle",
  "template_pin_resolved_at_queue_write",
  "receipt_email_queued",
  "template_pin_resolved_at_queue_write",
  "print_floor_channel_added",
  "receipt_sms_queued",
  "recipient_absent_on_record",
  "template_pin_resolved_at_queue_write",
  "print_floor_channel_added",
  "invoice_composition_unavailable",
  "payment_exceeded_the_bill_and_carries_as_credit",
  "a_code_nobody_has_words_for_yet",
].map((code) => ({ field: "one_time_charge_paid", code, tracks: "BR-PAY-021", detail: "x" }));

function result(unavailable: unknown[] = SERVER_ABSENCES, id: string = BUILD_ID): CommitResult {
  return {
    id,
    connection_no: "CON-26-0001",
    manifest: { units: 4, meters: 8, plan_assignments: 4 },
    unavailable,
    home: { kind: "account", id: "acc-1" },
  } as unknown as CommitResult;
}

function Where() {
  const location = useLocation();
  return <output data-testid="where">{location.pathname}</output>;
}

function mountDone(
  r: CommitResult = result(),
  documents: { filed: number; unfiled: number } | null = null,
) {
  const { container } = render(
    <MemoryRouter initialEntries={[`/${TENANT}/connections/new?step=5`]}>
      <Routes>
        <Route
          path="/:tenant/connections/new"
          element={<NewConnectDone result={r} t={t} documents={documents} />}
        />
        <Route path="/:tenant/connections/:connectionId" element={<Where />} />
        <Route path="/:tenant/accounts/:accountId" element={<Where />} />
      </Routes>
    </MemoryRouter>,
  );
  return container;
}

describe("DEF-CUS-7692 · the Created screen states the absence and never the reasoning", () => {
  it("renders a sentence for every code the commit can send, and drops none", () => {
    const el = mountDone();
    const notes = Array.from(el.querySelectorAll("[data-absence]")) as HTMLElement[];
    expect(notes).toHaveLength(SERVER_ABSENCES.length);
    for (const note of notes) {
      // (1) THE FACT SURVIVES. A vanished note passes every assertion below.
      expect((note.textContent ?? "").trim()).not.toBe("");
      expect(note.getAttribute("data-absence")).not.toBe("");
    }
  });

  it("never renders the server's prose, and never its $0.00", () => {
    const el = mountDone();
    const shown = el.textContent ?? "";
    expect(shown).not.toContain("a zero would read as");
    expect(shown).not.toContain("Reported rather than counted");
    expect(shown).not.toContain("$0.00");
    for (const absence of SERVER_ABSENCES) {
      expect(shown).not.toContain(absence.detail);
    }
    expect(shown).not.toMatch(/\bbecause\b/i);
    expect(shown).not.toMatch(/\bso there is\b/i);
  });

  it("keeps every sentence inside rule 33's six words, and never prints a code", () => {
    const el = mountDone(result([...SERVER_ABSENCES, ...PAYMENT_RIDERS]));
    for (const note of Array.from(el.querySelectorAll("[data-absence]")) as HTMLElement[]) {
      const sentence = (note.textContent ?? "").trim();
      // Payments' own reading may be two sentences of six (rule 33).
      for (const one of sentence.split(/(?<=\.)\s+/)) {
        expect(one.split(/\s+/).length).toBeLessThanOrEqual(6);
      }
      expect(sentence).not.toContain(note.getAttribute("data-absence") ?? "@@");
    }
  });

  it("knows every code the server can send — a seventh goes RED here", () => {
    // ⚠ Enumerated from `apps/metering/connections.py`'s own `absences.append`
    // sites. The day one is added, this is what says so.
    for (const absence of SERVER_ABSENCES) {
      expect(
        COMMIT_ABSENCE_FACT[absence.code],
        `\`${absence.code}\` reaches the Created screen and has no word. Add one to
COMMIT_ABSENCE_FACT in newConnectShared.tsx — six words, a FACT, no reasoning
(B14 rule 33). The server's own \`detail\` stays on the payload for support.`,
      ).toBeDefined();
    }
  });
});

describe("DEF-CUS-9174 · no internal code reaches the Created screen", () => {
  it("no snake_case token is on screen, whatever the commit forwards", () => {
    const el = mountDone(result([...SERVER_ABSENCES, ...PAYMENT_RIDERS]));
    const shown = el.textContent ?? "";
    // ⚠ The property, not a list: any `word_word` token is a code. An invented
    // code is in the input, so a fallback that prints codes fails here.
    // ⚠ NOT a `\b…\b` token regex: `textContent` glues siblings together, so
    // `…existed.account_balance_…_yetOpen the…` has no word boundary after the
    // last code and that regex matched NOTHING on the code-printing build — a
    // check that could not fail, caught by running it against the old code
    // (law 7). Any underscore between two lowercase letters is the test.
    expect(shown.match(/[a-z0-9]_[a-z0-9]/g) ?? []).toEqual([]);
    expect(shown).not.toContain("customers.newConnect");
    expect(shown).not.toContain("payments.problem");
  });

  it("states the facts a clerk acts on, once each, and drops the bookkeeping", () => {
    const el = mountDone(result(PAYMENT_RIDERS));
    const notes = (Array.from(el.querySelectorAll("[data-absence]")) as HTMLElement[]).map(
      (note) => (note.textContent ?? "").trim(),
    );
    // ⛔ `DEF-PAY-10736` (L2-05, PO 2026-10-30) — the balance-cache note was
    // first here; it is bookkeeping and is now silent on every screen.
    expect(notes).toEqual([
      t("payments.problem.not_cleared_so_not_allocated"),
      "A receipt has no recipient.",
      "Extra payment held as credit.",
    ]);
    // Bookkeeping is dropped BY NAME, not by accident of a missing key.
    expect(COMMIT_NOTES_NOT_FOR_A_CLERK).toContain("template_pin_resolved_at_queue_write");
    expect(new Set(notes).size).toBe(notes.length);
  });

  it("says '2 documents filed.' and '1 document filed.'", () => {
    const two = mountDone(result([]), { filed: 2, unfiled: 2 });
    expect(two.textContent).toContain("2 documents filed.");
    expect(two.textContent).toContain("2 documents were not filed.");
    cleanup();
    const one = mountDone(result([]), { filed: 1, unfiled: 1 });
    expect(one.textContent).toContain("1 document filed.");
    expect(one.textContent).toContain("1 document was not filed.");
  });
});

describe("DEF-CUS-9175 · Open the connection lands on the build's own page", () => {
  it("navigates to /<tenant>/connections/<id>, which is NCT-02 — not the account", () => {
    mountDone();
    fireEvent.click(screen.getByRole("button", { name: /Open the connection/ }));
    const landed = screen.getByTestId("where").textContent ?? "";
    expect(landed).toBe(`/${TENANT}/connections/${BUILD_ID}`);
    expect(landed).not.toContain("/accounts/");
    // By SCREEN ID too: the address must resolve to the build's page.
    expect(resolveScreen(landed).r10).toBe("NCT-02");
  });

  it("a commit with no id leaves the button disabled rather than going nowhere", () => {
    mountDone(result(SERVER_ABSENCES, ""));
    expect(screen.getByRole("button", { name: /Open the connection/ })).toBeDisabled();
  });
});

describe("DEF-MET-9245 · a receipt copy with no address names its channel", () => {
  it("a text with no mobile number says so, not that nobody got a receipt", () => {
    // The walk's S2: email and print queued, the SMS copy had no number.
    mountDone(
      result([
        { field: "one_time_charge_paid", code: "receipt_email_queued", tracks: "BR-BIL-036" },
        {
          field: "one_time_charge_paid",
          code: "recipient_absent_on_record",
          tracks: "BR-BIL-036",
          channel: "sms",
        },
      ]),
    );
    expect(screen.getByText("Text receipt: no mobile number.")).toBeInTheDocument();
    expect(screen.queryByText("A receipt has no recipient.")).toBeNull();
  });

  it("an absence with no channel keeps the general sentence", () => {
    mountDone(
      result([{ field: "one_time_charge_paid", code: "recipient_absent_on_record", tracks: "BR-BIL-036" }]),
    );
    expect(screen.getByText("A receipt has no recipient.")).toBeInTheDocument();
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-CUS-7692 · DEF-CUS-9174 · DEF-CUS-9175 · the New Connect browser
//   walks of 2026-09-28 and 2026-10-02
// generated: 2026-09-29 by lane NC-WALK; extended 2026-10-02 by lane NCD
// checklist: A✔ B=n/a C✔ D=n/a E✔ F✔ G✔ H=n/a
// gates: proved RED before it was trusted green — the DEF-CUS-9174 and
//   DEF-CUS-9175 cases fail against the tip that printed codes and opened
//   the account
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
