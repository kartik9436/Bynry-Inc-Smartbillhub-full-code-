// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  `CR-142-BRC07` `P5.12` (*"A door to the retention setting"*) and
//          `P4.6` (the two Reports settings cards it opens). Drawing p017
//          (Phase 5's task table), p047 (screen `E·2`) and p048's DOORS row,
//          read as IMAGES per B14 rule 42.
// Rules:   B14 rule 33 (a FACT ≤ 6 words; RATIONALE is ZERO words) · rule 31
//          (no database id on screen) · CLAUDE.md hard-won law 2 AND ITS
//          MIRROR · law 7 habit (2) — *what would make this pass wrongly*.
// ───────────────────────────────────────────────────────
//
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  A DOOR IS ASSERTED BY ADDRESS AND BY WHAT THAT ADDRESS OPENS.          ║
// ╚══════════════════════════════════════════════════════════════════════════╝
//
// `phaseHolds.dom.test.tsx` in this same folder records why, from this repo's
// own two failures: an address assertion alone was green over
// `/settings/audit-log`, which matched `settings/:tab` perfectly and opened
// Settings → Company; and a screen-id assertion alone was green while the
// router mounted the screen somewhere else entirely.
//
// ⚠ **WHAT WOULD MAKE THESE CASES PASS WRONGLY — asked before they were
// written.**
//
//   · **Asserting a link exists** would pass over a link to the reference-data
//     grid's TOP, which is forty cards away from the control and is the exact
//     state p048's DOORS row calls *"a setting nobody uses"*. So the case
//     asserts the `?list=` segment AND that the code in it is a card the grid
//     can actually open.
//   · **Asserting the clerk sees no link** would pass over a component that
//     rendered nothing at all for a clerk — which would take the FACT away
//     too, and the task table's OUTCOME is explicit: *"a clerk sees the fact
//     and no link"*. So the clerk case asserts the sentence IS there.
//   · **Asserting the sentence contains "days"** would pass over the
//     hard-coded `3` this change exists to remove. So it asserts the SERVED
//     number appears and the previously hard-coded one does not.
import { cleanup, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createMemoryRouter, matchRoutes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import { APP_ROUTES } from "@/App";
import { queryKeys } from "@/api/queryClient";
import type { MyPermissions } from "@/api/endpoints";
import { REFERENCE_CARDS, REFERENCE_GROUP_ORDER, referenceCard } from "@/features/tenancy/referenceDataConfig";
import { rulePageForCard } from "@/features/tenancy/settingsRulePages";
import { RULE_PAGE_SLUGS } from "@/api/endpoints";
import { openCardFrom } from "@/features/tenancy/SettingsReferenceData";

import { RetentionNote, retentionSettingHref } from "./RetentionNote";

afterEach(cleanup);

const TENANT = "brazosbend";
const HISTORY = `/${TENANT}/reports/history`;

function permissions(role: string): MyPermissions {
  return {
    role,
    role_name: role,
    permissions: [{ code: "reports", label: "Reports", access: "Full" }],
  };
}

function openHistoryNote(role: string, days: number | null) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  queryClient.setQueryData(queryKeys.myPermissions, permissions(role));
  // ⚠ MOUNTED UNDER THE REAL PATH PATTERN, never a bare MemoryRouter — a
  // fixture with no `/:tenant` pattern makes every address it builds come out
  // `//…`, a protocol-relative URL to another host that reads as a perfectly
  // good string to `toContain` (CLAUDE.md law 2's fixture clause).
  const router = createMemoryRouter(
    [
      {
        path: "/:tenant/reports/history",
        element: <RetentionNote tenant={TENANT} days={days} />,
      },
    ],
    { initialEntries: [HISTORY] },
  );
  return render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

describe("P5.12 · the door from the retention line to the retention setting", () => {
  it("an admin gets a link, and it opens the File retention card itself", async () => {
    openHistoryNote("system_admin", 3);
    await screen.findByText(/3/);
    const link = document.querySelector("[data-retention-door]") as HTMLAnchorElement | null;
    expect(link, "an admin was given no door to the setting").not.toBeNull();

    const href = link?.getAttribute("href") ?? "";
    expect(href.startsWith(`/${TENANT}/`), `href is not this tenant's: ${href}`).toBe(true);

    // BY ADDRESS: the router mounts something real there.
    const [address, query] = href.split("?");
    expect(matchRoutes(APP_ROUTES, address), `${address} matches no route`).not.toBeNull();

    // BY WHAT IT OPENS: `?list=` names a card the grid can actually open, and
    // that card opens a rule page whose slug has an endpoint behind it.
    const card = openCardFrom(new URLSearchParams(query));
    expect(card?.code, `?${query} opens no card on the grid`).toBe("file_retention");
    const page = rulePageForCard("file_retention");
    expect(page, "the File retention card opens no rule page").not.toBeNull();
    expect(RULE_PAGE_SLUGS).toContain(page?.slug);
  });

  it("a billing clerk sees the fact and no link", () => {
    openHistoryNote("billing_clerk", 3);
    expect(document.querySelector("[data-retention-note]")).not.toBeNull();
    expect(
      document.querySelector("[data-retention-door]"),
      "a clerk was shown a link to a form they cannot open",
    ).toBeNull();
  });

  it("states the utility's OWN number, not the constant it replaced", () => {
    openHistoryNote("system_admin", 9);
    const note = document.querySelector("[data-retention-note]")?.textContent ?? "";
    expect(note).toContain("9");
    expect(note, "the sentence is still the hard-coded three-day one").not.toContain("3 days");
  });

  it("draws no sentence at all while the number is unknown", () => {
    openHistoryNote("system_admin", null);
    expect(document.querySelector("[data-retention-note]")).toBeNull();
  });

  it("builds the address from the tenant it is given and nothing else", () => {
    expect(retentionSettingHref("lonestar")).toBe(
      "/lonestar/settings/reference-data/reference-data?list=file_retention",
    );
  });
});

describe("P4.6 · the Reports section of the Reference-data grid", () => {
  it("adds the group LAST, where the drawing puts it", () => {
    expect(REFERENCE_GROUP_ORDER.at(-1)).toBe("reports");
  });

  it("carries the two RULE cards P4.6 owns, and neither is a list with no endpoint", () => {
    const rules = REFERENCE_CARDS.filter(
      (card) => card.group === "reports" && card.kind === "rules",
    );
    expect(rules.map((card) => card.code)).toEqual(["file_retention", "default_format"]);
    for (const card of rules) {
      // ⚠ TENANCY, not reports: the number governs the platform export kernel.
      expect(card.owner).toBe("tenancy");
      const page = rulePageForCard(card.code);
      expect(page?.slug, `${card.code} opens no endpoint`).toBe("reports");
    }
  });

  // ── `BR-REP-044` · `P5.5`'s fourth card (PO ruling 2026-09-27, option (a)) ──
  it("Delivery is a LINK to 4·1 Scheduled, and it is not a promise", () => {
    const delivery = referenceCard("delivery");
    expect(delivery, "P5.5's fourth card is not declared").not.toBeNull();
    // A LINK and not a list: recipients live per SCHEDULE, never per tenant,
    // so there is no tenant-level list for this card to draw.
    expect(delivery?.kind).toBe("link");
    // ⚠ The address is asserted BY VALUE, not merely as "some target". A link
    // card whose target drifts is the dead-control failure this repo files
    // most, and `4·1 Scheduled` is where the recipients actually are.
    expect(delivery?.target).toBe("/reports/scheduled");
    // ⚠ NOT a promise. `arrivesWithKey` on a card with no dated owner is
    // hard-won law 2's mirror with better manners — the whole reason this
    // card waited for a ruling instead of shipping as "coming soon".
    expect(delivery?.arrivesWithKey).toBeUndefined();
    // BY ADDRESS: the router mounts something real there, so the card cannot
    // point at an address nothing serves. This is the assertion that fires if
    // `4·1 Scheduled` is ever moved or renamed.
    expect(
      matchRoutes(APP_ROUTES, delivery?.target ?? ""),
      `${delivery?.target} matches no route`,
    ).not.toBeNull();
  });

  it("does NOT declare Report groups — P5.5's remaining half is not built", () => {
    // The mirror of law 2: a card declared with no handler behind it draws a
    // count nobody served. When it gains one, DELETE this line and add the
    // card — this case is the reminder. `delivery` left here on 2026-09-27
    // under `BR-REP-044` and is asserted above instead.
    expect(referenceCard("report_groups")).toBeNull();
  });
});
