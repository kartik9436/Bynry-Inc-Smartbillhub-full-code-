// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   `CR-138-BRC07` `P4.28` — *"The letter is shown **before** it is
//           sent: the preview renders the disconnect template when the tone is
//           *Firm*."* The screen is `P4.14` + `P4.27`.
// Rules:    BR-NOT-008 (*"regulated ladder steps ALWAYS render the
//           disconnect-notice template class regardless of the tone picked"*) ·
//           BR-NOT-014 (each tier its OWN class) · B14 rule 11 (a consequence
//           preview before a commit that writes money, service state or LEGAL
//           NOTICES) · rule 4 (`Verb →` navigates, `Verb ✓` commits) ·
//           BR-SHL-019 (ONE transactional commit, at the LAST step)
// Ruling:   `OQ-PAY-12607` (2026-09-23, CLOSED — three tones, no fourth)
// Screens:  7·3d Notice (S35 · PAY-B)
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// THE BLUEPRINT'S OWN ANSWER TO "WHY IS THIS A WIZARD AND NOT A MODAL"
// ══════════════════════════════════════════════════════════════════════════
// *"Because the letter has to be seen before it is sent, and a modal had
// nowhere to put it."* And the sentence the screen exists to make unmissable,
// `BR-NOT-008` verbatim: choosing **Firm** does not send a firmer reminder —
// **it sends the regulated 10-day disconnect notice**, with a cut date and a
// statutory footer.
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT WAS ALREADY COVERED — AND IT IS A FIXTURE, NOT A SCREEN
// ══════════════════════════════════════════════════════════════════════════
// `sendNoticeWizard.dom.test.tsx` has
// `it("BR-NOT-008: *Firm* selects the REGULATED disconnect class…")`. Read it:
//
//     const TONES = [ …declared in the test file… ];
//     const firm = toneRow(TONES, "firm");
//     expect(firm?.template_class).toContain("disconnect_notice");
//
// **`TONES` is a constant in the test.** The case proves `toneRow` can find an
// entry in an array — which is true and is worth knowing — and it says nothing
// about what the SCREEN renders, nothing about WHEN, and nothing about whether
// a letter appears at all. That whole file is a unit suite: it imports four
// pure functions and reads `OutstandingsTab.tsx` as raw text. **It never mounts
// the wizard.**
//
// `P4.28` is a sentence about ORDER — *shown **before** it is sent* — and order
// is a property of a running screen. So this file drives one.
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT WOULD MAKE THIS PASS WRONGLY, ANSWERED
// ══════════════════════════════════════════════════════════════════════════
//   * *The letter could render on step 3 and the send could ALSO have run.*
//     Answered by asserting the send stub's call count is ZERO while the letter
//     is on screen — *before* is the claim, and a preview that appears
//     alongside a completed send is not a preview.
//   * *"A disconnect notice is on screen" could be the TONE PICKER's own words*
//     rather than the letter. Answered by asserting the rendered BODY text,
//     which only `GET /template-catalog/{code}` supplies, and by asserting the
//     fixture served it for the 10-day class specifically.
//   * *The wizard could render the letter for ANY tone.* Answered by walking
//     *Friendly* through the same steps and asserting the dunning body, not the
//     disconnect one — a preview that always shows the scariest letter teaches
//     a clerk to ignore it.
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { ApiClient } from "@/api/client";
import type { LadderBoardResponse } from "@/api/bankRecEndpoints";
import type { OutstandingRow } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";
import { SEND_NOTICE_ROUTE, SendNoticeWizard } from "./SendNoticeWizard";

afterEach(cleanup);

const TENANT = "brazosbend";
const AS_OF = "2026-09-23";
const ACCOUNT_ID = "01a046dd-d809-7e20-81a3-87b1eddc1b64";

/** The tone table, **served** — `notices.TONE_TO_STEP` published by
 *  `GET /notice-tones`. Three tones and no fourth (`OQ-PAY-12607`). */
const TONES = {
  tones: [
    {
      tone: "friendly",
      step: null,
      template_class: "dunning",
      regulated: false,
      certified_mail: false,
    },
    {
      tone: "firm",
      step: "first_10_day",
      template_class: "disconnect_notice_10_day",
      regulated: true,
      certified_mail: false,
    },
    {
      tone: "final",
      step: "final_48_hour",
      template_class: "disconnect_notice_48_hour",
      regulated: true,
      certified_mail: true,
    },
  ],
  stage_days: [7, 21, 14, 4],
  stage_days_unavailable: null,
  tiers: ["first_10_day", "second_5_day", "final_48_hour"],
  free_text_tones_exist: false,
  generation_queues_only: true,
};

/** The two letters, each with a body only its own class could produce.
 *  The strings are deliberately unmistakable for one another.
 *
 *  ⚠ **`merge_field_rows: []` IS REQUIRED AND ITS ABSENCE IS A CRASH.**
 *  `TemplateSurface` → `DocumentPaper` → `documentSamples(props.rows)` iterates
 *  it, so a fixture without it throws `TypeError: rows is not iterable` INSIDE
 *  the render — which surfaces as four cases failing on the same message and
 *  reads exactly like a product fault. The first draft of this file did that.
 *  A fixture that cannot render the component is not a test of it. */
const LETTERS: Record<string, unknown> = {
  disconnect_notice_10_day: {
    code: "disconnect_notice_10_day",
    merge_field_rows: [],
    name: "Disconnection notice — 10 day",
    category: "collections",
    category_source: "seed",
    kind: "notice",
    used_by: "collections",
    group: null,
    channel: "print",
    preview: {
      body:
        "NOTICE OF PENDING DISCONNECTION. Your water service may be " +
        "disconnected on or after the date shown unless payment is received.",
      subject: null,
      channel: "print",
      sample_data: true,
      sample_data_notice: "Sample data — nothing here is this customer's.",
      sample_data_detail: "Every value in this preview is sample data.",
      absences: [],
      problems: [],
      unsampled: [],
      rendered_length: 140,
    },
    preview_unavailable: null,
  },
  dunning: {
    code: "dunning",
    merge_field_rows: [],
    name: "Payment reminder",
    category: "collections",
    category_source: "seed",
    kind: "notice",
    used_by: "collections",
    group: null,
    channel: "print",
    preview: {
      body: "A friendly reminder that your account has an amount outstanding.",
      subject: null,
      channel: "print",
      sample_data: true,
      sample_data_notice: "Sample data — nothing here is this customer's.",
      sample_data_detail: "Every value in this preview is sample data.",
      absences: [],
      problems: [],
      unsampled: [],
      rendered_length: 63,
    },
    preview_unavailable: null,
  },
};

const BOARD: LadderBoardResponse = {
  as_of: AS_OF,
  rows: [
    {
      account_id: ACCOUNT_ID,
      account_no: "AC-2026-00001",
      balance: "1284.600000",
      currency: "USD",
      oldest_due_on: "2026-07-14",
      current_tier: "friendly",
      tier_sent_on: "2026-09-08",
      last_notice_on: "2026-09-08",
      plan_paused: false,
      plan_pause_reason: "",
      plan_id: null,
      medical_hold: false,
      runs: true,
      next_rung: "first_10_day",
      next_step_on: "2026-09-24",
      skip_reason: null,
      days_late: 62,
      detail_code: "",
    },
  ],
  rungs: ["friendly", "first_10_day", "second_5_day", "final_48_hour"],
  next_step_available: true,
  intervals: { reminder_days: 7, tier_days: [21, 14], final_hours: 4 },
  tiles: { accounts: 1, at_tier: { friendly: 1 }, not_started: 0, paused: 0, due_today: 1 },
  problems: [],
} as unknown as LadderBoardResponse;

const SELECTED: OutstandingRow = {
  account_id: ACCOUNT_ID,
  account_no: "AC-2026-00001",
  customer_name: "Ana Alvarez",
  balance: "1284.6000",
  days_late: 62,
  bucket: "61-90",
  open_bills: 2,
  last_payment_on: "2026-08-02",
  notice_summary: "1st sent",
  collection_tier: "friendly",
  next_step_due: null,
  plan_status: null,
  autopay: false,
  bad_address: false,
} as unknown as OutstandingRow;

/** A client that serves the three reads and **counts every POST**.
 *
 *  ⚠ **THE COUNTER IS THE *before* IN `P4.28`.** Without it this file could
 *  only say the letter is on the same screen as the button, which is also true
 *  of a screen that sent first and rendered afterwards. */
function client(sendSpy: ReturnType<typeof vi.fn>): ApiClient {
  const get = async (path: string) => {
    if (path.startsWith("/notice-tones")) {
      return { status: 200, data: TONES, headers: {} };
    }
    if (path.startsWith("/collections/ladder")) {
      return { status: 200, data: BOARD, headers: {} };
    }
    if (path.startsWith("/template-catalog/")) {
      const code = decodeURIComponent(path.split("/template-catalog/")[1].split("?")[0]);
      const letter = LETTERS[code];
      if (letter === undefined) {
        throw new Error(`no letter fixture for ${code}`);
      }
      return { status: 200, data: letter, headers: {} };
    }
    throw new Error(`the fixture was asked for ${path}, which it does not serve`);
  };
  const post = async (path: string, body?: unknown) => {
    sendSpy(path, body);
    return {
      status: 200,
      data: { sent: [], skipped: [], problems: [], queued_message_ids: [] },
      headers: {},
    };
  };
  return { get, post, put: post, patch: post, delete: get } as never;
}

/** 7·3d at its real address, with the selection in ROUTER STATE exactly as
 *  7·1's `openSendNotice()` hands it over — `{ accounts, asOf, currency }`. */
function openWizard(sendSpy: ReturnType<typeof vi.fn>) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter
          initialEntries={[
            {
              pathname: `/${TENANT}${SEND_NOTICE_ROUTE}`,
              state: { accounts: [SELECTED], asOf: AS_OF, currency: "USD" },
            },
          ]}
        >
          <Routes>
            {/* THE REAL PATH PATTERN — `App.tsx` mounts
                `SEND_NOTICE_ROUTE.slice(1)` under `/:tenant`. */}
            <Route
              path={`/:tenant${SEND_NOTICE_ROUTE}`}
              element={<SendNoticeWizard client={client(sendSpy)} />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** Walk the wizard: step 1 → pick a tone → step 3. Awaits nothing by hand —
 *  every query is seeded through the stub and resolves in a microtask, which
 *  `findBy*` waits for. */
async function walkTo3(tone: string, sendSpy: ReturnType<typeof vi.fn>) {
  openWizard(sendSpy);
  const advance = async () =>
    fireEvent.click(await screen.findByRole("button", { name: i18n.t("wizard.continue") }));
  await advance(); // 1 → 2
  const picker = await screen.findByLabelText(
    new RegExp(i18n.t("payments.notice.which.label"), "i"),
  );
  fireEvent.change(picker, { target: { value: tone } });
  await advance(); // 2 → 3
}

describe("P4.28 — the letter is on screen BEFORE anything is sent", () => {
  it("*Firm* renders the REGULATED 10-day disconnect letter, not a firmer reminder", async () => {
    const sent = vi.fn();
    await walkTo3("firm", sent);

    // The LETTER's own body — only `GET /template-catalog/disconnect_notice_10_day`
    // supplies it, so this cannot be satisfied by the picker's words.
    expect(await screen.findByText(/NOTICE OF PENDING DISCONNECTION/)).toBeInTheDocument();
    // …and it is labelled a sample, because the only render this product has is
    // sample data and the pane must never stop saying so.
    expect(screen.getByText(/Sample data/)).toBeInTheDocument();
  });

  it("and NOTHING has been sent while it is on screen — that is the whole word *before*", async () => {
    const sent = vi.fn();
    await walkTo3("firm", sent);
    expect(await screen.findByText(/NOTICE OF PENDING DISCONNECTION/)).toBeInTheDocument();
    // ⚠ **THE ASSERTION `P4.28` ACTUALLY MAKES.** A preview that appears after
    // the letter has gone is not a preview, and every other case in this file
    // would pass over one.
    expect(sent).not.toHaveBeenCalled();
  });

  it("the commit is still ahead of the clerk — `Send ✓`, danger tier (B14 rules 4 and 6)", async () => {
    const sent = vi.fn();
    await walkTo3("firm", sent);
    await screen.findByText(/NOTICE OF PENDING DISCONNECTION/);
    const commit = [...document.querySelectorAll("button")].find((button) =>
      (button.textContent ?? "").startsWith("Send"),
    );
    expect(commit).toBeDefined();
    // BR-SHL-019 — ONE transactional commit, and it is at the LAST step. The
    // letter and the button are on the same step, in that order.
    expect(sent).not.toHaveBeenCalled();
  });

  it("the selection SURVIVES to step 3 — the commit reads **Send 1** (`DEF-PAY-6301`, fixed)", async () => {
    // ⚠⚠ **THIS CASE WAS A PIN ON A LIVE DEFECT UNTIL 2026-09-23, AND THE
    // HISTORY IS KEPT BECAUSE IT IS THE PROOF.** It asserted `Send 0` — the
    // broken value — with a note saying *"the day it is fixed this case goes
    // RED and names `DEF-PAY-6301`"*. It did exactly that: the fix turned it
    // red with `expected [ 'Send 1 ✓' ] to include 'Send 0 ✓'`, which is the
    // only evidence that the fix reached the thing the walk had measured.
    //
    // **WHAT WAS WRONG.** `setNav` advanced the step with
    // `setSearchParams(params, { replace: true })`. In react-router v6 that
    // builds a PARTIAL PATH, and a partial path carries no `state` unless it
    // is passed again — so the handover this wizard is built on was destroyed
    // by the first press of Continue. Measured at the time: `location.state`
    // present at mount, `null` at `?step=2`; `accounts` became `[]`, the
    // commit read **Send 0 ✓**, Back showed `WhoStep`'s empty state as though
    // the clerk had removed everybody, and the commit POSTed
    // `account_ids: []`, which `notices_by_hand.send` refuses by name.
    // **7·3d could not send a notice at all.** It shipped that morning.
    //
    // **THE FIX** is `state: location.state` on that one call. Keeping a
    // selection OUT of the URL (B14 rule 31, which the screen reasoned
    // correctly) and carrying it ACROSS a step are two separate obligations,
    // and only the first had been met.
    //
    // **WHY THIS CASE EXISTS RATHER THAN A UNIT TEST.**
    // `sendNoticeWizard.dom.test.tsx` tests `sendNoticeHandover` as a pure
    // function and **never mounts the wizard**, so the screen had coverage and
    // no test of the thing it does. Only walking all three steps can see this.
    const sent = vi.fn();
    await walkTo3("firm", sent);
    await screen.findByText(/NOTICE OF PENDING DISCONNECTION/);
    const labels = [...document.querySelectorAll("button")]
      .map((button) => button.textContent ?? "")
      .filter((text) => text.startsWith("Send"));
    // The count is the whole assertion: it is the selection, carried through
    // two navigations, arriving at the commit.
    expect(labels).toContain(i18n.t("payments.notice.commit", { count: 1 }));
    expect(labels).not.toContain(i18n.t("payments.notice.commit", { count: 0 }));
    // …and still nothing has been sent — the preview is still a preview.
    expect(sent).not.toHaveBeenCalled();
  });

  it("*Friendly* renders the DUNNING letter — the preview follows the tone", async () => {
    // ⚠ **WITHOUT THIS CASE THE FILE PROVES NOTHING ABOUT THE TONE.** A screen
    // that always drew the disconnect notice would pass every case above, and
    // it would be worse than no preview: a clerk who sees the scariest letter
    // whatever they pick stops reading it.
    const sent = vi.fn();
    await walkTo3("friendly", sent);
    expect(await screen.findByText(/friendly reminder/i)).toBeInTheDocument();
    expect(screen.queryByText(/NOTICE OF PENDING DISCONNECTION/)).toBeNull();
    expect(sent).not.toHaveBeenCalled();
  });

  it("no letter is drawn before a tone is picked — step 2 shows the picker, not a guess", async () => {
    const sent = vi.fn();
    openWizard(sent);
    fireEvent.click(await screen.findByRole("button", { name: i18n.t("wizard.continue") }));
    await screen.findByLabelText(new RegExp(i18n.t("payments.notice.which.label"), "i"));
    // A wizard that pre-rendered *some* letter on the way past would be showing
    // a clerk a document their selection will not produce.
    expect(screen.queryByText(/NOTICE OF PENDING DISCONNECTION/)).toBeNull();
    expect(screen.queryByText(/friendly reminder/i)).toBeNull();
  });

  it("the day numbers beside the tone are the TENANT's, not a seed (`P4.15` on screen)", async () => {
    // `GET /notice-tones` serves `stage_days` from the tenant's own ladder and
    // this fixture's tenant chases on 7 · 21 · 14 · 4. `BR-REP-016`'s seeds are
    // 7/14/30 and the family's are 3/10/5; neither may appear. The backend half
    // is `tests/test_cr138_p4_15_tone_days_and_letters.py`.
    const sent = vi.fn();
    openWizard(sent);
    fireEvent.click(await screen.findByRole("button", { name: i18n.t("wizard.continue") }));
    const picker = await screen.findByLabelText(
      new RegExp(i18n.t("payments.notice.which.label"), "i"),
    );
    fireEvent.change(picker, { target: { value: "firm" } });
    expect(await screen.findByText(/7 · 21 · 14 · 4/)).toBeInTheDocument();
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-138-BRC07 `P4.28` · blueprint p023 (the task row) · p087–p089
//         (7·3d, read as images at 2.0) · BR-NOT-008 · BR-NOT-014 · B14 rule 11
// generated: 2026-09-23 by LANE P4-TESTS
// checklist: A=n/a B✔ C✔ D=n/a E✔ F✔ G✔ H=n/a
// gates: RED PROVED FIRST, through `vitest` — `letterQuery`'s key changed to
//         a fixed `"dunning"` made the *Firm* case fail on `Unable to find an
//         element with the text: /NOTICE OF PENDING DISCONNECTION/`, which is
//         BR-NOT-008 broken in the exact direction that matters (a clerk told
//         they are sending a reminder while a disconnect notice goes out); and
//         `commit()` called from step 2's `validate` made the *before* case
//         fail on `expected "spy" to not be called at all`.
// defects: `DEF-PAY-6301` — walking this wizard for the first time is what
//         found that `setSearchParams` drops the router state, so the selection
//         is gone by step 2 and the commit reads **Send 0**. Pinned by value in
//         the case named for it.
// exceptions: (1) THE LETTER BODIES ARE FIXTURES, NOT THE SEEDED TEMPLATES.
//         What is under test is that the SCREEN asks for the class the TONE
//         selects and renders what comes back; which words the seeded
//         `disconnect_notice_10_day` carries is `template_service`'s and is
//         asserted in the notifications suite. Two files asserting one body is
//         how they come to disagree.
//         (2) NO PER-ACCOUNT LETTER IS ASSERTED, because none exists. The only
//         render this product has is sample data and the panel says so — the
//         screen's own exception, and `DEF-PAY-6279`'s neighbour.
// status: VERIFIED-UNRATIFIED
