// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-SHL-6378 (2026-09-23) — Session expired's Sign in carries the
//          page back (`?next=`), and a parameter that decides where a browser
//          goes after a password is typed is the textbook open redirect.
// Rules:   BR-TEN-003 (the tenant comes from the URL the person is on, never a
//          value somebody could set) · BR-SHL-009 (the way out is the tenant's
//          OWN sign-in page)
// ───────────────────────────────────────────────────────
import { describe, expect, it } from "vitest";

import {
  RETURN_PARAM,
  safeReturnPath,
  signInAgainDestination,
  signOutDestination,
  tenantPathFrom,
} from "@/routing/tenantPath";

describe("DEF-SHL-6378 (d) — the return path refuses anything that could leave this tenant", () => {
  it("keeps an ordinary page, with its filters", () => {
    expect(safeReturnPath("/payments")).toBe("/payments");
    expect(safeReturnPath("/payments?q=smith&page=2")).toBe("/payments?q=smith&page=2");
    expect(safeReturnPath("/accounts/ACC-000123/billing")).toBe("/accounts/ACC-000123/billing");
    // A query value may be anything a filter box accepts; it cannot move the page.
    expect(safeReturnPath("/payments?q=a%2Fb%3F..%2F")).toBe("/payments?q=a%2Fb%3F..%2F");
  });

  it.each([
    ["an absolute URL to another site", "https://evil.example/phish"],
    ["a protocol-relative URL", "//evil.example/phish"],
    ["a backslash a browser reads as a slash", "/\\evil.example"],
    ["a script URL", "javascript:alert(1)"],
    ["a bare word", "payments"],
    ["a climb out of the tenant", "/../other-utility/payments"],
    ["a climb in the middle", "/payments/../../other-utility"],
    ["a percent-encoded climb", "/%2e%2e/other-utility"],
    ["a mixed-case encoded climb", "/.%2E/other-utility"],
    ["a DOUBLE-encoded climb", "/%252e%252e/other-utility"],
    ["an encoded protocol-relative URL", "/%2F%2Fevil.example"],
    ["an encoded backslash", "/%5Cevil.example"],
    ["a control character", "/payments\n/evil"],
    ["an empty value", ""],
    ["no value at all", null],
    ["the sign-in page itself (a loop)", "/signin"],
    ["an address longer than any we build", `/payments?q=${"x".repeat(2100)}`],
  ])("refuses %s", (_label, raw) => {
    expect(safeReturnPath(raw)).toBeNull();
  });

  it("a refused value can only ever land on this tenant's Dashboard, never elsewhere", () => {
    // The sign-in page prefixes whatever survives with ITS OWN tenant, so even a
    // kept value cannot name another utility: the prefix is not the value's.
    expect(tenantPathFrom("brazosbend", safeReturnPath("/payments") ?? "/dashboard")).toBe(
      "/brazosbend/payments",
    );
    expect(tenantPathFrom("brazosbend", safeReturnPath("//evil.example") ?? "/dashboard")).toBe(
      "/brazosbend/dashboard",
    );
  });
});

describe("DEF-SHL-6378 (c) — Sign in goes to the tenant's own door, carrying the page", () => {
  it("is sign-out's own address plus the tenant-relative page, encoded once", () => {
    expect(signInAgainDestination("/brazosbend/payments", "?q=smith")).toBe(
      `${signOutDestination("/brazosbend/payments")}?${RETURN_PARAM}=%2Fpayments%3Fq%3Dsmith`,
    );
    expect(signInAgainDestination("/brazosbend/payments", "?q=smith")).toBe(
      "/brazosbend/signin?next=%2Fpayments%3Fq%3Dsmith",
    );
  });

  it("keeps a wizard's draft handle, so Move-in resumes where it was saved", () => {
    expect(signInAgainDestination("/brazosbend/accounts/move-in", "?parked=wp-1&step=3")).toBe(
      "/brazosbend/signin?next=%2Faccounts%2Fmove-in%3Fparked%3Dwp-1%26step%3D3",
    );
  });

  it("with no tenant in scope, it is the help page and carries nothing", () => {
    expect(signInAgainDestination("/", "")).toBe("/signin-help");
  });
});
