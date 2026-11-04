// ── Trace ──────────────────────────────────────────────
// Story:    US-MET-002 (S15 units)   Change: CR-089 wave J (`PUJ-46`)
// Rules:    BR-MET-1161 (an address lives on the property; everything else
//           walks to it) · BR-MET-1162 (a unit may carry its own point) ·
//           BR-MET-082 clause 2 (a unit takes its route from its building) ·
//           B14 rule 6 (danger tier on a destructive commit) · B14 rule 32
//           (one sentence per item)
// Defects:  DEF-511 (nothing counts bills for one unit)
// ───────────────────────────────────────────────────────
/**
 * THE SEVEN CONSEQUENCES, AND THE FACT THAT THEY ARE SEVEN.
 *
 * `moveConsequences` is pure, so what a clerk reads before pressing **Move
 * unit** is provable with no browser, no server and no fixture beyond the
 * server's own answer. That is deliberate: the sentences ARE the deliverable
 * of `PUJ-46`, and a screen test that only asserted the box exists would pass
 * over six of them being wrong.
 *
 * ⚠ **THE FILE THIS TESTS HAS NO OTHER TEST OF ITS OWN, AND THAT USED TO BE
 * ARGUED FOR.** Its header said the modal *"is only ever reached from a units
 * ROW or the unit DETAIL header, and its cases sit beside the screens that open
 * it"* — true of the rendering, and not true of a pure function that seven
 * catalogue keys feed. The render cases stay in `UnitsPage.test.tsx`, beside
 * the screens; the seven sentences are here.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import i18n from "@/i18n";
import "@/i18n";
import type { MovePreview, UnitRow } from "@/api/endpoints";
import { buttonClasses } from "@/components/Button";
import { ToastProvider } from "@/components/Toast";

import { collectFormErrors } from "@/components/FormModal";

import { moveConsequences, moveRouteSentence, moveUnitSchema } from "./MoveUnitModal";
import { MoveUnitModal } from "./MoveUnitModal";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

/** The worked example `PUJ-46` is written against, as the server answers it. */
function preview(overrides: Partial<MovePreview> = {}): MovePreview {
  return {
    unit: { id: "u-101a", unit_no: "U-01145", label: "Unit A" },
    from: {
      premises_id: "p-101",
      premise_no: "P-00101",
      address_line: "412 Cypress Row",
      locality: "Katy, TX 77494",
      has_point: true,
    },
    to: {
      premises_id: "p-880",
      premise_no: "P-00080",
      address_line: "88 Marina Bay",
      locality: "Katy, TX 77494",
      has_point: true,
    },
    assets: { count: 5 },
    routes: [
      {
        service_code: "water",
        from: { route_code: "RT-012", cycle_code: "CY-003", basis: "area" },
        to: { route_code: "RT-004", cycle_code: "CY-001", basis: "area" },
        changes: true,
      },
    ],
    accounts: { ever: 2, occupying: { account_no: "A-10432", customer_name: "R. Okafor" } },
    bills: { count: null },
    point: { source: "premises", moves: true },
    ...overrides,
  };
}

/** The two arguments the table takes beyond the preview: what a clerk has typed
 *  into `Effective from`, and the property the unit is on today. */
const FROM = "101 Silver Creek Rd, Ottumwa, IA · P-00041";
const rows = (over: Partial<MovePreview> = {}, date = "2026-09-08") =>
  moveConsequences(preview(over), date, FROM, t);

describe("CR-089 PUJ-46 — what moving a unit does, itemised", () => {
  it("is SEVEN LABELLED rows, in the order the frame draws them", () => {
    const table = rows();
    expect(table).toHaveLength(7);

    // ⚠ **THE LABELS ARE THE CHANGE (`DEF-MET-4763`).** This was seven bullets
    // with nothing naming what each was about — `ConsequenceBox`'s
    // CUSTOMER-PORTAL look — where the frame draws a two-column table.
    expect(table.map((row) => row.label)).toEqual([
      "Bills already issued",
      "The next bill",
      "Accounts this unit has carried",
      "Bills it has produced",
      "Route and cycle",
      "Meters and assets",
      // B14 rule 34's ratified word for *held here*, and the frame draws it.
      "Recorded",
    ]);

    // 1 · money already posted keeps the property it was posted under. It used
    // to be half of a note ABOVE the fields; the frame puts it in the table.
    expect(table[0].text).toBe(
      "They stay on 101 Silver Creek Rd, Ottumwa, IA · P-00041 — nothing already billed moves.",
    );
    // 2 · and the date a clerk typed is IN the sentence, not implied by it.
    expect(table[1].text).toBe("It is attributed to the new property from 2026-09-08.");
    // 3 · the accounts, and what the move does to the address ON them.
    expect(table[2].text).toBe(
      "2 accounts take the new address.",
    );
    // 4 · DEF-511 — stated as an absence, and never as a zero.
    expect(table[3].text).toContain("are not counted per unit yet");
    // 5 · who reads the meter and when it bills — BOTH named, both sides.
    expect(table[4].text).toBe(
      "Water moves from Route RT-012 · Cycle CY-003 to Route RT-004 · Cycle CY-001. " +
        "A different route reads it.",
    );
    // 6 · THE ONE THE OLD SCREEN NEVER MENTIONED. Every asset tagged to the
    // unit derives its address by walking to the premises, so all five change
    // address at the moment of the press.
    expect(table[5].text).toBe(
      "5 assets move with it.",
    );
    // 7 · what is written down, which nothing on this screen used to say.
    expect(table[6].text).toBe(
      "Both properties, the date and your reason. In the audit log.",
    );

    // B14 rule 32's budget: ONE sentence each. (The route line is one sentence
    // per service and this unit takes one service.)
    for (const row of table) {
      expect(row.text.split(". ").length).toBeLessThanOrEqual(2);
    }
  });

  it("with no date typed yet, the next-bill row is a SENTENCE and not a blank", () => {
    // The table is drawn as soon as a destination is picked, which is usually
    // before the date is typed. *"from ."* is the shape of a bug.
    const table = rows({}, "");
    expect(table[1].text).toBe(
      "Attributed to the new property. From the date above.",
    );
    expect(table[1].text).not.toContain("from .");
  });

  it("DEF-511 / PUJ-55: the bill count is printed the moment the server can count it", () => {
    // ⚠ THE TEST THAT FIRES WHEN THE HOLD EXPIRES (hard-won law 2's mirror).
    // The absence is what the screen says today; the number is what it says the
    // day `apps/billing/selectors.issued_bill_count_for_unit` lands. Both are
    // asserted here so publishing that function cannot leave the screen still
    // apologising.
    expect(rows({ bills: { count: null } })[3].text).toContain("are not counted per unit yet");
    expect(rows({ bills: { count: 14 } })[3].text).toBe("Bills it has produced · 14.");
    // …and a unit that genuinely never billed says SO, which is a different
    // sentence from *nobody could count them* and the reason `null` is not `0`.
    expect(rows({ bills: { count: 0 } })[3].text).toBe("Bills it has produced · 0.");
  });

  it("the empty cases are stated, not skipped", () => {
    const bare = rows({
      assets: { count: 0 },
      accounts: { ever: 0, occupying: null },
      routes: [],
    });
    expect(bare).toHaveLength(7);
    expect(bare[5].text).toBe("Nothing is tagged here. No equipment moves.");
    expect(bare[4].text).toBe("On no route. Nobody's round changes.");
    expect(bare[2].text).toBe("No account has ever been attached.");
  });

  it("one asset and one account read as English, not as a machine's plural", () => {
    const one = rows({ assets: { count: 1 }, accounts: { ever: 1, occupying: null } });
    expect(one[5].text).toBe(
      "One asset moves with it.",
    );
    expect(one[2].text).toContain("One account takes the new address.");
    // DEF-MET-4694: `(s)` appears nowhere in any of the seven.
    for (const row of one) {
      expect(row.text).not.toContain("(s)");
    }
  });
});

describe("CR-089 PUJ-46 — every service is named, including the ones that do not move", () => {
  const side = (route: string, cycle: string | null) => ({
    route_code: route,
    cycle_code: cycle,
    basis: "area",
  });

  it("names a service that stays put beside one that moves", () => {
    const sentence = moveRouteSentence(
      preview({
        routes: [
          {
            service_code: "water",
            from: side("RT-012", "CY-003"),
            to: side("RT-004", "CY-001"),
            changes: true,
          },
          {
            service_code: "electric",
            from: side("RT-020", "CY-003"),
            to: side("RT-020", "CY-003"),
            changes: false,
          },
        ],
      }),
      t,
    );
    // ⚠ A LIST THAT PRINTED ONLY THE CHANGES WOULD LEAVE A CLERK TO ASSUME THE
    // REST. "Electric stays on RT-020" is the news for that service.
    expect(sentence).toContain("Water moves from Route RT-012 · Cycle CY-003");
    expect(sentence).toContain("Electric stays on Route RT-020 · Cycle CY-003.");
  });

  it("gaining a route and losing one are two different sentences", () => {
    const gained = moveRouteSentence(
      preview({
        routes: [
          {
            service_code: "gas",
            from: null,
            to: side("RT-004", "CY-001"),
            changes: true,
          },
        ],
      }),
      t,
    );
    const lost = moveRouteSentence(
      preview({
        routes: [
          {
            service_code: "gas",
            from: side("RT-012", "CY-003"),
            to: null,
            changes: true,
          },
        ],
      }),
      t,
    );
    expect(gained).toBe("Gas is on no route today and joins Route RT-004 · Cycle CY-001.");
    expect(lost).toBe(
      "Gas leaves Route RT-012 · Cycle CY-003. No route at the new property.",
    );
  });

  it("a route with no cycle prints the route alone rather than an empty cycle", () => {
    const sentence = moveRouteSentence(
      preview({
        routes: [
          {
            service_code: "trash",
            from: side("RT-012", null),
            to: side("RT-004", null),
            changes: true,
          },
        ],
      }),
      t,
    );
    expect(sentence).toContain("from Route RT-012 to Route RT-004");
    expect(sentence).not.toContain("Cycle ");
  });
});

describe("CR-089 PUJ-46 — B14 rule 6: a move commits through the danger tier", () => {
  /**
   * ⚠ **THIS FILE USED TO ARGUE THE OPPOSITE, IN ITS OWN HEADER.** The modal
   * carried a note saying rule 6's danger tier was deliberately NOT used
   * because a move *"destroys nothing — it is a correction"*, and that
   * `FormModal` offered no danger submit anyway. CR-089 overrules the first
   * half and this wave closed the second: `FormModal.submitVariant` is the same
   * OPTIONAL pass-through `ConfirmDialog.confirmVariant` got for DEF-718.
   *
   * Asserted on the WHOLE class string, not with `toContain`: an extra class
   * appended to every kit button would slip past a substring match, which is
   * DEF-182's hole and what `ConfirmDialogTier.dom.test.tsx` records.
   */
  function markup() {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return renderToStaticMarkup(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <MemoryRouter initialEntries={["/brazosbend/premises/units"]}>
            <MoveUnitModal
              unit={
                {
                  id: "u-101a",
                  premises_id: "p-101",
                  premise_no: "P-00101",
                  premise_address: "412 Cypress Row",
                  label: "Unit A",
                } as unknown as UnitRow
              }
              onClose={() => undefined}
              onMoved={() => undefined}
            />
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );
  }

  it("the submit button wears danger, and wears the danger CLASSES", () => {
    const html = markup();
    expect(html).toContain('data-variant="danger"');
    expect(html).toContain(buttonClasses("danger"));
    // The tier is not decoration: rule 6 says a destructive commit is *"never
    // the standard primary"*, so the primary classes must not be on it.
    expect(html).not.toContain('data-variant="primary"');
  });

  it("U11 — `Currently on` reads ADDRESS FIRST, and `Move to` shows it is required", () => {
    const html = markup();
    // ⚠ **THE JOIN ORDER IS THE ASSERTION (`DEF-MET-4763`).** The frame draws
    // `101 Silver Creek Rd, Ottumwa, IA · P-00041`; this rendered the property
    // CODE first, so the field a clerk reads to check they have the right
    // building opened with a string nobody navigates by. The values here are
    // the fixture's, never the blueprint's (B14 rule 37).
    expect(html).toContain("412 Cypress Row · P-00101");
    expect(html).not.toContain("P-00101 · 412 Cypress Row");
    // Read-only, and the frame's sentence says why rather than saying so.
    expect(html).toContain("Where its bills were attributed.");
    // `Move to` is required in the schema and was required nowhere a person
    // could see. `SearchSelectField` has taken both props all along.
    expect(html).toContain("It takes the new building&#x27;s route and services.");
  });

  it("the drawn commit label and the drawn title", () => {
    const html = markup();
    // B14 rule 31 — the LABEL, not the series number. The fixture's label is
    // `Unit A`, so the title reads it back; a fixture with a `unit_no` would
    // have hidden the change, because `unitLabel` prefers that.
    //
    // ⚠ **AND THE NOUN IS NOT IN THE KEY, WHICH THE FRAME PUTS THERE.** A
    // browser walk read `Move Unit Unit B to another property` on real data:
    // this product's unit labels already carry the noun (`Unit A`, `Suite
    // 200`, `Master`, `Apt 101` — `UnitsListPage`'s own column comment), so
    // the drawn `Move Unit 1 …` doubles it on the COMMON case.
    expect(html).toContain("Move Unit A to another property");
    expect(html).not.toContain("Move Unit Unit A");
    // B14's button grammar — `Verb ✓` commits — and the `U11` frame draws it:
    // *"Move unit ✓, danger tier. A tick commits."*
    expect(html).toContain("Move unit ✓");
  });

  it("the reason is still required and still says it is the only record", () => {
    // `PUJ-46` raises the tier; it does not remove what the screen already did
    // well, and this is the assertion that would go red if it did.
    const html = markup();
    expect(html).toContain("The only record of why it moved.");
    expect(html).toContain("A future date is refused");
  });
});

describe("DEF-MET-4721 — an error can reach the field it is about", () => {
  /**
   * ⚠ **THE DEFECT WAS INVISIBLE TO EVERY EXISTING CHECK, AND THIS IS WHY.**
   * `UnitsPage.test.tsx` asserted the three ids were present — true, and
   * nothing to do with whether an error can be filed under one. `collectFormErrors`
   * keys by the zod PATH; `useFieldError` looks up by the input's `id`; the
   * server files under its own `field` name. All three must be ONE string, and
   * they were three. Pressing the commit button on an empty form did nothing at
   * all: three errors nobody could look up, no summary (it prints above three),
   * and nothing focused.
   *
   * Asserted on the SCHEMA rather than through a render, because the schema is
   * where the string is decided and a render can only show the symptom.
   */
  it("the schema's keys are the server's field names, which are the input ids", () => {
    const shape = Object.keys(moveUnitSchema(t).shape);
    expect(shape).toEqual(["premises_id", "effective_date", "reason"]);

    const html = renderToStaticMarkup(
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <ToastProvider>
          <MemoryRouter initialEntries={["/brazosbend/premises/units"]}>
            <MoveUnitModal
              unit={{ id: "u-101a", premises_id: "p-101" } as unknown as UnitRow}
              onClose={() => undefined}
              onMoved={() => undefined}
            />
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );
    for (const field of shape) {
      expect(html).toContain(`id="${field}"`);
    }
  });

  it("an empty form files an error the field can find", () => {
    const result = collectFormErrors(moveUnitSchema(t), {
      premises_id: "",
      effective_date: "",
      reason: "",
    });
    expect(result.count).toBe(3);
    // The keys `useFieldError` will be asked for, by the ids the inputs carry.
    expect(Object.keys(result.errors).sort()).toEqual([
      "effective_date",
      "premises_id",
      "reason",
    ]);
    // …and the one the viewport lands on is a real element id.
    expect(result.first).toBe("premises_id");
  });
});
