// ── Trace ──────────────────────────────────────────────
// Story:    US-SHL-005 (EP-SHL-01 — sidebar footer user block & S48 user menu)
//           Screens: shell-chrome, S48, S3 (the sign-out destination)
// Rules:    BR-SHL-008 (user block + the four-item menu) ·
//           BR-SHL-009 (sign out ends the session, clears every client cache,
//           and — PO 2026-08-11 — returns to the TENANT'S sign-in page) ·
//           BR-SHL-025 (an unavailable affordance renders disabled WITH its reason)
// ───────────────────────────────────────────────────────
// The tests DEF-008 never had. Its escape_reason in 12-governance/10-defect-log.csv
// reads "no E2E journey covers sign-out", and there was no unit test either —
// `ShellWithSession` shipped 2026-08-10 with no test file at all, which is how
// a redirect that drops the tenant slug (DEF-037) reached the live app.
//
// Same conventions as AppShell.test.tsx: no DOM library in package.json, so the
// laws that can be stated purely are stated purely, and markup is asserted on
// react-dom/server static output. Two things that a click would prove in a
// browser are proven here another way, on purpose:
//
//   · WHERE sign-out goes — `signOutDestination` is a pure function of the
//     pathname, so the rule is provable with no browser and no session.
//   · THAT the shell actually calls it — hard-won law 2. The helper existing is
//     not the fix; being called is. DEF-007..010 were four components that were
//     built, styled, tested and never given their data, and this file reads the
//     wiring rather than assuming it (the same thing G13 does at gate level).
import { describe, expect, it } from "vitest";

import { WORK_ESCALATION_BELL_KEYS, bellTextFor } from "@/components/ShellWithSession";
import "@/i18n";
import i18n from "@/i18n";
import { HOME_ROUTE, SIGNIN_HELP_ROUTE, signOutDestination } from "@/routing/tenantPath";

// The module's own source, via Vite's `?raw` loader — no `@types/node` in this
// project, and adding a dependency to read one file would be the wrong trade.
import SHELL_SOURCE from "./ShellWithSession.tsx?raw";

// The PO's own report, 2026-08-11, verbatim: signing out of Silver Creek Water
// landed on `https://smartbillhub.bynry.com/` and must land on
// `https://smartbillhub.bynry.com/silver-creek-water/signin`.
const TENANT = "silver-creek-water";
const TENANT_SIGNIN = `/${TENANT}/signin`;

describe("CR-048 wave D — the utility's mark reaches the shell", () => {
  it("hard-won law 2: `tenantMark` is PASSED, not merely accepted", () => {
    // `AppShell` accepts `tenantMark?: ReactNode`. An optional prop nothing
    // passes is dead UI — this file exists because that happened four times in
    // this exact component. The source is read the same way sign-out is below.
    expect(SHELL_SOURCE).toContain("tenantMark=");
    expect(SHELL_SOURCE).toContain("BrandMark");
    // It is fed from the company profile the shell ALREADY fetches, so the
    // mark and the tenant name can never disagree about which utility this is.
    expect(SHELL_SOURCE).toContain("company.mark");
    expect(SHELL_SOURCE).toContain("company.has_logo");
  });
});

describe("US-SHL-005 TC-5 / BR-SHL-009 — sign-out returns to the TENANT'S sign-in page", () => {
  it("DEF-037: signing out of /silver-creek-water/dashboard lands on /silver-creek-water/signin, not on /", () => {
    expect(signOutDestination(`/${TENANT}/dashboard`)).toBe(TENANT_SIGNIN);
    // The exact defect, stated as its own assertion so a regression names it:
    // the bare host is the PUBLIC pricing page and is not a route this product
    // serves per tenant.
    expect(signOutDestination(`/${TENANT}/dashboard`)).not.toBe(HOME_ROUTE);
  });

  it("BR-SHL-009: the tenant is taken from the URL, so every tenant gets its OWN door", () => {
    expect(signOutDestination("/brazosbend/billing/bills/abc")).toBe("/brazosbend/signin");
    expect(signOutDestination("/lonestar/settings/company")).toBe("/lonestar/signin");
    // Nothing is hardcoded: two tenants, one code path, two destinations.
    expect(signOutDestination("/lonestar/dashboard")).not.toContain("brazosbend");
  });

  it("BR-SHL-009: depth and query-shaped tails never change the destination", () => {
    for (const path of [
      `/${TENANT}`,
      `/${TENANT}/`,
      `/${TENANT}/accounts/0198ffff-dead-7000-a000-000000000000/move-out`,
      `/${TENANT}/plans-rates/plans/new`,
    ]) {
      expect(signOutDestination(path)).toBe(TENANT_SIGNIN);
    }
  });

  it("BR-TEN-003: with no tenant in scope the fallback ASKS which utility — it never invents one", () => {
    // Unreachable from the shell (every authenticated URL carries a tenant);
    // asserted so the function is total and so nobody later "helpfully" makes
    // it guess a tenant, which would point a signed-out user at another
    // utility's sign-in page.
    expect(signOutDestination("/")).toBe(SIGNIN_HELP_ROUTE);
    expect(signOutDestination("/pricing")).toBe(SIGNIN_HELP_ROUTE);
    expect(signOutDestination("/signup")).toBe(SIGNIN_HELP_ROUTE);
  });

  it("law 2 (built is not wired): the shell's sign-out NAVIGATES to that helper's result", () => {
    // DEF-007..010 were all "the code exists and nothing calls it". A correct
    // `signOutDestination` that ShellWithSession does not use would leave the
    // live app exactly as broken while every assertion above stayed green.
    expect(SHELL_SOURCE).toContain("signOutDestination(pathname)");
    expect(SHELL_SOURCE).toContain("navigate(signOutTo, { replace: true })");
    // …and the old destination is gone, not merely shadowed.
    expect(SHELL_SOURCE).not.toContain("navigate(HOME_ROUTE");
  });

  it("BR-SHL-009 (the clause that is easy to miss): the client cache is cleared on the way out", () => {
    // Ending the session server-side is not enough while a TanStack cache still
    // holds the tenant's accounts and invoices in memory. Pinned here because
    // the redirect fix touches the same callback.
    expect(SHELL_SOURCE).toContain("queryClient.clear()");
  });

  it.todo(
    "US-SHL-005 TC-5 (browser half): after sign-out, pressing Back or deep-linking /{tenant}/dashboard re-prompts for sign-in and renders no cached tenant data — needs a live browser + server (E2E journey; DEF-008's escape_reason names the missing journey)",
  );
});

// ══════════════════════════════════════════════════════════════════════════
// CR-009 · THE BELL IS WIRED — hard-won law 2, the FOURTH time in this file
// ══════════════════════════════════════════════════════════════════════════
describe("US-NOT-018 / BR-NOT-019 — the notifications bell is finally given its data", () => {
  it("law 2 (built is not wired): the shell PASSES bellItems, which nothing ever did before", () => {
    // ⚠ THIS IS THE ASSERTION THAT MATTERS. `AppShell` has rendered a bell
    // badge, a popover, a list and a "Mark all read" button since 2026-08-09,
    // driven entirely by three OPTIONAL props — and its own comment admitted
    // the state of it: *"BE-09 wiring later"*. Every AppShell bell test passed
    // by supplying those props itself. In the running product the popover was
    // permanently empty, because the only component that renders AppShell
    // passed none of them.
    //
    // That is exactly the shape of DEF-007..010: built, styled, tested, and
    // never given its data.
    expect(SHELL_SOURCE).toContain("bellItems={bellItems}");
    expect(SHELL_SOURCE).toContain("onBellSelect=");
    expect(SHELL_SOURCE).toContain("onMarkAllRead=");
  });

  it("the items come from the SERVER's inbox read, not from a placeholder", () => {
    // A hardcoded demo array would satisfy the assertions above and prove
    // nothing — the PO's whole point is that a message ARRIVING is the proof.
    expect(SHELL_SOURCE).toContain("getInAppMessages");
    expect(SHELL_SOURCE).toContain("queryKeys.inAppMessages");
  });

  it("BR-NOT-005: the shell reads and marks read — it has no way to SEND anything", () => {
    // In-app is the first channel that can actually deliver, so it is the first
    // place a send call would have appeared to work. The three wrappers this
    // file may call are named; a send is not one of them.
    expect(SHELL_SOURCE).not.toContain("sendNotification");
    expect(SHELL_SOURCE).not.toContain("/in-app-messages/send");
  });

  it("BR-NOT-020: the failure count survives the trip to a one-line bell item", () => {
    // The count is at the END of the body and it is the part a clerk must see,
    // so the body is COLLAPSED and never truncated. A `…` here would cut off
    // exactly the number BR-NOT-020 exists to deliver.
    const line = bellTextFor({
      subject: null,
      body: "Billing run finished.\n\n1204 processed · 3 failed\n2026-08-17",
    });
    expect(line).toBe("Billing run finished. 1204 processed · 3 failed 2026-08-17");
    expect(line).toContain("3 failed");
    expect(line).not.toContain("…");
    expect(line).not.toContain("\n");
  });

  it("CR-168 §F — a field-work message is said in the clerk's language, plural keys included", () => {
    const translate = { exists: (k: string, p?: Record<string, unknown>) => i18n.exists(k, p), t: (k: string, p?: Record<string, unknown>) => i18n.t(k, p) };
    const body = "WO-0046 has field items that need review (6).\n2026-10-04";
    expect(
      bellTextFor({ subject: null, body, message_key: "notifications.fieldWork.needsReview", params: { order: "WO-0046", count: 6 } }, translate),
    ).toBe(i18n.t("notifications.fieldWork.needsReview", { order: "WO-0046", count: 6 }));
    expect(
      bellTextFor({ subject: null, body, message_key: "notifications.fieldWork.photosComplete", params: { order: "WO-0046", count: 0 } }, translate),
    ).toBe(i18n.t("notifications.fieldWork.photosComplete", { order: "WO-0046" }));
    // A key this build does not know falls back to the utility's body, never the raw key.
    expect(bellTextFor({ subject: null, body, message_key: "notifications.fieldWork.nope", params: {} }, translate)).toBe(
      "WO-0046 has field items that need review (6). 2026-10-04",
    );
  });

  it("CR-168 P3.57 — a Work escalation and a reminder are said in the clerk's language", () => {
    const translate = { exists: (k: string, p?: Record<string, unknown>) => i18n.exists(k, p), t: (k: string, p?: Record<string, unknown>) => i18n.t(k, p) };
    const body = "WO-0041 has nobody assigned after 4 h\n2026-10-04";
    expect(
      bellTextFor({ subject: null, body, message_key: "notifications.workEscalation.unassigned", params: { order: "WO-0041", count: 4 } }, translate),
    ).toBe("WO-0041: nobody assigned after 4 h");
    for (const key of WORK_ESCALATION_BELL_KEYS) expect(i18n.exists(key, { order: "WO-1", name: "D. Ortiz", count: 2 })).toBe(true);
  });

  it("a subject rides in front when a class has one (none does today)", () => {
    expect(bellTextFor({ subject: "Run complete", body: "40 processed · 0 failed" })).toBe(
      "Run complete — 40 processed · 0 failed",
    );
  });

  it.todo(
    "US-NOT-018 (browser half): a real staff event queued, dispatched and read in a booted app — the bell badge showing 1, the popover showing the summary and the badge clearing on open. Proved by hand with manage.py send_bulk_summary + dispatch_outbound and recorded in the lane report; it needs an E2E journey to become a gate",
  );
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-SHL-005@b16a4de (story+rules snapshot hash — EP-SHL-01)
// generated: 2026-08-11 by story-coder v1 (S48 user-menu lane — from the PO's live-app report of 2026-08-11)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ eslint✔ vitest✔ run_gates 15 PASS · 0 FAIL · 1 SKIP✔ · RED-PROVED FIRST (law 7): with `signOutDestination` returning the deployed behaviour, 4 of these 6 failed — "expected '/' to be '/silver-creek-water/signin'" — and went green on the one-line fix
// exceptions: E4 the "is it wired" assertions read this module's own SOURCE rather than clicking the menu — package.json carries no DOM library, and a component test that cannot click is worse evidence than reading the call site. Stated rather than dressed up as a behavioural test
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
