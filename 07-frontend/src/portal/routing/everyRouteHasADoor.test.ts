// ── Trace ──────────────────────────────────────────────
// Change:  CR-085 — the customer portal redesigned, doors first. PO, 2026-09-08,
//          after asking where four separate screens are reached from and being
//          told wrongly each time: *"all your screens are good - only problem is
//          door to that screen. when you mention that door is from x screen -
//          when we check x screen we dont find the door there"*
// Defects: DEF-CWP-4654 (`/stop-or-restart` — no door ANYWHERE, so a customer
//          could not stop service) · DEF-CWP-4655 (`/visit/:slug` — the list is
//          reachable and the detail is not) · DEF-CWP-4652 (Past due, no door
//          from Home) · DEF-CWP-4653 (budget billing behind hardship)
// Rules:   hard-won law 2's mirror — a live screen behind a dead control; this
//          is the OTHER mirror, a live screen behind NO control at all
// ───────────────────────────────────────────────────────
/**
 * EVERY REGISTERED PORTAL ROUTE MUST HAVE A DOOR.
 *
 * WHY NOTHING ELSE CATCHES THIS, WHICH IS THE WHOLE POINT
 * ------------------------------------------------------
 * On 2026-09-08 four screens were found unreachable or good-as-unreachable, and
 * **every check in this repository passed on all four.** `tsc` passes — the
 * route is registered and the component compiles. The 58 portal test files pass
 * — each screen is tested by rendering it AT ITS OWN ADDRESS, which is the one
 * place in the product where a door is not needed. `G13` passes — it asks
 * whether a prop is passed, and these props are passed. The hold-expiry work
 * passes — it asks whether a refusal is still true, and there is no refusal
 * here, just silence.
 *
 * Two questions were being confused for months:
 *
 *   * **Is this screen built?** — `portalRoutes.tsx` answers it and every test
 *     asserts it.
 *   * **Can a customer REACH it from where they are standing?** — nothing
 *     anywhere asked, until a human did.
 *
 * ⚠ **WHAT THIS CATCHES, AND WHAT IT HONESTLY CANNOT.**
 * It catches **no door anywhere** — the `/stop-or-restart` and `/visit/:slug`
 * shape. It does **not** catch **a door that is not where a person would look**,
 * which was the more common half of that day: Past due had a door (from Bills)
 * and budget billing had a door (from Help paying), and both were still wrong
 * because the door was in the wrong place. **No check can find that.** It needs
 * somebody to ask *where would a person go looking for this*, which is exactly
 * what the PO did four times. This test is the cheap half; the expensive half
 * stays human, and saying so here is the point of this paragraph.
 *
 * ⚠ **THERE ARE THREE WAYS TO WRITE A DOOR AND THIS CHECK NEEDED ALL THREE.**
 * It was built matching one, then two, and each time the run named healthy
 * screens: a quoted `to="/x"` misses `` `/pay/done` ``; adding backticks still
 * missed `` `/bills/${n}/document` `` because only the text before the first
 * `${` was captured; and both together still condemned `/pay/check` and
 * `/pay/done`, which the quick-pay wizard reaches by `navigate()` with no
 * anchor at all. **Five healthy routes failed before the matcher was right.**
 * That mattered more than the true findings: a guard that cries wolf on five
 * real screens is silenced by whoever meets it next, and then catches nothing —
 * law 7's *incapable of passing*, which is as useless as *incapable of
 * failing*. Every one of the three forms below is in the product today.
 */
import { describe, expect, it } from "vitest";

/**
 * Every portal source, read by Vite rather than by `node:fs`.
 *
 * ⚠ **`node:fs` COMPILED AND DID NOT TYPE-CHECK.** The first version of this
 * file read the tree with `readdirSync`. It ran green under vitest — which has
 * a Node runtime — and `tsc` then failed with *cannot find module 'node:fs'*,
 * because this front end has no `@types/node` and deliberately depends on no
 * Node types at all. `import.meta.glob` is Vite's own, needs no dependency, and
 * resolves at build time, so the set is fixed before a single test runs.
 */
const SOURCES = import.meta.glob("../**/*.tsx", { query: "?raw", import: "default", eager: true });
const ROUTE_TABLE = import.meta.glob("./portalRoutes.tsx", {
  query: "?raw",
  import: "default",
  eager: true,
})["./portalRoutes.tsx"] as string;

/** `to="/x"`, `to: "/x"`, `to={path("/x")}` — a link written out in full. */
const LINK_LITERAL = /to[:=]\s*\{?\s*(?:path\()?\s*"(\/[a-z0-9/:-]*)"/g;
/**
 * Any backtick string that looks like a portal path, WITH its interpolations
 * folded back to `:param` so it lines up with the route table.
 *
 * ⚠ **THIS SHAPE WAS FOUND BY WATCHING THE CHECK FAIL WRONGLY, NOT BY THINKING
 * ABOUT IT.** The first version matched only the text BEFORE the first `${`,
 * so `` `/bills/${n}/document` `` registered as a door to `/bills` and left
 * `/bills/:number/document` looking unreachable — and a bare `` `/pay/done` ``
 * with no interpolation at all was missed entirely, because the literal matcher
 * above wants quotes. Five healthy routes failed. A guard that cries wolf on
 * five real screens is silenced by whoever meets it next, and then catches
 * nothing — so the false positives mattered more than the true one.
 */
const LINK_BACKTICK = /`(\/[a-z0-9/-]*(?:\$\{[^`]*?\}[a-z0-9/-]*)*)`/g;
const AS_PARAM = /\$\{[^}]*\}/g;
/**
 * `navigate(path("/pay/check"))` — a door with no anchor, which is the right
 * shape for a step inside a flow: you arrive by finishing the step before it.
 *
 * ⚠ **THE THIRD FORM, AND IT COST A FALSE POSITIVE TO FIND.** With only the two
 * above, `/pay/check` and `/pay/done` looked unreachable — the quick-pay wizard
 * moves between its own steps programmatically and never renders a link to
 * them. Three ways to write a door and a check that knew two of them would have
 * condemned a working payment flow.
 */
const LINK_NAVIGATE = /navigate\(\s*(?:path\()?\s*"(\/[a-z0-9/:-]*)"/g;

/**
 * A route reached ONLY from outside the product. Each needs a reason, and
 * "nothing links to it" is never one — that is the defect this file exists for.
 */
const REACHED_FROM_OUTSIDE: Readonly<Record<string, string>> = {
  // A resume link emailed to somebody who abandoned the move-in form. There is
  // deliberately no in-product door: the draft token IS the address, and a list
  // of other people's unfinished applications is not a screen we want.
  "/start-service/:draft": "emailed resume link, US-CWP-018",
  // CR-189-BRC10 — the door is forgot-password's *Update your registered
  // email*, built by the PORTAL-RESET lane as `to={path(UPDATE_EMAIL_PATH)}`,
  // a constant this scan cannot read. `UpdateEmail.dom.test.tsx` asserts that
  // constant equals this route. Remove this line if the link is ever written
  // as a literal.
  "/update-email": "forgot-password's link (UPDATE_EMAIL_PATH), CR-189-BRC10",
};

describe("every registered portal route has a door", () => {
  const routes = [...ROUTE_TABLE.matchAll(/path: "(\/[a-z0-9/:-]*)"/g)].map((m) => m[1]);

  const linked = new Set<string>();
  for (const [file, source] of Object.entries(SOURCES)) {
    // The route table is not a door, and neither is a test.
    if (file.includes(".test.") || file.endsWith("portalRoutes.tsx")) continue;
    const text = source as string;
    for (const m of text.matchAll(LINK_LITERAL)) linked.add(m[1]);
    for (const m of text.matchAll(LINK_NAVIGATE)) linked.add(m[1]);
    for (const m of text.matchAll(LINK_BACKTICK)) {
      // `/bills/${n}/document` → `/bills/:p/document`, which is what the route
      // table calls it once the parameter name is set aside.
      linked.add(m[1].replace(AS_PARAM, ":p"));
    }
  }

  it("finds the route table and the links, so a green run means something", () => {
    // ⚠ Law 7: a check that silently measures nothing passes forever. If the
    // route table moves or the link syntax changes, these two numbers collapse
    // and this assertion says so before any route is called reachable.
    expect(routes.length).toBeGreaterThan(40);
    expect(linked.size).toBeGreaterThan(30);
  });

  it.each(routes.filter((r) => r !== "/" && !(r in REACHED_FROM_OUTSIDE)))(
    "%s is reachable from somewhere",
    (route) => {
      // A parameterised route is reached by its constructed prefix.
      const normalised = route.replace(/\/:[a-z]+/gi, "/:p");
      const reachable = linked.has(route) || linked.has(normalised);
      expect(
        reachable,
        `${route} is registered and rendered, and NOTHING in the portal links to it. ` +
          `A customer can only arrive by typing the address. Give it a door, or — if it ` +
          `is genuinely reached from outside the product — add it to REACHED_FROM_OUTSIDE ` +
          `with the reason. "Nothing links to it" is not a reason.`,
      ).toBe(true);
    },
  );
});
