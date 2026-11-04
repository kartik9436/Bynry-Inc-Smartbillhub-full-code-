// ── Trace ──────────────────────────────────────────────
// Change:  CR-016 ADDENDUM — "EVERY SCREEN CARRIES ITS ID, VISIBLE" (PO,
//          2026-08-19): *"give sreen Id to each and Every screen and for time
//          bing also display that as a tag - right bottom for every UI screen
//          so that we know which scren has a problem"*, narrowed the same day
//          to r10's vocabulary: *"assign tags that are visible on screen those
//          should be as per modules how we are using in r10"*
// Defects: DEF-137 — *"screens do not carry their own id in the frontend, so
//          no gate can [check screen coverage]"*
// Rules:   `src/routing/screenIds.ts` (the map) ·
//          `05-prototype/r10-2026-08-16/SMARTBillHub.dc.html` line 8830 (the
//          badge being copied) · hard-won law 6 (look at the RENDERED app) ·
//          hard-won law 7 (prove a new guard RED first)
// ───────────────────────────────────────────────────────
// THE HALF NO SOURCE-READING CHECK CAN SEE.
//
// `screenIds.test.tsx` proves the map matches the router and that
// `resolveScreen` answers correctly. It CANNOT prove three things, because this
// project has no DOM environment in vitest (every suite renders through
// `renderToStaticMarkup`, so no effect ever runs):
//
//   1. `data-screen-id` / `data-screen-a1` actually reach `<body>` — they are
//      written in a `useEffect`, which SSR skips entirely. This is the half
//      DEF-137 needs and the half a future coverage gate will read.
//   2. The tag is really in the BOTTOM-RIGHT CORNER and really INERT. A class
//      name is not a position, and `pointer-events: none` is a computed style.
//      A diagnostic that covered a row action would be a defect of its own.
//   3. It moves when the user moves. One mount above the whole router serves
//      every screen; a stale tag would name the previous screen, which is worse
//      than no tag at all.
//
// ══════════════════════════════════════════════════════════════════════════
// HOW TO RUN IT
// ══════════════════════════════════════════════════════════════════════════
//     E2E_BASE_URL=http://127.0.0.1:8080 \
//     E2E_CHROMIUM_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome \
//     npx playwright test e2e/CR-016-screen-ids.spec.ts
//
// ⚠ REBUILD THE FRONTEND FIRST. `boot_stack.sh` serves `dist/`, so a stale
// bundle reports this feature as absent — which has already cost two lanes a
// wrong conclusion on 2026-08-19.
//
// ══════════════════════════════════════════════════════════════════════════
// PROVED RED BEFORE TRUSTED GREEN
// ══════════════════════════════════════════════════════════════════════════
// Against the bundle that was serving before this lane landed — the product had
// no tag and no attribute at all — every assertion below fails, naming the
// first destination it reached:
//
//     expected 'DSH-01' but the page carries no data-screen-id at all
//
// Against the rebuilt bundle: green, and the corner check reports the tag's
// measured box.
import { expect, test } from "@playwright/test";

import { SCREEN_ROUTES, resolveScreen } from "../src/routing/screenIds";

import { baseUrl, signIn, skipUnlessAppServer, tenant } from "./support/app";

skipUnlessAppServer(test);

/** A short walk that covers the shapes, not the whole product: a plain screen,
 *  a screen whose id comes from a tab, an r10 sub-id, and — since 2026-09-03 —
 *  a screen whose id is ALLOCATED rather than drawn by r10.
 *
 *  ⚠ **THE LAST STOP USED TO BE THE OPPOSITE SHAPE AND THAT SHAPE NO LONGER
 *  EXISTS.** It read `{ path: "/audit-log", r10: null, a1: "S61" }` with the
 *  comment *"no r10 badge → no tag, by design"*, and that was true: r10 draws
 *  no audit-log screen. After the PO's instruction of 2026-09-03 (*"We need
 *  unique screen ID - on every screen"*) the missing ids are allocated in r10's
 *  own grammar in `10-scripts/gates/g29_allocated_badges.txt`, which G29 reads
 *  as a third authority — so `/audit-log` draws `SET-16` and **no mapped screen
 *  in the product has an empty corner any more.** The stop is kept at the same
 *  address on purpose: it now exercises the ALLOCATED case, which is the one
 *  shape this walk would otherwise never see. */
const WALK = [
  { path: "/dashboard", r10: "DSH-01", a1: "S7" },
  { path: "/plans-rates", r10: "PLN-01", a1: "S9" },
  { path: "/plans-rates/charges", r10: "PLN-01.charges", a1: "S9" }, // r10's sub-id
  { path: "/accounts", r10: "ACC-01", a1: "S17" },
  { path: "/payments/outstandings", r10: "PAY-02", a1: "S34" }, // A1 numbers this tab itself
  { path: "/audit-log", r10: "SET-16", a1: "S61" }, // ALLOCATED, not drawn by r10
] as const;

test.describe("CR-016 — every screen carries its id, visible and machine-readable", () => {
  test("the walk is real and agrees with the map it is checking", () => {
    // DEF-057's shape: without this, an emptied list is a loop over nothing
    // that reports itself as a pass. It also holds the walk to the MAP, so a
    // remapped screen fails here rather than silently changing what is checked.
    expect(WALK.length).toBeGreaterThanOrEqual(6);
    expect(SCREEN_ROUTES.length).toBeGreaterThanOrEqual(50);
    for (const stop of WALK) {
      const resolved = resolveScreen(`/acme${stop.path}`);
      expect(resolved.r10, `${stop.path} in the map`).toBe(stop.r10);
      expect(resolved.a1, `${stop.path} in the map`).toBe(stop.a1);
    }
  });

  test("the id is on <body> and drawn bottom-right @app-server", async ({ page }) => {
    test.setTimeout(300_000);
    await signIn(page);

    for (const stop of WALK) {
      // Client-side navigation, the way a person moves through the app, and the
      // only affordable way to walk six screens through one large chunk.
      await page.evaluate((to) => {
        window.history.pushState({}, "", to);
        window.dispatchEvent(new PopStateEvent("popstate"));
      }, `/${tenant()}${stop.path}`);
      await page.waitForURL((url) => url.pathname === `/${tenant()}${stop.path}`, {
        timeout: 30_000,
      });
      await page.waitForTimeout(1_200);

      // ── 1 · THE MACHINE-READABLE HALF, which is the durable one.
      const attributes = await page.evaluate(() => ({
        id: document.body.dataset.screenId ?? null,
        a1: document.body.dataset.screenA1 ?? null,
      }));
      expect(attributes.id, `data-screen-id on ${stop.path}`).toBe(stop.r10);
      expect(attributes.a1, `data-screen-a1 on ${stop.path}`).toBe(stop.a1);

      // CR-018 Route B: the tag is utilities now; its handle is data-testid.
      const tag = page.locator('[data-testid="screen-id-tag"]');

      if (stop.r10 === null) {
        // ⚠ NO STOP REACHES THIS BRANCH ANY MORE, AND IT IS KEPT DELIBERATELY.
        // Until 2026-09-03 `/audit-log` came through here: no authority defined
        // a badge, so the tag drew NOTHING and that absence was the finding
        // CR-016 reported. Every mapped screen now has an id, so the shape is
        // gone from the product — but the branch is the correct behaviour for a
        // screen that ships before its id is allocated, and an invented id here
        // would still have someone filing a defect against a name no authority
        // defines. What CATCHES that case is `g29_screen_ids.py`'s ratchet
        // (`screens_without_r10`, exact and currently 0), not this walk.
        await expect(tag).toHaveCount(0);
        continue;
      }

      // ── 2 · THE VISIBLE HALF, read off the rendered page.
      await expect(tag).toHaveCount(1);
      await expect(tag).toHaveText(stop.r10);

      const box = await page.evaluate(() => {
        const el = document.querySelector<HTMLElement>('[data-testid="screen-id-tag"]');
        if (el === null) {
          return null;
        }
        const rect = el.getBoundingClientRect();
        const style = getComputedStyle(el);
        return {
          right: window.innerWidth - rect.right,
          bottom: window.innerHeight - rect.bottom,
          position: style.position,
          pointerEvents: style.pointerEvents,
          // The S-id must never be rendered (PO ruling 2026-08-19).
          text: el.textContent ?? "",
        };
      });
      expect(box, `the tag's box on ${stop.path}`).not.toBeNull();
      expect(box?.position).toBe("fixed");
      // BOTTOM-RIGHT, which is where the PO asked for it and where r10 draws
      // it. r10 uses 12px from each edge; the tolerance is generous because the
      // question is "is it in that corner", not "is it at that pixel".
      expect(box?.right ?? 999).toBeLessThan(40);
      expect(box?.bottom ?? 999).toBeLessThan(40);
      // INERT: a click passes straight through to whatever is underneath. The
      // bottom-right corner is where several screens put a table's last row
      // action, so this is not a formality.
      expect(box?.pointerEvents).toBe("none");
      expect(box?.text).not.toContain(stop.a1 ?? "S-");
    }
  });

  test("the element under the tag is still clickable @app-server", async ({ page }) => {
    // `pointer-events: none` asserted above is the declaration; this is the
    // BEHAVIOUR. `elementFromPoint` answers what a real click would hit, and if
    // the tag ever intercepted one this returns the tag itself.
    await signIn(page);
    await page.waitForTimeout(1_200);
    const hit = await page.evaluate(() => {
      const el = document.querySelector<HTMLElement>('[data-testid="screen-id-tag"]');
      if (el === null) {
        return "no-tag";
      }
      const rect = el.getBoundingClientRect();
      const under = document.elementFromPoint(
        rect.left + rect.width / 2,
        rect.top + rect.height / 2,
      );
      // CR-018 Route B: comparing IDENTITY, not the class string — under a
      // utility className the old `not.toContain("screen-id-tag")` would have
      // passed even if the tag itself intercepted the click.
      return under === null ? "nothing" : under === el ? "the-tag-itself" : "something-under-it";
    });
    expect(String(hit)).not.toBe("the-tag-itself");
    expect(String(hit)).not.toBe("no-tag");
  });
});
