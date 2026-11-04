// ── Trace ──────────────────────────────────────────────
// Change:   CR-035 step 6 part 2/3 — the typed client for the parked-draft
//           store. The backend half (`POST/GET/PATCH/DELETE /wizard-parks`) is
//           lane PARKSVC's; this file is the ONE place this app speaks to it.
// Rules:    BR-SHL-048 (a parked wizard changes nothing until it is executed —
//           PO 2026-08-26, verbatim: *"Option A - Unitl move in executed, no
//           records updates."*) · BR-SHL-047 (every wizard parks) · B19 §12.2
//           (`Save & exit` and `Park` are TWO controls) · CLAUDE.md hard rule 1
//           (the tenant rides in the path the client builds, never in a body)
// Design:   12-governance/11-change-requests.md → CR-035 step 6 table
// Tests:    wizardPark.dom.test.tsx · WaitingOnTab.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// 1 · WHY THERE IS NO FOREIGN KEY IN THIS PAYLOAD, AND WHY THAT IS THE RULE
// ══════════════════════════════════════════════════════════════════════════
// BR-SHL-048 (a): *"A parked draft carries NO FOREIGN KEY to the record it is
// about. An FK is a relationship, and the ruling says there is none until
// execution."* So `subject_ref` below is a **copied value** — the unit id or
// account id the clerk had chosen, carried so the wizard can re-look-it-up on
// resume — and `subject_label` is the words the clerk will recognise in the
// list. Neither is a join. Deleting the unit named in `subject_ref` must not be
// blocked by this row, and no ageing bucket, occupancy query or report may
// reach a parked draft by joining to it.
//
// ⚠ **AND THAT IS WHY THIS FILE HAS NO `resolve`, NO `expand` AND NO ENRICHED
// ROW.** A list cell that showed "Unit 12 · Vacant" would be a join in the
// frontend wearing a different hat: it would make the rest of the product speak
// about a parked draft, which is exactly the surface the ruling closed. The
// list renders what the DRAFT recorded, and nothing else.
//
// ══════════════════════════════════════════════════════════════════════════
// 2 · `values` IS OPAQUE HERE ON PURPOSE
// ══════════════════════════════════════════════════════════════════════════
// Five flows park, and each one's typed form is a different shape. Declaring a
// union of five drafts in the transport would put a second opinion about each
// wizard's state in the client — and it would go stale the first time a wizard
// grew a field, silently, because a wider `values` still parses. So the wire
// type is `Record<string, unknown>` and **each wizard owns the narrowing**, in
// its own `hydrate`, where a missing or wrong-typed field is one screen's
// problem and not the transport's.
//
// ⚠ **A DRAFT IS NEVER TRUSTED ON THE WAY BACK IN (BR-SHL-048 (b)).** Nothing
// in this file validates a draft into correctness, and nothing may: *"everything
// in it was true on 26 August; by 2 September the unit may be taken, the plan
// may have a new version, the deposit rule may have changed."* Hydration puts
// the typed values back in the FORM; the wizard's own checks then run again
// from step 1, exactly as if a clerk had typed them a moment ago.
import { api } from "@/api/client";
import type { ApiClient, ApiResponse } from "@/api/client";

/** A 2xx with no body where the contract promises one is a server bug (B12 r1).
 *  Restated locally rather than imported, on `serviceRequestEndpoints`' own
 *  rule — this file adds no coupling to `endpoints.ts`, which several lanes
 *  edit. */
function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

// ══════════════════════════════════════════════════════════════════════════
// THE VOCABULARY — five flows, and it is CLOSED
// ══════════════════════════════════════════════════════════════════════════

/**
 * The five wizards CR-035 §3 measured as carrying the control with no store:
 * Move-in, Move-out, Transfer, Disconnect, New connect.
 *
 * ⚠ **SERVICE REQUESTS ARE NOT IN THIS LIST AND MUST NOT JOIN IT.** A service
 * request already parks — `park()` / `unpark()` in `service_request_service.py`,
 * with `waiting_on`, `park_note`, `remind_on`, `parked_at` and `parked_by` as
 * columns on `customers.ServiceRequest` — because it is ALREADY A SAVED,
 * NUMBERED ROW. Parking one moves its own state; parking a wizard writes a
 * draft that is not a record at all. Folding the two together is Option B, the
 * shape the PO was shown (*"the draft becomes a numbered service request
 * SR-26-0043"*) and did not choose.
 */
export const WIZARD_PARK_FLOWS = [
  "move_in",
  "move_out",
  "transfer",
  "disconnect",
  "new_connect",
] as const;

export type WizardParkFlow = (typeof WIZARD_PARK_FLOWS)[number];

export function isWizardParkFlow(value: string): value is WizardParkFlow {
  return (WIZARD_PARK_FLOWS as readonly string[]).includes(value);
}

/**
 * The flow's name in words, as ONE literal catalogue key per flow.
 *
 * A template key (`customers.waitingOn.flow.${flow}`) renders identically and is
 * INVISIBLE to G18, which matches literal dotted strings — all five would report
 * as dead catalogue entries the day they are translated. `WIZARD_PARK_REASON_COPY`
 * in `WizardFrame.tsx` is written this way for exactly this reason and says so.
 */
export const WIZARD_PARK_FLOW_COPY: { flow: WizardParkFlow; key: string; en: string }[] = [
  { flow: "move_in", key: "customers.waitingOn.flow.moveIn", en: "Move-in" },
  { flow: "move_out", key: "customers.waitingOn.flow.moveOut", en: "Move-out" },
  { flow: "transfer", key: "customers.waitingOn.flow.transfer", en: "Transfer" },
  { flow: "disconnect", key: "customers.waitingOn.flow.disconnect", en: "Disconnect" },
  { flow: "new_connect", key: "customers.waitingOn.flow.newConnect", en: "New connect" },
];

// ══════════════════════════════════════════════════════════════════════════
// THE ROW
// ══════════════════════════════════════════════════════════════════════════

/**
 * The COPIED ids a draft names — **a JSON OBJECT, and never a bare string.**
 *
 * ⚠ **THIS FIELD WAS TYPED `string | null` FOR HALF A DAY AND WOULD HAVE 422'd
 * EVERY SINGLE PARK.** `wizard_parks._clean_json_object` refuses a non-dict with
 * `VAL-002`, and the shape of that failure is the one worth remembering: **the
 * button acts, the panel submits, nothing is saved, and a unit suite that mocks
 * its own response shape stays green all the way through.** No test written
 * against a fixture the author invented can see it — only a fixture copied from
 * what the service really answers can. The fixtures in
 * `wizardPark.dom.test.tsx` and `WaitingOnTab.dom.test.tsx` are now that.
 *
 * ⚠ **AND IT IS STILL NOT A FOREIGN KEY (BR-SHL-048 (a)).** An object with a
 * `unit_id` in it is a COPIED VALUE: the wizard looks it up AGAIN on resume, and
 * *"deleting a unit cannot be blocked by a forgotten draft."* The service says
 * the same in its own words — *"it resolves nothing"*.
 *
 * The two members are the two a wizard has. It stays open at the edges because
 * `values` and `subject_ref` are both handed back verbatim by the service, and a
 * closed shape here would silently drop a key a later flow adds.
 */
export interface WizardParkSubjectRef {
  unit_id?: string | null;
  account_id?: string | null;
  premises_id?: string | null;
  /**
   * **`BR-SHL-048 (d)` (PO 2026-09-21) — the BUILD a New Connect wizard is
   * finishing**, where an approval raised one before the wizard opened.
   *
   * ⚠ **IT IS STILL A COPIED VALUE AND STILL NOT A FOREIGN KEY.** The clause
   * that adds it says so itself: clause (a) is *the fix rather than the
   * obstacle*. `connection_id` is what the last press sends as
   * `connection_id`, so the commit FINISHES that build instead of minting a
   * second one beside it; `connection_no` is what the server takes as the
   * draft's `reference`, so the row a parked wizard leaves on the New connects
   * tab names its build rather than nothing at all.
   *
   * Both absent on a New Connect started from SCRATCH — there is no build to
   * name, `BR-MET-112` is unchanged, and the park holds `{}` exactly as it did.
   */
  connection_id?: string | null;
  connection_no?: string | null;
}

/**
 * One parked draft, as `GET /wizard-parks` serves it.
 *
 * ⚠ **`age_days` IS THE SERVER'S AND IS NOT DECORATION.** The CR-035 ruling
 * states it plainly: *"The remind-on date and the visible age on the 'Waiting
 * on' list are the only thing stopping a draft sitting forever."* It is read
 * from the payload rather than computed here for the same reason every other
 * derived figure in this product is: the browser's clock is the user's, and two
 * clerks in two time zones must not read different ages off the same row.
 * `parkAgeDays` on the frame is the WIZARD's own age, computed from
 * `parked_at` while the clerk is standing in the flow; this is the LIST's.
 */
export interface WizardParkRow {
  id: string;
  flow: WizardParkFlow;
  /** The words a clerk recognises — "Unit 12, 500 Main St". A COPIED string. */
  subject_label: string;
  /** COPIED ids, NOT a join. `null` on the wire arrives back as `{}`. */
  subject_ref: WizardParkSubjectRef;
  /** BR-SHL-046's index into the flow's ONE declared step list. */
  step: number;
  /** What was typed. Opaque here; each wizard narrows its own. See §2. */
  values: Record<string, unknown>;
  /** `CR-122-BRC06` — `MVI-{YY}-{0000}`, the reference a clerk quotes while the
   *  job is still in their hands, and the one the finished `move_records` row
   *  is filed under. **NULL is a real answer**: the four other flows allocate
   *  none, and a tenant with no `move_in` series gets a draft without one
   *  rather than no draft. A screen prints what is there and never a dash it
   *  invented. */
  reference?: string | null;
  /** `CR-122-BRC06` — TRUE when nobody chose a reason, i.e. this row came from
   *  the wizard keeping the typing rather than from a clerk pressing `Park`.
   *  ⚠ **Read THIS, never `waiting_on === ""`** — the server owns the
   *  distinction and a screen that re-derived it would be a second copy free
   *  to disagree. */
  is_draft?: boolean;
  /**
   * ⚠ **FREE TEXT, NOT A CLOSED UNION, AND THAT IS DELIBERATE ON BOTH SIDES.**
   * The nine reasons are what the SCREEN offers (B18 §4.2's closed list, in
   * `WIZARD_PARK_REASON_COPY`); the COLUMN matches `customers.ServiceRequest.
   * waiting_on` so one "Waiting on" list can one day carry both kinds of parked
   * work. A `WizardParkReason` union here would make TypeScript reject a value
   * the server happily stored — the client refusing the server's own data.
   * `waitingOnLabel` renders an unknown code as itself rather than inventing
   * English for it.
   */
  waiting_on: string;
  park_note: string | null;
  remind_on: string | null;
  /** ISO instant. `null` only if the row has none, which the service allows for. */
  parked_at: string | null;
  parked_by: string | null;
  parked_by_name: string | null;
  /** The SERVER's figure. `null` when `parked_at` is — never a browser clock. */
  age_days: number | null;
}

/** The list envelope — DRF pagination, measured against `wizard_parks_api`
 *  (`paginator.get_paginated_response`). `listWizardParks` still normalises a
 *  bare array, because a normaliser that has been proved unnecessary costs
 *  nothing and a screen that blanks on an envelope change costs a support call. */
export interface WizardParkList {
  count: number;
  next?: string | null;
  previous?: string | null;
  results: WizardParkRow[];
}

/** `POST /wizard-parks` — every field the create reads. */
export interface WizardParkBody {
  flow: WizardParkFlow;
  subject_label: string;
  subject_ref: WizardParkSubjectRef;
  step: number;
  values: Record<string, unknown>;
  waiting_on: string;
  park_note?: string | null;
  remind_on?: string | null;
}

/**
 * `PATCH /wizard-parks/{id}` — **FIVE FIELDS, and the two that are missing are
 * missing on purpose.**
 *
 * `update_park`'s own words: *"`flow` and `subject_ref` do not [move], and that
 * is deliberate — a draft that changed which flow it was, or which unit it
 * named, would be a different draft wearing the same id, and the 'Waiting on'
 * list would silently rewrite its own history."* `subject_label` is not in its
 * five either. The service simply ignores keys it does not read, so sending the
 * whole create body would have worked and would have been a lie in the type:
 * a caller would believe they had moved a subject that never moved.
 */
export interface WizardParkPatch {
  step?: number;
  values?: Record<string, unknown>;
  /** `CR-122-BRC06` — the subject follows the clerk **while the row is still a
   *  draft** and freezes the moment it is parked. The server enforces that;
   *  these two are here so an autosave can keep a draft created at wizard-open
   *  from being stuck with the empty label it was born with. */
  subject_label?: string;
  subject_ref?: WizardParkSubjectRef;
  waiting_on?: string;
  park_note?: string | null;
  remind_on?: string | null;
}

// ══════════════════════════════════════════════════════════════════════════
// THE CALLS
// ══════════════════════════════════════════════════════════════════════════

export interface WizardParkQuery {
  flow?: WizardParkFlow;
  /** `?mine=` — the clerk's OWN parked work, which is the surface BR-SHL-048
   *  names: *"the parked work appears in the clerk's own 'Waiting on' list"*. */
  mine?: boolean;
}

/**
 * `GET /wizard-parks` — newest first, each row with its `age_days`.
 *
 * ⚠ **A BARE ARRAY IS ACCEPTED AND NORMALISED, AND THAT IS A CONTRACT
 * QUESTION, NOT A PREFERENCE.** The CR-035 contract says *"list, newest first"*
 * without naming an envelope, and this codebase serves two (`{count, results}`
 * and `{total, rows}`). Rather than guess one and blank the tab if the other
 * arrives, this reads both and reports the ambiguity upward. It invents no
 * ordering: whatever order the server sent is the order rendered.
 */
export async function listWizardParks(
  query: WizardParkQuery = {},
  client: ApiClient = api,
): Promise<WizardParkList> {
  const payload = requireData(
    await client.get<WizardParkList | WizardParkRow[]>("/wizard-parks", {
      query: {
        flow: query.flow,
        mine: query.mine === undefined ? undefined : query.mine ? "1" : "0",
      },
    }),
  );
  if (Array.isArray(payload)) {
    return { count: payload.length, results: payload };
  }
  return payload;
}

/** `POST /wizard-parks` — park a flow that has never been parked. */
export async function createWizardPark(
  body: WizardParkBody,
  client: ApiClient = api,
): Promise<WizardParkRow> {
  return requireData(await client.post<WizardParkRow>("/wizard-parks", body));
}

/**
 * `GET /wizard-parks/{id}` — the row, for resume.
 *
 * This is the ONLY read a resuming wizard makes of the store. Everything else
 * it needs (the unit, the account, the plan) it re-reads from the product,
 * because BR-SHL-048 (b) says the draft is not evidence about any of them.
 */
export async function getWizardPark(
  id: string,
  client: ApiClient = api,
): Promise<WizardParkRow> {
  return requireData(
    await client.get<WizardParkRow>(`/wizard-parks/${encodeURIComponent(id)}`),
  );
}

/** `PATCH /wizard-parks/{id}` — re-park a draft that was resumed and parked
 *  again. Not an execution: still nothing outside this table changes. */
export async function patchWizardPark(
  id: string,
  body: WizardParkPatch,
  client: ApiClient = api,
): Promise<WizardParkRow> {
  return requireData(
    await client.patch<WizardParkRow>(`/wizard-parks/${encodeURIComponent(id)}`, body),
  );
}

/**
 * `DELETE /wizard-parks/{id}` — discard.
 *
 * ⚠ **A DISCARD IS NOT A FINANCIAL DELETE AND HARD RULE 4 DOES NOT REACH IT.**
 * That rule forbids UPDATE/DELETE on issued invoices, invoice lines, payments
 * and journal entries. A parked draft is none of those and, by BR-SHL-048, is
 * not a record of anything at all — it is a saved form. Discarding one is the
 * clerk throwing away their own unfinished typing, and there is nothing for a
 * correcting row to correct.
 */
export async function discardWizardPark(id: string, client: ApiClient = api): Promise<void> {
  await client.del<null>(`/wizard-parks/${encodeURIComponent(id)}`);
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-035 (11-change-requests.md) · 02-decision-log.md 2026-08-26 ·
//         BR-SHL-048 · BR-SHL-047 · BR-SHL-046 · B19 §12.2 · B18 §4.2
// generated: 2026-08-26 by lane PARKUI (the frontend half of CR-035)
// checklist: A=n/a(backend half is lane PARKSVC) B✔ C✔ D✔ E✔ F✔ G✔
//         H=deferred(PO 2026-08-09)
// exceptions: E3 the list envelope is READ BOTH WAYS — the CR-035 contract says
//         "list" and names no envelope, and this repo serves two; REPORTED
//         upward as a contract question rather than settled here · E3 `values`
//         is `Record<string, unknown>` and each wizard narrows its own (see §2)
//         · E3 no story owns the "Waiting on" surface (hard-won law 8) — OWED
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
