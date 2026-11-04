// ── Trace ──────────────────────────────────────────────
// Change:   CR-094 wave 2 lane J — step 7 (`Telling the customer`) and step 8's
//           two owed blocks (`From each step`, `What happens next`), both built
//           from `05-prototype/02 Accounts Menu Blueprint.pdf` p091–p093 read AS
//           IMAGES at scale 2 (B14 rule 42).
// Rules:    PO ruling 2026-09-16 (three messages, not the drawn six) ·
//           BR-NOT-013 (nothing is sent) · BR-NOT-002 (a contract version is
//           effective-dated and cannot be seeded) · BR-SHL-025 (a control that
//           cannot act is DISABLED) · B14 rules 31, 33, 37
// Questions: ⛔ OQ-376 · ⛔ OQ-379
// ───────────────────────────────────────────────────────
//
// ⚠ **WHAT WOULD MAKE THESE PASS WRONGLY — the question hard-won law 7 says to
// ask of every check, because a check you cannot describe a false pass for is a
// check you do not understand.**
//
//   · A `toContain` over a rendered string passes on ANY occurrence, so the
//     "three messages and not six" case asserts the dropped three are ABSENT by
//     name as well as the kept three present. Presence alone would pass over a
//     screen showing all six.
//   · The rule-33 case counts words in the CELLS it parses out of the markup.
//     If the parse found nothing it would pass over an empty list, so it pins
//     the row count first and fails when the table is not seven rows.
//   · The hold cases assert each refusal BY ITS REASON rather than by "some
//     refusal is present" — so the day `OQ-376` closes and the reason stops
//     being true, this file goes red and NAMES it. A hold with no such test is
//     a promise nobody is keeping (`DEF-CWP-3925`).
//   · The components are mounted under the REAL `/:tenant/connections/new`
//     route. A bare `MemoryRouter` leaves `useParams().tenant` undefined and
//     every address the page builds comes out protocol-relative, which reads as
//     a perfectly good string to `toContain` — that cost the customer portal six
//     of its eight front-page doors.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";
import i18next from "i18next";

import "@/i18n";

import { ToastProvider } from "@/components/Toast";

import { MessagesFold, WhoWeAreTelling } from "./NewConnectCommunicationStep";
import type { ConnectTemplateChoices } from "./newConnectEndpoints";
import { ReviewStep } from "./NewConnectReviewStep";
import { emptyDraft, draftManifest } from "./newConnectDraft";
import type { NewConnectDraft } from "./newConnectDraft";

const TEST_TENANT = "brazosbend";

const t = (key: string, options?: Record<string, unknown>) => String(i18next.t(key, options));

/** The build p092 draws, in the two fields these two steps read back. */
function drawnDraft(over: Partial<NewConnectDraft> = {}): NewConnectDraft {
  const base = emptyDraft();
  return {
    ...base,
    owner: {
      ...base.owner,
      name: "Balcones Development LLC",
      email: "ops@balconesdev.example",
      phone: "(512) 555-0199",
      partyKind: "company",
    },
    premise: {
      ...base.premise,
      address: "212 Balcones Drive",
      parcelRef: "R-0044-1189",
      readRoute: "Route 4 · North",
    },
    pattern: { ...base.pattern, prefix: "Apt", from: "101", to: "106", includeCommonArea: true },
    premiseServices: ["electric", "water", "sewer"],
    apartmentServices: ["electric", "water", "sewer"],
    commonAreaServices: ["electric", "water"],
    ...over,
  };
}

/**
 * The rows `GET /connections/message-templates` really returns for a seeded
 * utility, PLUS a draft — measured against real PostgreSQL in
 * `06-backend/tests/test_new_connect_step7_picker_door.py`, which pins the two
 * published rows and the contract's absence.
 */
const PICKER_ROWS: ConnectTemplateChoices = {
  rows: [
    {
      code: "new_connect_confirmed",
      name: "New connect — confirmed",
      group: "email",
      channel: "email",
      category: "default",
      language: "default",
      version: 1,
      status: "published",
      pickable: true,
    },
    {
      code: "new_connect_quote",
      name: "Connection quote",
      group: "email",
      channel: "email",
      category: "default",
      language: "default",
      version: 1,
      status: "published",
      pickable: true,
    },
    {
      code: "new_connect_quote",
      name: "Connection quote — Spanish",
      group: "email",
      channel: "email",
      category: "default",
      language: "es",
      version: 1,
      status: "draft",
      pickable: false,
    },
  ],
  unavailable: [],
};

function render(node: React.ReactNode, seed?: ConnectTemplateChoices): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  if (seed !== undefined) {
    queryClient.setQueryData(["connect-message-templates", ""], seed);
  }
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/connections/new?step=7`]}>
          <Routes>
            <Route path="/:tenant/connections/new" element={<>{node}</>} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

function renderStep7(
  seed: ConnectTemplateChoices = PICKER_ROWS,
  over: Partial<NewConnectDraft> = {},
): string {
  // `DEF-GOV-10106` (closing `DEF-CUS-7626`): the `CommunicationStep` wrapper
  // is deleted, so these cases mount the two parts Review renders directly —
  // exactly what the note below promised would be the only change.
  const draft = { ...drawnDraft(), ...over };
  return render(
    <>
      <WhoWeAreTelling draft={draft} t={t} />
      <MessagesFold draft={draft} onPatch={() => undefined} t={t} />
    </>,
    seed,
  );
}

function renderStep8(
  draft: NewConnectDraft = drawnDraft(),
  quote: { total: string | null; currency: string | null } = { total: null, currency: null },
): string {
  return render(
    <ReviewStep
      draft={draft}
      manifest={draftManifest(draft, null)}
      // ⊕ 2026-09-28 — the server's 4-decimal figure and its CHAR(3), which
      // `ReviewStep` now needs so the One-time charges row can go through
      // `MoneyCell` instead of printing `1035.00` raw. Both are REQUIRED
      // props: an optional currency nothing passes is the bare number back.
      quoteTotal={quote.total}
      quoteCurrency={quote.currency}
      workOrderCount={2}
      onPatch={() => undefined}
      t={t}
    />,
  );
}

// ══════════════════════════════════════════════════════════════════════════
// STEP 7 — TELLING THE CUSTOMER
// ══════════════════════════════════════════════════════════════════════════

// ══════════════════════════════════════════════════════════════════════════
// THE MESSAGES TABLE — step 7's content, now FOLDED INTO REVIEW
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **THESE MOUNT `WhoWeAreTelling` AND `MessagesFold` DIRECTLY** — the two
// parts Review renders, so they test the components a clerk actually meets.
// They went through a `CommunicationStep` wrapper until it was deleted
// (`DEF-CUS-7626`, `DEF-GOV-10106`).
//
// ⚠ **TWO CASES ARE GONE AND THEIR ABSENCE IS DELIBERATE.** *"holds every
// tick DISABLED, because nothing the clerk chose could travel"* asserted a
// claim that was FALSE when it was written: `commit_connection` has always
// passed `data["messages"]` into `queue_on_commit`, whose own docstring calls
// it *"the clerk's ticks and their template picks"*. The DOOR was open and the
// WIRE was missing. The reversal is argued in §1 of
// `NewConnectCommunicationStep.tsx` and in the decision log of 2026-09-29, and
// the new behaviour — a removed row travels as `messages.send` — is asserted
// in `NewConnectRedesignSteps45.dom.test.tsx`.
//
// ⚠ **AND ONE THING THIS HARNESS CANNOT SEE ANY MORE.** The template PICKER is
// behind `+ Add template` now, so `renderToStaticMarkup` — which cannot press
// anything — never renders its six columns or its `data-would-use` marks.
// That is a real blind spot and it is NOT left unnamed: the browser walk
// `10-scripts/nct_steps45_walkthrough.mjs` presses the button and fails when
// the picker does not open. A blind spot with no number beside it is
// indistinguishable from an empty one (hard-won law 7).

describe("the messages table · what goes out", () => {
  it("draws the PO's three messages and not the drawn six", () => {
    const html = renderStep7();
    // Present, in the ruling's order (the build exists, the contract, the cost).
    expect(html).toContain('data-cell="message-build_created"');
    expect(html).toContain('data-cell="message-contract"');
    expect(html).toContain('data-cell="message-quote_and_what_is_owed"');
    // ⚠ **COUNTED ON THE STATE CELL, NOT ON `message-`.** The first draft of
    // this line matched `data-cell="message-[a-z_]+"` and got NINE: the TO and
    // WHEN columns are `message-to` and `message-when`, so the pattern counted
    // three columns across three rows and read as three times too many rows.
    // It failed loudly, which is the only reason it was seen — a looser
    // pattern would have passed over a six-row table. One STATE cell per
    // occasion is one row per occasion.
    expect(html.match(/data-cell="state-[a-z_]+"/g)).toHaveLength(3);
    // ⚠ ABSENT BY NAME — presence alone would pass over a screen drawing six.
    // *"all these 6-8 line items are not required"* (PO 2026-09-16).
    expect(html).not.toContain("Schedule of works");
    expect(html).not.toContain("Inspection booked");
    expect(html).not.toContain("Welcome pack");
    // ⚠ `Unit energised` is NOT among the dropped — BR-MET-115 moved it to the
    // work-order screen — but it is not drawn HERE, because this table is what
    // happens ON COMMIT and it fires as each unit activates.
    expect(html).not.toContain("Unit energised");
  });

  it("says nothing is sent ON EVERY ROW, and never in a strip above them", () => {
    // The red strip was deleted on 2026-09-28 (B14 rule 33 — it explained how
    // the product behaves rather than refusing anything). **THE FACT IT
    // GUARDED HAS NOT MOVED**: every row still carries its own stop reason, so
    // a screen that quietly started queueing still goes red here.
    const html = renderStep7();
    expect(html).not.toContain("Everything is queued. Nothing is sent.");
    for (const code of ["build_created", "contract", "quote_and_what_is_owed"]) {
      const from = html.indexOf(`data-cell="state-${code}"`);
      expect(from, `row ${code} has a State cell`).toBeGreaterThan(-1);
      const cell = html.slice(from, html.indexOf("</td>", from));
      // ⊕ `CR-164-BRC10` (PO Q8, item 31) — each row says what will happen to
      // it: *Sent on approval* where a template exists, *Not sent* where none.
      expect(cell, `row ${code} states what happens to it`).toMatch(
        /data-message-state="(on-approval|no-template)">[^<]+</,
      );
    }
  });

  it("says which messages go on approval and which have no template", () => {
    // ⊕ `CR-164-BRC10` — the contract has no published template in this
    // fixture, so it is *Not sent*; the two with a version go on approval.
    const html = renderStep7();
    const state = (code: string) => {
      const from = html.indexOf(`data-cell="state-${code}"`);
      return html.slice(from, html.indexOf("</td>", from));
    };
    expect(state("build_created")).toContain('data-message-state="on-approval"');
    expect(state("contract")).toContain('data-message-state="no-template"');
    expect(html).not.toContain("On commit");
  });

  it("offers a draft version and refuses it, rather than hiding it", () => {
    const html = renderStep7();
    // p091: hiding it sends a clerk looking for something they can see exists;
    // offering it would queue a letter nobody has approved. The TEMPLATE cell
    // is a chooser now, so *cannot be used* is a `disabled` option rather than
    // a marker in a picker column.
    expect(html).toContain("Connection quote — Spanish");
    expect(html).toMatch(/<option [^>]*disabled[^>]*>Connection quote — Spanish/);
  });

  it("never names a DRAFT as the version a message would use, whatever the order", () => {
    // ⚠ **THIS CASE EXISTS BECAUSE AN EARLIER VERSION OF IT COULD NOT FAIL
    // (hard-won law 7), AND IT IS CARRIED OVER FOR THAT REASON.** Removing
    // `&& row.pickable` from `usedRow` — the exact change that would let an
    // unapproved draft be named as the wording a letter goes out on — left
    // every case GREEN, because the seeded rows happen to list the published
    // variant before the draft and `rows.find` takes the first. So this
    // reverses the order, which is the only arrangement that tells the two
    // apart. What `usedRow` decides is now the cell's PLACEHOLDER — the
    // version that WOULD be used when the clerk picks nothing.
    const reversed = { ...PICKER_ROWS, rows: [...PICKER_ROWS.rows].reverse() };
    const html = renderStep7(reversed);
    const from = html.indexOf('data-cell="template-quote_and_what_is_owed"');
    expect(from).toBeGreaterThan(-1);
    const cell = html.slice(from, html.indexOf("</select>", from));
    expect(cell).toContain("Connection quote · v1");
    expect(cell).not.toMatch(/<option value="">Connection quote — Spanish/);
  });

  it("names no template for the contract, because a contract cannot be seeded", () => {
    const html = renderStep7();
    // BR-NOT-002 — an effective date needs a human, and there is none in a
    // provisioning transaction. Measured: a seeded utility gets TWO rows.
    const from = html.indexOf('data-cell="template-contract"');
    // ⚠ **PIN THE SLICE BEFORE READING IT.** `indexOf` answers -1 for a marker
    // that is not there, and `slice(-1, -1)` is an empty string that every
    // `not.toContain` would pass over.
    expect(from).toBeGreaterThan(-1);
    const cell = html.slice(from, html.indexOf("</td>", from));
    expect(cell).not.toContain("This utility has published none.");
    // ⊕ `DEF-CUS-9198` (PO item 22) — not a bare dash: it says what to do and
    // links to where templates are published.
    expect(cell).toContain('data-template-missing="contract"');
    expect(cell).toContain("/settings/templates");
    // And the two that DO resolve a version still name theirs, so this case
    // cannot pass over a screen that has simply stopped resolving any.
    expect(html).toContain("New connect — confirmed · v1");
    expect(html).toContain("Connection quote · v1");
  });

  it("never prints a database id", () => {
    // B14 rule 31. The picker's rows carry `template_id` on the wire and the
    // TYPE deliberately has no member for it, so there is nothing to leak.
    expect(renderStep7()).not.toContain("template_id");
  });

  it("shows the owner we are telling, and refuses to invent a language", () => {
    const html = renderStep7();
    expect(html).toContain("Balcones Development LLC");
    expect(html).toContain("ops@balconesdev.example");
    // ⚠ NOT DEFAULTED TO ENGLISH — *they chose English* and *they chose nothing*
    // are different facts and only one may be shown to a clerk as a preference.
    expect(html).toContain('data-telling-field="language"');
    // ⊕ `DEF-CUS-9195` — step 1 asks now; nothing picked is said as that.
    expect(html).not.toContain("Not asked on this build.");
    expect(html).not.toMatch(/data-telling-field="language">English/);
  });

  it("shows the language picked on step 1 by name", () => {
    // ⊕ `DEF-CUS-9195` — PO Q8: *"language from step 1"*.
    const html = renderStep7(undefined, { communication: { language: "es-MX", paperlessBill: false, smsReminders: false } });
    expect(html).toMatch(/data-telling-field="language">[^<]*Espa/);
  });
});

// ══════════════════════════════════════════════════════════════════════════
// STEP 8 — WHAT WILL BE CREATED
// ══════════════════════════════════════════════════════════════════════════


// ══════════════════════════════════════════════════════════════════════════
// FOUR DESCRIBES RETIRED HERE BY `CR-150-BRC09`, AND WHERE EACH WENT
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **THEY ARE RETIRED BECAUSE THEIR SCREEN NO LONGER EXISTS, NOT BECAUSE
// THEY WENT RED.** Eight steps became five: step 7 is folded into Review and
// step 8's three read-back blocks are replaced by the *At a glance* strip and
// four collapsible groups (`DEF-CUS-7613`, PO: *"the information architecture
// is not grouped in logical section and text is so much please reduce it"*).
// A case asserting `data-what-next` is asserting a superseded truth — which
// is what `CR-150-BRC09` §3 says of every walkthrough that drives this wizard
// by step number: *"They will fail correctly."*
//
// ⚠ **EVERY ONE IS ACCOUNTED FOR. A RETIRED CASE WITH NOWHERE NAMED IS
// COVERAGE LOST QUIETLY**, which is the whole shape this repo files as *a
// check that does not check*.
//
//   · `step 8 · from each step` (3 cases) — the read-back is now four
//     collapsible groups. Covered by *draws four collapsible groups, each
//     with an Edit at the RIGHT step* in
//     `NewConnectRedesignSteps45.dom.test.tsx`, which also presses one.
//   · `step 8 · what happens next` (5 cases) — the seven-row table is
//     replaced by *What Create makes*, whose fourteen rows are checked
//     against `commit_connection` itself. Covered by the task-14 describe in
//     the new file, including the FOUR claims the drawing gets wrong.
//     ⚠ Its `CR-032` case — *the word `energis` appears nowhere* — is
//     **carried over below** rather than retired: it is a PO ruling said
//     TWICE and it must not lapse with the table it was written against.
//   · `what happens next · rule 33 in ELEVEN languages` — **NOT RETIRED.** It
//     reads the CATALOGUES, not the screen, and `customers.newConnect.next.*`
//     still exists in all eleven. The new table's own family gets the same
//     check in the new file.
//   · `step 8 · the manifest` (4 cases) — the manifest table is the *At a
//     glance* strip. Covered by *draws the At a glance strip with all nine
//     cells*, *prints One-time charges through MoneyCell* and *shows an em
//     dash and never a zero* in the new file.
//
// ⚠ **AND THE STEP-7 DESCRIBE ABOVE IS TRIMMED RATHER THAN KEPT WHOLE:** two
// of its cases asserted the three ticks were DISABLED, and that is REVERSED
// on purpose (the door has always taken the clerk's choice; the wire was the
// missing half). The reversal is argued in §1 of
// `NewConnectCommunicationStep.tsx` and in the decision log of 2026-09-29 —
// never silently.

describe("CR-032 · `activate`, never `energis` — carried over from step 8", () => {
  it("says activate, and the word `energis` appears nowhere on the review", () => {
    // ⚠ **THE PO RULED THIS TWICE** — 2026-08-25, *"instead of energise can we
    // use activated"*, and again 2026-09-21, *"we ahe to say activate"* — so
    // it outlives the table it was first written against. Retiring it with
    // *What happens next* would have let a ruling lapse because the screen
    // around it moved, which is this repo's most-filed rot.
    const html = renderStep8();
    expect(/energis/i.test(html)).toBe(false);
  });
});

describe("what happens next · rule 33 in ELEVEN languages, not one", () => {
  it("caps every cell at six words in every catalogue", async () => {
    // ⚠ **THE RENDERED CHECK ABOVE READS ENGLISH AND ONLY ENGLISH, SO IT CANNOT
    // SEE THIS.** B14 rule 33 caps a FACT at six words on SCREEN, and the screen
    // a Mexican or French utility sees is its own catalogue's. Measured when the
    // batch first landed: `es` and `es-MX` carried a seven-word cell and `fr-FR`
    // a nine-word one, with every English assertion green. Twenty-six strings on
    // a neighbouring step were in NO catalogue at all on the same day — that
    // failure and this one are the same blind spot, one step apart.
    const catalogues = import.meta.glob("@/i18n/locales/*.json", { eager: true }) as Record<
      string,
      { default: Record<string, string> }
    >;
    const names = Object.keys(catalogues);
    // Pin the shape first — a glob that matched nothing would pass the loop.
    expect(names.length).toBe(11);
    const offences: string[] = [];
    for (const [file, mod] of Object.entries(catalogues)) {
      const rows = Object.entries(mod.default).filter(([key]) =>
        key.startsWith("customers.newConnect.next."),
      );
      // 7 rows × 3 columns, in every language — so a catalogue that silently
      // lost the family is a failure rather than a vacuous pass.
      expect(rows.length, `${file} is missing what-happens-next keys`).toBe(21);
      for (const [key, text] of rows) {
        const words = text.split(/\s+/).filter(Boolean).length;
        if (words > 6) offences.push(`${file} ${key} = ${words} words: ${text}`);
      }
    }
    expect(offences).toEqual([]);
  });
});

