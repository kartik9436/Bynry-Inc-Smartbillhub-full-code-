// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-CUS-6917 — the Accounts list drew TWO service chips on an
//           account the Product Owner believed held four, and no surface in
//           the product could say whether the account took two or whether this
//           read lost two. `selectors.service_codes_for_accounts` skipped any
//           open agreement whose service point it could not resolve to a code
//           (`if code:`) and counted nothing.
// Law:      CLAUDE.md hard-won law 7, fifth shape, verbatim — *a declared blind
//           spot with no number beside it is indistinguishable from an empty
//           one*. The fix is the NUMBER, on the screen and in the log.
// Rules:    B14 rule 33 (a FACT ≤ 6 words; RATIONALE is ZERO words on screen)
//           · rule 31 (no database id on screen) · hard-won law 2 (the prop is
//           passed at the one call site — `AccountsListPage.tsx`)
// ───────────────────────────────────────────────────────
//
// ⚠ **WHAT WOULD MAKE THESE PASS WRONGLY.** A component that always rendered
// the chip would satisfy tc1 and be wrong on every healthy row, so tc2 asserts
// a clean row carries NOTHING — which is the case that runs on 100% of today's
// data (measured 2026-09-27: 479 open agreements across the two local tenants,
// 479 resolvable, 0 dropped). A component that rendered it in place of the
// service chips would also satisfy tc1, so tc1 asserts both are present. And a
// chip whose count came from `services.length` rather than from the server
// would pass tc1 by accident, so tc3 asserts the NUMBER is the server's.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { AccountServiceChips } from "./accountsListCells";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

function markup(services: readonly string[], unresolved?: number): string {
  return renderToStaticMarkup(
    <AccountServiceChips services={services} kind="regular" unresolved={unresolved} t={t} />,
  );
}

describe("DEF-CUS-6917 — a dropped service chip is counted on screen", () => {
  it("tc1: two chips and two dropped says so, beside the chips it did draw", () => {
    const html = markup(["water", "fire"], 2);

    expect(html).toContain('data-testid="account-services-unresolved"');
    // The number, which is the whole point: `?2`, not a bare warning glyph.
    expect(html).toContain("?2");
    // …and the two chips it COULD resolve are still drawn. The marker is an
    // addition to the cell, never a replacement for it.
    expect(html).toContain('aria-label="Water"');
    expect(html).toContain('aria-label="Fire"');
    // The accessible name is the translated FACT — four words (rule 33).
    expect(html).toContain("2 services not shown");
  });

  it("tc2: a row that lost nothing says nothing", () => {
    const html = markup(["water", "sewer", "trash", "fire"], 0);
    expect(html).not.toContain('data-testid="account-services-unresolved"');
    expect(html).not.toContain("services not shown");
  });

  it("tc2b: a caller that passes no count claims nothing either", () => {
    const html = markup(["water", "fire"]);
    expect(html).not.toContain('data-testid="account-services-unresolved"');
  });

  it("tc3: the count is the SERVER's, not the number of chips drawn", () => {
    // Three chips, one drop — an arithmetic no `services.length` can produce.
    const html = markup(["water", "sewer", "fire"], 1);
    expect(html).toContain("?1");
    expect(html).toContain("1 services not shown");
  });

  it("tc4: every chip lost still leaves an honest cell, not a silent dash", () => {
    // The page-wide failure: metering's seam answers nothing, every code drops.
    // Before DEF-CUS-6917 this rendered as `— No services`, which is a lie.
    const html = markup([], 4);
    expect(html).toContain("?4");
    expect(html).not.toContain(">No services<");
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-CUS-6917 (PO, live beta v2.352.0 — `AC-2026-00057`)
// generated: 2026-09-27 by lane CUS-CHIPS
// gates: tsc · eslint --max-warnings 0 · vitest · g15 (the one new key is in all eleven catalogues) · g31/G134 (this file and `accountsListCells.tsx` are on `styles/route-b-migrated.txt`)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
