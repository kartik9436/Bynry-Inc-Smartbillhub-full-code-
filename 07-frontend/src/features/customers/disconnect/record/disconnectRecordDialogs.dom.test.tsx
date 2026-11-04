// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-125-BRC07 — blueprint p144 (`Hold DSC-26-0003`) and p145
//           (`Mark DSC-26-0003 as cut`), the record's two dialogs.
// Rules:    BR-CUS-039 · BR-CUS-043 · BR-CUS-096 · BR-SHL-025 · B14 rule 6
//           (danger tier) · rule 33 · hard-won law 2 and its mirror
// ───────────────────────────────────────────────────────
/**
 * What this file holds the two dialogs to.
 *
 * **1 · THE HOLD DIALOG RE-ACQUIRING THE PROMISES IT CANNOT KEEP.** p144
 * promises three immediate effects and `record_protection` delivers one. The
 * table is asserted against what a person READS, so a lane restoring *the cut
 * date is cleared* has to make it true in `disconnects.py` first — and when
 * they do, the server's `effects` list moves and this goes red naming the row.
 *
 * **2 · THE FOURTH REASON BECOMING SELECTABLE.** *A bill is disputed* cannot
 * be recorded; nothing stores a disputed AMOUNT. It is drawn and DISABLED with
 * its reason as **visible text**, never a tooltip.
 *
 * **3 · THE `Review on` FIELD APPEARING FOR A PAYMENT PLAN.** `BR-CUS-043`
 * holds that protection while the plan is active and current, so
 * `record_protection` REFUSES a date on it by name. A dialog that offered one
 * would collect a value the server rejects — a form that cannot be submitted,
 * which is the shape a clerk cannot diagnose.
 *
 * **4 · `Mark as cut` POSTING SOMETHING OTHER THAN WHAT IT DREW.** The body is
 * asserted field by field against the real endpoint's contract.
 *
 * **5 · p145's `Who did it` BECOMING A CONTROL.** `commit_cut` takes no such
 * argument and no vocabulary exists for a crew outcome. A select there would
 * collect a value that is silently dropped, which is worse than the absence.
 *
 * ⚠ **RED PROVED FIRST for every case here**, through `vitest` in the jsdom
 * environment these run in — the harness that will run them.
 */
import "@/i18n";
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Mock } from "vitest";

import type { ApiClient } from "@/api/client";

import { ToastProvider } from "@/components/Toast";

import { HoldCaseDialog } from "./HoldCaseDialog";
import { MarkAsCutDialog } from "./MarkAsCutDialog";
import type { DisconnectRecordDetail } from "./disconnectRecordEndpoints";

afterEach(cleanup);

const ACCOUNT_ID = "01a0bf3d-13c5-7cfa-96a1-486d6b84f070";

const ABSENT = (code: string, detail: string) => ({ code, detail });

function detail(over: Partial<DisconnectRecordDetail> = {}): DisconnectRecordDetail {
  return {
    case_no: { value: "DSC-26-0003", unavailable: null },
    customer_name: { value: "Bramble Bakery", unavailable: null },
    address: { value: "142 Bakers Row · Suite 1 · Silver Creek, TX 78611", unavailable: null },
    customer_class: { value: "Commercial", unavailable: null },
    state: { value: "scheduled", unavailable: null },
    tier: { value: "tier_3_48_hour", unavailable: null },
    cut_date: { value: "2026-05-14", unavailable: null },
    the_case: {
      account_no: { value: "A-11812", unavailable: null },
      owed: { stored: "2410.0000", display: "2410.00", currency: "USD", unavailable: null },
      oldest_debt: { value: null, unavailable: ABSENT("oldest_debt_age_has_no_source", "none") },
      tier: { value: "tier_3_48_hour", unavailable: null },
      cut_date: { value: "2026-05-14", unavailable: null },
      opened_on: { value: "2026-04-14", unavailable: null },
      raised_by: { value: null, unavailable: ABSENT("case_opener_not_recorded", "none") },
    },
    notices: {
      rows: [],
      state_column_unavailable: ABSENT("notice_delivery_state_is_null_by_rule", "by rule"),
      channel_column_empty: ABSENT("service_channel_is_the_proof_channel", "not attested"),
      delivery: ABSENT("delivery_adapter_absent", "no adapter"),
    },
    protections: {
      as_of: "2026-05-14",
      checks: [
        // p143's drawn order, which is NOT `disconnects.PROTECTIONS`' —
        // the server re-orders it (`disconnect_record.DRAWN_ORDER`) and the
        // fixture carries what ships rather than what the writer declares.
        { check: "medical_certificate", outcome: "pass", reason: "none in force" },
        { check: "weather_moratorium", outcome: "pass", reason: "none in force" },
        { check: "payment_plan", outcome: "pass", reason: "none in force" },
        { check: "dispute", outcome: "unavailable", reason: "nothing stores a disputed amount" },
      ],
      all_clear: true,
    },
    what_a_cut_would_do: {
      services_affected: { value: ["electric", "water"], unavailable: null },
      reconnection_fee: {
        charge_code_configured: false,
        stored: null,
        display: null,
        currency: "USD",
        unavailable: ABSENT("reconnect_charge_code_not_seeded", "no seed creates that code"),
      },
      account_status_becomes: ABSENT("disconnected_status_assigned_at_the_cut", "BR-CUS-107"),
      to_clear_before_reconnection: {
        stored: null,
        display: null,
        currency: "USD",
        unavailable: ABSENT("reconnect_charge_code_not_seeded", "no seed"),
      },
      base_charges: ABSENT("base_charges_stop_at_the_cut", "BR-CUS-103"),
      not_a_close_out: ABSENT("a_cut_is_not_a_close_out", "the account stays open"),
    } as DisconnectRecordDetail["what_a_cut_would_do"],
    actions: {
      available: ["hold", "open_account", "mark_as_cut"],
      account_id: ACCOUNT_ID,
      hold: {
        kinds: ["medical_certificate", "weather_moratorium", "payment_plan"],
        review_date: {
          medical_certificate: "required",
          payment_plan: "refused",
          weather_moratorium: "required",
        },
        dispute_unrecordable: ABSENT("dispute_is_not_a_protection", "nothing stores an amount"),
        effects: [
          { when: "now", code: "ladder_stops" },
          { when: "not_now", code: "cut_date_stays" },
          { when: "not_now", code: "debt_stays_and_ages" },
        ],
        promises_not_kept: ABSENT("hold_clears_no_date_and_moves_no_state", "measured"),
      },
      mark_as_cut: { ready: true, refusal: null, blockers: [] },
    },
    ...over,
  };
}

/**
 * A stub API client whose `post` stays a `Mock` to the type checker.
 *
 * ⚠ **`as never` WOULD HIDE THE ONE THING THESE CASES ASSERT.** The static
 * suites in this repository stub their client with `as never` because they only
 * ever READ; here the whole point is what was POSTED, and `never` makes
 * `api.post.mock.calls` a type error — which is how the first draft of this
 * file reached `tsc` twice. The cast is narrowed to the two verbs used and the
 * mock survives it.
 */
function client(cutBody: unknown = {}): ApiClient & { post: Mock; get: Mock } {
  return {
    // ⚠ **THE ENVELOPE IS PART OF THE FIXTURE (`DEF-CUS-6051`).**
    // `ApiClient.post` resolves `{ status, data, … }` and `commit_cut`'s answer
    // about the account status is inside `data`. A fixture that returned the
    // payload flat would have made a dialog reading `result.account_status_held`
    // pass — a fixture that cannot tell a right read from a wrong one, which is
    // hard-won law 2's own footnote.
    post: vi.fn(async () => ({ status: 201, data: cutBody })),
    get: vi.fn(async () => ({ status: 200, data: {} })),
  } as unknown as ApiClient & { post: Mock; get: Mock };
}

/** `commit_cut`'s answer when it WROTE `Disconnected` (CR-052 W0). */
const CUT_WROTE_STATUS = {
  account_status_written: "disconnected",
  account_status_before_cut: "active",
};

/**
 * `commit_cut`'s answer when it deliberately HELD the status — the shape both
 * real cuts this product has performed came back with. `detail` is carried so
 * the test can prove the screen does NOT print it (`BR-SHL-020` r2, `DEF-742`).
 */
const CUT_HELD_STATUS = {
  account_status_written: null,
  account_status_before_cut: null,
  account_status_held: {
    code: "cut_bill_blocked_status_not_written",
    br_ref: "BR-CUS-107 · BR-CUS-103 · BR-BIL-015 · PO ruling 2026-08-30",
    detail:
      "billing could not raise the final bill for the days before this cut, so the "
      + "`Disconnected` status was NOT written and the account stays in the bill run.",
  },
};

describe("p144 — the Hold dialog promises only what holding does", () => {
  it("draws the one true effect and the two that are NOT true as `Not now`", async () => {
    render(
      <ToastProvider>
        <HoldCaseDialog
          record={detail()}
          today="2026-05-14"
          dateFormat="MM/DD/YYYY"
          client={client()}
          onClose={() => undefined}
        />
      </ToastProvider>,
    );

    const table = await screen.findByTestId("disconnect-hold-effects");
    // ⚠ **ASSERTED BY THE EFFECT CODE AND THE WORDS TOGETHER.** The code alone
    // would pass over a row whose sentence was rewritten to promise the old
    // behaviour; the words alone would pass over a row moved between the two
    // halves of the table.
    expect(table).toHaveTextContent("The notice ladder stops.");
    expect(table).toHaveTextContent("The cut date stays.");
    expect(table).toHaveTextContent("The debt stays and ages.");

    // ⛔ **AND NOT THE TWO p144 PROMISES THAT `record_protection` DOES NOT
    // KEEP.** `cut_scheduled_for` is untouched and `state = 'on_hold'` is
    // assigned by nothing in the repository.
    expect(table).not.toHaveTextContent("cleared");
    expect(table).not.toHaveTextContent("On hold");
  });

  it("does not offer the fourth reason at all — it can never be honoured", async () => {
    // ⛔ **RE-POINTED 2026-09-25 (`DEF-CUS-6757`).** This asserted that p144's
    // fourth reason was DRAWN DISABLED with its sentence under it, on
    // `BR-SHL-025`'s authority. That rule is about a control **this
    // deployment** cannot honour — something a tenant could switch on. There is
    // no deployment, setting or future flag that makes this one pressable:
    // `record_protection` refuses a fourth kind by name and nothing anywhere
    // stores a disputed amount. A permanent impossibility offered beside its
    // own refusal is the mirror of hard-won law 2, and on a dialog with three
    // real choices it costs a clerk a decision every time.
    // ⚠ **THE THREE REAL ONES ARE ASSERTED TOO**, so a lane that removed the
    // whole radio group would not pass this by deleting more than it should.
    render(
      <ToastProvider>
        <HoldCaseDialog
          record={detail()}
          today="2026-05-14"
          dateFormat="MM/DD/YYYY"
          client={client()}
          onClose={() => undefined}
        />
      </ToastProvider>,
    );

    expect(await screen.findByText("Medical certificate")).toBeInTheDocument();
    expect(screen.getByText("Weather moratorium")).toBeInTheDocument();
    expect(screen.getByText("Payment plan")).toBeInTheDocument();
    expect(screen.queryByTestId("disconnect-hold-dispute")).toBeNull();
    expect(screen.queryByText("A bill is disputed")).toBeNull();
    expect(screen.queryByText("A dispute cannot be recorded here.")).toBeNull();
  });

  it("says what is missing when the review date is left empty", async () => {
    // ⛔ **`DEF-CUS-6756` / `DEF-CUS-6758`.** The button was live with the field
    // empty, pressing it did nothing, and NO message appeared anywhere.
    // `FormModal` validated correctly and blocked the post the whole time; the
    // message was looked up by the input's ID while the error map was keyed by
    // the ZOD PATH, so it was collected and rendered nowhere.
    // ⚠ **THIS ASSERTS THE SENTENCE A CLERK READS, NOT THAT THE POST WAS
    // BLOCKED** — the post was already blocked before the fix, so an assertion
    // on the client would have passed on the defect (law 7: ask what makes a
    // check pass wrongly).
    const api = client();
    render(
      <ToastProvider>
        <HoldCaseDialog
          record={detail()}
          today="2026-05-14"
          dateFormat="MM/DD/YYYY"
          client={api}
          onClose={() => undefined}
        />
      </ToastProvider>,
    );

    const submit = await screen.findByRole("button", { name: "Hold the case" });
    fireEvent.click(submit);

    // ⚠ **"Give a review date." IS THE ERROR; "A hold needs a review date." IS
    // THE HELP TEXT, AND IT IS ON SCREEN EITHER WAY.** A first draft of this
    // case asserted the HELP sentence and PASSED against the defect — the
    // check could not distinguish fixed from broken, which is the exact shape
    // law 7 warns about. It is asserted by the error element's own id so it
    // cannot be satisfied by any other sentence on the dialog.
    const message = await screen.findByText("Give a review date.");
    expect(message).toHaveAttribute("id", "disconnect-hold-review-on-error");
    expect(screen.getByLabelText(/Review on/)).toHaveAttribute("aria-invalid", "true");
    expect(api.post).not.toHaveBeenCalled();
  });

  it("drops the `Review on` field for a payment plan, and posts no date", async () => {
    // BR-CUS-043 — `record_protection` REFUSES an expiry on a plan by name.
    const api = client();
    render(
      <ToastProvider>
        <HoldCaseDialog
          record={detail()}
          today="2026-05-14"
          dateFormat="MM/DD/YYYY"
          client={api}
          onClose={() => undefined}
        />
      </ToastProvider>,
    );

    // The certificate is first and DOES take a date.
    expect(screen.getByLabelText(/Review on/i)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("radio", { name: /Payment plan/i }));
    expect(screen.queryByLabelText(/Review on/i)).not.toBeInTheDocument();
    expect(screen.getByTestId("disconnect-hold-no-review-date")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /Hold the case/i }));
    await waitFor(() => expect(api.post).toHaveBeenCalled());
    const [path, body] = api.post.mock.calls[0];
    expect(path).toBe(`/accounts/${ACCOUNT_ID}/protections`);
    expect(body).toEqual({
      kind: "payment_plan",
      effective_from: "2026-05-14",
      // ⚠ **`null` AND NOT `""`.** `_optional_date` reads an empty string as a
      // value to parse and refuses it.
      expires_on: null,
    });
  });
});

describe("p145 — Mark as cut", () => {
  it("posts the drawn cut date and nothing the server cannot take", async () => {
    const api = client();
    render(
      <ToastProvider>
        <MarkAsCutDialog
          record={detail()}
          today="2026-05-14"
          dateFormat="MM/DD/YYYY"
          client={api}
          onClose={() => undefined}
        />
      </ToastProvider>,
    );

    await userEvent.click(screen.getByRole("button", { name: /Mark as cut/i }));
    await waitFor(() => expect(api.post).toHaveBeenCalled());
    const [path, body] = api.post.mock.calls[0];
    expect(path).toBe(`/accounts/${ACCOUNT_ID}/disconnect-case/cut`);
    // The earliest lawful date is the DEFAULT, not today — `DSC-02.3` locks it
    // and `commit_cut` refuses anything before it.
    expect(body).toEqual({ cut_on: "2026-05-14" });
  });

  it("states `Who did it` as an absence and offers no control", async () => {
    render(
      <ToastProvider>
        <MarkAsCutDialog
          record={detail()}
          today="2026-05-14"
          dateFormat="MM/DD/YYYY"
          client={client()}
          onClose={() => undefined}
        />
      </ToastProvider>,
    );

    const line = await screen.findByTestId("disconnect-cut-no-crew");
    expect(line).toHaveTextContent("Who did it");
    expect(line).toHaveTextContent("is not recorded anywhere yet.");
    // ⚠ **THE ABSENCE OF A CONTROL IS THE ASSERTION.** `commit_cut` takes no
    // crew argument, so a select here would collect a value that is dropped.
    expect(line.querySelector("select")).toBeNull();
    expect(screen.queryByLabelText(/Who did it/i)).not.toBeInTheDocument();
  });

  it("DEF-CUS-6051 — the status row is the SERVER's answer, not a constant", async () => {
    // The payload says the status WILL be written, so the drawn sentence reads
    // as it always has — and it now carries the CONDITION that was missing.
    render(
      <ToastProvider>
        <MarkAsCutDialog
          record={detail()}
          today="2026-05-14"
          dateFormat="MM/DD/YYYY"
          client={client()}
          onClose={() => undefined}
        />
      </ToastProvider>,
    );
    const row = (await screen.findByTestId("disconnect-cut-effects")).querySelector(
      '[data-effect="status_disconnected"]',
    );
    expect(row).toHaveAttribute("data-cut-status", "written");
    expect(row).toHaveTextContent("The account reads Disconnected.");
    // ⚠ **THE CONDITION IS THE POINT.** `BR-CUS-107`'s `Disconnected` is
    // written only when the days up to the cut are billed, and this row stated
    // it as a certainty while no cut could complete anywhere.
    expect(row).toHaveTextContent("Only once the final bill lands.");
  });

  it("DEF-CUS-6051 — a HELD answer on the payload changes the row, and nothing else moves", async () => {
    const held = detail();
    held.what_a_cut_would_do.account_status_becomes = ABSENT(
      "cut_bill_blocked_status_not_written",
      "billing could not raise the final bill",
    ) as DisconnectRecordDetail["what_a_cut_would_do"]["account_status_becomes"];
    render(
      <ToastProvider>
        <MarkAsCutDialog
          record={held}
          today="2026-05-14"
          dateFormat="MM/DD/YYYY"
          client={client()}
          onClose={() => undefined}
        />
      </ToastProvider>,
    );
    const table = await screen.findByTestId("disconnect-cut-effects");
    const row = table.querySelector('[data-effect="status_disconnected"]');
    expect(row).toHaveAttribute("data-cut-status", "held");
    expect(row).toHaveTextContent("The account status does not change.");
    expect(row).not.toHaveTextContent("Disconnected");
    // The other four rows are untouched — only the one the server answers moves.
    expect(table).toHaveTextContent("The notice ladder stops.");
    expect(table).toHaveTextContent("A reconnection fee is raised.");
  });

  it("DEF-CUS-6051 — a code nobody taught this screen says NOTHING, never `Disconnected`", async () => {
    // ⚠ **AN UNKNOWN CODE MUST NOT FALL THROUGH TO THE PROMISE.** That default
    // is the defect: the screen would go on claiming a status for an answer it
    // cannot read.
    const strange = detail();
    strange.what_a_cut_would_do.account_status_becomes = ABSENT(
      "zz_a_new_ruling",
      "something nobody has taught this screen",
    ) as DisconnectRecordDetail["what_a_cut_would_do"]["account_status_becomes"];
    render(
      <ToastProvider>
        <MarkAsCutDialog
          record={strange}
          today="2026-05-14"
          dateFormat="MM/DD/YYYY"
          client={client()}
          onClose={() => undefined}
        />
      </ToastProvider>,
    );
    const row = (await screen.findByTestId("disconnect-cut-effects")).querySelector(
      '[data-effect="status_disconnected"]',
    );
    expect(row).toHaveAttribute("data-cut-status", "unstated");
    expect(row).toHaveTextContent("The status change is not stated.");
    expect(row).not.toHaveTextContent("Disconnected");
  });

  it("DEF-CUS-6051 — a HELD cut tells the clerk so, in the clerk's words", async () => {
    // ⚠ **THIS IS THE HALF THAT REACHES A REAL CUT.** Both cuts this product
    // has performed came back held, and the dialog showed `The supply is
    // recorded cut.` and nothing else.
    const api = client(CUT_HELD_STATUS);
    render(
      <ToastProvider>
        <MarkAsCutDialog
          record={detail()}
          today="2026-05-14"
          dateFormat="MM/DD/YYYY"
          client={api}
          onClose={() => undefined}
        />
      </ToastProvider>,
    );
    await userEvent.click(screen.getByRole("button", { name: /Mark as cut/i }));
    await waitFor(() => expect(api.post).toHaveBeenCalled());
    const toast = await screen.findByRole("status");
    expect(toast).toHaveTextContent("The supply is cut.");
    expect(toast).toHaveTextContent("The status waits on billing.");
    // ⛔ **THE SERVER'S `detail` NEVER REACHES A CLERK** — `BR-SHL-020` r2 and
    // `DEF-742`. The SCREEN authors the sentence, keyed off the code.
    expect(toast).not.toHaveTextContent("accounts_for_bill_run");
    expect(toast).not.toHaveTextContent("BR-CUS-107");
    expect(toast).not.toHaveTextContent("billing could not raise");
  });

  it("DEF-CUS-6051 — a cut that DID write the status keeps the ordinary sentence", async () => {
    const api = client(CUT_WROTE_STATUS);
    render(
      <ToastProvider>
        <MarkAsCutDialog
          record={detail()}
          today="2026-05-14"
          dateFormat="MM/DD/YYYY"
          client={api}
          onClose={() => undefined}
        />
      </ToastProvider>,
    );
    await userEvent.click(screen.getByRole("button", { name: /Mark as cut/i }));
    await waitFor(() => expect(api.post).toHaveBeenCalled());
    const toast = await screen.findByRole("status");
    expect(toast).toHaveTextContent("The supply is recorded cut.");
    expect(toast).not.toHaveTextContent("waits on billing");
  });

  it("DEF-CUS-6051 — a held block with no readable code still says the status did not move", async () => {
    // `null` means WRITTEN and earns the ordinary sentence; a held block whose
    // code cannot be read is still a hold, and collapsing the two would restore
    // the fixed sentence for exactly the case it is wrong for.
    const api = client({ account_status_written: null, account_status_held: {} });
    render(
      <ToastProvider>
        <MarkAsCutDialog
          record={detail()}
          today="2026-05-14"
          dateFormat="MM/DD/YYYY"
          client={api}
          onClose={() => undefined}
        />
      </ToastProvider>,
    );
    await userEvent.click(screen.getByRole("button", { name: /Mark as cut/i }));
    await waitFor(() => expect(api.post).toHaveBeenCalled());
    const toast = await screen.findByRole("status");
    expect(toast).toHaveTextContent("The status did not change.");
  });

  it("refuses the commit with the server's reason when the record is not ready", async () => {
    const notReady = detail();
    notReady.actions.mark_as_cut = {
      ready: false,
      refusal: {
        code: "cut_on_unrecorded_service",
        br_ref: "BR-CUS-100",
        detail: "nobody has recorded how the tier-3 notice was served",
      },
      blockers: [],
    };
    const api = client();
    render(
      <ToastProvider>
        <MarkAsCutDialog
          record={notReady}
          today="2026-05-14"
          dateFormat="MM/DD/YYYY"
          client={api}
          onClose={() => undefined}
        />
      </ToastProvider>,
    );

    // R4's posture through `FormModal.commitBlocked`: the FORM stays live and
    // only the COMMIT is refused, so a clerk reads what will be asked.
    expect(await screen.findByText("The final notice needs proof.")).toBeInTheDocument();
    expect(screen.getByTestId("disconnect-cut-what")).toBeInTheDocument();
  });
});
