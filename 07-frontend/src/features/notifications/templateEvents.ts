// ── Trace ──────────────────────────────────────────────
// Change:  CR-048 wave E · E7 — "Group the template list by event — the codes
//          already carry the channel. No schema change, no migration."
// Screens: SET-09 (the template catalog) · SET-10 (the designer's surface
//          switcher, E5, which is the same relationship read the other way)
// Rules:   BR-SHL-010 (an undeclared capability is not rendered) · B14 rule 20
//          (one table type — this derives ROWS, it does not draw a table)
// ───────────────────────────────────────────────────────
// ONE EVENT, SEVERAL SURFACES — DERIVED, BECAUSE THE SERVER DOES NOT SERVE IT.
//
// ── THE COMPLAINT ─────────────────────────────────────────────────────────
// SET-09 lists 37 rows because **every channel is its own row**. *"Bill ready ·
// e-bill email"* and *"Bill ready · SMS"* sit apart as though they were
// unrelated documents. They are one EVENT on two SURFACES.
//
// ── ⚠ WHAT THE PAYLOAD DOES NOT CARRY, AND WHY THIS IS DERIVATION ─────────
// **`TemplateCatalogRow` has no event field.** It carries `group` and
// `channel`, and `apps/notifications/catalogs.py` is explicit that neither is
// the event:
//
//     "⚠ THIS IS NOT `category`. `group` is the CHANNEL family (printable /
//      email / sms / contracts) and answers *what kind of artifact is this*;
//      `category` answers *what part of the business sends it*."
//
// The event key DOES exist on the server — `rule_catalog.EventClass.key`, with
// `template_classes={E: "email_bill_ready", S: "sms_bill_ready"}` — and it is
// **not on this endpoint**. Reading it would mean a second request into the
// notification-rules contract, which is another screen's payload and another
// lane's file. So it is not read, and it is not invented as a field either.
//
// **What IS in hand is the NAME**, and the seeded names already write the
// relationship out in full: `<event> · <surface>`. That is not a coincidence of
// copy — it is the shape CR-048 E7 itself quotes when it names the problem, and
// it is how all 37 rows are seeded in `catalogs.py`. Deriving from it is a
// regrouping of rows that already know their event and their surface, with no
// schema change and no migration, which is exactly the task.
//
// ── ⚠ THE LIMIT OF THAT DERIVATION, STATED (hard-won law 1) ───────────────
// A name is COPY. If somebody renames *"Bill ready · SMS"* to *"SMS: bill
// ready"* the two rows stop grouping, and nothing here will complain — the list
// simply returns to the flat drawing it has today. That is the failure mode
// chosen on purpose: **the fallback of a wrong derivation is the OLD screen,
// never a wrong grouping.** A separator that appears in a name for some other
// reason produces a group of one, which `EventRun.count === 1` draws exactly as
// an ungrouped row.
//
// ── ⚠ THE DURABLE FIX IS A SERVER FIELD, AND IT IS NOT MINTED HERE ────────
// What would replace this file is an `event` key on the catalog row, sourced
// from `rule_catalog.EventClass.key`. **That question is NOT carried as an
// OQ-ID in this docstring, deliberately.** This lane's territory is the
// notifications feature files and the locale catalogues; it does not include
// `12-governance/01-open-questions.md`, and an id written here that no register
// row answers to is the dangling-citation shape DEF-524 records — a reference
// that outlives, or in this case PRE-dates, the thing it names.
//
// So the question is stated in full and left for the lane that owns the
// register to allocate: **which of the 37 template classes belongs to which
// event?** It is a product statement and not a derivation — `rule_catalog`
// gives an entry to ten classes and NONE to the other twenty-seven, and three
// of the five multi-row families this file groups (*"Payment receipt"*,
// *"Payment plan"*, and the printable *"Past-due reminder"*) have no event
// entry at all. The prime directive forbids answering it here, and this file
// does not: it groups by the name and says so.

/** The separator the seeded names use between an event and its surface.
 *
 *  A MIDDLE DOT with a space each side, which is this product's separator
 *  everywhere — the same one `templates.detail.sampleDataIs` and the version
 *  trail write. It is matched with its spaces so a name containing a bare `·`
 *  for some other reason is not split at it. */
export const SURFACE_SEPARATOR = " · ";

/** The EVENT a row belongs to: everything before the FIRST separator.
 *
 *  First and not last: *"Disconnect notice · 10-day warning"* has one
 *  separator, but a name with two would still belong to the event its FIRST
 *  segment names — the segments narrow, they do not re-parent. */
export function templateEvent(name: string): string {
  const at = name.indexOf(SURFACE_SEPARATOR);
  return at === -1 ? name : name.slice(0, at);
}

/** The SURFACE, or `null` when the template is its own event.
 *
 *  `null` and not `""`, and not the row's `kind` either: a row with no
 *  separator has not told us which surface it is, and answering with the kind
 *  would be this screen composing a fact the data does not state. The name
 *  carries it or nothing does. */
export function templateSurface(name: string): string | null {
  const at = name.indexOf(SURFACE_SEPARATOR);
  return at === -1 ? null : name.slice(at + SURFACE_SEPARATOR.length);
}

/** What the grouping knows about ONE row, once its neighbours are read. */
export interface EventRun {
  /** The event this row belongs to. */
  event: string;
  /** This row's surface, or `null` when the template is its own event. */
  surface: string | null;
  /** True on the FIRST row of a contiguous run — the row that carries the
   *  heading. A heading on every row is the flat list with extra ink. */
  leads: boolean;
  /** How many rows on THIS PAGE share the event. `1` for an ungrouped row. */
  count: number;
}

/**
 * Read a page of rows as runs.
 *
 * ⚠ **CONTIGUITY IS THE WHOLE CONTRACT, AND IT IS A PROPERTY OF THE SORT.**
 * This walks the rows IN THE ORDER GIVEN and only ever joins ADJACENT ones. It
 * deliberately does NOT gather scattered rows under one heading: a heading
 * drawn over rows that are not next to each other states something false about
 * the list, and the caller cannot see that from a `Map` keyed by event.
 *
 * So two rows of one event that are separated by a third event's row are two
 * runs of one, and each draws as an ordinary ungrouped row. The caller is what
 * decides whether the current sort can produce contiguity at all — see
 * `TemplateCatalog.tsx`, which falls back to the plain name under any sort but
 * `name`.
 *
 * Pure and index-keyed so it is provable without a DOM, which is the only way
 * the contiguity rule can be pinned by a test that goes red if somebody
 * "improves" it into a global group-by.
 */
export function eventRuns(rows: readonly { name: string }[]): EventRun[] {
  // Pass one: how long is each contiguous run, and where does it start.
  const leadOf: number[] = [];
  const lengths: number[] = [];
  for (let i = 0; i < rows.length; i += 1) {
    const event = templateEvent(rows[i].name);
    if (i > 0 && templateEvent(rows[i - 1].name) === event) {
      leadOf[i] = leadOf[i - 1];
      lengths[leadOf[i]] += 1;
    } else {
      leadOf[i] = i;
      lengths[i] = 1;
    }
  }
  // Pass two: hand every row its run's total, not just the count so far.
  return rows.map((row, i) => ({
    event: templateEvent(row.name),
    surface: templateSurface(row.name),
    leads: leadOf[i] === i,
    count: lengths[leadOf[i]],
  }));
}

/**
 * The SIBLING SURFACES of one template — E5's channel switcher, read from the
 * same derivation.
 *
 * *"One notice, four surfaces; switching changes both the rail and the page."*
 * The detail payload carries no sibling list, so the switcher is built from the
 * catalog page the list already holds and hands down. Rows are returned in the
 * order they arrive, INCLUDING the current one, so the switcher can mark which
 * surface is open without a second lookup.
 *
 * Order is NOT sorted here: the caller's page order is the server's `name`
 * order, which is the order a person just read the list in.
 */
export function siblingSurfaces<T extends { code: string; name: string }>(
  rows: readonly T[],
  code: string,
): T[] {
  const self = rows.find((row) => row.code === code);
  if (self === undefined) {
    return [];
  }
  const event = templateEvent(self.name);
  const siblings = rows.filter((row) => templateEvent(row.name) === event);
  // A template that is its own event has no switcher to draw — one tab is a
  // control that cannot do anything, which BR-SHL-010 does not render.
  return siblings.length > 1 ? siblings : [];
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-048 wave E task E7 (12-governance/11-change-requests.md CR-048
//         step 5, WAVE E) · apps/notifications/catalogs.py (the 37 seeded
//         names) · apps/notifications/rule_catalog.py (EventClass.key, which is
//         the durable source this file is standing in for)
// generated: 2026-08-30 by the CR-048 wave E designer lane
// gates: tsc✔ · vitest templateEvents.test.ts (pure) +
//        templateCatalogGrouping.dom.test.tsx (rendered), RED-proved first
// exceptions: (1) THE EVENT IS DERIVED FROM COPY, and the fallback of a wrong
//         derivation is the OLD flat screen rather than a wrong grouping. The
//         open question — which class belongs to which event — is stated in the
//         module note above and left UNNUMBERED for the lane that owns
//         `12-governance/01-open-questions.md` to allocate.
//         (2) CONTIGUOUS RUNS ONLY — never a global group-by, because the list
//         is server-sorted and server-paged and this file can see neither.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
