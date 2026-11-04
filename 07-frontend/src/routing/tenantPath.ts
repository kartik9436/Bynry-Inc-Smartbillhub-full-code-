// ── Trace ──────────────────────────────────────────────
// Story:    US-SHL-001 (the shell's nav/breadcrumb targets) · US-SHL-002 (breadcrumb) ·
//           US-SHL-005 (where sign-out lands) ·
//           US-IDN-001 (per-tenant sign-in) · US-TEN-001 (signup lands the owner in the new tenant) ·
//           US-TEN-003 (the S62 checklist's deep links)
//           Screens: every authenticated screen (S7–S114) plus S3 and S110–S114
// Rules:    BR-TEN-003 (the tenant is resolved from the REQUEST, never from client input — PO 2026-08-10
//           moves the SOURCE from the Host's first label to the URL's first PATH segment) ·
//           BR-IDN-001 (resolve the tenant FIRST, then the credentials) ·
//           BR-SHL-001 (sidebar targets) · BR-SHL-004 (breadcrumb ancestors) ·
//           BR-SHL-009 (sign out returns to the TENANT'S sign-in page — PO 2026-08-11)
// ───────────────────────────────────────────────────────
// PO ruling 2026-08-10 — TENANCY IS PATH-BASED. One origin serves every tenant:
//
//   SPA   `/{tenant}/…`      e.g. /brazosbend/settings/company
//   API   `/api/{tenant}/…`  e.g. /api/brazosbend/settings/company
//   public (no tenant)       `/`, `/pricing`, `/signup`, `/signin-help`
//                            and `/api/public/…`, `POST /api/tenants`,
//                            `/api/jobs/{id}`, `/api/exports…`
//
// This file is the ONE place that knows that shape. Every internal link, every
// redirect and the API client's base all build their URL here, so the tenant
// segment cannot be dropped by one screen and kept by another — and a screen
// never string-concatenates a tenant of its own (which is how a link to
// ANOTHER tenant's path would get written).
//
// The tenant is read from the URL, never held in a variable somebody could set:
// that keeps BR-TEN-003 true under path tenancy exactly as it was under host
// tenancy — the request carries the tenant, the client never chooses it. The
// browser no longer isolates tenants (one origin, one cookie jar), so the
// SERVER binds each session to its tenant and answers 404 on a foreign tenant's
// path; nothing here may "helpfully" rewrite a path to the session's own tenant.
import { useLocation } from "react-router-dom";

/** The route parameter that carries the tenant slug (`/:tenant/…`). */
export const TENANT_PARAM = "tenant";

/**
 * First-path segments that are NOT tenants — the public surface. Every one of
 * them is also on the server's reserved-slug list (BR-TEN-011 as amended by the
 * 2026-08-10 ruling: `api`, `signup`, `signin`, `pricing`, `static`, `assets`),
 * so no tenant can ever be named one of these and the test below is exact
 * rather than a heuristic.
 */
export const PUBLIC_SEGMENTS: readonly string[] = ["pricing", "signup", "signin-help"];

/** The public routes themselves, so App.tsx and the links agree on one spelling. */
export const HOME_ROUTE = "/";
export const PRICING_ROUTE = "/pricing";
export const SIGNUP_ROUTE = "/signup";
/**
 * The tenant-less sign-in surface. Sign-in itself is per-tenant
 * (`/{tenant}/signin`), so a visitor arriving without a tenant has to say which
 * utility they are signing in to. The 2026-08-10 ruling names this public path;
 * A1 has no screen for it beyond S2's "First time / Sign in" fork, and no ID is
 * claimed (CLAUDE.md forbids renumbering A1).
 *
 * CORRECTED 2026-08-15 (US-IDN-011): this comment used to end *"so the route
 * renders the W0 marker until that packet lands"*. That stopped being true on
 * 2026-08-10, when `SignInHelpPage` replaced the placeholder — the marker string
 * had escaped onto a public page and the PO found it on the first live deploy.
 * The comment outlived the defect by five days, which is hard-won law 1 in its
 * purest form: a comment is a note, and a note nobody re-reads becomes a lie.
 * The route renders `features/identity/SignInHelpPage.tsx`, which builds a
 * `/{tenant}/signin` URL and asks the server nothing (BR-IDN-027).
 */
export const SIGNIN_HELP_ROUTE = "/signin-help";

/** The per-tenant sign-in segment: `/{tenant}/signin` (11b, PO 2026-08-10). */
export const SIGNIN_SEGMENT = "/signin";

/** The first path segment, or "" for the root. */
function firstSegment(pathname: string): string {
  const trimmed = pathname.replace(/^\/+/, "");
  const cut = trimmed.indexOf("/");
  return cut === -1 ? trimmed : trimmed.slice(0, cut);
}

/**
 * The tenant this URL is scoped to, or "" when it is a public URL. Pure, so the
 * rule is provable without a browser: the tenant IS the first path segment
 * unless that segment is public.
 */
export function tenantFromPathname(pathname: string): string {
  const first = firstSegment(pathname);
  return first === "" || PUBLIC_SEGMENTS.includes(first) ? "" : first;
}

/**
 * The path WITHIN a tenant — the same URL with its tenant segment removed, so
 * route-matching config (SHELL_NAV, the breadcrumb map) stays written once, in
 * tenant-relative form. A public URL is returned unchanged.
 */
export function withinTenant(pathname: string): string {
  const tenant = tenantFromPathname(pathname);
  if (tenant === "") {
    return pathname;
  }
  const rest = pathname.slice(pathname.indexOf(tenant) + tenant.length);
  return rest === "" ? "/" : rest;
}

/**
 * THE helper: a tenant-relative segment (`/settings/company`) → the real URL
 * (`/brazosbend/settings/company`). With no tenant in scope the segment is
 * returned as-is rather than guessed at — a link that would have to invent a
 * tenant stays honest and lands on the public surface, where the router says
 * so, instead of pointing at some other utility's data.
 */
export function tenantPathFrom(tenant: string, segment: string): string {
  const suffix = segment === "" || segment.startsWith("/") ? segment : `/${segment}`;
  return tenant === "" ? suffix : `/${tenant}${suffix}`;
}

/** The tenant the CURRENT route is scoped to ("" on the public surface). */
export function useTenant(): string {
  return tenantFromPathname(useLocation().pathname);
}

/**
 * WHERE SIGN-OUT LANDS — pure, so the rule is provable without a browser.
 *
 * PO 2026-08-11, from the live deployment: signing out landed on
 * `https://smartbillhub.bynry.com/` and it must land on
 * `https://smartbillhub.bynry.com/silver-creek-water/signin`. Under path
 * tenancy the bare host is the PUBLIC pricing page — it is not a route this
 * product serves for a tenant, so a user who signed out had no way back to
 * their own utility's sign-in page except by retyping the URL.
 *
 * The tenant comes from the pathname the user was on, never from a variable
 * (BR-TEN-003), so this is the same rule the rest of this file keeps: the
 * request carries the tenant, the client never chooses it.
 *
 * With no tenant in scope there is nothing to return TO, and inventing one
 * would point a signed-out user at some other utility's door — so the fallback
 * is the public `/signin-help` landing, which exists precisely to ask which
 * utility you meant. It is unreachable from the shell (every authenticated URL
 * is `/{tenant}/…`) and is here so the function is total rather than partial.
 */
export function signOutDestination(pathname: string): string {
  const tenant = tenantFromPathname(pathname);
  return tenant === "" ? SIGNIN_HELP_ROUTE : tenantPathFrom(tenant, SIGNIN_SEGMENT);
}

// ── THE WAY BACK AFTER A SESSION ENDS (DEF-SHL-6378, 2026-09-23) ─────────────
//
// The PO: *"we need to say your session is expired and login again"*. Signing
// in again is only half of that; the other half is landing where you were, or a
// clerk half-way down the Payments list is sent to the Dashboard and has to
// find their place again. So the sign-in page takes ONE query parameter naming
// where to go next — and a parameter that decides where a browser goes after a
// password is typed is the textbook open redirect, so what it may hold is
// narrow, and decided here, where every other URL shape in the product is.

/** The sign-in page's one parameter: the TENANT-RELATIVE page to return to. */
export const RETURN_PARAM = "next";

/** Longer than any address this product builds; a longer one is not ours. */
const MAX_RETURN_LENGTH = 2048;

/** A control character: never part of an address this product builds. */
function hasControlCharacter(value: string): boolean {
  for (let index = 0; index < value.length; index += 1) {
    const code = value.charCodeAt(index);
    if (code < 0x20 || code === 0x7f) {
      return true;
    }
  }
  return false;
}

/** How many times a path may still decode to something new before it is refused. */
const MAX_DECODE_PASSES = 3;

/** A path segment that a browser would resolve UPWARD: `.`, `..` or `%2e` spellings of them. */
function isDotSegment(segment: string): boolean {
  const plain = segment.toLowerCase().replace(/%2e/g, ".");
  return plain === "." || plain === "..";
}

/** One spelling of the PATH is safe: one leading slash, no backslash, no dot segment. */
function isSafePathSpelling(path: string): boolean {
  return (
    path.startsWith("/") &&
    !path.startsWith("//") &&
    !path.includes("\\") &&
    !hasControlCharacter(path) &&
    !path.split("/").some(isDotSegment)
  );
}

/**
 * The return path, if it is SAFE to follow, else `null` — pure, so the rule is
 * provable without a browser.
 *
 * Safe means it can only ever land inside THIS tenant: the caller prefixes it
 * with the tenant the sign-in page is on (`tenantPathFrom`), so the value must
 * be a tenant-RELATIVE path that cannot climb out of that prefix or out of the
 * origin. Refused:
 *   · anything whose path does not start with exactly one `/` — `https://…`,
 *     `//host`, `javascript:…` and a bare word are all other places;
 *   · a backslash or a control character — `/\host` is `//host` to a browser;
 *   · a `.` or `..` segment in ANY spelling, including percent-encoded and
 *     double-encoded ones — `/../other-utility/payments` would leave the tenant
 *     once the browser normalised it;
 *   · the sign-in page itself, which would be a loop.
 * The PATH is checked in every spelling a browser might decode it to, not only
 * the first. The query string is carried as it is: it cannot change where the
 * browser goes, only what the page it lands on filters by.
 */
export function safeReturnPath(raw: string | null | undefined): string | null {
  if (typeof raw !== "string" || raw === "" || raw.length > MAX_RETURN_LENGTH) {
    return null;
  }
  if (hasControlCharacter(raw)) {
    return null;
  }
  let path = raw.split(/[?#]/, 1)[0] ?? "";
  for (let pass = 0; ; pass += 1) {
    if (!isSafePathSpelling(path)) {
      return null;
    }
    let decoded: string;
    try {
      decoded = decodeURIComponent(path);
    } catch {
      return null;
    }
    if (decoded === path) {
      break;
    }
    if (pass === MAX_DECODE_PASSES) {
      return null; // still decoding — nothing this product builds nests that deep
    }
    path = decoded;
  }
  if (path === SIGNIN_SEGMENT || path.startsWith(`${SIGNIN_SEGMENT}/`)) {
    return null;
  }
  return raw;
}

/**
 * WHERE "Sign in" GOES WHEN A SESSION HAS ENDED UNDER AN OPEN PAGE — the
 * tenant's own sign-in page (the SAME address sign-out uses, so the two can
 * never disagree) carrying the page the person was on.
 *
 * `search` is the query string of that page (`?q=smith`), kept so a filtered
 * list comes back filtered. With no tenant in scope there is nothing to return
 * to, and the tenant-less help page is returned bare, exactly as sign-out does.
 */
export function signInAgainDestination(pathname: string, search = ""): string {
  const door = signOutDestination(pathname);
  if (tenantFromPathname(pathname) === "") {
    return door;
  }
  const back = safeReturnPath(`${withinTenant(pathname)}${search}`);
  return back === null ? door : `${door}?${RETURN_PARAM}=${encodeURIComponent(back)}`;
}

/** A tenant-scoped segment → URL builder bound to the current route's tenant. */
export type TenantPath = (segment: string) => string;

/**
 * `const tenantPath = useTenantPath();` then `tenantPath("/dashboard")`. Every
 * internal link and redirect in the app goes through this — screens never write
 * `/${tenant}/…` themselves.
 */
export function useTenantPath(): TenantPath {
  const tenant = useTenant();
  return (segment: string) => tenantPathFrom(tenant, segment);
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-SHL-001@b16a4de (story+rules snapshot hash — the shell owns the app's URL shape; co-packet US-TEN-001@d5f8c32, US-IDN-001@402b6db)
// generated: 2026-08-10 by story-coder v1 (path-tenancy lane — PO ruling 2026-08-10) · AMENDED 2026-08-11 by story-coder v1 (S48 user-menu lane — `signOutDestination` added for DEF-037: sign-out dropped the tenant slug and landed on the bare public root. NOT DEF-035 — that ID was claimed by a concurrent lane mid-flight and this trailer kept the stale number after the renumber; corrected on review)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: trace_lint✔ run_gates✔ (11 PASS · 0 FAIL · 1 SKIP) tsc✔ eslint✔ vitest✔
// exceptions: E4 `/signin-help` is named by the 2026-08-10 ruling as public surface but has no A1 screen and no A13 copy — no ID is claimed and none is invented (S72 was a PROPOSAL riding with OQ-078, never assigned). CORRECTED 2026-08-15 (US-IDN-011): this line used to end "App.tsx routes it to the W0 marker rather than inventing a 'which utility?' screen", which stopped being true the same day it was written — SignInHelpPage replaced the placeholder on 2026-08-10 and the trailer was never re-read. Hard-won law 1, inside a lifecycle trailer.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
