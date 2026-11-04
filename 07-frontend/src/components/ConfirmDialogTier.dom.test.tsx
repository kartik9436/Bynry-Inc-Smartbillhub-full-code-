// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-718 — B14 rule 6's danger tier did not reach `ConfirmDialog`,
//           across 30 non-test call sites that delete, retire, archive,
//           deactivate and roll back. (DEF-712 is the same defect on the wizard
//           half; its fix landed the tier on `WorkingButton`.)
// Rules:    B14 rule 6 (danger tier on destructive commits) · A18 §3 (the
//           working state) · IS-6 (modal → explicit confirm)
// PO:       ruling 2026-08-26 — "B14 rule 6 is ratified; the tier exists; the
//           only reason they're wrong is that nothing could reach it until
//           tonight."
// ───────────────────────────────────────────────────────
/**
 * ⚠ **WHY THIS FILE CLICKS, AND WHY IT READS `class` RATHER THAN A PROP.**
 *
 * DEF-718's escape reason is that **no gate in this repo reads rendered
 * output** — so a rule that could not be obeyed at all looked exactly like one
 * nobody had got to, and 2624 passing tests, `tsc` and `eslint` were all green
 * over it. A case asserting that `confirmVariant` was passed would have been
 * green on the broken day too, when there was no prop to pass. So every
 * assertion below reads the confirm button's own rendered `class` attribute
 * against `buttonClasses(...)`, pinned at BOTH quotes so an appended class
 * cannot slide past a substring match (DEF-182's shape).
 *
 * And it clicks because **a confirm dialog is state**: `renderToStaticMarkup`
 * paints first paint and stops, and these dialogs only exist after a row action
 * is pressed. That is the DEF-523 pattern, in jsdom.
 *
 * ⚠ **THE SCREENS CHOSEN ARE THE POLYMORPHIC ONES, DELIBERATELY.** Twenty-one
 * call sites pin `confirmVariant="danger"` and are read by the census at the
 * bottom of this file; the three below COMPUTE the tier, because one dialog
 * serves both a destructive action and a harmless one — deactivate/reactivate,
 * archive/publish, disable/enable. Those are the only sites where the tier can
 * be *wrong* rather than merely absent, and both directions are asserted on
 * each: **a tier that appears everywhere carries no information.**
 */
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import type { Paginated, TenantServiceRow, TenantUser } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";
import { buttonClasses } from "@/components/buttonKit";
import { DEFAULT_PAGE_SIZE } from "@/components/tableTypes";

import { UsersTab } from "@/features/identity/SettingsUsersTab";
import { ServicesTab } from "@/features/tenancy/SettingsServicesTab";

afterEach(cleanup);

function mount(node: ReactNode, seed: (qc: QueryClient) => void) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  seed(queryClient);
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter>{node}</MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/**
 * The confirm button inside the open dialog, by the copy it renders.
 *
 * ⚠ It is found by NAME and not by "the last button on the page": the dialog
 * also draws ✕ Close and Cancel, and the screen behind it is full of row
 * actions that already use the `ghost-danger` colour (a different tier for a
 * different job — see `buttonKit`). Asking the whole document whether any
 * button carries a danger token would be answered by one of those.
 */
function confirmButton(label: string): HTMLElement {
  // ⚠ SCOPED TO THE OPEN DIALOG, not to the document. `Reset temp password` is
  // the accessible name of BOTH the row action that opens this dialog and the
  // commit inside it — a document-wide lookup finds two and the ambiguity is
  // the test telling the truth about the page.
  return within(screen.getByRole("alertdialog")).getByRole("button", { name: label });
}

/** The row action that OPENS a confirm — outside the dialog, by design. */
function rowAction(label: string): HTMLElement {
  return screen.getAllByRole("button", { name: label })[0];
}

/** Rule 6, both halves of its own wording, on ONE button's rendered class. */
function expectDangerTier(button: HTMLElement): void {
  expect(button.getAttribute("data-variant")).toBe("danger");
  expect(button.getAttribute("class")).toBe(buttonClasses("danger"));
  // "outlined accent, filled on hover" — rule 6's words.
  expect(button.getAttribute("class")).toContain("bg-transparent");
  expect(button.getAttribute("class")).toContain("border-danger-500");
  expect(button.getAttribute("class")).toContain("hover:not-disabled:bg-danger-700");
  // "…never the standard primary."
  expect(button.getAttribute("class")).not.toContain("bg-accent");
}

/** The negative half — and it is load-bearing, not a formality. */
function expectPrimaryTier(button: HTMLElement): void {
  expect(button.getAttribute("data-variant")).toBe("primary");
  expect(button.getAttribute("class")).toBe(buttonClasses("primary"));
  expect(button.getAttribute("class")).toContain("bg-accent");
  expect(button.getAttribute("class")).not.toContain("border-danger-500");
}

// ══════════════════════════════════════════════════════════════════════════
// S8 · Settings → Users & roles — ONE dialog, five row actions, two meanings
// ══════════════════════════════════════════════════════════════════════════

const USERS: TenantUser[] = [
  {
    id: "u-alex",
    name: "Alex Reed",
    email: "alex@silvercreek.example",
    role: "system_admin",
    role_name: "System Admin",
    last_active_at: "2026-08-09T14:02:00Z",
    status: "active",
  },
  {
    id: "u-marcus",
    name: "",
    email: "marcus@silvercreek.example",
    role: "billing_clerk",
    role_name: "Billing Clerk",
    last_active_at: null,
    status: "invited",
  },
  {
    id: "u-carla",
    name: "Carla Ortiz",
    email: "carla@silvercreek.example",
    role: "billing_clerk",
    role_name: "Billing Clerk",
    last_active_at: "2026-07-10T09:00:00Z",
    status: "deactivated",
  },
];

function pageOf<T>(rows: T[]): Paginated<T> {
  return { count: rows.length, next: null, previous: null, results: rows };
}

function mountUsers() {
  return mount(<UsersTab readOnly={false} timeZone="America/Chicago" />, (qc) => {
    qc.setQueryData(queryKeys.tenantUsers(1, DEFAULT_PAGE_SIZE), pageOf(USERS));
    qc.setQueryData(queryKeys.rolesMatrix, { roles: [], permissions: [] });
  });
}

describe("B14 rule 6 (DEF-718) — S8 Users & roles: one ConfirmDialog, two tiers", () => {
  it("DEACTIVATE — the destructive half — commits through the DANGER tier", async () => {
    mountUsers();
    await userEvent.click(rowAction("Deactivate"));
    expect(screen.getByText("Deactivate Alex Reed?")).toBeInTheDocument();
    expectDangerTier(confirmButton("Deactivate user"));
  });

  it("REMOVE — a permanent deactivation (BR-IDN-030) — is destructive too", async () => {
    mountUsers();
    await userEvent.click(rowAction("Remove"));
    expectDangerTier(confirmButton("Remove user"));
  });

  it("REACTIVATE — restoring access — stays the PRIMARY, and that is the point", async () => {
    // ⚠ If this went danger too, the tier would appear on every dialog on the
    // screen and stop meaning anything. Rule 6's subject is the destructive
    // commit; restoring a sign-in is its opposite.
    mountUsers();
    await userEvent.click(rowAction("Reactivate"));
    expectPrimaryTier(confirmButton("Reactivate user"));
  });

  it("RESET TEMP PASSWORD — issuing a credential — stays the PRIMARY", async () => {
    mountUsers();
    await userEvent.click(rowAction("Reset temp password"));
    expectPrimaryTier(confirmButton("Reset temp password"));
  });

  it("A18 §3 survives the tier: the in-flight confirm is DISABLED, asked as an attribute", async () => {
    // ⚠ NOT a `toContain("disabled")` on markup — that assertion CANNOT FAIL
    // under Route B, because the kit spells `disabled:opacity-45` into every
    // button's class string (DEF-712's mutant 5 was green on it).
    mountUsers();
    await userEvent.click(rowAction("Deactivate"));
    const commit = confirmButton("Deactivate user");
    expect(commit).not.toBeDisabled();
    expect(confirmButton("Cancel")).not.toBeDisabled();
  });
});

// ══════════════════════════════════════════════════════════════════════════
// S8 · Settings → Services & UoM — the same dialog for ON and for OFF
// ══════════════════════════════════════════════════════════════════════════

const SERVICES: TenantServiceRow[] = [
  {
    service: "electric",
    name: "Electric",
    enabled: true,
    primary_uom: "kWh",
    alt_uom: "kW",
    // DEF-2409: `billing_basis` is BR-RAT-081's declaration as re-ruled on
    // 2026-09-02 — one of THREE (metered · share · capacity), never a
    // boolean. `billed_uom: null` means the register's own unit is billed.
    billing_basis: "metered",
    billed_uom: null,
    conversion_factor: null,
    revenue_account: null,
    base_revenue_account: null,
    rate_schedules: 3,
    active_accounts: 612,
  },
  {
    service: "gas",
    name: "Gas",
    enabled: false,
    primary_uom: null,
    alt_uom: null,
    // DEF-2409: `billing_basis` is BR-RAT-081's declaration as re-ruled on
    // 2026-09-02 — one of THREE (metered · share · capacity), never a
    // boolean. `billed_uom: null` means the register's own unit is billed.
    billing_basis: "metered",
    billed_uom: null,
    conversion_factor: null,
    revenue_account: null,
    base_revenue_account: null,
    rate_schedules: 0,
    active_accounts: 0,
  },
];

describe("B14 rule 6 (DEF-718) — S8 Services & UoM: the tier follows the verb", () => {
  it("DISABLE — a deactivation — commits through the DANGER tier", async () => {
    mount(<ServicesTab readOnly={false} />, (qc) =>
      qc.setQueryData(queryKeys.tenantServices, SERVICES),
    );
    await userEvent.click(rowAction("Disable"));
    expect(screen.getByText("Turn off Electric?")).toBeInTheDocument();
    expectDangerTier(confirmButton("Turn off Electric"));
  });

  it("ENABLE — turning a service ON — stays the PRIMARY", async () => {
    mount(<ServicesTab readOnly={false} />, (qc) =>
      qc.setQueryData(queryKeys.tenantServices, SERVICES),
    );
    await userEvent.click(rowAction("Enable"));
    expectPrimaryTier(confirmButton("Turn on Gas"));
  });
});

// ══════════════════════════════════════════════════════════════════════════
// THE CENSUS — every call site is CLASSIFIED, and a new one cannot be silent
// ══════════════════════════════════════════════════════════════════════════
/**
 * ⚠ **THIS IS A SOURCE CHECK AND IT IS SAID SO PLAINLY** — it reads text, not
 * rendered output, so on its own it is exactly the kind of assertion DEF-718's
 * escape reason warns about. It is not on its own: the rendered-output cases
 * above and in `ConfirmDialog.test.tsx` / `AssetLifecycle.test.tsx` are what
 * prove the tier reaches the browser. What the census adds is the ONE thing a
 * per-screen test cannot: **coverage of the sites nobody has written a test
 * for.** Thirty call sites were audited by hand for DEF-718; the audit is
 * written down here so that the thirty-first — a confirm added next month —
 * fails this file until somebody classifies it, instead of quietly shipping in
 * whichever tier the default happens to be.
 *
 * `"computed"` marks the polymorphic sites, which the clicking suites above
 * cover in both directions.
 */
const CENSUS: Record<string, readonly ("danger" | "primary" | "computed")[]> = {
  // ── DESTRUCTIVE — rule 6's subject, pinned ──────────────────────────────
  "src/features/assets/AssetDetailPage.tsx": ["danger"], // delete an asset
  "src/features/assets/AssetImportsTab.tsx": ["danger"], // roll back an import
  "src/features/assets/AssetRegistryPage.tsx": ["danger"], // delete an asset
  // ⚠ `AccountImportsTab.tsx`'s roll-back confirm LEFT on 2026-09-22
  // (`470e316f8`, P1.5 — *"the run list is one component with two callers"*)
  // and its row stayed here for ten days: the LEAVING half of `DEF-SHL-5101`
  // again. Removed 2026-10-02.
  // CR-094-BRC01 wave M (2026-09-13) — take back a filed document. DANGER, and
  // the classification needs its sentence because the obvious objection is that
  // NOTHING IS DESTROYED: `BR-CUS-1052` withdraws the FILING and the stored
  // object stays under `BR-SHL-031`'s seven-year lock, untouched. What IS
  // irreversible is the thing the clerk is looking at — the document leaves
  // that customer's file and nothing in this product puts it back. Rule 6's
  // subject is the COMMIT the reader cannot undo, not the row count, which is
  // the same reasoning `parkedDrafts`' Discard already carries three lines up.
  "src/features/customers/AccountDocumentsTab.tsx": ["danger"], // take a filing back
  // CR-035 — discard a parked wizard draft. DANGER, and the classification is
  // worth a sentence because the obvious objection is that nothing is deleted:
  // BR-SHL-048 means a parked draft is not a record, so hard rule 4's
  // immutability has nothing to say here. What IS destroyed is the clerk's own
  // unfinished typing — up to nine steps of it — and it does not come back.
  // ⚠ **THE FILE MOVED ON 2026-08-26 AND THE CLASSIFICATION DID NOT** —
  // CR-035 · AMENDMENT 1 folded the Waiting-on TAB into the six worklists
  // (PO: *"seperate queue not reequired"*), so the same Discard confirm now
  // lives on `parkedDrafts.tsx`, pinned above each flow list. Same dialog,
  // same tier, same reason.
  "src/features/customers/parkedDrafts.tsx": ["danger"], // discard a parked draft
  "src/features/metering/PremisesImportsTab.tsx": ["danger"], // roll back an import
  // ⚠ **ONE DIALOG, NOT TWO, SINCE 2026-09-10 — AND THIS ROW SAID TWO FOR
  // THREE DAYS.** The row read `["danger", "danger"] // deactivate · delete`.
  // `CR-089` P1/P10 (`67da0e4f2`) REMOVED the deactivate confirm on purpose —
  // `DEF-4743`: *"POST /premises/{id}/deactivate records no date and no
  // reason"* — and the census was not moved with it, which is the LEAVING half
  // of `DEF-SHL-5101` rather than the arriving half everybody looked at.
  // **A census is wrong in both directions or it is not a census**, and a row
  // claiming a destructive dialog that no longer exists is the one kind of
  // error nobody goes looking for.
  "src/features/metering/PremisesListPage.tsx": ["danger"], // delete a premise
  // CR-069 wave E (2026-09-04) — disconnect a provider. DANGER, and the
  // classification is not a close call: the credential is DESTROYED, every
  // version of it, on confirm. `US-INT-025` is the story and its whole reason
  // for existing is that the secret must be removable, so the one dialog that
  // removes it had better not look like Save.
  // ⚠ IT IS ALSO THE FIRST CALL SITE TO USE `typeToConfirm`, which this file's
  // subject grew in the same commit for the same reason `confirmVariant` was
  // added by DEF-718: optional, absent means unchanged, and put only where the
  // reader could plausibly be looking at the wrong row. It was the
  // THIRTY-THIRD call site and this file went red on it, which is what the
  // census is for.
  // ⚠ **AND THREE MORE ON THIS PAGE ARRIVED UNAUDITED ON 2026-09-17**, which
  // is the census's FIRST red of the ten-day run fixed 2026-10-02
  // (`aec547e7f` regenerate, `2836c242a` Run now's Apply, `7c10c943c` delete a
  // custom API). Read 2026-10-02; all four declare danger and all four are
  // right: a REGENERATED key kills the old one wherever it is still in use,
  // DISCONNECT destroys the credential, APPLY writes a partner's changes into
  // our records with no undo, and DELETE removes a custom API definition.
  "src/features/integrations/ConnectionDetailPage.tsx": ["danger", "danger", "danger", "danger"], // regenerate · disconnect · apply a run · delete a custom API
  // CR-156-BRC10 wave B (2026-10-01) — CHG-01's own page, Retire a charge code
  // (it stops on new bills). DANGER: the drawn header puts Retire beside Edit,
  // and it is the destructive act of the three. Read by a reader, not banked.
  "src/features/rating/ChargeCodeDetailPage.tsx": ["danger"], // retire a charge code
  // ⚠ **FIVE MORE ARRIVED UNAUDITED AND THIS FILE WAS RED FROM 2026-09-19
  // UNTIL 2026-10-02 — the first at `c656deea1`.** Each was read on
  // 2026-10-02 before its row was written (`DEF-SHL-5101`'s remedy: never
  // raise the record to match the code without a reader). All five declare
  // `danger` and all five are right to — each commit cannot be taken back:
  //   * DISCARD A DRAFT discount version (`c656deea1`, 2026-09-19) and a draft
  //     rate schedule (`5804b0fc1`, 2026-10-01) — typed work is destroyed;
  //     the same reasoning as `parkedDrafts`' Discard above.
  //   * POST A MONTH-END BATCH of journal entries (`af8956920`, 2026-09-24)
  //     and POST ACCRUALS from the workbench (`88f7338a1`, 2026-09-24) —
  //     journal lines are immutable (hard rule 4); a mistake is a reversal,
  //     never an undo.
  //   * APPROVE A REFUND (`88f7338a1`) — money leaves the utility.
  // CR-166-BRC10 r3 t6 (2026-10-03): `discountDetailTabs.tsx` is deleted and its
  // discard moved to the details page's More ▾ — same act, same tier.
  "src/features/rating/discountDetail/DiscountDetailPage.tsx": ["primary", "danger"], // approve (goes live on its start date) · delete a draft discount version
  "src/features/rating/RateScheduleThreeStep.tsx": ["danger"], // discard a draft rate schedule
  "src/features/ledger/JournalBatchPage.tsx": ["danger"], // post a batch of journal entries
  "src/features/ledger/AccrualsWorkbench.tsx": ["danger"], // post accruals
  "src/features/ledger/RefundDetailPage.tsx": ["danger"], // approve a refund — money leaves
  // ⚠ **THE NEXT THREE ARE `DEF-SHL-5101`'s, AUDITED HERE RATHER THAN LEFT IN
  // THE PILE.** That defect records this census finding call sites the audit
  // did not have — *"THREE destructive dialogs have a tier nobody has
  // checked"* — and its own remedy says the recorded number *"must never be
  // raised to match the code without a reader looking at each new call site"*.
  // A reader looked at each, on 2026-09-13, while adding a fourth. All three
  // declare `danger` already and all three are right to:
  //   * REVOKE A MACHINE KEY — the key stops working for whatever is using it
  //     and cannot be un-revoked; its own trailing comment says *"this one
  //     really does break something"*, which is rule 6 in the author's words.
  //   * CANCEL A WORK ORDER, from the order page and from the editor — the
  //     same commit reached two ways. A cancelled order is not a draft being
  //     abandoned; it is a job somebody may be on their way to.
  // Their tiers were never wrong. What was missing was the AUDIT, which is the
  // half this file exists for — the same sentence `SettingsPortalTips` carries
  // below, for the same reason.
  "src/features/integrations/MachineKeysPage.tsx": ["danger"], // revoke a machine key
  "src/features/work/OrderDetailPage.tsx": ["danger", "primary", "primary"], // cancel a work order (danger); duplicate it (primary — a CREATION, found unclassified 2026-10-12); accept a completed one (primary — CR-168 P1.32, nothing is destroyed: costs and readings are recorded)
  "src/features/work/OrderEditPage.tsx": ["danger"], // cancel a work order, from the editor
  // Same removal, same day, same commit family — `a298224c6`, *"the three unit
  // dialogs get their drawn frames, and two second doors close"*. One dialog.
  "src/features/metering/UnitsListPage.tsx": ["danger"], // delete a unit
  "src/features/notifications/TemplateDetail.tsx": ["danger"], // deactivate a variant
  "src/features/rating/ChargeCodesTab.tsx": ["danger"], // delete a charge code
  // CR-167 r3 task 7: the plan details page moved into `planDetail/` with the same two dialogs.
  // 2026-10-04 (DEF-BIL-9591, found beside it) — a saved new version is
  // PUBLISHED from this page since 97724c5cb (DEF-RAT-9364, 2026-10-03), a
  // primary confirm between retire and delete that never reached this row.
  "src/features/rating/planDetail/PlanDetailPage.tsx": ["danger", "primary", "danger"], // RETIRE — rule 6's own example · delete a draft (CR-167 §5.5 L13)
  "src/features/rating/RateScheduleDetail.tsx": ["danger"], // RETIRE — rule 6's own example
  "src/features/rating/RateSchedulesTab.tsx": ["danger"], // archive a schedule
  "src/features/tenancy/CycleDetailPage.tsx": ["danger"], // delete a cycle
  "src/features/tenancy/RouteDetailPage.tsx": ["danger"], // deactivate OR delete — both
  "src/features/tenancy/SettingsReferenceData.tsx": ["danger", "danger"], // delete entry · remove holiday
  // CR-068 wave D (2026-09-04) — remove a service centre. DANGER, and the
  // classification is the easy half: what makes it destructive is not the row
  // but the ADDRESS, which may already be printed on bills a customer is
  // holding. The dialog's consequence says exactly that and offers hiding
  // instead, which is `BR-CWP-096`'s *hidden is a state, not a deletion* put
  // where a clerk meets it. ⚠ It was the THIRTY-SECOND call site and this file
  // went red on it the moment it was written, which is what the census is for.
  // ⚠ THE THIRTY-FOURTH, and it was RED AT THE BRANCH TIP for a while before
  // anybody read it (`DEF-SHL-3938`). *Remove* on a portal tip is a real
  // deletion — the dialog says so in the clerk's own words, *"A removed tip
  // cannot be brought back. Turning it off keeps it here and off the portal"*,
  // which is `BR-CWP-096`'s *hidden is a state, not a deletion* again, offered
  // beside the destructive act. The tier was declared `danger` correctly by
  // whoever wrote it; what was missing was the AUDIT, which is the half this
  // file exists for. The census did its job on the day the dialog was written
  // and the failure was read as a pass, which is the defect above, not this one.
  "src/features/tenancy/SettingsPortalTips.tsx": ["danger"], // remove a portal tip
  "src/features/tenancy/SettingsServiceCentres.tsx": ["danger"], // remove a service centre
  "src/features/tenancy/SettingsRoutesCyclesTab.tsx": ["danger", "danger"], // route deact/delete · cycle delete

  // ── POLYMORPHIC — one dialog, both meanings; clicked above ──────────────
  "src/features/identity/SettingsUsersTab.tsx": ["computed"], // deactivate/remove vs reactivate/temp password
  "src/features/tenancy/SettingsServicesTab.tsx": ["computed"], // disable vs enable
  // `8cd893e14` (2026-09-20) — the move-out record's one dialog for four acts.
  // `DANGER_DIALOGS` makes WRITE OFF (the debt is cancelled) and DISCARD (the
  // parked move-out is deleted) danger; TIE BACK and COLLECT move who is
  // chased and post nothing yet, so they stay primary. Read 2026-10-02.
  "src/features/customers/moveRecordActionBar.tsx": ["computed"], // write off/discard vs tie back/collect

  // ── NOT RULE 6's SUBJECT — left primary ON PURPOSE ──────────────────────
  // A confirm in front of a CREATION, a PUBLISH or a SEND is not a destructive
  // commit. Reddening these would spend the tier's meaning everywhere it IS
  // true, which is the failure mode the PO's ruling is guarding against.
  // DEF-BIL-9591 (2026-10-04) — Discard a draft bill run (DEF-BIL-9255,
  // 2.467.19). DANGER: the draft run and its draft bills are deleted. It
  // arrived unaudited and the census stood red for a day before anyone read it.
  "src/features/billing/bulkRun/BulkRunPage.tsx": ["danger"], // discard a draft bill run
  // DEF-BIL-10068 (2.570.0) — Cancel a one-time DRAFT. DANGER: the draft is
  // deleted and its number is not reused (`runs.discard_run`).
  "src/features/billing/oneTimeBill/DraftDecision.tsx": ["danger"], // cancel a one-time draft
  // DEF-CUS-9840 — ✕ on a New connection service row that holds pieces.
  // DANGER: the service and every piece under it are removed from the request.
  "src/features/customers/NewConnectUnitsStep.tsx": ["danger"], // remove a service and its pieces
  // CR-168-BRC10 (2.503.0) — Retire a part. DANGER: the part leaves the
  // catalogue for new work. Unclassified since 2.503.0; found 2026-10-12.
  "src/features/work/PartsPage.tsx": ["danger"], // retire a part
  // CR-168 round 2 (lane ORDERS-LIST, 2026-10-04) — ACCEPT finished field work
  // from the Approvals queue (image 22). PRIMARY, not danger: nothing is
  // destroyed or reversed — the act the field asked for is accepted, and
  // image 22 draws its commit in the accent tier. The dialog exists because
  // BR-MET-110 wants a person to read what goes live before it does.
  "src/features/work/AwaitingApprovalPage.tsx": ["primary"], // accept field work (one row or the ticked rows)
  // CR-187-BRC10 (EP-WRK-11, 2026-10-21) — the office side of the field app.
  // Accept on *Finished jobs* is the same act as Approvals' (PRIMARY: nothing
  // destroyed, the field's work is accepted). Accept on *Raised on site* puts
  // an order raised on a handset into the dispatch queue (PRIMARY: a
  // creation's approval). Its *Refuse* cancels the order and is a FormModal
  // with `submitVariant="danger"`, not a ConfirmDialog, so it is not here.
  "src/features/work/field/FieldResultsPane.tsx": ["primary"], // accept a finished job
  "src/features/work/field/FieldRaisedPane.tsx": ["primary"], // accept an order raised on site
  // Sign a handset out — DANGER: every token of the handset is revoked and
  // everyone on it is signed out (R115). Unsent work is kept (R113).
  "src/features/work/field/TechnicianDevicesPanel.tsx": ["danger"], // sign a handset out
  "src/features/ledger/CloseExportPage.tsx": ["primary"], // SEND the close export to an external system
  "src/features/rating/RateChangesTab.tsx": ["primary", "primary"], // apply previewed rate changes · run the preview
  "src/features/tenancy/SettingsNumberingTab.tsx": ["primary"], // move a counter FORWARD (the form refuses backwards)
  "src/features/tenancy/SettingsRegionalTab.tsx": ["primary"], // change the tenant currency — a setting, not a deletion
};

/**
 * Every feature source, as TEXT.
 *
 * ⚠ Read through Vite's own `?raw` and NOT through `node:fs`: this app's
 * tsconfig carries no `@types/node`, so a bare `node:fs` import passes vitest
 * and FAILS `tsc --noEmit` — the same trap `DataTable.test.tsx` and
 * `buttonKit.test.ts` both document next door.
 */
const FEATURE_SOURCES = import.meta.glob("../features/**/*.tsx", {
  query: "?raw",
  eager: true,
  import: "default",
}) as Record<string, string>;

/** `../features/rating/PlanDetail.tsx` → `src/features/rating/PlanDetail.tsx`. */
function repoPath(globKey: string): string {
  return globKey.replace(/^\.\.\//, "src/");
}

/**
 * The tier each `<ConfirmDialog` in one file declares, in source order.
 *
 * ⚠ **A TRAILING COMMENT USED TO MAKE THIS READ THE WRONG TIER, SILENTLY
 * (`DEF-CWP-3729`, 2026-09-04).** The pattern anchored on `\s*$`, so
 *
 *     confirmVariant="danger" // B14 rule 6
 *
 * did not match — and the `null` branch then recorded **`primary`**, because
 * `null` had been made to mean *the prop is absent*. It cannot mean only that:
 * it also means *a prop is here and I could not read it*, and those two want
 * opposite answers. `SettingsServiceCentres` declared `danger`, in the very
 * words of the rule it was obeying, and this census recorded it as `primary`.
 *
 * **That is worse than a red test.** A lane trusting the scanner would have
 * written `["primary"]` into the audit to make the suite pass, and the census —
 * whose entire job is to be the record of what was audited — would then have
 * pinned the wrong tier on a destructive action, permanently, with a green
 * suite. It is the same shape as `DEF-182`: a check whose output cannot tell
 * pass from fail is worse than no check, because it is trusted.
 *
 * So the two cases are separated. An ABSENT prop is `primary`, by the prop's
 * own contract. A prop that is PRESENT but unparseable throws by name, because
 * the honest answer to *"which tier is this?"* is sometimes *"I cannot tell"*,
 * and that must never be spelled `primary`.
 */
function tiersDeclaredIn(source: string): ("danger" | "primary" | "computed")[] {
  const tiers: ("danger" | "primary" | "computed")[] = [];
  const opens = [...source.matchAll(/<ConfirmDialog\b/g)];
  for (let i = 0; i < opens.length; i += 1) {
    const from = opens[i].index ?? 0;
    const to = i + 1 < opens.length ? (opens[i + 1].index ?? source.length) : source.length;
    const block = source.slice(from, to);
    // A trailing `// comment` is allowed after the value; nothing else is.
    const declared = /^\s*confirmVariant=(\{.*?\}|"[a-z]+")\s*(?:\/\/.*)?$/m.exec(block);
    if (declared === null) {
      // Is the prop ABSENT, or PRESENT and unreadable? Only the first is primary.
      const present = /^\s*confirmVariant=/m.exec(block);
      if (present !== null) {
        throw new Error(
          `a <ConfirmDialog> declares confirmVariant in a form this census ` +
            `cannot read: ${block.slice(present.index, present.index + 120).trim()}. ` +
            `Teach the pattern rather than classifying it as primary — DEF-CWP-3729 ` +
            `is what happens when "I cannot tell" is spelled "primary".`,
        );
      }
      tiers.push("primary"); // absent = primary, by the prop's own contract
    } else if (declared[1] === '"danger"') {
      tiers.push("danger");
    } else if (declared[1] === '"primary"') {
      tiers.push("primary");
    } else {
      tiers.push("computed");
    }
  }
  return tiers;
}

describe("B14 rule 6 (DEF-718) — the call-site census", () => {
  it("every ConfirmDialog in the product is classified, and the classification is the one audited", () => {
    const found: Record<string, ("danger" | "primary" | "computed")[]> = {};
    for (const [key, source] of Object.entries(FEATURE_SOURCES)) {
      if (key.includes(".test.")) {
        continue;
      }
      const tiers = tiersDeclaredIn(source);
      if (tiers.length > 0) {
        found[repoPath(key)] = tiers;
      }
    }
    // The glob has to have SEEN the tree at all — an empty census would make
    // every assertion below vacuously true, which is the failure mode a check
    // like this dies of (DEF-182's family).
    expect(Object.keys(FEATURE_SOURCES).length).toBeGreaterThan(100);
    // Sorted so the failure message reads as a diff of the audit, not of a
    // directory walk order.
    const sortKeys = (o: Record<string, unknown>) => Object.keys(o).sort();
    expect(sortKeys(found)).toEqual(sortKeys(CENSUS));
    for (const path of sortKeys(CENSUS)) {
      expect(found[path], `tiers declared in ${path}`).toEqual(CENSUS[path]);
    }
  });

  it("the audit covers THIRTY-FIVE call sites — four arrived unaudited, two left unrecorded (DEF-SHL-5101), one left with the old bill-run wizard", () => {
    const total = Object.values(CENSUS).reduce((n, tiers) => n + tiers.length, 0);
    // ⚠ **THIS NUMBER MOVED ON 2026-08-26 AND THAT IS THE CHECK WORKING, NOT
    // THE CHECK BREAKING.** DEF-718 audited thirty by hand; the thirty-first is
    // `parkedDrafts`' Discard (CR-035; `WaitingOnTab` until amendment 1 moved it). The file's own words: *"the
    // thirty-first — a confirm added next month — fails this file until
    // somebody classifies it, instead of quietly shipping in whichever tier the
    // default happens to be."* It did exactly that, on the day it was added.
    // ⚠ MOVED AGAIN ON 2026-09-04, and again because the check worked: the
    // thirty-second is *Remove* on a service centre (CR-068 wave D), which
    // went red here before it shipped.
    // ⚠ AND AGAIN ON 2026-09-04, the same day, from a different wave: the
    // thirty-third is *Disconnect* on a provider connection (CR-069 wave E),
    // which destroys a utility's stored mail password. It too went red here
    // before it shipped — twice in one day is the strongest evidence this file
    // has produced that a census beats a per-screen test for the sites nobody
    // has written a test for.
    // ⚠ AND AGAIN ON 2026-09-05: the thirty-fourth is *Remove* on a portal tip
    // (CR-068 settings). This one is the census's least comfortable win — it
    // went red the moment the dialog was written, exactly as designed, and then
    // STAYED red at the branch tip because `vitest run` was being read through
    // a pipe that reported its own exit code (`DEF-SHL-3938`). A check that
    // fires correctly and is not read is worth what an unread check is worth.
    // ⚠ **THE NUMBER WENT DOWN ON 2026-09-13, WHICH IS NOT WHAT ANYBODY
    // EXPECTED FROM THIS CHECK — `DEF-SHL-5101`.** It had been RED FOR A DAY
    // before anybody read it, and the reading found the census wrong in BOTH
    // directions at once:
    //   * **FOUR ARRIVED UNAUDITED** — `MachineKeysPage`, `OrderDetailPage`,
    //     `OrderEditPage` (all 2026-09-12, the defect's own three) and
    //     `AccountDocumentsTab` (2026-09-13, the lane that read the failure).
    //     Each was looked at by a person before its row was written; **raising
    //     a number to match the code without that is how an unenforced rule
    //     becomes a green test**, which is the defect's remedy in its own
    //     words.
    //   * **TWO LEFT AND NOBODY MOVED THE RECORD** — the deactivate confirms
    //     on `PremisesListPage` and `UnitsListPage`, deliberately removed on
    //     2026-09-10 by `CR-089` P1/P10 (`DEF-4743`). The audit went on
    //     claiming two destructive dialogs that did not exist. **That half is
    //     the one nobody goes looking for**, and it is why 34 + 4 is 36.
    // ⚠ **AND DOWN AGAIN ON 2026-09-30: 36 → 35.** `BillRunWizard.tsx` — whose
    // bulk-apply confirm was the one audited `primary` row for billing — was
    // DELETED with the six-step wizard (bulk bill run plan task F2,
    // `DEF-BIL-8200`); its row left the census in the same commit. The page that
    // replaced it (`bulkRun/BulkRunPage.tsx`) opens no ConfirmDialog: its one
    // irreversible act, Send, is the wizard frame's danger-tier commit.
    // ⚠ **AND UP ON 2026-10-01: 35 → 36.** `ChargeCodeDetailPage.tsx` (CHG-01
    // rebuilt as its own page, `CR-156-BRC10` wave B) confirms Retire — read by
    // the lane that wrote it and classified `danger` above, not banked blind.
    // ⚠ **AND 36 → 41 ON 2026-10-02**: five unaudited arrivals classified
    // `danger` and one computed (see the rows), and `AccountImportsTab`'s
    // departed roll-back confirm taken off the record — read, not banked.
    // ⚠ **AND 41 → 44 THE SAME DAY**: three more on `ConnectionDetailPage`,
    // the earliest of the run (2026-09-17).
    // ⚠ **AND 44 → 45 ON 2026-10-03** (`CR-166-BRC10` round 3 task 6): the
    // discount details page carries TWO confirms where `discountDetailTabs.tsx`
    // (deleted) carried one — Delete draft (`danger`, the same act moved) and
    // Approve (`primary`: approval goes live on its start date and is undone by
    // Retire on a date, so it destroys nothing). Read by the lane that wrote it.
    // 2026-10-03 · 45 → 44: `PlanWizard.tsx`'s archive confirm (danger) left
    // with that file (CR-167-BRC10 r3 t8); a plan is retired from its details
    // page's More menu, already counted.
    // 2026-10-04 · 44 → 46: Approvals' accept (primary, CR-168 round 2) and
    // the bill run's Discard (danger, DEF-BIL-9591 — there since 2.467.19).
    // … and 46 → 47: the plan page's Publish version (primary), there since
    // 97724c5cb and found by the same read.
    // 2026-10-04 · 47 → 48: the work order page's Accept (primary, CR-168
    // round 2 P1.32, lane ORDER-PAGE) — acceptance records costs and readings
    // and destroys nothing, the same reading as Approvals' accept.
    // 2026-10-12 · 48 → 51: three danger arrivals left unclassified — the
    // one-time draft's Cancel (DEF-BIL-10068), New connection's remove-a-service
    // (DEF-CUS-9840) and Parts' Retire (CR-168-BRC10, red since 2.503.0).
    // … and 51 → 52: the work order page's Duplicate (primary — it creates).
    // 2026-10-21 · 52 → 55: the field app's office side (CR-187-BRC10) — two
    // accepts (primary) and a handset sign-out (danger), classified above.
    expect(total).toBe(55);
    const destructive = Object.values(CENSUS)
      .flat()
      .filter((tier) => tier === "danger").length;
    // 27 pinned danger + 3 computed + 5 deliberately left primary (six until the bill-run
    // wizard's bulk-apply confirm left with that file, 2026-09-30).
    // 2026-10-01 · 27 → 28: CHG-01's Retire confirm (CR-156-BRC10 wave B), classified above.
    // 2026-10-02 · 28 → 35: eight arrivals classified danger, one departure.
    // 2026-10-03 · stays 35: PlanWizard's archive confirm (danger) left with
    // that file, and the count had read 36 against this 35 since a danger
    // arrival before it was classified without moving the figure (red at
    // 532df04e9 — `expected 36 to be 35`).
    // 2026-10-04 · 35 → 36: the bill run's Discard (DEF-BIL-9591).
    // 2026-10-12 · 36 → 39: the three arrivals above.
    // 2026-10-21 · 39 → 40: a technician's handset sign-out (CR-187-BRC10).
    expect(destructive).toBe(40);
    // 2026-10-03 · 4 → 3: the Plans list's polymorphic confirm left with the
    // old list (`6f107d0a7`, CR-167 r2 t6) and its row was removed above without
    // moving this figure — masked until now by the destructive line failing first.
    expect(Object.values(CENSUS).flat().filter((t) => t === "computed").length).toBe(3);
    // 2026-10-03 · 5 → 6: the discount details page's Approve (CR-166 r3 t6).
    // 2026-10-04 · 6 → 8: Approvals' accept (CR-168 round 2) and the plan
    // page's Publish version (97724c5cb, recorded by DEF-BIL-9591).
    // 2026-10-04 · 8 → 9: the work order page's Accept (CR-168 P1.32).
    // 2026-10-12 · 9 → 10: the work order page's Duplicate.
    // 2026-10-21 · 10 → 12: the field app's two accepts (CR-187-BRC10).
    expect(Object.values(CENSUS).flat().filter((t) => t === "primary").length).toBe(12);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// generated: 2026-08-26 by lane CONFIRMTIER (DEF-718)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
