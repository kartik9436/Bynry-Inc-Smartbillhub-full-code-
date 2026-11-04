// ── Trace ──────────────────────────────────────────────
// Defect: DEF-336 — Settings → Configure → Reference data (SET-04) drew a bare
//         chevron and no number on every BILLING card (Billing defaults, Budget
//         billing rules, Document & message templates) while READS showed 5 and
//         PAYMENTS showed 7. Beside WORK's honest "Not set up yet" that reads as
//         missing configuration, to the one person who can act on it.
// Screens: S8 → Settings → Configure → Reference data
// Routes:  /{tenant}/settings/reference-data · GET /api/{tenant}/lookups
// Rules:   BR-TEN-029 (a card's count is computed LIVE, so the badge IS the row
//          count) · BR-TEN-031 · BR-TEN-033 (the templates card is navigation
//          only) · DEF-026 (the `uncounted` state — set up, not countable here)
// ───────────────────────────────────────────────────────
//
// **WHY THIS IS A BROWSER TEST AND NOT A UNIT TEST.**
//
// The unit tests in `SettingsReferenceData.test.tsx` prove the badge FUNCTION
// returns three different things. They cannot prove the SCREEN shows the number
// the server actually took, because they hand it their own fixture. DEF-336 was
// exactly that gap: every unit test passed, `GET /lookups` served
// `custom_fields: 3`, and the tile discarded the 3 before rendering because the
// card's kind was not "list". Hard-won law 6 — diff the running app against what
// it claims — is the only thing that finds this class, and it found this one.
//
// So this spec reads BOTH ends and compares them:
//   · `GET /api/{tenant}/lookups` — the server's own answer, the same one
//     `reference_data_report()` builds, which is what the seeder writes.
//   · the rendered `.lookup-card` badges a person reads.
//
// **THE ASSERTION THE DEFECT WOULD HAVE FAILED**: a card whose list is NON-EMPTY
// and whose badge carries no digits is red. Nothing asserted that before, which
// is DEF-336's escape reason in one sentence.
//
// ⚠ PROVED RED FIRST (law 7), against the 2.29.1 build serving the defect:
// `custom_fields` served count 0 and rendered "›", and the three BILLING cards
// rendered "›" with no words at all. Both assertions below named them.

import { expect, test } from "@playwright/test";

import { APP_SERVER_TAG } from "./support/census";
import { signIn, skipUnlessAppServer, tenant } from "./support/app";

skipUnlessAppServer(test);

/** The three BILLING cards the PO photographed, by their on-screen label. */
const BILLING_CARDS = [
  "Billing defaults",
  "Budget billing rules",
  "Document & message templates",
];

interface ServedCard {
  list: string;
  owner: string;
  count: number | null;
  state: string;
}

test.describe(`DEF-336 · every card states a count or says why not ${APP_SERVER_TAG}`, () => {
  test(`the rendered badge equals the server's own count ${APP_SERVER_TAG}`, async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);

    // The server's answer FIRST, through the browser's own session — so this is
    // the same request the screen makes, not a second opinion from curl.
    const served: ServedCard[] = await page.evaluate(async (slug) => {
      const response = await fetch(`/api/${slug}/lookups`, {
        headers: { accept: "application/json" },
      });
      return response.json();
    }, tenant());
    expect(served.length, "the grid endpoint serves cards at all").toBeGreaterThan(0);

    await page.goto(`/${tenant()}/settings/reference-data`);
    await expect(page.locator(".lookup-card").first()).toBeVisible();

    // ── 1 · every card the SERVER counted shows that number on screen ───────
    // DEF-336's first cause: the tile read the count only for `kind: "list"`,
    // so `custom_fields` threw a real number away at the last step.
    //
    // The grid keys cards by label, not by list code, so compare through the
    // badges: every badge that carries digits must be a number the server sent,
    // and every non-null server count must appear on some badge.
    const badges = await page.locator(".lookup-card .v").allTextContents();
    const rendered = badges
      .map((text) => text.replace("›", "").trim())
      .filter((text) => /^\d+$/.test(text))
      .map(Number)
      .sort((a, b) => a - b);
    const expected = served
      .filter((card): card is ServedCard & { count: number } => card.count !== null)
      .map((card) => card.count)
      .sort((a, b) => a - b);
    expect(
      rendered,
      "every count the server took is drawn, and no badge invents one",
    ).toEqual(expected);

    // ── 2 · A CARD WHOSE LIST IS NON-EMPTY AND WHOSE BADGE IS BLANK IS RED ──
    // This is the assertion the defect would have failed, written as the brief
    // asks: non-empty list, blank count → fail.
    const blankBadges = (
      await page.locator(".lookup-card .v").allTextContents()
    ).filter((text) => text.replace("›", "").trim() === "");
    expect(
      blankBadges,
      "no badge is a bare chevron: a blank says nothing, and a person reads " +
        "nothing as 'nothing here' (DEF-336)",
    ).toEqual([]);

    // ── 3 · the three states are DISTINCT, and the BILLING section says so ──
    for (const label of BILLING_CARDS) {
      const tile = page.locator(".lookup-card").filter({ hasText: label });
      await expect(tile, `${label} is on the grid`).toHaveCount(1);
      const badge = tile.locator(".v");
      await expect(badge, `${label} badge is not a bare chevron`).not.toHaveText("›");
      // The reason is reachable, not merely implied — support and the admin
      // both read it off the control itself.
      await expect(badge).toHaveAttribute("title", /.+/);
    }

    // WORK is untouched and must stay untouched: its lists genuinely are not set
    // up, and "Not set up yet" is the honest sentence for that — a different
    // statement from "this card holds settings".
    const work = page.locator(".lookup-card").filter({ hasText: "Skills catalog" });
    await expect(work).toContainText("Not set up yet");
  });
});
