// ── Trace ──────────────────────────────────────────────
// Change:  CR-016 addendum — "EVERY SCREEN CARRIES ITS ID, VISIBLE" (PO, 2026-08-19)
// Defects: DEF-137 (screens carry no id in the frontend)
// Rules:   `routing/screenIds.ts` is a SECOND list of route patterns; this file
//          is the thing that refuses to let it drift, exactly as
//          `sidebarReachability.test.tsx` does for `sidebarDestinations.ts`.
// ───────────────────────────────────────────────────────
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, useRoutes } from "react-router-dom";
import type { RouteObject } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { APP_ROUTES } from "@/App";
import { ScreenIdTag } from "@/components/ScreenIdTag";
import { SCREEN_ROUTES, resolveScreen, screenLabel } from "@/routing/screenIds";

/**
 * Every route App.tsx declares, as a FULL pattern, in declaration order.
 *
 * A pathless layout route (the shell) contributes no segment of its own, an
 * `index` route resolves to its parent's path, and `*` becomes `<parent>/*` —
 * which is exactly how `matchPath` reads them, so the two lists compare
 * like for like.
 *
 * A route that has CHILDREN and no element of its own is purely structural —
 * `{ path: "/:tenant", children: […] }` renders nothing, and its address is
 * served by the index route inside it. It contributes no screen, so it
 * contributes no row; without this the tenant root would appear twice.
 */
function flatten(routes: readonly RouteObject[], parent = ""): string[] {
  const out: string[] = [];
  for (const route of routes) {
    let here = parent;
    const structural = route.children !== undefined && route.element === undefined;
    if (route.index === true) {
      out.push(parent === "" ? "/" : parent);
    } else if (typeof route.path === "string") {
      here = route.path.startsWith("/")
        ? route.path
        : `${parent === "/" ? "" : parent}/${route.path}`;
      if (!structural) {
        out.push(here);
      }
    }
    if (route.children) {
      out.push(...flatten(route.children, here));
    }
  }
  return out;
}

describe("the screen-id map is the router's own route table", () => {
  it("covers every routed screen, in App.tsx's order, with nothing extra", () => {
    // Both directions in ONE assertion, deliberately: an added route that
    // nobody mapped and a mapped path that no route serves are the same defect
    // seen from two ends, and a `toContain` pair would let the ORDER rot
    // silently — and order is what makes `matchPath` pick the static segment
    // over the dynamic one.
    expect(SCREEN_ROUTES.map((entry) => entry.path)).toEqual(flatten(APP_ROUTES));
  });

  it("is not an empty loop", () => {
    // DEF-057's shape: without this, an emptied table turns the assertion above
    // into `[] === []` and reports itself as a pass.
    expect(SCREEN_ROUTES.length).toBeGreaterThanOrEqual(50);
  });

  it("gives every screen an id, or says in its note why it has none", () => {
    for (const entry of SCREEN_ROUTES) {
      if (entry.ids.a1 === null && entry.ids.r10 === null && entry.byParam === undefined) {
        // A row with neither id must SAY so — that sentence is the law-8
        // finding, and a silent null is how a finding becomes a shrug.
        expect(
          entry.noScreen !== undefined || (entry.note ?? "").length >= 40,
          `${entry.path} has no screen id and no reason`,
        ).toBe(true);
      }
    }
  });

  it("never invents an A1 sub-id, and follows r10's for tabs", () => {
    // The A1 half is quoted; the r10 half may be extended, because r10 is the
    // file that defines the `PLN-01.charges` convention.
    for (const entry of SCREEN_ROUTES) {
      const pairs = [entry.ids, ...Object.values(entry.byParam?.values ?? {})];
      for (const pair of pairs) {
        if (pair.a1 !== null) {
          // S31.2 and S31.3 are A1's OWN dotted ids; anything else dotted would
          // be this lane extending a vocabulary that is not ours.
          expect(pair.a1, `${entry.path} carries an A1 id A1 does not write`).toMatch(
            /^S\d+(\.\d+)?$/,
          );
        }
        if (pair.r10 !== null) {
          expect(pair.r10, `${entry.path} carries a malformed r10 id`).toMatch(
            /^[A-Z]{3}-[0-9A-Za-z]+(\.[0-9A-Za-z-]+)?$/,
          );
        }
      }
    }
  });
});

describe("resolveScreen reads the URL the way each screen does", () => {
  it("resolves the first screen after every sign-in", () => {
    const found = resolveScreen("/brazos/dashboard");
    expect(found.a1).toBe("S7");
    expect(found.r10).toBe("DSH-01");
  });

  it("prefers the static segment over the dynamic one, as the router does", () => {
    expect(resolveScreen("/brazos/premises/units").a1).toBe("S15");
    expect(resolveScreen("/brazos/premises/12").a1).toBe(null); // premises DETAIL: no A1 row
    expect(resolveScreen("/brazos/premises/12").r10).toBe("PRM-02");
  });

  it("follows A1 where A1 numbers the tabs of one screen separately", () => {
    // S32 · S33 · S34 are three A1 screens behind one component and one route.
    expect(resolveScreen("/brazos/payments").a1).toBe("S32");
    expect(resolveScreen("/brazos/payments/record").a1).toBe("S33");
    expect(resolveScreen("/brazos/payments/outstandings").a1).toBe("S34");
  });

  it("DEF-3480 CLOSED: every Payments tab draws a badge, Summary included", () => {
    // ⚠ **THIS CASE USED TO PIN THE OPPOSITE AND IT WAS RIGHT TO.** It asserted
    // `null` for Summary and for the collections board, and its comment said the
    // collision was in the decision log for the Product Owner. **NAMING THE
    // RULING THAT CHANGED IT IS WHAT THAT PIN EXISTED TO FORCE, so here it is.**
    //
    // PO instruction 2026-09-03: *"We need unique screen ID - on every screen"*.
    // The decision of the same day takes a THIRD road past the collision this
    // case was pinning. The two the previous lane reported were: render the A1
    // `S`-id (which reverses the PO's own ruling of 2026-08-19 — *"assign tags
    // that are visible on screen those should be as per modules how we are using
    // in r10"*), or widen G29 to accept an id no authority defines (which retires
    // the only check standing between us and an invented id in a screenshot).
    // **Both are still declined.** What changed is that "modules how we are using
    // in r10" is read as a SCHEME rather than as a closed list of the ids a
    // frozen prototype happened to draw — so the missing ids are ALLOCATED in
    // that same grammar in `10-scripts/gates/g29_allocated_badges.txt`, and G29
    // reads that register as a THIRD AUTHORITY. It still refuses an id no
    // authority defines; it gained an authority rather than losing a check.
    //
    // `PAY-summary` is deliberately the string **r10 itself computes**
    // (`map[s.payTab] || 'PAY-' + s.payTab`, and Summary sets `payTab:
    // 'summary'`) rather than a tidier new number, so the running prototype and
    // the running product call that tab the same thing. G29 was right to refuse
    // it while it was only computed; it is declared now.
    expect(resolveScreen("/brazos/payments/record").r10).toBe("PAY-01");
    expect(resolveScreen("/brazos/payments/outstandings").r10).toBe("PAY-02");
    expect(resolveScreen("/brazos/payments").r10).toBe("PAY-summary");
    expect(resolveScreen("/brazos/payments/summary").r10).toBe("PAY-summary");
    // ⚠ BOTH SPELLINGS, ON PURPOSE. Bare `/payments` falls back to Summary and
    // `/payments/summary` reaches it as a tab; they are ONE screen, and an id
    // that appeared on one URL and not the other is a bug report nobody can
    // write down.
    //
    // The collections board keeps NO A1 id — A1's S70 is the collections RULES
    // in Settings, a different screen — and gains `PAY-06`, minted in the
    // register because r10 draws PAY-01..05 and no board.
    expect(resolveScreen("/brazos/payments/collections").r10).toBe("PAY-06");
    expect(resolveScreen("/brazos/payments/collections").a1).toBe(null);
    // The A1 half is untouched throughout, and it is what a ticket cites. NO
    // `S`-id is rendered anywhere: the 2026-08-19 ruling stands.
    expect(resolveScreen("/brazos/payments").a1).toBe("S32");
  });

  it("follows r10's sub-id for a tab it does not number separately", () => {
    expect(resolveScreen("/brazos/plans-rates/plans").r10).toBe("PLN-01");
    expect(resolveScreen("/brazos/plans-rates/rates").r10).toBe("RAT-01");
    expect(resolveScreen("/brazos/plans-rates/charges").r10).toBe("PLN-01.charges");
  });

  it("reads the signup wizard's step out of the query string", () => {
    // A resolver that only read the PATH would tag all five signup screens
    // S110, and step 4 is the screen DEF-137 was filed about.
    expect(resolveScreen("/signup").a1).toBe("S110");
    expect(resolveScreen("/signup", "?step=4").a1).toBe("S113");
    expect(resolveScreen("/signup", "?step=5").r10).toBe("ONB-04.5");
  });

  it("DEF-NOT-4443 — the template DESIGNER is SET-10, and the catalogue behind it stays SET-09", () => {
    // Two screens, one address. The list is 38 rows; `?template=` replaces it
    // with the designer for ONE of them, and both drew the LIST's badge — so a
    // fault photographed on the designer was filed against the catalogue.
    // r10 made this distinction in its own id function all along (line 9280):
    //   `s.tplView ? 'SET-10.' + s.tplView : 'SET-09'`.
    expect(resolveScreen("/brazos/settings/configure/templates").r10).toBe("SET-09");
    expect(
      resolveScreen("/brazos/settings/configure/templates", "?template=email_bill_ready").r10,
    ).toBe("SET-10");
    // The variant is a position INSIDE the designer, not a third screen.
    expect(
      resolveScreen(
        "/brazos/settings/configure/templates",
        "?template=email_bill_ready&variant=7c9",
      ).r10,
    ).toBe("SET-10");
    // ⚠ NO DOTTED SUFFIX. r10 appends the template key; one of our keys is
    // `bill:<uuid>` (CR-048 E9's other store), and B14 rule 31 forbids a
    // database id as the visible value of anything.
    expect(
      resolveScreen("/brazos/settings/configure/templates", "?template=bill:0f3c-uuid").r10,
    ).toBe("SET-10");
    // An EMPTY parameter is the list, which is what the screen itself does.
    expect(resolveScreen("/brazos/settings/configure/templates", "?template=").r10).toBe("SET-09");
    // The A1 half never moves: A1 numbers all of Settings S8 and does not
    // number this designer separately, so nothing is minted here.
    expect(
      resolveScreen("/brazos/settings/configure/templates", "?template=email_bill_ready").a1,
    ).toBe("S8");
    // AND IT IS PINNED TO THIS TAB. `?template=` is a parameter any screen
    // could carry; `over: "SET-09"` is what stops it relabelling the six
    // sibling tabs that resolve through the same row.
    expect(
      resolveScreen("/brazos/settings/configure/routes-cycles", "?template=email_bill_ready").r10,
    ).toBe("SET-05");
  });

  it("keeps the tab's default rather than blanking on an unknown value", () => {
    // Every one of these params already falls back to a default tab inside its
    // own screen, so a tag that went empty would disagree with what is drawn.
    expect(resolveScreen("/brazos/payments/not-a-tab").a1).toBe("S32");
    expect(resolveScreen("/brazos/settings/not-a-tab").a1).toBe("S8");
  });

  it("answers nothing for an address with no screen", () => {
    expect(resolveScreen("/brazos/nowhere-at-all").label).toBe("");
    expect(screenLabel({ a1: "S7", r10: null })).toBe("");
  });

  it("renders the r10 id ONLY — the S-id is never on screen (PO 2026-08-19)", () => {
    expect(screenLabel({ a1: "S7", r10: "DSH-01" })).toBe("DSH-01");
  });
});

function tagMarkupAt(url: string): string {
  function Routes() {
    return useRoutes([{ path: "*", element: <ScreenIdTag /> }]);
  }
  return renderToStaticMarkup(
    <MemoryRouter initialEntries={[url]}>
      <Routes />
    </MemoryRouter>,
  );
}

describe("the tag on screen", () => {
  // ⚠ WHAT THIS SUITE CANNOT SEE, STATED RATHER THAN IMPLIED. This project has
  // no DOM environment in vitest (no jsdom, no happy-dom — every suite here
  // renders through `renderToStaticMarkup`), so the `useEffect` that writes
  // `data-screen-id` / `data-screen-a1` onto `<body>` DOES NOT RUN under these
  // tests. That half is asserted in a real browser by
  // `e2e/CR-016-screen-ids.spec.ts`, which is the only place it can be, and the
  // attributes are ALSO written onto the tag element itself so that the shape
  // below is exercised somewhere cheap.
  it("draws r10's id, and never the S-id (PO ruling 2026-08-19)", () => {
    const markup = tagMarkupAt("/brazos/dashboard");
    expect(markup).toContain('data-testid="screen-id-tag"'); // CR-018: the class went with ScreenIdTag.css
    expect(markup).toContain(">DSH-01<");
    expect(markup).toContain('data-screen-id="DSH-01"');
    expect(markup).toContain('data-screen-a1="S7"');
    expect(markup).not.toContain(">S7<");
  });

  it("is inert and invisible to a screen reader", () => {
    // `pointer-events: none` lives in ScreenIdTag.css; the CLASS is the
    // contract this suite can hold, and the browser spec measures the computed
    // value. `aria-hidden` is assertable here and is: an id is not content.
    expect(tagMarkupAt("/brazos/dashboard")).toContain('aria-hidden="true"');
  });

  it("draws the ALLOCATED id where r10 draws none — never an S-id, never a guess", () => {
    // ⚠ **THIS CASE USED TO ASSERT AN EMPTY CORNER ON THESE TWO ADDRESSES AND
    // ITS SUBJECT IS GONE.** It read *"draws NOTHING where r10 allocates no
    // id — the finding, not an invention"*, and the finding was real: r10
    // draws no audit-log screen and no cost-of-service screen, so the corner
    // was empty on both.
    //
    // **THE EMPTINESS WAS NEVER THE GUARANTEE.** What was worth holding is that
    // the tag does not INVENT an id and does not PROMOTE the S-id to fill the
    // gap, and both of those are still true and are what this case asserts now.
    // PO instruction 2026-09-03 (*"We need unique screen ID - on every screen"*)
    // is answered by ALLOCATING the missing ids in r10's own grammar in
    // `10-scripts/gates/g29_allocated_badges.txt`, which G29 reads as a third
    // authority — so these two corners are full, and full of an id an authority
    // defines rather than one this file made up.
    const auditLog = tagMarkupAt("/brazos/audit-log");
    expect(auditLog).toContain(">SET-16<");
    expect(auditLog).not.toContain(">S61<"); // the S-id is NOT the visible value
    expect(auditLog).toContain('data-screen-a1="S61"'); // ...but it is still carried

    const costOfService = tagMarkupAt("/brazos/finance/cost-of-service");
    expect(costOfService).toContain(">FIN-01.costOfService<");
    expect(costOfService).not.toContain(">S73<");
    expect(costOfService).toContain('data-screen-a1="S73"');

    // ⚠ WHAT THIS CASE CANNOT PROVE, so that nobody reads it as proving it:
    // that the two ids above are defined ANYWHERE is `g29_screen_ids.py`'s
    // check, not this suite's — it refuses any id absent from A1, from r10's
    // own sid() and from the register, and was proved RED on an invented id
    // before it was trusted. Here we can only assert WHAT IS RENDERED.
  });

  it("DEF-3480 FIXED: both spellings of the Payments landing tab draw the SAME id", () => {
    // ⚠ **THIS CASE USED TO ASSERT THE DEFECT AND SAID SO IN ITS OWN WORDS** —
    // *"THIS CASE ASSERTS AN OPEN DEFECT … pinning it means the day somebody
    // changes it they must come here and say which ruling let them."* This is
    // that day and this is the ruling.
    //
    // The PO, walking the deployed build: *"no screen IDs are shown on Payment
    // screens"*. Then, 2026-09-03: *"We need unique screen ID - on every
    // screen"*. The previous lane reported only two roads — render the S-id
    // (reversing the PO's ruling of 2026-08-19) or accept an id no authority
    // defines (gutting G29) — and **both are still declined**. The third road
    // reads *"modules how we are using in r10"* as a SCHEME rather than a closed
    // list, and allocates `PAY-summary` in the register. It is deliberately the
    // string **r10 itself computes** (`map[s.payTab] || 'PAY-' + s.payTab`, and
    // Summary sets `payTab: 'summary'`) rather than a tidier new number, so the
    // prototype and the product name that tab identically.
    //
    // **THE GUARANTEE THIS CASE NOW HOLDS IS THE REASON THE FIX WAS WORTH
    // MAKING:** bare `/payments` falls back to Summary and `/payments/summary`
    // reaches it as a tab. They are ONE screen. An id that appeared on one URL
    // and not the other is a bug report nobody can write down.
    const landed = tagMarkupAt("/brazos/payments");
    const asTab = tagMarkupAt("/brazos/payments/summary");
    expect(landed).toContain(">PAY-summary<");
    expect(asTab).toContain(">PAY-summary<");
    expect(tagMarkupAt("/brazos/payments/record")).toContain(">PAY-01<");
    expect(tagMarkupAt("/brazos/payments/outstandings")).toContain(">PAY-02<");

    // ⚠ THE S-ID IS STILL NOT PROMOTED, AND THE ASSERTION HAD TO CHANGE SHAPE
    // TO KEEP SAYING SO. The old one was `.not.toContain("S32")` over the WHOLE
    // markup, which passed only because the markup was empty — and would now be
    // wrong for a reason that has nothing to do with the ruling: the tag carries
    // `data-screen-a1="S32"` on purpose, as a machine-readable attribute, and
    // always did. What the 2026-08-19 ruling forbids is the S-id being the
    // VISIBLE value, so that is what is asserted, exactly as the dashboard case
    // above asserts `not.toContain(">S7<")`.
    expect(landed).not.toContain(">S32<");
    expect(asTab).not.toContain(">S32<");
    expect(landed).toContain('data-screen-a1="S32"');
  });

  it("a screen with ONLY an r10 id draws it, and no S-id is ever promoted", () => {
    // `/premises/:premisesId` has a badge and no A1 row — the tag is the badge
    // alone, and the A1 half stays null rather than being invented.
    expect(tagMarkupAt("/brazos/premises/12")).toContain(">PRM-02<");
    expect(resolveScreen("/brazos/premises/12").a1).toBe(null);

    // ⚠ **THIS CASE USED TO PROVE THE OTHER HALF ON A REAL ROW AND IT NO LONGER
    // CAN — the row it used is gone, and that is the point rather than a loss.**
    // It asserted that `/finance/taxes` was S41 with no badge and therefore drew
    // NOTHING, because *an A1 id is never promoted onto the screen to fill a
    // gap* (DEF-3465). **That rule has not moved.** What moved is that after the
    // 2026-09-03 allocation there is no longer ANY mapped screen with an A1 id
    // and no badge — `screens_without_r10` went 35 to 0 — so the gap the rule
    // governs cannot be demonstrated on a real route any more. `/finance/taxes`
    // now draws `FIN-01.taxes`, a Finance tab under the FIN-01 parent r10 draws.
    expect(resolveScreen("/brazos/finance/taxes").a1).toBe("S41");
    expect(resolveScreen("/brazos/finance/taxes").r10).toBe("FIN-01.taxes");
    expect(tagMarkupAt("/brazos/finance/taxes")).toContain(">FIN-01.taxes<");
    // The rule itself keeps its guard at the unit level, where a synthetic pair
    // can still make the gap the real map no longer has — see "answers nothing
    // for an address with no screen" and "renders the r10 id ONLY" above. A
    // guard whose subject disappears is retired deliberately and out loud, never
    // by deleting the case and hoping the rule holds.
    expect(screenLabel({ a1: "S41", r10: null })).toBe("");
  });
});
