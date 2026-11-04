// ── Trace ──────────────────────────────────────────────
// Story:    US-CUS-012 · US-CUS-013 · US-CUS-014 · US-CUS-015 · US-CUS-003
//           Screens: S21 · S22
// Change:   CR-094-BRC01 step 2 wave J — `ACC-S14`, the thirteen quick actions.
//           Drawn as `R4`, pages 154–174 of the accounts blueprint; committed
//           by `ACC-S14` on page 208.
// Rules:    BR-SHL-025 (a control this deployment cannot honour renders
//           DISABLED WITH ITS REASON, never hidden) · BR-SHL-045 (the rail's
//           seven) · BR-CUS-018 (activate a draft) · B14 rule 33 (on-screen
//           text is capped by what it is FOR) · B14 rule 38 (where a drawing
//           and our UI rules disagree about how a FORM IS BUILT, the UI rules
//           win — and what the form CONTAINS is still the drawing's)
// Tests:    accountQuickActions.test.ts — the census, and the endpoint truth
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// ONE CONFIGURATION, THIRTEEN ACTIONS — AND WHY IT IS DATA AND NOT THIRTEEN
// COMPONENTS
// ══════════════════════════════════════════════════════════════════════════
// PO standing instruction: *"Do all changes based on actual code — also don't
// create duplicate code."* Thirteen quick actions is thirteen chances to write
// one form thirteen times, so the form is `AccountQuickActionForm.tsx` — ONE
// component — and everything that differs between the thirteen is a row in this
// file.
//
// **Every one of the thirteen is declared here, including the eleven this wave
// does not open as a form.** A census that lists only what is built cannot tell
// a reader the difference between *"not drawn"* and *"drawn and not done"*, and
// that difference is the whole point of `ACC-S14`.
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ THE ENDPOINT IS THE DESIGN CONSTRAINT, AND IT IS NOT WHAT THE DRAWING
//   ASSUMES
// ══════════════════════════════════════════════════════════════════════════
// The lane brief said to find out which of the thirteen writes through an
// endpoint that exists BEFORE designing, and this is what that found:
//
// **`POST /accounts/{id}/activate` ACCEPTS EXACTLY TWO FIELDS.**
// `apps/customers/services.activate_account` opens with
//
//     _reject_unknown(data, frozenset({"opened_at", "status"}))
//
// and `_reject_unknown` does not ignore a stranger — it raises a field error
// naming it. **`R4`'s `ACC-Q03` draws TEN fields**: an activation date, an
// opening-read choice, a start date per service, the unit's plan, its base
// charge, a deposit choice, a deposit amount, a deposit due date, a billing
// cycle and two notification checkboxes. **Nine of those ten cannot be sent at
// all**, and a form that collects a value the server refuses is worse than a
// form that never asked — it is CLAUDE.md hard-won law 2 in its most expensive
// shape, because every test passes over a field whose value is thrown away.
//
// **So the built form asks for the one field the endpoint takes, SHOWS the
// facts it can read, and STATES the rest as absences rather than drawing inputs
// for them.** R4 itself already states two of the three in its own caveat box
// (*"No plan snapshot is recorded"*, *"No deposit is applied"*); this adds the
// third, the opening read, which the drawing draws as a live picker.
//
// Filed as `DEF-CUS-5121` against the drawing — B14 rule 37 is the general
// form of it: a figure drawn in a wireframe is an illustration, never a fact to
// build to.
//
// ⚠ **AND `Base charge` AND `Billing cycle` ARE NOT SERVED EITHER.**
// `AccountUnitPlan` is `{name, code, version, since}` and `AccountDetail`
// carries no cycle, so even as READ-ONLY facts those two boxes would have
// nothing to put in them. They are not drawn.

import type { AccountOverlayId } from "./accountActionOverlays";

/** The thirteen, in the drawn order — six header actions, then the rail's
 *  seven. The ids are the ones the header and `AccountIconRail` already use,
 *  so this file names controls that exist rather than minting new ones. */
export const ACCOUNT_QUICK_ACTION_IDS = [
  "adjust",
  "moveOut",
  "activate",
  "moveIn",
  "closeOut",
  "recordPayment",
  "sendStatement",
  "printBill",
  "issueCredit",
  "changePlan",
  "disconnectNotice",
  "paymentPlan",
  "addNote",
] as const;

export type AccountQuickActionId = (typeof ACCOUNT_QUICK_ACTION_IDS)[number];

/** What kind of control the field is. Only the kinds the wired forms use are
 *  declared — an unused variant is not coverage (LAW 0). */
export type QuickFieldKind = "date" | "readonly";

export interface QuickField {
  /** The DOM id and the form-state key. Where the value is SENT, this is the
   *  server's own field name, so a reader can check the two against each
   *  other without a mapping table. */
  id: string;
  labelKey: string;
  kind: QuickFieldKind;
  required?: boolean;
  helpKey?: string;
}

export interface QuickSection {
  headingKey: string;
  fields: readonly QuickField[];
}

/** A row of the recap. `source` says where the VALUE comes from, resolved by
 *  the form against the account it is open over — never a literal, because a
 *  literal in a recap is a figure that cannot go stale and therefore lies. */
export type QuickRecapSource =
  | "statusName"
  | "openedAt"
  | "unitPlan"
  | "outcomeSentence";

export interface QuickRecapRow {
  labelKey: string;
  /**
   * Where the value comes from when the account already holds it.
   *
   * ⚠ **OPTIONAL SINCE `ACC-Q07` (wave M), AND THE ABSENCE IS THE HONEST
   * CASE.** `rowValue` reads `fromField` FIRST and returns before it ever
   * looks at `source`, so a row reading back a date the clerk just typed has
   * never used this field. Until wave M every such row still had to name one,
   * which meant writing `source: "openedAt"` on a row about a statement
   * period — a label that is simply untrue, sitting in the file a reader goes
   * to in order to find out where a value comes from. A row with a `fromField`
   * and no `source` now says what is actually happening: **the clerk is the
   * source.** Every pre-existing row still names one and none changed.
   */
  source?: QuickRecapSource;
  /**
   * **THE FIELD THIS ROW READS BACK, when the value is one the clerk just
   * typed rather than one the account already holds.**
   *
   * ⚠ A recap whose rows all came from the SERVER would echo the account as it
   * is, not as the commit will leave it — which is the opposite of what
   * `ACC-S14` asks for (*"reads back a recap"*). `Service starts` is the date
   * in the box above it, and if the clerk changes the date and the recap does
   * not move, the recap is decoration. Named as a field id so the link is
   * checkable: `accountQuickActions.test.ts` asserts every `fromField` names a
   * field that the same form actually declares.
   */
  fromField?: string;
}

/**
 * The form a quick action opens over the account.
 *
 * ⚠ **`caveatBulletKeys` IS NOT DECORATION.** R4 draws a box on `ACC-Q03` and
 * `ACC-Q09` headed *"Two things the server will not manage, and says so now
 * rather than after"*. It is the honest half of a form whose endpoint does less
 * than the drawing implies, and `BR-SHL-025`'s principle one level down: where
 * the product cannot do a thing, it SAYS SO before the click rather than after.
 */
export interface QuickForm {
  titleKey: string;
  /** One consequence sentence under the title. B14 rule 33 caps a consequence
   *  at six words per sentence, at most two sentences. */
  leadKey?: string;
  sections: readonly QuickSection[];
  recapTitleKey: string;
  recapRows: readonly QuickRecapRow[];
  recapOutcome?: QuickRecapRow;
  caveatHeadingKey?: string;
  caveatBulletKeys?: readonly string[];
  commitLabelKey: string;
  /** `BR-SHL-025` — the reason this form cannot commit on this deployment, or
   *  absent when it can. */
  commitBlockedKey?: string;
}

/**
 * Where a quick action takes the clerk today.
 *
 * `form`    — a form DECLARED IN THIS FILE, rendered over the account by
 *             `AccountQuickActionForm`.
 * `mounted` — an EXISTING screen, rendered over the account as a child route
 *             (`accountActionOverlays.tsx`). Nothing about it is re-authored
 *             here; `overlay` names which one.
 * `modal`   — a dialog this page already owned before `ACC-S14`.
 * `held`    — it cannot act at all and carries its reason (`BR-SHL-025`).
 *
 * ⚠ **`route` IS GONE, AND ITS ABSENCE IS THE DELIVERABLE** (`BR-CUS-1051`, PO
 * 2026-09-13: *"Yes move the eight quick actions over the account"*). It used
 * to mean *"it navigates to a screen that already owns the whole form"*, and
 * after this wave **not one of the thirteen does**: eleven open over the
 * account and two are held. Leaving the variant declared would leave a shape
 * for the next lane to reach for; `opensOverTheAccount` below is the question
 * the ruling actually asks, and the census test counts it.
 */
export type QuickDestination =
  | { kind: "form"; form: QuickForm }
  | { kind: "mounted"; overlay: AccountOverlayId; why: string }
  | { kind: "modal"; why: string }
  | { kind: "held"; why: string };

export interface AccountQuickAction {
  id: AccountQuickActionId;
  /** The figure id on the drawing this was built from — `ACC-Q01`…`ACC-Q13`.
   *  Counted off R4's own captions, never off either of the blueprint's two
   *  disagreeing sentences about how many there are (B14 rule 37). */
  figure: string;
  destination: QuickDestination;
}

// ── ACC-Q03 · Activate account ─────────────────────────────────────────────
//
// **The one this wave opens as a form, and the one that most needed it.**
// Today the header button calls `activate.mutate()` on the click: it commits
// immediately, irreversibly, with no dialog and no way back — which is exactly
// what R4's own caption says (*"the confirmation the product is missing, and it
// names the partial failure BEFORE the click"*) and what its drawn lead line
// says on the form itself.
//
// **What it asks for:** `opened_at`, the one writable field, which the draft
// flow could not set at all before this. **What it shows:** the status it is
// leaving and the plan it will inherit, both read from the account in front of
// the clerk. **What it says it will not do:** the three things the server does
// not manage.
const ACTIVATE_FORM: QuickForm = {
  titleKey: "customers.account.quick.activate.title",
  leadKey: "customers.account.quick.activate.lead",
  sections: [
    {
      headingKey: "customers.account.quick.section.whenServiceStarts",
      fields: [
        {
          // The SERVER'S OWN FIELD NAME. `activate_account` accepts
          // `opened_at`, so the form-state key and the wire key are one string
          // and cannot drift apart.
          id: "opened_at",
          labelKey: "customers.account.quick.activate.openedAt",
          kind: "date",
          required: true,
          helpKey: "customers.account.quick.activate.openedAtHelp",
        },
      ],
    },
    {
      headingKey: "customers.account.quick.section.thePlan",
      fields: [
        {
          // READ-ONLY on purpose, and the helper says why in the drawing's own
          // words: a plan belongs to the UNIT and the account inherits it
          // (BR-CUS-029). There is nothing to pick, so no picker is drawn.
          id: "unit_plan",
          labelKey: "customers.account.quick.activate.unitPlan",
          kind: "readonly",
          helpKey: "customers.account.quick.activate.unitPlanHelp",
        },
      ],
    },
  ],
  recapTitleKey: "customers.account.quick.recap.whatHappens",
  recapRows: [
    { labelKey: "customers.account.quick.recap.statusNow", source: "statusName" },
    {
      labelKey: "customers.account.quick.recap.serviceStarts",
      source: "openedAt",
      fromField: "opened_at",
    },
    { labelKey: "customers.account.quick.recap.plan", source: "unitPlan" },
  ],
  recapOutcome: {
    labelKey: "customers.account.quick.recap.afterThis",
    source: "outcomeSentence",
  },
  caveatHeadingKey: "customers.account.quick.activate.notDoneHeading",
  caveatBulletKeys: [
    "customers.account.quick.activate.noOpeningRead",
    "customers.account.quick.activate.noDeposit",
    "customers.account.quick.activate.noPlanSnapshot",
  ],
  // REUSED, not minted: the header button has carried this label since S21 was
  // built, and two strings for one control is how a product grows two names for
  // one act.
  commitLabelKey: "customers.account.action.activate",
};

// ── ACC-Q07 · Send statement ───────────────────────────────────────────────
//
// **THE ONE THAT HAD REFUSED SINCE THE RAIL WAS DRAWN**, on the sentence
// *"nothing in this product renders a statement"*. The wave that released it
// measured that claim first and it was wrong in the way hard-won law 2
// describes: all three parts existed — the seeded `email_statement` wording,
// `ledger.reporting.account_ledger` since 2026-08-11, and the outbound queue —
// and nothing joined them. `POST /accounts/{id}/statement` joins them now.
//
// **What it asks for is a PERIOD and nothing else**, because that is the only
// thing a statement needs that the books do not already know. `BR-TEN-043`:
// the server has no default and reads no clock, so the two dates are the
// clerk's. Both boxes propose today (the shared form's own behaviour for a
// date field) and the clerk widens them — a proposal they can SEE and change,
// rather than a hidden default that quietly covers the wrong three months.
//
// ⚠ **THE FIELD IDS ARE THE SERVER'S OWN NAMES** — `from` and `to` are what
// the endpoint reads — so the form-state key and the wire key are one string
// and cannot drift apart, exactly as `opened_at` is above.
//
// ⚠ **THE CAVEATS ARE THE HONEST HALF AND NOT DECORATION.** The printed copy
// has no wording on any deployment (`DEF-BIL-5133`), and a statement is not a bill
// (`BR-CUS-040` / A19 rule 1 — *"both the printed statement and the statement
// email must say nothing is due, or customers pay twice"*). Each is said
// BEFORE the click rather than after, which is `BR-SHL-025`'s principle one
// level down. ⚠ There were three until 2026-10-22: *"Nothing is sent this
// release."* was retired (`DEF-NOT-10537`) — the statement's email row sends
// through the utility's Custom SMTP connector.
const STATEMENT_FORM: QuickForm = {
  titleKey: "customers.account.quick.statement.title",
  leadKey: "customers.account.quick.statement.lead",
  sections: [
    {
      headingKey: "customers.account.quick.section.period",
      fields: [
        {
          id: "from",
          labelKey: "customers.account.quick.statement.from",
          kind: "date",
          required: true,
          helpKey: "customers.account.quick.statement.fromHelp",
        },
        {
          id: "to",
          labelKey: "customers.account.quick.statement.to",
          kind: "date",
          required: true,
          helpKey: "customers.account.quick.statement.toHelp",
        },
      ],
    },
  ],
  recapTitleKey: "customers.account.quick.recap.whatHappens",
  // Both rows read the LIVE form state, so moving a date above moves the recap
  // below it. Neither names a `source`: there is no server-side fact behind
  // either one — the clerk is the source (see `QuickRecapRow.source`).
  recapRows: [
    {
      labelKey: "customers.account.quick.recap.statementFrom",
      fromField: "from",
    },
    {
      labelKey: "customers.account.quick.recap.statementTo",
      fromField: "to",
    },
  ],
  caveatHeadingKey: "customers.account.quick.statement.notDoneHeading",
  caveatBulletKeys: [
    "customers.account.quick.statement.noPaperWording",
    "customers.account.quick.statement.notABill",
  ],
  commitLabelKey: "customers.account.quick.statement.commit",
};

/**
 * The thirteen.
 *
 * ⚠ **THE EIGHT `mounted` ENTRIES ARE THE WAVE THE `route` ENTRIES PREDICTED.**
 * Wave J wrote, of the eleven that then navigated away: *"Moving the CONTAINER
 * without copying the FORM is a wave of its own, and this file is what that
 * wave edits: a destination changes, and no form is re-typed."* That is exactly
 * what happened on 2026-09-13 (`BR-CUS-1051`). Each of the eight still names
 * the screen that holds the whole form, with its own tests and its own
 * park-and-resume; what changed is that the screen now renders in a dialog over
 * the account instead of replacing it. **Roughly 7,300 lines of live, tested
 * behaviour were MOUNTED and not one line of it was copied.**
 *
 * ⚠ **THE TWO `held` ENTRIES WERE NOT SWEPT IN, AND THE RULING SAYS SO.**
 * `Adjust` has no adjustment writer in billing and `Send statement` has nothing
 * that renders a statement; a dialog over either would open onto nothing, which
 * is the dead control hard-won law 2 is about. The ruling names EIGHT.
 */
export const ACCOUNT_QUICK_ACTIONS: readonly AccountQuickAction[] = [
  {
    id: "adjust",
    figure: "ACC-Q01",
    // ⚠ A DEAD BUTTON TODAY — `onClick={() => undefined}` on `AccountDetailPage`.
    // There is no adjustment writer anywhere: `services.ACTION_UNAVAILABLE`
    // records that *"billing publishes no writer for it — `apps.billing.services`
    // exports the late fee and nothing else"*. R4 draws the form with its commit
    // disabled; the dead button is `DEF-CUS-5125` and the form is NOT built here, because
    // building it is ~50 catalogue keys in eleven languages and this wave proved
    // the shared form on the action that is actively unsafe instead.
    destination: { kind: "held", why: "no adjustment writer exists in billing" },
  },
  {
    id: "moveOut",
    figure: "ACC-Q02",
    destination: {
      kind: "mounted",
      overlay: "moveOut",
      why: "MoveOutWizard owns the whole six-step form — mounted, never copied",
    },
  },
  { id: "activate", figure: "ACC-Q03", destination: { kind: "form", form: ACTIVATE_FORM } },
  {
    id: "moveIn",
    figure: "ACC-Q04",
    destination: {
      kind: "mounted",
      overlay: "moveIn",
      why: "MoveInWizard owns the whole five-step form — mounted, never copied",
    },
  },
  {
    id: "closeOut",
    figure: "ACC-Q05",
    destination: { kind: "mounted", overlay: "closeOut", why: "CloseOutPage owns the whole form" },
  },
  {
    id: "recordPayment",
    figure: "ACC-Q06",
    destination: { kind: "modal", why: "already a form over the account — RecordPaymentModal" },
  },
  { id: "sendStatement", figure: "ACC-Q07", destination: { kind: "form", form: STATEMENT_FORM } },
  {
    id: "printBill",
    figure: "ACC-Q08",
    // BILL-SCOPED: `BillDocumentPage` reads `useParams().invoiceId`, and WHICH
    // bill is the rail's derivation (the newest ISSUED one), not this file's.
    destination: { kind: "mounted", overlay: "printBill", why: "billing's bill-document screen" },
  },
  {
    id: "issueCredit",
    figure: "ACC-Q09",
    destination: {
      kind: "mounted",
      overlay: "issueCredit",
      why: "billing's fix-a-bill screen owns the credit — a credit is raised ON A BILL",
    },
  },
  {
    id: "changePlan",
    figure: "ACC-Q10",
    destination: {
      kind: "mounted",
      overlay: "changePlan",
      why: "ChangePlanWizard owns the whole three-step form",
    },
  },
  {
    id: "disconnectNotice",
    figure: "ACC-Q11",
    destination: {
      kind: "mounted",
      overlay: "disconnectNotice",
      why: "DisconnectWizard owns the whole five-step form — it SCHEDULES a cut, never performs one",
    },
  },
  {
    id: "paymentPlan",
    figure: "ACC-Q12",
    destination: { kind: "mounted", overlay: "paymentPlan", why: "PaymentPlanWizard owns the whole form" },
  },
  {
    id: "addNote",
    figure: "ACC-Q13",
    destination: { kind: "modal", why: "already a form over the account — the note modal" },
  },
];

/** The configuration for one action, or `undefined` where none is declared. */
export function quickActionFor(id: AccountQuickActionId): AccountQuickAction | undefined {
  return ACCOUNT_QUICK_ACTIONS.find((action) => action.id === id);
}

/**
 * **DOES THIS CONTROL KEEP THE CLERK ON THE ACCOUNT?**
 *
 * The question `BR-CUS-1051` actually asks, and the one finding `F12` measured:
 * before 2026-09-13, **nine of the thirteen took a clerk off the account they
 * were reading**. `accountQuickActions.test.ts` counts this rather than counting
 * a variant name, so the census cannot be satisfied by renaming anything.
 */
export function opensOverTheAccount(id: AccountQuickActionId): boolean {
  const kind = quickActionFor(id)?.destination.kind;
  return kind === "form" || kind === "mounted" || kind === "modal";
}

/** The form an action opens over the account, or `null` when it opens none. */
export function quickFormFor(id: AccountQuickActionId): QuickForm | null {
  const action = quickActionFor(id);
  if (action === undefined || action.destination.kind !== "form") {
    return null;
  }
  return action.destination.form;
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-094-BRC01 step 2 wave J · ACC-S14 (accounts blueprint p208) · R4 p154–174 · 14-ui-conventions.md rules 33, 37, 38
// generated: 2026-09-12 by the CR-094 wave J build lane
// checklist: A✔ B✔ C✔ D✔(POST /accounts/{id}/activate, read from services.activate_account) E✔ F✔ G✔ H=n/a
// gates: tsc · vitest accountQuickActions.test.ts · G13 (the form is rendered by AccountDetailPage, not an unpassed prop)
// exceptions: E3 nine of ACC-Q03's ten drawn fields are NOT built — POST /accounts/{id}/activate refuses every field but `opened_at` and `status` by name, so drawing them would collect values the server rejects (DEF-CUS-5121) · E3 `Base charge` and `Billing cycle` are not drawn even read-only, because AccountUnitPlan carries neither and AccountDetail carries no cycle · E3 eleven of the thirteen keep their existing destination this wave — see the comment on ACCOUNT_QUICK_ACTIONS
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
