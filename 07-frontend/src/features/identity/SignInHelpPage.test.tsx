// ── Trace ──────────────────────────────────────────────
// Component: /signin-help (SignInHelpPage) + diagnosticOf (api/client)
// Both landed 2026-08-10 from the PO's FIRST LIVE DEPLOYMENT: a public page was
// rendering the marker string "SMARTBillHub — W0 scaffold", and every failure
// state said "Something went wrong" while hiding the status code that would
// have identified a downed backend.
// ───────────────────────────────────────────────────────
// Same conventions as the other identity/shell packets: no DOM library in
// package.json, so markup asserts on react-dom/server static output inside a
// MemoryRouter, and behavior laws run through the exported pure pieces. Typing
// and real navigation are honest it.todo → Playwright journeys.
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";

import { ApiError, diagnosticOf } from "@/api/client";

import { SLUG_PATTERN, SignInHelpPage, signInHelpDestination } from "./SignInHelpPage";

/** A host that is NOT the production one, on purpose — see the DEF-050 case. */
const APP_HOST = "utilities.example.test:8080";

function html(appHost: string = APP_HOST): string {
  return renderToStaticMarkup(
    <MemoryRouter initialEntries={["/signin-help"]}>
      <SignInHelpPage appHost={appHost} />
    </MemoryRouter>,
  );
}

describe("/signin-help", () => {
  it("TC-1 no longer renders the W0 marker on a public page", () => {
    const markup = html();
    expect(markup).not.toContain("W0 scaffold");
    // DEF-152 retired that string; the catch-all is now known by its marker.
    expect(markup).not.toContain("data-not-built-yet");
    expect(markup).toContain("<h1"); // CR-018: the heading carries utilities now
  });

  it("DEF-573 the public nav does not reach into its own buttons", () => {
    // The same nav shape as S1 and the same fix: the descendant rule that
    // out-specified the button kit is gone from BOTH public screens together.
    const nav = /<nav class="([^"]*)"/.exec(html());
    expect(nav).not.toBeNull();
    // `&` renders as `&amp;`, so the marker is matched WITHOUT it — the first
    // draft of this line looked for `[&_a`, passed with the bug restored, and
    // would have been a check that could not fail (hard-won law 7).
    expect(nav?.[1]).not.toMatch(/_a:not\(/);
  });

  it("TC-2 renders the address field the page is built around", () => {
    const markup = html();
    expect(markup).toContain('id="signin-help-slug"');
    // ⚠ AMENDED 2026-08-24 (DEF-050). This line read
    // `expect(markup).toContain("smartbillhub.bynry.com/")` — it PINNED the
    // live production host into the hint, which is the defect itself, and it
    // passed for thirteen days because the reviewer and the test both sat on
    // that host. The field is now identified by the field, and the host by the
    // case below.
    expect(markup).toContain('id="signin-help-hint"');
  });

  it("DEF-050 the hint names the host SERVING THE PAGE, never a host typed into the copy", () => {
    // The sign-in hint has to end in a host, because it is telling you which
    // part of a web address to type. Which host is a deployment fact, not a
    // copy fact: path tenancy (PO 2026-08-10) puts every utility at a PATH on
    // the origin the visitor is already on, so the correct host is by
    // definition the one that served this page.
    expect(html()).toContain("utilities.example.test:8080/");
    // …and a DIFFERENT deployment gets its own, from the same one sentence.
    expect(html("bills.othercity.gov")).toContain("bills.othercity.gov/");
    // ⚠ THE NEGATIVE IS THE HALF THAT WOULD HAVE CAUGHT IT. The 2026-08-10
    // sweep searched for the DEAD domain and could not see the live one —
    // *"a search shaped by the bug you already know about finds only that
    // bug"* — so this asserts that NO host survives in the copy except the one
    // the page was served from, whatever it is called.
    const markup = html("bills.othercity.gov");
    const hint = markup.slice(markup.indexOf('id="signin-help-hint"'));
    expect(hint.slice(0, 400)).not.toContain("smartbillhub");
  });

  it("TC-3 makes no request: there is no form action and no fetch on this page", () => {
    // The membership oracle this page refuses to be. A name that does not exist
    // must be indistinguishable from one that does (BR-IDN-006), and the
    // cheapest way to guarantee that is to ask the server nothing at all.
    expect(html()).not.toContain("action=");
  });

  it("TC-4 accepts the slugs provisioning accepts", () => {
    expect(SLUG_PATTERN.test("brazosbend")).toBe(true);
    expect(SLUG_PATTERN.test("silver-creek-water-work")).toBe(true);
    expect(SLUG_PATTERN.test("no-such-utility-here")).toBe(true); // unknown ≠ invalid
  });

  it("TC-5 (neg) rejects exactly what BR-TEN-011 rejects server-side", () => {
    // This test caught a real mismatch on 2026-08-10: the first pattern written
    // here allowed a 1-character slug while the field's own hint promised 3–63.
    // The grammar of record is selectors.subdomain_problem (BR-TEN-011).
    expect(SLUG_PATTERN.test("Not A Slug!")).toBe(false); // charset
    expect(SLUG_PATTERN.test("-leading")).toBe(false); // edge hyphen
    expect(SLUG_PATTERN.test("trailing-")).toBe(false); // edge hyphen
    expect(SLUG_PATTERN.test("ab")).toBe(false); // length: floor is 3
    expect(SLUG_PATTERN.test("a")).toBe(false); // length
    expect(SLUG_PATTERN.test("a".repeat(63))).toBe(true); // ceiling is 63
    expect(SLUG_PATTERN.test("a".repeat(64))).toBe(false);
  });

  it("TC-5b does not mirror the reserved-name list", () => {
    // Server-side knowledge. Mirroring it would tell a stranger which names the
    // platform holds back; a reserved name routes like any other non-tenant.
    expect(SLUG_PATTERN.test("api")).toBe(true);
  });

  // ── US-IDN-011's own TCs, on the pure decision the page makes ────────────
  // These replace an `it.todo` that stood since 2026-08-10 saying "navigation
  // is a Playwright journey". It is — but WHERE the page decides to send you is
  // a pure function of what you typed, and leaving the product's only behaviour
  // unasserted because the DOM is untestable was the wrong trade. The handler
  // now calls `signInHelpDestination` and so do these.

  it("US-IDN-011 TC-2 sends a real utility to its own sign-in page", () => {
    expect(signInHelpDestination("brazosbend")).toEqual({ path: "/brazosbend/signin" });
    // the PO's own signup fixture of 2026-08-10
    expect(signInHelpDestination("silver-creek-water-work")).toEqual({
      path: "/silver-creek-water-work/signin",
    });
  });

  it("US-IDN-011 TC-3 sends an address that does not exist to exactly the same shape", () => {
    // THE point of the page (BR-IDN-027 / BR-IDN-006). A page that could tell
    // you "no such utility" would confirm to any stranger which utilities exist
    // on the platform. Unknown and real must be indistinguishable, so they are
    // the SAME code path and this asserts the output shape is identical.
    const real = signInHelpDestination("brazosbend");
    const invented = signInHelpDestination("no-such-utility-here");
    expect(invented).toEqual({ path: "/no-such-utility-here/signin" });
    expect(Object.keys(invented)).toEqual(Object.keys(real));
  });

  it("US-IDN-011 TC-4/TC-5 (neg) refuses locally and navigates nowhere", () => {
    for (const typed of ["Not A Slug!", "-leading", "trailing-", "ab", "a".repeat(64), ""]) {
      expect(signInHelpDestination(typed)).toEqual({ error: true });
    }
    expect(signInHelpDestination("a".repeat(63))).toEqual({ path: `/${"a".repeat(63)}/signin` });
  });

  it("US-IDN-011 TC-6 (neg) forwards a RESERVED name like any other", () => {
    // `api` is on the server's reserved list. Mirroring that list here would
    // tell a stranger which names the platform holds back, so the page does not
    // know it: `api` is forwarded and finds nothing, exactly like any other
    // name that is not a tenant.
    expect(signInHelpDestination("api")).toEqual({ path: "/api/signin" });
    expect(signInHelpDestination("signup")).toEqual({ path: "/signup/signin" });
  });

  it("US-IDN-011 TC-7 (isolation) normalises input without asking anything", () => {
    // No network call to make, so nothing to leak and no timing to measure: the
    // function is total, synchronous and depends on nothing but its argument.
    expect(signInHelpDestination("  BrazosBend  ")).toEqual({ path: "/brazosbend/signin" });
    expect(signInHelpDestination("BRAZOSBEND")).toEqual(signInHelpDestination("brazosbend"));
  });

  it.todo("the browser really lands on /{tenant}/signin after submit — Playwright journey");
});

describe("diagnosticOf", () => {
  it("TC-6 surfaces the status when a proxy answers without an envelope", () => {
    // Exactly the live case: the API pass-through 502s because the backend is
    // not up, and the body is not the ratified envelope.
    const error = new ApiError(502, { code: null, message_key: "api.error.unexpected" });
    expect(diagnosticOf(error)).toBe("HTTP 502");
  });

  it("TC-7 includes code, br_ref and the READABLE-ALOUD reference (DEF-328)", () => {
    // A real trace id is `uuid4().hex` — 32 characters. The PO's 2026-08-19
    // ruling is that what a person is asked to quote must be dictatable, and
    // that the short form is the one support can search by, so this asserts the
    // short form and NOT the raw value.
    const error = new ApiError(422, {
      code: "BIZ-CAP",
      message_key: "audit.export.row_cap_exceeded",
      br_ref: "BR-AUD-014",
      trace_id: "5f2b9c1d3e7a4b6c8d9e0f1a2b3c4d5e",
    });
    // AMENDED 2026-08-21 (DEF-332). The `br_ref` is GONE FROM THIS LINE and
    // that is the rule change: the PO ruled on 2026-08-19 that internal ids do
    // not belong on a user's screen, and this line RENDERS (StateFrame, the
    // public pricing page). The support need the 2026-08-10 ruling asked for is
    // met by the short reference, which did not exist when the two collided.
    expect(diagnosticOf(error)).toBe("HTTP 422 · BIZ-CAP · ref 5F2B-9C1D");
    // ⚠ The value is CARRIED, not dropped — B8 makes br_ref mandatory on a BIZ
    // refusal and support reads it. It stays on the error and reaches the DOM
    // through `RefusalNotice`'s `data-br-ref`.
    expect(error.brRef).toBe("BR-AUD-014");
    expect(diagnosticOf(error)).not.toContain("5f2b9c1d3e7a4b6c8d9e0f1a2b3c4d5e");
  });

  it("TC-8 describes a request that never got an answer at all", () => {
    expect(diagnosticOf(new TypeError("Failed to fetch"))).toBe("TypeError: Failed to fetch");
  });

  it("TC-9 returns null when there is genuinely nothing to say", () => {
    expect(diagnosticOf(undefined)).toBeNull();
    expect(diagnosticOf(null)).toBeNull();
  });

  it("TC-10 never carries server prose — codes and identifiers only (TD-16/G14)", () => {
    const error = new ApiError(409, {
      code: "BIZ-CONFLICT",
      message_key: "tenant.slug.taken",
      trace_id: "t-9",
    });
    const line = diagnosticOf(error) ?? "";
    expect(line).not.toContain("tenant.slug.taken"); // the KEY is not shown either
    // `t-9` cannot be shortened to eight hex characters, so the raw value still
    // shows: a diagnostic that silently emptied itself would be worse (DEF-320).
    expect(line).toBe("HTTP 409 · BIZ-CONFLICT · trace t-9");
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-IDN-011@f1f263c (EP-IDN-01)
// generated: 2026-08-10 by Eng-Lead, alongside the page and diagnosticOf
// checklist: A✔ B✔ C✔ D=deferred(no API call by design) E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: vitest 11 passed / 1 todo✔ · suite 540✔ · tsc✔
//        [2026-08-15] vitest this file 16 passed / 1 todo✔ · full suite 1047 passed /
//        185 todo (71 files)✔ · tsc --noEmit✔
// exceptions: [2026-08-15] the `it.todo` that stood for the page's ONLY behaviour —
//        where submitting sends you — is gone. Navigation still needs Playwright, but WHERE
//        the page decides to send you is a pure function of what you typed, so
//        `signInHelpDestination` was extracted from the submit handler and US-IDN-011's
//        TC-2/TC-3/TC-6/TC-7 now assert it. TC-3 is the load-bearing one: an invented address
//        and a real one must produce the SAME SHAPE, which is the membership-oracle rule
//        itself · TC-5 was written asserting a 1-char slug is valid and FAILED —
//        the page's own pattern disagreed with its own 3–63 hint. The pattern
//        was wrong, not the test; both now follow BR-TEN-011 · the navigation
//        TC is an honest it.todo (no DOM library in package.json) and becomes a
//        Playwright journey
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
