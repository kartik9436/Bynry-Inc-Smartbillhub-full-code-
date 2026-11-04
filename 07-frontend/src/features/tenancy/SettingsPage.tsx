// ── Trace ──────────────────────────────────────────────
// Story:    US-TEN-005 · US-TEN-006 (EP-TEN-05) · US-TEN-007 · US-TEN-008 (EP-TEN-06) ·
//           US-TEN-009 · US-TEN-010 · US-TEN-011 (EP-TEN-07) · US-TEN-012 (EP-TEN-08) ·
//           US-IDN-004 · US-IDN-005 · US-IDN-006 · US-IDN-007 (EP-IDN-02) · US-IDN-010 (EP-IDN-04) ·
//           US-MET-006 (EP-MET-02) · US-IDN-008 (GET /me/permissions — the caller's own A4 row) ·
//           US-BIL-009 (EP-BIL-02 — the Accounting tab this frame now mounts)
//           Screens: S8 (all tabs), S63–S71 (Reference-data rule cards)
// Rules:    BR-SHL-035 (ONE Reference-data shell for every card) · BR-SHL-003 (an unreachable surface is
//           not drawn) · BR-SHL-025 (gating from the SERVER's permission set, never a client role check) ·
//           BR-SHL-020 (six shared states, plain-language failure) · BR-IDN-009 (Settings is System Admin;
//           Executive views) · BR-IDN-014 (the read-only A4 grid is the server's own catalog) ·
//           BR-BIL-067 · BR-BIL-069 (the two rulings the Accounting tab exists to surface)
// ───────────────────────────────────────────────────────
// S8 Settings — the tab frame every Settings screen lives in.
//
// What this file owns, and nothing more:
//   · the A1 tab set and its ORDER (addendum 2026-08-07, r6 rename, r7
//     "Company → Users & roles → …", r8 Templates after Numbering);
//   · Company's SECOND-LEVEL strip and its two sub-tabs;
//   · `/settings/:tab?/:sub?` — both levels are URL state, so every Settings
//     surface is linkable. The ids `company` · `services` · `number-series` ·
//     `users` are a CONTRACT with US-TEN-003, whose checklist deep-links them,
//     and so is the pre-nesting `regional` (see LEGACY_SETTINGS_TAB_PATHS);
//   · RBAC gating from the SERVER's permission grid (see resolveSettingsAccess);
//   · the honest "arrives with …" state for a tab whose backend does not exist
//     yet — never a form that posts nowhere.
// Each tab's body is its own file; this frame only picks one.
//
// E2 (CLOSED 2026-08-10): A1's Settings addendum, EP-TEN-05 and the signed
// prototype all model "Regional, formats & fiscal calendar" as the SECOND
// SUB-TAB of Company; the build packet listed it as its own tab and this frame
// used to draw it as the sibling immediately after Company. The prototype is
// the tie-breaker for layout (CLAUDE.md: it is the clickable reference for
// layout/copy/flows), so Regional now nests where UtilityBilling.html draws it
// — a `.settings-tabs` strip inside the Company tab BODY (lines 4458–4461),
// not a second PageHeader: a nested PageHeader would render a second <h1>,
// which BR-SHL-044's skeleton and G14's shape check both forbid.
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Navigate, useNavigate, useParams } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getMe, getMyPermissions, getRolesMatrix, getShellDisplay } from "@/api/endpoints";
import type { MyPermissions, RolesMatrix, SessionUser } from "@/api/endpoints";
import { REFERENCE_STALE_MS, queryKeys } from "@/api/queryClient";
import { LoadingSkeleton } from "@/components/StateFrame";
import { IntegrationsTab } from "@/features/integrations/IntegrationsTab";
import { SecurityTab } from "@/features/identity/SettingsSecurityTab";
import { RolesMatrixTab, UsersTab } from "@/features/identity/SettingsUsersTab";
import { useTenantPath } from "@/routing/tenantPath";

import { TemplateCatalogTab } from "../notifications/TemplateCatalog";
import { NotificationsTab } from "../notifications/SettingsNotificationsTab";

import { AccountingTab } from "./SettingsAccountingTab";
import { CustomerPortalTab } from "./SettingsCustomerPortalTab";
import { BillingPlanTab } from "./SettingsBillingPlanTab";
import { CompanyTab } from "./SettingsCompanyTab";
import { NumberingTab } from "./SettingsNumberingTab";
import { ReferenceDataTab } from "./SettingsReferenceData";
import { RegionalTab } from "./SettingsRegionalTab";
import { RoutesCyclesTab } from "./SettingsRoutesCyclesTab";
import { ServicesTab } from "./SettingsServicesTab";
import { ArrivesWith, SettingsDenied } from "./settingsShared";

import "./SettingsPage.css";

// ── The tab set (A1 addendum 2026-08-07 + r6 + r7 order + r8 Templates) ────

/**
 * The A4 permission ROW that governs a tab. Both codes are the server's
 * (`GET /roles` → `permissions[].code`), never invented here.
 */
export type SettingsPermission = "settings_lookups" | "user_management";

export interface SettingsTab {
  id: string; // URL segment — a contract with US-TEN-003's checklist targets
  labelKey: string;
  permission: SettingsPermission;
  // Absent = live. Present = the honest A18 state naming what the tab waits
  // for; such a tab renders no fields and posts nothing.
  arrivesWithKey?: string;
}

/**
 * The tab that carries everything a tenant SETS UP and then leaves alone —
 * reference lists, read routes and billing cycles, number formats, document
 * templates. Its id stays `reference-data` deliberately (CR-001): the label
 * changed, the URL did not, so nothing anyone bookmarked stops working.
 */
export const CONFIGURE_TAB = "reference-data";

/**
 * S8 → Accounting — the GL code mapping surface (BR-BIL-067 · BR-BIL-069).
 *
 * The id is the URL segment, and it is `accounting` because that is the word
 * the prototype uses for this destination ("Edit in Settings → Accounting").
 * Nothing links here yet, so no legacy redirect is owed.
 */
export const ACCOUNTING_TAB = "accounting";
/**
 * BR-TEN-041 #8's delivery/dispatch home — a CONFIGURE SEGMENT since
 * 2026-10-22, no longer a top-level tab.
 *
 * PO, verbatim: *"Settings → Configure → Notifications, sitting next to
 * Templates - this is correct understanding"*. The id is unchanged so the word
 * in the address is unchanged; it moved one level down, exactly as CR-001
 * moved Templates, and `/settings/notifications/...` redirects to it
 * (`legacyNotificationsPath`, one routed test per old address).
 */
export const NOTIFICATIONS_TAB = "notifications";
/**
 * S8 → Billing plan — S107, what this utility pays BYNRY (DEF-1092).
 *
 * The id is the URL segment it has always had, so nothing anyone bookmarked
 * while it was an "arrives with" panel stops resolving.
 */
export const BILLING_PLAN_TAB = "billing-plan";

export const SETTINGS_TABS: readonly SettingsTab[] = [
  { id: "company", labelKey: "settings.tab.company", permission: "settings_lookups" },
  { id: "users", labelKey: "settings.tab.users", permission: "user_management" },
  { id: "services", labelKey: "settings.tab.services", permission: "settings_lookups" },
  // CR-001 (PO 2026-08-11): Routes & Cycles, Numbering and Templates moved
  // INSIDE this tab, and the tab is relabelled "Configure". Four top-level
  // tabs became one; the id stays `reference-data` so every deep link, every
  // checklist target and every bookmark still resolves (see
  // CONFIGURE_SUB_TABS and LEGACY_SETTINGS_TAB_PATHS below).
  { id: CONFIGURE_TAB, labelKey: "settings.tab.referenceData", permission: "settings_lookups" },
  // S8 → Accounting: the GL code mapping (BR-BIL-067 · BR-BIL-069), added
  // 2026-08-11. The PO closed OQ-106 with *"it will be done during GL code
  // mapping in settings"*, and the prototype names the destination in its own
  // words — `05-prototype/UtilityBilling.html` 3714 and 3930 both send the
  // reader to "Settings → Accounting" from the read-only Finance panel. That
  // is a TWO-segment path, which is why this is a top-level tab and not a
  // fifth child of Configure; CR-001's four children are the four the PO named
  // and adding a fifth would be inferring a grouping the CR warns against.
  // ⚠ NINE tabs where CR-001 measured that eight fit on one line and eleven
  // wrapped. OQ-151 puts the placement to the PO; moving it is one line here
  // plus a LEGACY_SETTINGS_TAB_PATHS entry.
  { id: ACCOUNTING_TAB, labelKey: "settings.tab.accounting", permission: "settings_lookups" },
  // ⚠ NOTIFICATIONS LEFT THIS ROW 2026-10-22 — it is Configure's segment now,
  // next to Templates (PO: *"Settings → Configure → Notifications, sitting next
  // to Templates - this is correct understanding"*). See CONFIGURE_SUB_TABS.
  // CR-069 wave A, 2026-09-03: `arrivesWithKey` REMOVED and the tab MOUNTED —
  // the third time this exact edit has been made (DEF-128 notifications,
  // DEF-1092 billing plan). It read *"Accounting, payment, meter and email
  // connections arrive with the Integrations feature. No connection can be made
  // from here yet"* in all eleven catalogues, and the grid now draws seventeen
  // provider cards from the registry, so the sentence stopped being true. A
  // string claiming a state of the product is a claim (hard-won law 1).
  { id: "integrations", labelKey: "settings.tab.integrations", permission: "settings_lookups" },
  { id: "security", labelKey: "settings.tab.security", permission: "settings_lookups" },
  // DEF-1092, 2026-08-27: `arrivesWithKey` REMOVED and the tab MOUNTED. It read
  // *"Your SMARTBillHub subscription, invoices and payment method arrive with
  // the Billing plan feature"* in all eleven catalogues while `subscriptions`
  // had been seeded since `tenancy/0005` — sixteen days — and CR-039 wave F
  // added `implementation_orders`, `addons` and `tenant_addons` behind the same
  // sentence. **A tenant carried a quotable `IMPL-26-0001` that no human being
  // could see anywhere in the product.** The PO asked for the screen directly:
  // *"wave F has models and numbering but no screen (DEF-1092) — Can you build
  // this screen?"*
  //
  // ⚠ THE SENTENCE IS NOT WHOLLY RETIRED, IT MOVES AND NARROWS. Two thirds of
  // what it promised are still absent — the subscription INVOICES (S108) and
  // the PAYMENT METHOD (S109) — so those two clauses are now stated ON the tab,
  // beside the things that DO render, instead of standing in for the whole
  // feature. A blanket "arrives with" over a built subscription card is the
  // stale-claim shape hard-won law 1 is about (DEF-128 removed this exact
  // `arrivesWithKey` from Notifications for the same reason).
  { id: BILLING_PLAN_TAB, labelKey: "settings.tab.billingPlan", permission: "settings_lookups" },
];

export const DEFAULT_SETTINGS_TAB = "company";

/** BR-SHL-011's spirit: an unknown `:tab` falls back, it never errors. */
export function settingsTabFromParam(raw: string | undefined): string {
  if (raw === undefined) {
    return DEFAULT_SETTINGS_TAB;
  }
  return SETTINGS_TABS.some((tab) => tab.id === raw) ? raw : DEFAULT_SETTINGS_TAB;
}

// ── Company's second-level strip (prototype §Settings, lines 4458–4461) ────

/** A sub-tab inside a tab body. Same shape of contract, one level down. */
export interface SettingsSubTab {
  id: string; // URL segment — `/settings/company/<id>`
  labelKey: string;
}

/** The one tab that has a second level. Named so the switch and the URL agree. */
export const COMPANY_TAB = "company";

/**
 * The two the prototype draws, in its order. The labels are ITS words, not a
 * paraphrase: G14 compares shipped tab labels against the prototype's own
 * `.settings-tabs` strips, and both of these come out of one.
 */
export const COMPANY_SUB_TABS: readonly SettingsSubTab[] = [
  { id: "profile", labelKey: "settings.company.subTab.profile" },
  { id: "regional", labelKey: "settings.company.subTab.regional" },
];

// ── Configure's second-level strip (CR-001, PO ruling 2026-08-11) ──────────

/**
 * The four surfaces that used to be four top-level tabs.
 *
 * WHY THIS IS A REVERSAL AND WHY IT IS SOUND. A1 Addendum r6 (2026-08-07) says
 * in as many words that "Routes & Cycles, Numbering, and Security remain their
 * own tabs (they are configuration/security, not editable reference lists)" —
 * a signed decision with a good reason. The PO's move works because it comes
 * with the RENAME: r6's objection is to the words "Reference data", not to the
 * grouping, and "Configure" describes all four accurately. Filing them under a
 * heading still called "Reference data" would have been exactly the mistake r6
 * refused.
 *
 * SECURITY DOES NOT MOVE, and the two lists differ by one on purpose: r6 named
 * Routes & Cycles, Numbering and SECURITY; the PO named Routes & Cycles,
 * Numbering and TEMPLATES. A password policy is not a thing you file next to a
 * list of meter types, and r6's reason for that is untouched.
 *
 * IDs are the segments these tabs already had, so `/settings/number-series`
 * and friends keep meaning what they meant (LEGACY_SETTINGS_TAB_PATHS
 * redirects them one level down). Reference data is first and is the default,
 * because it is the surface the tab was before it grew.
 */
export const CONFIGURE_SUB_TABS: readonly SettingsSubTab[] = [
  { id: "reference-data", labelKey: "settings.configure.subTab.referenceData" },
  { id: "routes-cycles", labelKey: "settings.tab.routesCycles" },
  { id: "number-series", labelKey: "settings.tab.numbering" },
  { id: "templates", labelKey: "settings.tab.templates" },
  // 2026-10-22 — the delivery home, moved from the top row to sit next to
  // Templates. Its own strip (Settings · Messages needing attention · Blocked
  // addresses) is the fourth segment of the address.
  { id: NOTIFICATIONS_TAB, labelKey: "settings.tab.notifications" },
  // CR-068 wave A (2026-09-03): the portal's back office — CWP-069 Overview and
  // CWP-070 Branding — as a FIFTH Configure segment, NOT a tenth top-level tab
  // (EP-CWP-12: Settings already carries nine; the blueprint's own §15 records
  // the miscount that argued for a tenth). Its screens live in
  // SettingsCustomerPortalTab.tsx; its own third-level strip is `:segment`.
  { id: "customer-portal", labelKey: "settings.configure.subTab.customerPortal" },
];

export const DEFAULT_CONFIGURE_SUB_TAB = "reference-data";

/** BR-SHL-011's spirit, one level down: an unknown `:sub` falls back. */
export function configureSubTabFromParam(raw: string | undefined): string {
  if (raw === undefined) {
    return DEFAULT_CONFIGURE_SUB_TAB;
  }
  return CONFIGURE_SUB_TABS.some((sub) => sub.id === raw) ? raw : DEFAULT_CONFIGURE_SUB_TAB;
}

export const DEFAULT_COMPANY_SUB_TAB = "profile";

// ── Users & roles' second-level strip (PO ruling 2026-09-17) ───────────────
//
// ⚠ **NO `CR` ID IS CITED HERE AND THAT IS DELIBERATE.** This branch holds no
// block in `12-governance/14-id-reservations.md`, and a CR number invented
// outside a reserved block is the collision that file exists to prevent — the
// STRING `CR-0xx-BRCyy` is unique while the NUMBER is not, and a number is what
// a person says out loud. The ruling is in `12-governance/02-decision-log.md`
// with its date and the PO's own words, which is where the next lane looks.

/** The tab id, named so the switch, the strip and the URL agree on one spelling. */
export const USERS_TAB = "users";

/**
 * THE GRID STOPS BEING A PANEL AND BECOMES AN ADDRESS.
 *
 * Until now `Users & roles` drew the user table and a *"View roles &
 * permissions"* button that toggled `matrixOpen` and revealed the BR-IDN-014
 * grid underneath it. Two surfaces, one address, and the second one reachable
 * only by pressing something — so it could not be linked, could not be
 * bookmarked, and vanished the moment anyone navigated away and came back.
 *
 * It is the third strip in this file and it is deliberately the SAME mechanism
 * as the other two rather than a better one: `/settings/users/roles` is a URL
 * like `/settings/company/regional`, `usersSubTabFromParam` falls back exactly
 * as its two siblings do, and `UsersSubTabs` renders the same `.settings-tabs`
 * markup. A second way of doing sub-tabs would be a second thing to keep true.
 *
 * ⚠ **NOTHING BOOKMARKED BREAKS, because nothing COULD be bookmarked** — the
 * panel was `useState`, not a route, and `/settings/users` still opens the user
 * table exactly as it always did. The grid gains an address; it loses none.
 */
export const USERS_SUB_TABS: readonly SettingsSubTab[] = [
  { id: "users", labelKey: "settings.users.subTab.users" },
  { id: "roles", labelKey: "settings.users.subTab.roles" },
];

export const DEFAULT_USERS_SUB_TAB = "users";

/** BR-SHL-011's spirit once more, one level down: unknown `:sub` falls back. */
export function usersSubTabFromParam(raw: string | undefined): string {
  if (raw === undefined) {
    return DEFAULT_USERS_SUB_TAB;
  }
  return USERS_SUB_TABS.some((sub) => sub.id === raw) ? raw : DEFAULT_USERS_SUB_TAB;
}

/** BR-SHL-011's spirit again, one level down: unknown `:sub` falls back. */
export function companySubTabFromParam(raw: string | undefined): string {
  if (raw === undefined) {
    return DEFAULT_COMPANY_SUB_TAB;
  }
  return COMPANY_SUB_TABS.some((sub) => sub.id === raw) ? raw : DEFAULT_COMPANY_SUB_TAB;
}

/**
 * Tab ids that USED to be top-level and now live one level down. The S62
 * checklist's targets are SERVER data (`apps/tenancy/selectors.py`
 * CHECKLIST_TARGETS still sends "settings/regional" for `fiscal_billing`), so
 * the old URL cannot simply stop existing: App.tsx mounts a redirect for every
 * entry here, and the link keeps landing on the surface it always meant.
 * Moving a tab and breaking a live deep link would be the worse defect.
 */
export const LEGACY_SETTINGS_TAB_PATHS: Readonly<Record<string, string>> = {
  regional: `/settings/${COMPANY_TAB}/regional`,
  // CR-001: three tabs moved one level down. Every one of these is a LIVE
  // deep link today — `settings/number-series` is a checklist target the
  // SERVER sends (US-TEN-003), the Reference data screen links to
  // `/settings/templates` for the BR-TEN-033 document-template pointer, and
  // the deployed app has been serving all three for weeks. A tab move that
  // 404s a checklist link would be this change request causing a defect.
  "routes-cycles": `/settings/${CONFIGURE_TAB}/routes-cycles`,
  "number-series": `/settings/${CONFIGURE_TAB}/number-series`,
  templates: `/settings/${CONFIGURE_TAB}/templates`,
  // 2026-10-22: Notifications moved under Configure, next to Templates.
  [NOTIFICATIONS_TAB]: `/settings/${CONFIGURE_TAB}/${NOTIFICATIONS_TAB}`,
};

/** Configure → Notifications, the one spelling every link builds from. */
export const CONFIGURE_NOTIFICATIONS_PATH = `/settings/${CONFIGURE_TAB}/${NOTIFICATIONS_TAB}`;

/** Its *Messages needing attention* tab — the bell links here in one click. */
export const MESSAGES_NEEDING_ATTENTION_PATH = `${CONFIGURE_NOTIFICATIONS_PATH}/messages`;

/**
 * Where an old `/settings/notifications/<sub>` address goes (decision log
 * 2026-10-22, lane SETTINGS-MOVE item 2). Two of the old tabs moved OUT of
 * Notifications, so they get their new home rather than a 404:
 *   · `rights` — the Customer rights wording is on Templates, under the
 *     disconnection letter it prints on;
 *   · `sender` — the mail server lives on Connectors only.
 * Every other segment (`messages`, `blocked`, an event key) keeps its name one
 * level down.
 */
export const LEGACY_NOTIFICATIONS_SUB_PATHS: Readonly<Record<string, string>> = {
  rights: `/settings/${CONFIGURE_TAB}/templates?template=disconnect_notice_10_day`,
  sender: "/settings/integrations/email_smtp",
};

export function legacyNotificationsPath(sub: string | undefined): string {
  if (sub === undefined || sub === "") {
    return CONFIGURE_NOTIFICATIONS_PATH;
  }
  return LEGACY_NOTIFICATIONS_SUB_PATHS[sub] ?? `${CONFIGURE_NOTIFICATIONS_PATH}/${encodeURIComponent(sub)}`;
}

/** `/settings/notifications/:sub` → its new home (routed in App.tsx). */
export function LegacyNotificationsRedirect() {
  const tenantPath = useTenantPath();
  const { sub } = useParams();
  return <Navigate to={tenantPath(legacyNotificationsPath(sub))} replace />;
}

/** The canonical path a retired tab id now points at, or null if it is live. */
export function legacySettingsPath(tab: string | undefined): string | null {
  if (tab === undefined) {
    return null;
  }
  return LEGACY_SETTINGS_TAB_PATHS[tab] ?? null;
}

/**
 * The redirect App.tsx mounts at each retired tab's old path. It resolves the
 * tenant through the ONE helper (never a hand-built `/${tenant}/…`), so the old
 * link stays inside the tenant it was opened in.
 */
export function LegacySettingsTabRedirect(props: { tab: string }) {
  const tenantPath = useTenantPath();
  const target = legacySettingsPath(props.tab) ?? `/settings/${DEFAULT_SETTINGS_TAB}`;
  return <Navigate to={tenantPath(target)} replace />;
}

// ── RBAC (BR-SHL-025: the SERVER's permission set, never a role-name check) ──

// The A4 cell vocabulary exactly as the server serves it (identity A4_MATRIX).
export const CELL_NONE = "—";
export const CELL_VIEW = "View";
export const CELL_FULL = "Full";

export interface SettingsAccess {
  settings_lookups: string; // the server's cell, copied verbatim
  user_management: string;
}

/**
 * THE access source (BR-SHL-025): `GET /me/permissions` — the server's own
 * answer for "what may I reach", readable by ANY tenant role. Every cell is
 * copied verbatim; nothing here decides what a role may do, and nothing here
 * grants anything: each endpoint still enforces its own gate and its 403 is
 * still the boundary. Hiding a "—" tab is convenience, and only convenience.
 *
 * This replaces the old probe-a-tab-and-read-the-403 behaviour: before this
 * route existed, the only permission read was the System-Admin-only `/roles`
 * grid, so a Clerk or Executive could not be gated at all and every tab had to
 * be drawn and then denied.
 */
export function accessFromPermissions(
  permissions: MyPermissions | null | undefined,
): SettingsAccess | null {
  if (permissions === null || permissions === undefined) {
    return null;
  }
  const cell = (code: SettingsPermission): string =>
    permissions.permissions.find((row) => row.code === code)?.access ?? CELL_NONE;
  return { settings_lookups: cell("settings_lookups"), user_management: cell("user_management") };
}

/**
 * The BACKSTOP source, kept for the case where `/me/permissions` itself cannot
 * be read: the membership role from `GET /me` against the `GET /roles` grid.
 *
 * Returns null when either half is missing. Null means "hide nothing": each
 * tab's own request is then the boundary and answers 403, which renders A18 §6
 * inside the frame. The server is always the law.
 */
export function resolveSettingsAccess(
  me: SessionUser | null | undefined,
  matrix: RolesMatrix | null | undefined,
): SettingsAccess | null {
  if (me === null || me === undefined || me.role === null) {
    return null;
  }
  if (matrix === null || matrix === undefined) {
    return null;
  }
  const role = me.role;
  const cell = (code: SettingsPermission): string =>
    matrix.permissions.find((permission) => permission.code === code)?.cells[role] ?? CELL_NONE;
  return { settings_lookups: cell("settings_lookups"), user_management: cell("user_management") };
}

/** BR-SHL-003: a surface the role cannot reach is not drawn at all. */
export function visibleSettingsTabs(
  tabs: readonly SettingsTab[],
  access: SettingsAccess | null,
): readonly SettingsTab[] {
  if (access === null) {
    return tabs;
  }
  return tabs.filter((tab) => access[tab.permission] !== CELL_NONE);
}

/** BR-SHL-025: a "View" cell renders the tab with every write control disabled. */
export function tabIsReadOnly(tab: SettingsTab, access: SettingsAccess | null): boolean {
  return access !== null && access[tab.permission] === CELL_VIEW;
}

// ── The screen ─────────────────────────────────────────────────────────────

export interface SettingsPageProps {
  client?: ApiClient; // test seam — screens never build their own transport
  /** Which Configure segment a four-segment `…/:segment` route belongs to —
   *  `customer-portal` (CWP-069/070) or `notifications` (2026-10-22). */
  configureSub?: string;
}

export function SettingsPage(props: SettingsPageProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const params = useParams();
  const client = props.client ?? api;
  // `settings/reference-data/customer-portal/:segment` (App.tsx) is an
  // all-static path plus one id, so React Router ranks it above
  // `settings/:tab/:sub` — and hands this component `segment` INSTEAD of
  // `tab`/`sub`. Reading them back here keeps one SettingsPage rather than a
  // second frame for a third-level strip (the routes-cycles routes are the
  // precedent for the shape; this is the first tab whose strip goes three deep).
  const tab = params.tab ?? (params.segment !== undefined ? CONFIGURE_TAB : undefined);
  const sub =
    params.sub ??
    (params.segment !== undefined ? (props.configureSub ?? "customer-portal") : undefined);
  const activeId = settingsTabFromParam(tab);

  const meQuery = useQuery({
    queryKey: queryKeys.me,
    queryFn: () => getMe(client),
    staleTime: REFERENCE_STALE_MS,
  });
  // BR-SHL-025: the caller's OWN A4 row — the read that actually gates this
  // frame. Any tenant role may make it (ETag-cacheable, 11b G6).
  const permissionsQuery = useQuery({
    queryKey: queryKeys.myPermissions,
    queryFn: async () => (await getMyPermissions(client)).data,
    staleTime: REFERENCE_STALE_MS,
  });
  // BR-IDN-014: the whole grid is a System-Admin-only reference read. It is the
  // BACKSTOP only — a 403 here is not an error state, it is "you are not an
  // admin", and each tab body's own 403 still carries the message.
  const rolesQuery = useQuery({
    queryKey: queryKeys.rolesMatrix,
    queryFn: async () => (await getRolesMatrix(client)).data,
    staleTime: REFERENCE_STALE_MS,
  });
  // CR-155-BRC09 — the page subtitle. The SAME key the shell already fetched
  // at boot, so this resolves from cache and issues no second request.
  const displayQuery = useQuery({
    queryKey: queryKeys.shellDisplay,
    queryFn: () => getShellDisplay(client),
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });
  const company = displayQuery.data?.company;
  // `params.tenant` rather than the shell's `tenantFromPathname(pathname)`:
  // this component is mounted UNDER `/:tenant/settings/...`, so the router has
  // already parsed it and a second parser would be a second answer.
  const utilityName = company?.dba_name || company?.legal_name || (params.tenant ?? "");

  if (meQuery.isPending) {
    return <LoadingSkeleton variant="card" />; // A18 §3
  }

  const access =
    accessFromPermissions(permissionsQuery.data) ??
    resolveSettingsAccess(meQuery.data, rolesQuery.data);
  const tabs = visibleSettingsTabs(SETTINGS_TABS, access);

  if (tabs.length === 0) {
    // A4: Settings is "—" for a Billing Clerk — the whole page, not one tab.
    return <SettingsDenied helper={t("settings.denied.page")} />;
  }

  const active = tabs.find((tab) => tab.id === activeId) ?? tabs[0];
  const readOnly = tabIsReadOnly(active, access);

  return (
    <div className="settings-page">
      <div className="settings-head">
        <h1>{t("settings.title")}</h1>
        {/* ── CR-155-BRC09 · THE SUBTITLE IS THE UTILITY, NOT A SENTENCE ────
         *
         * It read *"Configure the platform. Every change is audit-logged."*
         * The PO's approved Security redesign (2026-09-29) draws the utility's
         * NAME here instead, and both halves of that old line are why:
         *   · *"Configure the platform"* restates the word `Settings` in the
         *     `<h1>` directly above it — B14 rule 32's description budget, and
         *     the same "a row never repeats what its own control offers" the
         *     PO ruled four times in twenty minutes;
         *   · *"Every change is audit-logged"* is RATIONALE — why the product
         *     works this way — which B14 rule 33 puts at ZERO words on screen.
         *     The Audit log card on the Security tab now says it by existing,
         *     which is the difference between showing and explaining.
         *
         * The fallback chain is `ShellWithSession`'s own, copied deliberately
         * rather than invented: two places naming one utility two different
         * ways is worse than the duplication.
         */}
        <p className="settings-sub">{utilityName}</p>
      </div>

      {/* A12 `.settings-tabs` — ported layout from the signed prototype. */}
      <div className="settings-tabs" role="tablist" aria-label={t("settings.tabsLabel")}>
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={tab.id === active.id}
            className={tab.id === active.id ? "active" : undefined}
            onClick={() => navigate(tenantPath(`/settings/${tab.id}`))}
          >
            {t(tab.labelKey)}
          </button>
        ))}
      </div>

      <SettingsTabBody tab={active} sub={sub} readOnly={readOnly} client={client} />
    </div>
  );
}

/**
 * The body behind the active tab. EXPORTED for one reason (DEF-INT-3632,
 * 2026-09-04): the honest-state mechanism — a tab declaring `arrivesWithKey`
 * renders the A18 absence box and no control — must stay proved after the
 * last real tab carrying the key was mounted, so the frame's suite hands this
 * a tab of its own instead of borrowing one that no longer exists.
 */
export function SettingsTabBody(props: {
  tab: SettingsTab;
  sub: string | undefined;
  readOnly: boolean;
  client: ApiClient;
}) {
  const { t } = useTranslation();
  const { tab, readOnly, client } = props;
  if (tab.arrivesWithKey !== undefined) {
    return <ArrivesWith title={t(tab.labelKey)} message={t(tab.arrivesWithKey)} />;
  }
  switch (tab.id) {
    case COMPANY_TAB:
      return <CompanySubTabs sub={props.sub} readOnly={readOnly} client={client} />;
    case USERS_TAB:
      // `sub` IS PASSED, like Company's and Configure's. A prop declared and
      // not supplied is the DEF-007..010 class G13 exists for.
      return <UsersSubTabs sub={props.sub} readOnly={readOnly} client={client} />;
    case "services":
      return <ServicesTab readOnly={readOnly} client={client} />;
    case CONFIGURE_TAB:
      return <ConfigureSubTabs sub={props.sub} readOnly={readOnly} client={client} />;
    case ACCOUNTING_TAB:
      // `sub` IS PASSED (CR-008): Accounting grew three sub-tabs of its own —
      // chart · mapping · controls — and they are URL segments like Configure's,
      // so `/settings/accounting/mapping` is a link somebody can send. A prop
      // declared and not supplied is the DEF-007..010 class G13 exists for.
      return <AccountingTab readOnly={readOnly} sub={props.sub} client={client} />;
    case "integrations":
      // CR-069 wave B, 2026-09-03: `readOnly` now travels, because the grid
      // carries a button per card and the modal behind it (wave A passed
      // nothing on purpose — a read with no write control, G13's shape). An
      // Executive sees every control disabled with the reason (BR-SHL-025).
      return <IntegrationsTab readOnly={readOnly} client={client} />;
    case "security":
      return <SecurityTab readOnly={readOnly} client={client} />;
    case BILLING_PLAN_TAB:
      // BOTH props are passed. `readOnly` is not decorative here (G13): the
      // screen has no write control to disable, so it selects the sentence at
      // the foot — an Executive is told the read is what their role gets, a
      // System Admin is told a plan change is a conversation with Bynry.
      return <BillingPlanTab readOnly={readOnly} client={client} />;
    default:
      // Unreachable while SETTINGS_TABS and this switch agree; the honest state
      // beats a blank panel if they ever drift.
      return <ArrivesWith title={t(tab.labelKey)} message={t("settings.arrivesWith.unknown")} />;
  }
}

/**
 * Configure's strip (CR-001). Same mechanism as Company's, one tab over —
 * a plain `.settings-tabs` block INSIDE the tab body, never a second
 * PageHeader (that would put a second <h1> on the page; see CompanySubTabs
 * below for the full reasoning, which is unchanged and not repeated).
 *
 * TEMPLATES IS NOT BUILT, and it says so rather than rendering an empty panel.
 * It was a top-level tab carrying an `arrivesWith` message; moving it one level
 * down must not lose that honesty, so the sub-tab renders the same message. A
 * moved tab that silently became blank would be this change request causing a
 * defect — which is the same trap `LEGACY_SETTINGS_TAB_PATHS` exists to avoid
 * one level up.
 *
 * All four are governed by the SAME A4 cell (`settings_lookups`) that gated
 * them as top-level tabs, so `readOnly` passes straight through and the move
 * changes nobody's permissions.
 */
/**
 * CR-009 — the Notifications tab's one piece of routing, kept HERE rather than
 * inside the tab so the tab stays a pure consumer of `sub` like every other.
 * `null` closes the open rule page and returns to the matrix, which is the
 * requirement's *"Save … returns to matrix"* and the ← Back control's target.
 */
function NotificationsTabWithRouting(props: {
  sub: string | undefined;
  readOnly: boolean;
  client: ApiClient;
}) {
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  return (
    <NotificationsTab
      readOnly={props.readOnly}
      client={props.client}
      sub={props.sub}
      onOpenRule={(eventKey) => {
        navigate(
          tenantPath(
            eventKey === null
              ? CONFIGURE_NOTIFICATIONS_PATH
              : `${CONFIGURE_NOTIFICATIONS_PATH}/${eventKey}`,
          ),
        );
      }}
    />
  );
}

function ConfigureSubTabs(props: {
  sub: string | undefined;
  readOnly: boolean;
  client: ApiClient;
}) {
  // ⛔ **DEF-212 (4)'s `templateDetailOpen` GUARD IS GONE, AND IT IS SOLVED
  // RATHER THAN DROPPED — CR-048 task E9, 2026-08-30.** It read the `?template=`
  // param here so the bill-layout chooser stopped rendering underneath an open
  // template ("One document, one home"), because the chooser was a SIBLING of
  // the catalogue and neither knew the other existed. Under `BR-NOT-026` the
  // Templates sub-tab renders ONE component, which lists both kinds and opens
  // the chooser as a bill row's editor — so only one editor can be open at a
  // time structurally, and a condition that duplicated that fact here would be
  // a second, drifting statement of it (hard-won law 1).
  const { t } = useTranslation();
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const { readOnly, client } = props;
  const active = configureSubTabFromParam(props.sub);
  // Configure → Notifications' own segment (`…/notifications/:segment`):
  // `messages`, `blocked` or an event key, exactly as `:sub` was before.
  const { segment } = useParams();
  return (
    <>
      <div className="settings-tabs" role="tablist" aria-label={t("settings.tab.referenceData")}>
        {CONFIGURE_SUB_TABS.map((sub) => (
          <button
            key={sub.id}
            type="button"
            role="tab"
            aria-selected={sub.id === active}
            className={sub.id === active ? "active" : undefined}
            onClick={() => navigate(tenantPath(`/settings/${CONFIGURE_TAB}/${sub.id}`))}
          >
            {t(sub.labelKey)}
          </button>
        ))}
      </div>
      {active === "routes-cycles" ? (
        <RoutesCyclesTab readOnly={readOnly} client={client} />
      ) : active === "number-series" ? (
        <NumberingTab readOnly={readOnly} client={client} />
      ) : active === "customer-portal" ? (
        <CustomerPortalTab readOnly={readOnly} client={client} />
      ) : active === NOTIFICATIONS_TAB ? (
        <NotificationsTabWithRouting readOnly={readOnly} sub={segment} client={client} />
      ) : active === "templates" ? (
        // ⚠ THE `arrivesWith` PANEL IS GONE, 2026-08-16. It said "arrives with
        // the template designer" while `templates_service.py` held a complete
        // draft→publish→archive lifecycle nothing could reach — and the PO then
        // CUT the designer outright (*"why cant we give 5 differnt tempaltes to
        // start with and ask user to choose anyone; we will ahve 1 default
        // tempalte allways"*). So the sentence was doubly stale: it promised a
        // screen that is no longer being built, in place of one that now exists.
        // Hard-won law 1 — a string claiming a state of the product is a claim.
        //
        // ⚠ AND IT IS NO LONGER ALONE, 2026-08-17 (CR-007). SET-09/SET-10 —
        // the catalog of every document and message the platform sends, with
        // variants, live preview, editing and versioning — is the tab's main
        // surface now, and the bill layout chooser keeps its own panel BELOW
        // it rather than being folded in.
        //
        // The split is B2 r10 #4 and it is not a layout preference: bills and
        // statements pin BILLING's registry (`bill_templates`) with its own
        // chooser, and everything else pins NOTIFICATIONS' (BR-TEN-033 —
        // *"tenancy stores no template content"*). The catalog deliberately
        // does not list bills, so a table that cannot serve them must not be
        // the only thing on this tab. One document, one home.
        //
        // Both are gated by the SAME A4 cell that gates every Configure
        // sub-tab, so `readOnly` passes straight through to both — the PO's
        // 2026-08-16 ruling (*"all settingsa re Admin only I believ; follow
        // same rule that we folowed for settings related permission"*) is the
        // gate this tab already used.
        // ⚠ **ONE COMPONENT NOW, NOT TWO — CR-048 task E9, 2026-08-30.**
        // `BillLayoutTab` used to render as a SIBLING below the catalogue, so
        // this tab drew TWO lists and *"the template we print bills on"* was in
        // the second one. The PO ruled on 2026-08-30 (*"Yes, Go with option B;
        // I agree"*, BR-NOT-026) that a person opens Templates ONCE and sees
        // both kinds together. `TemplateCatalogTab` lists both and OPENS the
        // layout chooser for a bill row, the way it opens the template detail
        // for a notification row — so the chooser is not deleted, it is the
        // editor behind a row instead of a second list beside one.
        //
        // ⚠ The `templateDetailOpen` guard that used to live here went with it
        // (DEF-212 (4) — "one document, one home"). It is now structural rather
        // than conditional: only one editor can be open at a time because only
        // one component renders.
        <TemplateCatalogTab readOnly={readOnly} client={client} />
      ) : (
        <ReferenceDataTab readOnly={readOnly} client={client} />
      )}
    </>
  );
}

/**
 * Company's own strip, drawn the way the prototype draws it: a plain
 * `.settings-tabs` block INSIDE the tab body (UtilityBilling.html §Settings
 * `show_company`), above the panels the chosen sub-tab renders.
 *
 * Deliberately not a PageHeader. PageHeader (US-SHL-020) owns a screen's ONE
 * header — back-link, kicker, <h1>, roll-up, actions, then its strip — and S8
 * already has a head above the top-level tabs. Nesting a second one inside a
 * tab body would put a second <h1> on the page, which BR-SHL-044's skeleton and
 * G14's shape check both forbid, and would offer an action slot and an
 * explainer that the prototype's sub-strip does not have. The prototype nests
 * a strip; so does this.
 *
 * Both sub-tabs are governed by the SAME A4 cell (`settings_lookups`) that
 * gates the Company tab, so `readOnly` passes straight through — nesting moved
 * the surface, it changed no permission.
 */
function CompanySubTabs(props: { sub: string | undefined; readOnly: boolean; client: ApiClient }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const active = companySubTabFromParam(props.sub);
  return (
    <div className="settings-subtabs">
      <div className="settings-tabs" role="tablist" aria-label={t("settings.company.subTabsLabel")}>
        {COMPANY_SUB_TABS.map((sub) => (
          <button
            key={sub.id}
            type="button"
            role="tab"
            aria-selected={sub.id === active}
            className={sub.id === active ? "active" : undefined}
            onClick={() => navigate(tenantPath(`/settings/${COMPANY_TAB}/${sub.id}`))}
          >
            {t(sub.labelKey)}
          </button>
        ))}
      </div>
      {active === "regional" ? (
        <RegionalTab readOnly={props.readOnly} client={props.client} />
      ) : (
        <CompanyTab readOnly={props.readOnly} client={props.client} />
      )}
    </div>
  );
}

/**
 * Users & roles' own strip, drawn exactly as Company's is drawn: a nested
 * `.settings-tabs` block inside the tab body, above whichever surface the
 * chosen sub-tab renders. Not a PageHeader, for the reason `CompanySubTabs`
 * records — S8 already has one head, and a second would put a second `<h1>` on
 * the page.
 *
 * Both sub-tabs are governed by the SAME A4 cell (`user_management`) that gates
 * the tab itself, so `readOnly` passes straight through. Nesting moved a
 * surface; it changed no permission — and BR-IDN-014's grid was read-only
 * before the move and is read-only after it, with no mutation route in
 * existence for it to gain.
 */
function UsersSubTabs(props: { sub: string | undefined; readOnly: boolean; client: ApiClient }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const active = usersSubTabFromParam(props.sub);
  return (
    <div className="settings-subtabs">
      <div className="settings-tabs" role="tablist" aria-label={t("settings.users.subTabsLabel")}>
        {USERS_SUB_TABS.map((sub) => (
          <button
            key={sub.id}
            type="button"
            role="tab"
            aria-selected={sub.id === active}
            className={sub.id === active ? "active" : undefined}
            onClick={() => navigate(tenantPath(`/settings/${USERS_TAB}/${sub.id}`))}
          >
            {t(sub.labelKey)}
          </button>
        ))}
      </div>
      {active === "roles" ? (
        <RolesMatrixTab client={props.client} />
      ) : (
        <UsersTab readOnly={props.readOnly} client={props.client} />
      )}
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-TEN-009@178c282 (story+rules snapshot hash — EP-TEN-07 lead story; co-packets EP-TEN-05@0733260 · EP-TEN-06@53479d6 · EP-TEN-08@80cdedf · EP-IDN-02@9d61512 · EP-IDN-03@c4e29d2 · EP-IDN-04@493ea2f · EP-MET-02@14f767b)
// generated: 2026-08-09 by story-coder v1 (W0 Settings screens lane) · AMENDED 2026-08-09 by story-coder (frontend integration lane: tab visibility now reads GET /me/permissions) · AMENDED 2026-08-10 by story-coder v1 (path-tenancy lane — PO ruling 2026-08-10: SPA `/{tenant}/…`, API `/api/{tenant}/…`) · AMENDED 2026-08-10 by story-coder v1 (Settings → Company sub-tab lane: E2 CLOSED — Regional nests as Company's second sub-tab, where the signed prototype draws it) · AMENDED 2026-08-11 by story-coder (S8 Accounting lane — a NINTH top-level tab mounting the GL code mapping; BR-BIL-067 and BR-BIL-069 both shipped a backend and neither had a screen)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: trace_lint✔ run_gates✔ (11 PASS · 0 FAIL · 1 SKIP) tsc✔ eslint✔ vitest 296 passed / 83 todo across 30 files✔ (239+72 baseline unchanged and green; this packet adds 57 passing + 11 todo — the todos are browser-interaction, server/RLS and unbuilt-neighbour-screen scope) · 2026-08-10 path-tenancy re-run: tsc✔ eslint✔ vitest 529 passed / 134 todo across 44 files✔ (509 passed / 132 todo was the pre-lane baseline — the suite grew, nothing was dropped) · vite build✔ · run_gates 11 PASS · 0 FAIL · 1 SKIP · trace_lint✔ · 2026-08-10 Company sub-tab re-run: tsc✔ eslint✔ vitest 604 passed / 142 todo across 46 files✔ (593 + 141 across 46 was the pre-lane baseline; +11 passing, +1 todo, none dropped — the 6 new checks were each shown RED on the divergence first, law 7) · vite build✔ · run_gates 13 PASS · 0 FAIL · 1 SKIP
// exceptions: E4 [S8 Accounting lane 2026-08-11] the strip now draws NINE top-level tabs where CR-001 measured eight fitting on one line at 1920px and eleven wrapping; `Accounting` is placed top-level on the prototype's own two-segment wording ("Edit in Settings → Accounting", UtilityBilling.html 3714/3930) and the placement is put to the PO as OQ-151, reversible in one line plus a legacy redirect · E4 no A1 screen id owns the Accounting surface — the prototype names it and never draws it, and US-BIL-009 declares screens [S56, S66] where S66 is Billing defaults; rendered under S8 and REPORTED, never renumbered (hard-won law 8) · E2 CLOSED 2026-08-10 — A1, EP-TEN-05 and 05-prototype/UtilityBilling.html (lines 4443, 4458–4461) all place Regional as Company's second SUB-tab; it now renders there, as a nested `.settings-tabs` strip inside the Company tab body rather than a second PageHeader (a nested PageHeader would draw a second <h1>, which BR-SHL-044 and G14's shape check forbid). The pre-nesting `/settings/regional` deep link REDIRECTS (LEGACY_SETTINGS_TAB_PATHS) because the S62 checklist target is server data this lane may not edit · E4 the prototype's Settings strip has TEN top-level tabs and the app draws ELEVEN: `templates` (A1 addendum r8, "Templates after Numbering") is in no prototype strip — divergence REPORTED by this lane, not fixed, because it is a spec-vs-prototype question for the PO, not this defect · E4 the two new sub-tab labels are prototype-verbatim but are NOT yet in G14's TAB_LABEL_KEYS list (10-scripts/ is outside this lane's territory) — adding them would make G14 guard them; REPORTED · E3 `GET /me/permissions` is a NEW route with no A11/11b contract row (it exists on the PO's 2026-08-09 "create endpoints for all and integrate" directive, and the backend packet reported it for the A11 addendum) — consumed here as the ratified-in-spirit gating source, flagged · E4 the A4 matrix has NO audit-log row, so the S61 entry in Settings → Security is gated by BR-AUD-009's own role list (System Admin + Executive), not by a permission cell — the backend flagged the same gap for the PO batch
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
