// ── Trace ──────────────────────────────────────────────
// Story:    US-SHL-005 (EP-SHL-01 — sidebar footer user block & user menu), PARTIAL
//           Screens: shell-chrome, S48 (the menu; the three modals are the remainder), S3
// Rules:    BR-SHL-008 (initials · name · CURRENT-tenant role) ·
//           BR-SHL-009 (sign out ends the session, clears every client cache,
//           returns to the TENANT'S sign-in page — PO 2026-08-11) ·
//           BR-SHL-025 (an item with no destination is disabled WITH its reason)
// ───────────────────────────────────────────────────────
// The layout route that gives AppShell a session.
//
// `<AppShell />` has always accepted `user`, and App.tsx has always rendered it
// with no props at all — so the footer identity block never appeared and there
// was NO WAY TO SIGN OUT anywhere in the product. The PO found that on the live
// deployment 2026-08-10 ("this entire functionality from login/logout is
// missing"). Everything needed already existed: `getMe()`, `signOut()` and the
// footer block itself. Nothing connected them.
//
// SCOPE, STATED HONESTLY — AND CORRECTED 2026-08-11. US-SHL-005's menu is four
// items: My profile, Change password, Two-factor authentication, Sign out. Only
// Sign out WORKS. Until 2026-08-11 the other three were not rendered at all, on
// the reasoning that "a menu with three dead items is worse than a short menu
// that works". The PO found the one-item menu on the live app and rejected that
// call, and it was wrong on the repo's own rules too: BR-SHL-025 settles this
// everywhere else in the product — an affordance you cannot use right now is
// DISABLED WITH ITS REASON, never absent (the billing screens' Void, the
// permission-gated list actions). All four now render; three carry the reason
// they are not ready. The remainder of US-SHL-005 — the three modals — is still
// open, and it is now visible in the product instead of invisible.
//
// WHAT THE MODALS ARE WAITING ON, since "not built yet" is not a plan (law 1).
// Two of the three have a SERVED backend already:
//   · `PATCH /api/{tenant}/me`        → My profile
//   · `POST  /api/{tenant}/me/password` → Change password
// Both are in 06-backend/openapi/schema.json, neither has a typed wrapper in
// api/endpoints.ts and neither has a caller — an endpoint nobody calls, which
// is hard-won law 2 from the other end. Two-factor has NO endpoint at all and
// BR-IDN-028 keeps 2FA off the v1 Security tab, so it is a genuinely later
// feature rather than an unfinished one. Reported to the PO with this packet.
//
// BR-SHL-009 has three clauses and the cache one is the one that is easy to
// miss: ending the session server-side is not enough while a TanStack cache
// still holds the tenant's accounts and invoices in memory. `queryClient.clear()`
// is what makes "no tenant data readable after sign-out" true rather than
// merely intended.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";

import { api, isApiError } from "@/api/client";
import {
  getInAppMessages,
  getMe,
  getShellDisplay,
  globalSearch,
  markAllInAppMessagesRead,
  markInAppMessageRead,
  signOut,
} from "@/api/endpoints";
import { REFERENCE_STALE_MS, queryKeys } from "@/api/queryClient";
import { AppShell } from "@/components/AppShell";
import type { ShellBellItem } from "@/components/AppShell";
// US-SHL-003: the SAME two-character minimum the box's own debouncer uses, so
// the enabled-guard here and the fire-guard there cannot drift apart.
import { SEARCH_MIN_CHARS } from "@/components/DataTable";
import { isRegionalDateFormat } from "@/components/DateCell";
import { formatMoney } from "@/components/MoneyCell";
import { resetAnalytics, track, useStaffAnalytics } from "@/analytics";
import { SessionExpiryBoundary } from "@/components/SessionExpired";
import { LoadingSkeleton } from "@/components/StateFrame";
import { TenantRegionalProvider, type TenantRegional } from "@/components/TenantRegional";
import { WarningBox } from "@/components/WarningBox";
import { Button } from "@/components/Button";
import { FieldAppNotice } from "@/components/FieldAppNotice";
import { BrandMark, MARK_SIZE_SIDEBAR } from "@/features/tenancy/BrandMark";
import { FIELD_APP_SIGN_IN } from "@/features/identity/SignInPage";
import { signOutDestination, tenantFromPathname, useTenantPath } from "@/routing/tenantPath";

/** One delivered message → the single line the bell popover shows.
 *
 * The stored body is a small block — *"Billing run finished.\n\n1204 processed
 * · 3 failed\n2026-08-17"* — and a `.bell-item` is one button on one line, so
 * the whitespace is collapsed rather than the text truncated. TRUNCATION IS THE
 * WRONG CHOICE HERE and the reason is BR-NOT-020: the failure count is the part
 * a clerk must see, it is at the END of the body, and a `…` would cut off
 * exactly the number the whole rule exists to deliver.
 *
 * The subject rides in front when a class has one. No in-app class does today. */
/**
 * The catalogue keys a field-work message can name (CR-168-BRC10 §F) — the
 * SERVER picks one (`notifications.field_work_events.BELL_KEY`) and the bell
 * renders it. Listed here so the eleven catalogues' entries have a visible
 * reader in the front end; a key the server adds and this list lacks still
 * renders, through `bellTextFor`.
 */
export const FIELD_WORK_BELL_KEYS = [
  "notifications.fieldWork.closed",
  "notifications.fieldWork.closedUploading",
  "notifications.fieldWork.photosComplete",
  "notifications.fieldWork.needsReview",
] as const;

/** The same, for a Work rule's escalations and the two Work reminders
 *  (CR-168-BRC10 P3.57–P3.59, lane SRV-4) — the server picks one in
 *  `notifications.work_escalations.bell_key`. */
export const WORK_ESCALATION_BELL_KEYS = [
  "notifications.workEscalation.unassigned",
  "notifications.workEscalation.not_accepted",
  "notifications.workEscalation.running_late",
  "notifications.workEscalation.overdue",
  "notifications.workEscalation.on_hold_too_long",
  "notifications.workEscalation.failed",
  "notifications.workEscalation.not_approved",
  "notifications.workReminder.certificateExpiring",
  "notifications.workReminder.technicianDay",
] as const;

export function bellTextFor(
  message: {
    subject: string | null;
    body: string;
    message_key?: string | null;
    params?: Record<string, unknown>;
  },
  translate?: {
    exists: (key: string, params?: Record<string, unknown>) => boolean;
    t: (key: string, params?: Record<string, unknown>) => string;
  },
): string {
  // CR-168-BRC10 §F — a product event names a catalogue key; the bell speaks
  // the clerk's language. A key this build does not know falls back to the
  // utility's rendered body, never to the raw key.
  // ⚠ `exists` is asked WITH the params: a plural key lives as `_one`/`_other`
  // only, and a bare `exists("…needsReview")` is false — which is how the
  // first walk showed the English body instead (the count picks the form).
  if (message.message_key && translate?.exists(message.message_key, message.params ?? {})) {
    return translate.t(message.message_key, message.params ?? {});
  }
  const collapsed = message.body.replace(/\s+/g, " ").trim();
  return message.subject ? `${message.subject} — ${collapsed}` : collapsed;
}

/**
 * The tenant's regional settings as the renderer needs them, or `null` when
 * they are NOT KNOWN (DEF-SHL-3964).
 *
 * `null` covers three genuinely different situations and treats them the same
 * way on purpose, because the product cannot tell them apart and must not
 * guess in any of them: the request has not answered yet; the tenant row has
 * no timezone or date format stored; the stored `date_format` is a string this
 * build cannot draw. Exported so a test can assert the last one without
 * mounting the shell.
 */
/**
 * What a screen draws when the tenant has SETTLED regional settings we cannot
 * use (DEF-SHL-5666) — never when they are merely still loading.
 *
 * `UTC` is chosen rather than the viewer's own `Intl` zone because a utility's
 * records belong to the utility: two staff in different states must not read
 * the same payment as taken on different days. The date format is the US-first
 * seed `provision_tenant` already writes, so in practice only the zone is ever
 * missing and only the zone is ever replaced here.
 *
 * ⚠ **THIS IS ONLY LAWFUL BECAUSE THE SCREEN SAYS SO.** `DEF-SHL-3964` banned a
 * SILENT default reaching a date through a `??`; a stated one is a different
 * act. Render this value without the notice beside it and that defect is back.
 */
const REGIONAL_FALLBACK: TenantRegional = { timeZone: "UTC", dateFormat: "MM/DD/YYYY" };

export function tenantRegionalOf(
  settings: { timezone: string | null; date_format: string | null } | undefined,
): TenantRegional | null {
  if (settings === undefined) {
    return null;
  }
  const { timezone, date_format: dateFormat } = settings;
  if (!timezone || !isRegionalDateFormat(dateFormat)) {
    return null;
  }
  return { timeZone: timezone, dateFormat };
}

/**
 * `DEF-CUS-5114` — the tenant's currency rides on the SAME response as the zone
 * and the format, so it is published beside them rather than re-read by each
 * screen. `BR-TEN-042`: one tenant, one currency. An unset code publishes
 * `null` and the screen states the absence; nothing here defaults `USD`, and
 * the zone fallback above never carries a currency of its own.
 */
export function withTenantCurrency(
  regional: TenantRegional | null,
  settings: { currency: string | null } | undefined,
): TenantRegional | null {
  if (regional === null) {
    return null;
  }
  return { ...regional, currency: settings?.currency || null };
}

/**
 * The layout route App.tsx mounts. The shell proper is `ShellWithSessionBody`;
 * this wraps it in the ONE place a dead session is answered (`DEF-SHL-6378`).
 *
 * ⚠ **THE BOUNDARY IS OUTSIDE THE BODY ON PURPOSE.** When the session ends the
 * body's own reads — `/me`, `/shell/display`, the bell — must unmount with the
 * page, or the emptied cache would have them ask again, each ask would answer
 * 401, and the shell would redraw its sidebar from nothing around the card.
 */
export function ShellWithSession() {
  return (
    <SessionExpiryBoundary>
      <ShellWithSessionBody />
    </SessionExpiryBoundary>
  );
}

/** The forced-change gate's 403 (`BR-IDN-022`) — not the wrong door. */
const PASSWORD_CHANGE_REQUIRED_KEY = "errors.auth.password_change_required";

function ShellWithSessionBody() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { t, i18n } = useTranslation();
  const { pathname } = useLocation();
  // DEF-SHL-5666 — the notice's way out. This file never concatenates a tenant
  // of its own; `routing/tenantPath.ts` is the one place that spelling lives.
  const tenantPath = useTenantPath();

  // BR-SHL-009 as amended by the PO 2026-08-11 (live app): sign-out returns to
  // the TENANT'S OWN sign-in page, `/{tenant}/signin`. Computed during render
  // from the route the user is on, not inside the callback, so the destination
  // is decided by the URL that was open when the shell rendered rather than by
  // whatever the closure happens to hold later. `signOutDestination` is the ONE
  // place that spelling lives (routing/tenantPath.ts) — this file never
  // concatenates a tenant of its own.
  const signOutTo = signOutDestination(pathname);

  const meQuery = useQuery({
    queryKey: queryKeys.me,
    queryFn: () => getMe(api),
    // One session per tenant path; a 401 means signed out, and retrying it
    // would only delay the Session expired card the boundary above draws.
    // ⚠ This comment used to say *"the redirect the router already handles"*.
    // No router code in this product has ever handled a 401 — which is how an
    // expired session reached every screen's ROLE denial instead
    // (`DEF-SHL-6378`, hard-won law 1).
    retry: false,
  });

  // `to` is where the person lands afterwards — the sign-in page by default;
  // DEF-IDN-9748's wrong-door state passes the field app's own sign-in.
  const signOutMutation = useMutation({
    // eslint-disable-next-line @typescript-eslint/no-unused-vars -- read in onSettled
    mutationFn: (_to?: string) => signOut(api),
    // Settled, not success: a failed DELETE still means the user asked to
    // leave. Keeping them signed in on the screen because the network hiccuped
    // is the wrong side to fail on — the cookie is httpOnly and the server
    // rejects it on the next request anyway.
    onSettled: (_data, _error, to) => {
      // CR-169-BRC10 §2 row 7 — the sign-out is sent, THEN this browser
      // forgets who it was, so the next person here starts anonymous.
      track("user_signed_out", { reason: "clicked" });
      resetAnalytics();
      queryClient.clear(); // BR-SHL-009 — no tenant data readable after
      // DEF-037: this used to navigate to the bare public root and dropped the
      // tenant on every sign-out. `replace` so Back cannot re-enter a dead session.
      if (to) {
        navigate(to, { replace: true });
        return;
      }
      navigate(signOutTo, { replace: true });
    },
  });

  // BR-SHL-030 — APPLY the tenant's language. Selecting "Español (México)" in
  // Settings → Regional saved the value and changed nothing on screen, because
  // `i18n.changeLanguage` was called NOWHERE in the application: the setting
  // reached the database and stopped there. The PO found it on the live app
  // 2026-08-10. This is the one place every authenticated screen passes
  // through, so it is where the stored preference becomes the rendered
  // language. Saving on the Regional tab invalidates this query, so the switch
  // is immediate and needs no reload.
  //
  // Per-user override (BR-SHL-030's first resolution step) is not built yet —
  // `getMe()` carries no language — so this applies the TENANT default. When
  // the override lands it takes precedence here, ahead of this value.
  //
  // ── DEF-SHL-4272 · WHY THIS IS ONE QUERY AND WHY IT IS NOT `/settings/…` ──
  //
  // ⚠ **A BILLING CLERK COULD NOT USE THIS PRODUCT AT ALL FROM 2026-08-21 TO
  // 2026-09-06, AND THIS QUERY IS WHERE IT HAPPENED.** These two reads were
  // `GET /settings/regional` and `GET /settings/company`, and both are gated
  // `SettingsReadAnyWriteSystemAdmin` — `{system_admin, executive}`, because
  // A4's `settings_lookups` row gives a Billing Clerk **no cell at all**. So a
  // clerk signed in successfully, reached `/dashboard`, and the block below
  // rendered `settings.regional.failedTitle` over **every screen in the
  // product**, with a Retry that could never succeed.
  //
  // Nothing saw it. Every frontend test passes formatting as a prop or seeds
  // the query cache; every backend test drives services or an admin fixture;
  // and every walkthrough in this repo signs in as a system admin.
  //
  // **The fix is a separation, not a widening.** `GET /shell/display` serves
  // the branding and the display formats to any signed-in role, read-only.
  // `GET /settings/regional` stays Admin/Executive and keeps the accounting
  // method, close cadence, close day and closed-period lock — a utility's
  // finance policy, which nobody should receive in order to draw a date. The
  // Settings screens that EDIT these values still read the settings endpoints
  // and are still behind the admin gate; only the shell moved.
  //
  // **ONE query, not two.** The shell cannot draw a screen with half of this,
  // so two queries would give one indivisible fact two loading states, two
  // failure states and two Retry buttons — and a boot read failing with a dead
  // Retry is the defect being fixed.
  const displayQuery = useQuery({
    queryKey: queryKeys.shellDisplay,
    queryFn: () => getShellDisplay(api),
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });
  const tenantLanguage = displayQuery.data?.regional.language ?? null;

  useEffect(() => {
    // Guard on inequality: changeLanguage on every render would refetch the
    // catalog chunk and reset any in-flight language switch.
    if (tenantLanguage && i18n.language !== tenantLanguage) {
      void i18n.changeLanguage(tenantLanguage);
    }
  }, [tenantLanguage, i18n]);

  // ── DEF-SHL-3964 · THE OTHER TWO FIELDS OF THE SAME RESPONSE ────────────
  //
  // The PO, on the running product 2026-09-05: *"date and time format is set in
  // the settings, plus we save location - but date shown everywhere in the
  // product does not change with that format change. If I change the language
  // it changes across entire app, date does not change."*
  //
  // ⚠ THE TWO SETTINGS WERE ALWAYS IN ONE RESPONSE AND ONLY ONE WAS READ. The
  // query above has existed since 2026-08-10 and this file took `.language` off
  // it and stopped. `timezone` and `date_format` were sitting in the same
  // payload, unread, while every screen in the product fell through to
  // `SEED_TIME_ZONE` ("UTC") and `SEED_DATE_FORMAT` ("MM/DD/YYYY"). A Texas
  // utility with `America/Chicago` saved read every timestamp five or six hours
  // out — a payment taken at 7pm local showed as the next day — on 83 screens.
  //
  // Language worked for exactly one reason: it is applied GLOBALLY, above, and
  // needs no prop. This is the same move for the other two, and a context is
  // what "globally" means for a value React has to re-render on.
  //
  // The date format is validated against the seven `RegionalDateFormat`s rather
  // than cast: `tenant_settings.date_format` is a bare TEXT column, and an
  // unknown string reaching `arrange()` returns `undefined` from a switch with
  // no default. An unrecognised value is treated as NOT KNOWN, so the shell
  // waits and says so rather than rendering a screen full of `undefined`.
  const publishedRegional: TenantRegional | null = tenantRegionalOf(displayQuery.data?.regional);

  // ── DEF-SHL-5666 · A SETTLED ANSWER THAT IS EMPTY IS NOT A WAIT ─────────
  //
  // ⚠ **A TENANT WHOSE `timezone` IS UNSET RENDERED A PERMANENT SKELETON ON
  // EVERY SCREEN — the app shell itself never mounted, so the whole product was
  // a blank page, for ever, with nothing reporting an error anywhere.**
  //
  // `tenantRegionalOf` returns `null` for three different situations and says
  // so deliberately. That is right about the VALUE and wrong about the WAIT:
  // a request that has not answered is worth waiting for, and one that HAS
  // answered — 200, with an empty zone — is not. The gate below could not tell
  // them apart, so it took its "still loading" branch and stayed there.
  //
  // **It is reachable the ordinary way.** `provision_tenant` seeds the zone
  // from `default_timezone_for_state(data["state_code"])` and `state` is
  // OPTIONAL on the signup payload, so a utility that signs up without one can
  // never open the product it just paid for.
  //
  // **WHY A STATED FALLBACK AND NOT A BLOCKING FRAME.** The one screen that can
  // set a timezone — Settings → Regional — lives INSIDE this shell, so a
  // blocking frame cannot link anywhere useful: following the link renders this
  // same gate again. Rendering with a stated fallback is the only option that
  // lets the person fix it.
  //
  // **AND IT DOES NOT REOPEN `DEF-SHL-3964`.** That defect was a SILENT default
  // arriving through a `??` — nobody chose "MM/DD/YYYY" for the Payments list.
  // This says on screen which zone it is using and why, which is a different
  // act; `BR-SHL-025` requires the statement. `UTC` rather than the viewer's
  // browser zone on purpose: a utility's records are not a property of whoever
  // happens to be looking at them, and two staff in different states must not
  // read a payment as taken on different days.
  const regionalUnset = displayQuery.isSuccess && publishedRegional === null;
  const effectiveRegional: TenantRegional | null = withTenantCurrency(
    publishedRegional ?? (regionalUnset ? REGIONAL_FALLBACK : null),
    displayQuery.data?.regional,
  );

  // The sidebar tenant block. `AppShell` has styled `.sidebar .tenant` and
  // rendered it `props.tenantName !== undefined` since the shell was built, and
  // nothing ever passed the prop — the THIRD instance of the same defect found
  // on the live app in one day (the user block and sign-out were the others).
  // The prototype puts the utility's name at the top of the sidebar, and
  // without it a multi-tenant product gives an operator no standing answer to
  // "whose data am I looking at".
  //
  // DEF-SHL-4272 — the sidebar's name and mark now ride on the SAME response
  // as the formats above. They were a second admin-only read (`GET
  // /settings/company`) and are a second reason a clerk saw nothing.
  //
  // DBA first — it is the name customers see on the bill. Falls back to the
  // legal name, then to the tenant slug in the URL, which is always present.
  const company = displayQuery.data?.company;
  const tenantName = company?.dba_name || company?.legal_name || tenantFromPathname(pathname);

  const me = meQuery.data;

  // CR-169-BRC10 §2 rows 5–7 — who this is, by internal id only, and which
  // utility. A different tenant path in the same browser resets first.
  useStaffAnalytics({
    userId: me?.id,
    role: me?.role,
    tenant: tenantFromPathname(pathname),
    app: "staff",
    language: tenantLanguage,
  });

  // ── CR-009 · THE BELL, FINALLY WIRED (BR-NOT-019, BR-SHL-007) ────────────
  //
  // ⚠ `AppShell` has accepted `bellItems`, `onBellSelect` and `onMarkAllRead`
  // since the shell was built and NOTHING HAS EVER PASSED THEM — the prop
  // comment said so in as many words: *"BE-09 wiring later"*. That is hard-won
  // law 2 exactly (*"a component with an optional prop that nothing passes is
  // dead UI: it renders nothing, every test passes, and the feature does not
  // exist"*), and it is the FOURTH time this file has been the place it was
  // fixed — the user block, sign-out and the tenant name were the others.
  //
  // It could not be wired before today for an honest reason rather than an
  // oversight: there was nothing to put in it. No channel could deliver a
  // message to a member of staff, and `rule_catalog.py` recorded the reason —
  // *"there is no in-app notification surface — no bell, no inbox"*. In-app is
  // that surface, so this is the same commit that made the sentence false.
  const inboxQuery = useQuery({
    queryKey: queryKeys.inAppMessages,
    queryFn: () => getInAppMessages(api),
    // No polling. A bell that polled every 30 seconds would be a request per
    // user per half-minute forever, on a product built for utilities with one
    // or two staff — the cost is real and the benefit is a badge that updates
    // without a navigation. It refetches when the window regains focus, which
    // is TanStack's default and is when a person is actually looking.
    retry: false,
  });

  const bellItems: readonly ShellBellItem[] = (inboxQuery.data?.results ?? []).map((message) => ({
    id: message.id,
    text: bellTextFor(message, { exists: (key, params) => i18n.exists(key, params), t: (key, params) => t(key, params) }),
    read: message.read,
  }));

  // Both writes invalidate the ONE inbox key, so the badge and the list are
  // re-read together from the server rather than patched apart on the client.
  const markReadMutation = useMutation({
    mutationFn: (messageId: string) => markInAppMessageRead(messageId, api),
    onSettled: () => queryClient.invalidateQueries({ queryKey: queryKeys.inAppMessages }),
  });
  const markAllReadMutation = useMutation({
    mutationFn: () => markAllInAppMessagesRead(api),
    onSettled: () => queryClient.invalidateQueries({ queryKey: queryKeys.inAppMessages }),
  });

  // ── US-SHL-003 · UNIVERSAL SEARCH, FINALLY WIRED ────────────────────────
  //
  // ⚠ `AppShell` has accepted `onSearch` since the shell was built and NOTHING
  // HAS EVER PASSED IT. That is hard-won law 2 for the FIFTH time in this file
  // — the user block, sign-out, the tenant name and the bell were the others —
  // and this one was KNOWN: `check_unwired_props.py` exempted the prop BY NAME
  // so G13 would pass on purpose, and DEF-2423 made the box state its own
  // absence rather than swallow what a user typed. **That exemption is removed
  // in this commit**, because an exemption left behind after its reason is gone
  // makes the guard blind to this prop forever.
  //
  // It could not be wired before today for an honest reason rather than an
  // oversight: there was nothing to call. `GET /search` did not exist anywhere
  // in the backend — the BE-08 kernel, this component's debouncer and the ✕
  // were all built and no route joined them. The PO's words on the running
  // product: *"Can you enable universal search ?"*.
  //
  // THE QUERY LIVES HERE AND NOT IN `AppShell` because AppShell is the
  // presentational frame: it owns the box, the 300 ms debounce and the ✕ (IS-3,
  // through the ONE `createSearchDebouncer`), and this component owns the
  // session, the client and the cache. `searchQuery` is the DEBOUNCED text —
  // AppShell only calls `onSearch` after the debounce and only at two
  // characters or more, so this state changes at most once per pause in typing
  // rather than once per keystroke.
  const [searchQuery, setSearchQuery] = useState("");
  const searchResults = useQuery({
    queryKey: queryKeys.globalSearch(searchQuery),
    queryFn: () => globalSearch(searchQuery, api),
    // The box's own minimum (IS-3) is enforced in the debouncer AND on the
    // server; this stops the empty key from ever being fetched, so clearing the
    // box costs no request at all.
    enabled: searchQuery.length >= SEARCH_MIN_CHARS,
    // A search is a keystroke-driven read of live data. One minute is long
    // enough that re-typing the same query inside a single task is instant and
    // short enough that a record created a moment ago is findable.
    staleTime: 60_000,
    // A18 §4: a failure shows its own retry in the popover rather than three
    // silent attempts a user cannot see.
    retry: false,
  });

  const searchStatus: "idle" | "loading" | "error" | "ready" =
    searchQuery.length < SEARCH_MIN_CHARS
      ? "idle"
      : searchResults.isError
        ? "error"
        : searchResults.isPending
          ? "loading"
          : "ready";

  // ── DEF-SHL-3964 · NO SCREEN RENDERS BEFORE ITS DATE FORMAT IS KNOWN ────
  //
  // Decision D3 of this lane: the shell WAITS. This is the one place in the
  // authenticated product every screen passes through, so one gate here covers
  // all 83 of them and none can opt out by accident — which is exactly how the
  // defect spread in the first place. Nobody chose "MM/DD/YYYY" for the
  // Payments list; it arrived there through a `??`.
  //
  // The wait is short and usually invisible: it is a single small GET that is
  // already in flight beside `/me`, cached for the
  // session, so after the first paint this is a cache read and there is no wait
  // at all. The alternative — rendering a dash on every date until the settings
  // land — was rejected because it would flicker a dash across every list on
  // first paint and would mean widening `dateFormat` to nullable at 82 call
  // sites and every child they hand it to.
  if (effectiveRegional === null) {
    // A FAILED read is a different fact from a SLOW one and gets said out loud
    // (decision D4). Waiting forever would darken the whole product because one
    // settings GET returned 500; carrying on would print timestamps in a zone
    // nobody chose, which is the defect. So: the sentence the Settings screen
    // itself uses for this exact failure — already translated in all eleven
    // catalogues, so this lane mints no key — and a retry.
    // ⊕ `DEF-SHL-9241` — a 404 on the shell's own boot read is NOT a failed
    // read: every tenant-scoped route answers 404 to a non-member (HR-1), so
    // this is a person signed in to ANOTHER utility opening this one's
    // address. A Retry could never succeed; this utility's own sign-in page is
    // the honest way on, and it reveals nothing the 404 did not.
    if (displayQuery.isError && isApiError(displayQuery.error) && displayQuery.error.status === 404) {
      return <Navigate to={signOutTo} replace />;
    }
    // ⊕ `DEF-IDN-9748` — a 403 on the boot read is the WRONG DOOR, not a
    // failed read: `GET /shell/display` serves every office role, so the one
    // signed-in login it refuses is a field technician (`BR-WRK-043`, PO
    // 2026-09-04: *"they will login to mobile app only"*). A Retry could
    // never succeed. The one action ends this web session and opens the field
    // app's sign-in. A 403 asking for a password change is a different fact
    // and keeps the branch below.
    // ⊕ `DEF-IDN-9777` (PO 2026-10-06) — the sign-in page's notice, as a whole
    // centred page: the PO's two sentences and one "Open the field app"
    // button, where this was one small line and a small button on an empty
    // frame.
    if (
      displayQuery.isError &&
      isApiError(displayQuery.error) &&
      displayQuery.error.status === 403 &&
      displayQuery.error.messageKey !== PASSWORD_CHANGE_REQUIRED_KEY
    ) {
      const fieldSignIn = tenantPath(FIELD_APP_SIGN_IN);
      return (
        <div data-def-ref="DEF-IDN-9748">
          <FieldAppNotice
            layout="page"
            href={fieldSignIn}
            onOpen={() => signOutMutation.mutate(fieldSignIn)}
          />
        </div>
      );
    }
    if (displayQuery.isError) {
      return (
        <div className="state-frame">
          <p>{t("settings.regional.failedTitle")}</p>
          <Button variant="primary" onClick={() => void displayQuery.refetch()}>
            {t("states.failed.retry")}
          </Button>
        </div>
      );
    }
    return <LoadingSkeleton variant="card" />;
  }

  return (
    <TenantRegionalProvider value={effectiveRegional}>
      {regionalUnset && (
        <WarningBox
          tone="now"
          data-warning="regional-zone-unset"
          sentence={t("shell.regional.zoneUnset")}
          action={
            <Link className="text-accent-text underline" to={tenantPath("/settings/regional")}>
              {t("shell.regional.zoneUnsetAction")}
            </Link>
          }
        />
      )}
      <AppShell
        tenantName={tenantName}
        // CR-048 wave D — the mark, wired in the same commit the prop is added
        // (hard-won law 2). Rendered only once the profile has arrived: a mark
        // built from a missing profile would flash the tenant SLUG's initials
        // and then change to the real ones, which reads as a bug.
        tenantMark={
          company ? (
            <BrandMark
              mark={company.mark}
              hasLogo={company.has_logo}
              logoRef={company.logo_ref}
              size={MARK_SIZE_SIDEBAR}
              name={tenantName}
            />
          ) : undefined
        }
        user={
          me
            ? {
                fullName: me.full_name,
                // The S48 menu header reads "email · role" — `GET /me` has always
                // carried the address and nothing read it until 2026-08-11.
                email: me.email,
                // BR-SHL-008: the role of the CURRENT tenant's membership. Null
                // while the server has not named one — render the person, not a
                // guess at their authority.
                roleName: me.role_name ?? "",
              }
            : undefined
        }
        onSignOut={() => signOutMutation.mutate(undefined)}
        bellItems={bellItems}
        // Opening a message marks it read. There is deliberately NO deep link
        // yet: the bulk-action summary's subject is a RUN, and no screen in this
        // product shows one (the per-run delivery dashboard is US-BIL-024 and the
        // bill run fires no staff event at all — OQ-262). Navigating somewhere
        // plausible would be worse than not navigating.
        onBellSelect={(item) => markReadMutation.mutate(item.id)}
        onMarkAllRead={() => markAllReadMutation.mutate()}
        // US-SHL-003 — the five props that make the box search. `onSearch`
        // receives the DEBOUNCED query (or "" when the ✕ clears it), which is
        // exactly what this state wants.
        onSearch={setSearchQuery}
        searchGroups={searchResults.data?.groups ?? []}
        searchStatus={searchStatus}
        onSearchRetry={() => void searchResults.refetch()}
        // Hard rule 2: money is stored to 4 places and DISPLAYED to 2. The wire
        // carries the exact stored decimal beside its CHAR(3) code and this is
        // where it becomes two places — the same `formatMoney` every list uses,
        // so a bill's total reads identically in the popover and on S30.
        formatSearchMoney={(amount, currency) => formatMoney(amount, currency)}
      />
    </TenantRegionalProvider>
  );
}

export default ShellWithSession;

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-SHL-005@b16a4de (EP-SHL-01 — PARTIAL: the menu and sign-out; the My profile /
//         Change password / Two-factor modals remain unbuilt and US-SHL-005
//         stays OPEN, now visibly so)
// generated: 2026-08-10 by Eng-Lead, from the PO's live-deployment report
//         ("this entire functionality from login/logout is missing") · AMENDED 2026-08-11
//         by story-coder v1 (S48 user-menu lane — PO live-app report: DEF-037 sign-out
//         dropped the tenant slug, DEF-038 the menu had one item, DEF-039 its styling
//         named tokens that do not exist, DEF-040 the tenant block drew one line of two)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ · vitest suite✔ · vite build✔ · run_gates 11-PASS/0-FAIL/1-SKIP✔ · 2026-08-11 re-run: tsc✔ eslint✔ vitest✔ (G15 red on the 9 new keys this lane may not add — reported)
// exceptions: US-SHL-005 is delivered PARTIALLY and said so — 1 of its 4 menu
//         items WORKS; the other three render disabled with their reason per
//         BR-SHL-025 (this replaces the 2026-08-10 call to omit them, which the
//         PO rejected) · `PATCH /me` and `POST /me/password` are SERVED with no
//         wrapper and no caller — reported, not built here · sign-out proceeds
//         on a FAILED DELETE by design: the user asked to leave and the cookie
//         is httpOnly · E4 the sign-out redirect's wiring is asserted by reading
//         this file's source (no DOM library in package.json)
// amended: 2026-09-05 by lane REGION (DEF-SHL-3964 — the PO on the running
//         product: the date format and time zone saved on Settings → Regional
//         changed nothing anywhere, while the language beside them changed
//         everything). This file fetched all three fields and read ONE. It now
//         publishes the tenant's zone and date format through
//         `TenantRegionalProvider` and renders NO routed screen until it knows
//         them — decision D3: 83 screens inherit one rule and none can opt out
//         by accident, which is exactly how the seed default spread. A FAILED
//         read says so with a retry (D4) using strings that already exist in
//         all eleven catalogues, so this lane mints no locale key.
// amended: 2026-09-23 by lane SESSION-EXPIRY (DEF-SHL-6378 — the PO on production:
//         an expired session showed the ROLE denial on Payments and "many
//         places"). The layout route is now `SessionExpiryBoundary` around
//         this body: on the first 401 anywhere it empties the cache
//         (BR-SHL-009) and replaces the whole shell with Session expired and
//         a Sign in link to this tenant's own sign-in page, carrying the page
//         back. A 401 on the shell's own boot read therefore no longer draws
//         the regional-settings failure with a Retry that could never work.
// amended: 2026-10-05 by lane TECH-WEB (DEF-IDN-9748 — a customer on sandbox:
//         a Field Technician signed in to the staff web app and every screen
//         drew the regional-settings failure with a dead Retry, because the
//         boot read is office-only). A 403 on the boot read now says "Sign in
//         on the field app." with one action that signs this web session out
//         and opens the field app's sign-in; no new locale key.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
