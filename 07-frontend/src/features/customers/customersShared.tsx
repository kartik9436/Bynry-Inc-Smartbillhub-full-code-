// ── Trace ──────────────────────────────────────────────
// Story:    US-CUS-001 (S17 accounts table + header roll-up) ·
//           US-CUS-002 (S17 search, filters and the wizard entry points) ·
//           US-CUS-003 (S18 New account — the two create statuses) ·
//           US-CUS-008 (S21 header identity, pills and refusals) ·
//           US-CUS-004 (S19 route + BR-CUS-056's earliest legal start) ·
//           US-CUS-005 (S20 route + the BR-CUS-030 occupant predicate)
//           Screens: S17 · S18 · S19 · S20 · S21
// Rules:    BR-CUS-015 (the S17 list contract; Balance is the CACHED
//           `accounts.balance`, the ledger stays the source of truth) ·
//           BR-CUS-016 (stored status comes from the account-status lookup;
//           Current / 30d past / 60+ past are DERIVED from open-invoice
//           due-date math and are NEVER stored) · BR-CUS-018 (a new account is
//           a draft that occupies nothing until something activates it) ·
//           BR-CUS-029 (the account plan snapshot has no table — the refusal is
//           rendered, never a substituted unit plan) · BR-CUS-045 (contact PII:
//           the last four of a government id is all there is) ·
//           BR-CUS-053 (the capability row: searched fields, the AC-8 filter
//           set, default sort name A→Z) · BR-CUS-054 (the first-class customer
//           entity has no table, so the name shown is the primary CONTACT's) ·
//           BR-CUS-055 (the five seeded, tenant-extensible statuses and their
//           behaviour classes) · BR-CUS-017 (at most ONE active account per
//           unit — which behaviour classes OCCUPY) · BR-CUS-030 (only an
//           occupant can move out) · BR-CUS-056 (the outgoing account pays the
//           move day, so the incoming one starts the next) · BR-SHL-025 (the A4
//           cell gates the UI; the server is authoritative) · BR-SHL-020
//           (plain-language absence)
// ───────────────────────────────────────────────────────
// The pieces S17 is built from. They live beside the screen rather than inside
// it so the honesty rules below are components, not conventions a second
// customers screen could forget.
//
// Three things this module refuses to do:
//
//   1. **It never invents an aging state.** BR-CUS-016 derives Current / 30d
//      past / 60+ past from open invoices; billing owns `invoices` and it does
//      not exist (W3), so the server sends `aging: null` and the row renders
//      the STORED status only. There is no code path here that turns a null
//      aging into "Current" — a fabricated one is a claim about a customer's
//      money.
//
//   2. **It never renders an absent value as zero or as a dash.** `AwaitsCell`
//      exists so "we do not know yet" is visibly different from "none" —
//      the `metering.ops.notCollected` precedent, applied to Last bill and to
//      the past-due-60+ roll-up figure.
//
//   3. **It never re-formats money or a date.** Every amount goes through the
//      shared MoneyCell and every date through the shared DateCell
//      (BR-SHL-023 / BR-SHL-034); nothing here parses a decimal string.
import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import type { AccountContact, AccountDetail, AccountRow, ServerWarning } from "@/api/endpoints";
import type { StatusTone } from "@/components/StatusPill";
import type { Translator } from "@/features/tenancy/settingsShared";
// The A4 row that governs accounts is the SAME row metering gates premises on
// — "Premises / Accounts" (BR-IDN-014). Importing the constant rather than
// re-typing the code keeps one literal, so the two screens cannot drift onto
// different permissions for one grid cell.
import { PREMISES_PERMISSION } from "@/features/metering/meteringShared";

import { getServiceRequestCategories } from "./serviceRequestEndpoints";

import "./customers.css";

// ── Routes (the AppShell sidebar's own path — SHELL_NAV `accounts`) ────────
// TENANT-RELATIVE, like every route constant since path tenancy landed (PO
// 2026-08-10): the screen that navigates puts it through `tenantPath()`.

export const ACCOUNTS_ROUTE = "/accounts";
export const DASHBOARD_ROUTE = "/dashboard";
/** S18 — the guided New account page (US-CUS-003). Static, so it outranks `:id`. */
export const ACCOUNT_NEW_ROUTE = "/accounts/new";

/**
 * S68 — the guided Import accounts page (US-CUS-019, screen id assigned by the
 * OQ-063 closure). Static like `new`, so React Router ranks it above
 * `:accountId` and the wizard is never mistaken for an account id.
 */
export const ACCOUNT_IMPORT_ROUTE = "/accounts/import";

/** S21 — the account detail (US-CUS-008). Deep-linkable, per-tab via `?tab=`. */
export function accountDetailPath(accountId: string): string {
  return `${ACCOUNTS_ROUTE}/${encodeURIComponent(accountId)}`;
}

/**
 * S20 — the guided Move-Out page (US-CUS-005). ACCOUNT-SCOPED, because the
 * endpoint is (`POST /accounts/{id}/move-out`, 11b §S20): the account leaving
 * is the one in the URL, so there is no "find account" search to build and no
 * standalone route to invent.
 */
export function accountMoveOutPath(accountId: string): string {
  return `${accountDetailPath(accountId)}/move-out`;
}

/**
 * DEF-724 — the CLOSE-OUT page (BR-CUS-430, PO 2026-08-27). Account-scoped for
 * `accountMoveOutPath`'s reason: the endpoint is
 * `GET|POST /accounts/{id}/close-out`.
 *
 * ⚠ **A SEPARATE PATH BECAUSE IT IS A SEPARATE ACT.** The temptation is to
 * route a cut customer at `/move-out` and relax the guard there — which would
 * file a disconnection as a move-out in the permanent record, and *"to a
 * regulator those are not the same event"*. Two paths, two acts.
 */
export function accountCloseOutPath(accountId: string): string {
  return `${accountDetailPath(accountId)}/close-out`;
}

/**
 * S19 — the guided Move-In page (US-CUS-004). The id is the OUTGOING account:
 * `POST /accounts/{id}/move-in` creates the next occupant of THAT account's
 * unit (11b §S19 defines exactly one move-in row and it is account-scoped).
 * A standalone move-in onto a unit with no predecessor has no path of its own
 * server-side; it is `POST /accounts` with an occupying status, which is S18.
 */
export function accountMoveInPath(fromAccountId: string): string {
  return `${accountDetailPath(fromAccountId)}/move-in`;
}

/**
 * S23 — the guided Change Plan page (US-CUS-016/017). ACCOUNT-SCOPED for the
 * same reason S19/S20 are: its endpoints are (`POST
 * /accounts/{id}/plan-changes`, 11b §2.6). The static `change-plan` segment
 * ranks above nothing that could swallow it.
 */
export function accountChangePlanPath(accountId: string): string {
  return `${accountDetailPath(accountId)}/change-plan`;
}

/**
 * S24 — the guided Payment Plan page (US-CUS-018). ACCOUNT-SCOPED like S19/S20
 * and S23, because its endpoints are (`GET|POST /accounts/{id}/payment-plans`
 * and its preview, 11b §S24): the account whose arrears are spread is the one
 * in the URL, so there is no "find account" step to build.
 *
 * The static `payment-plan` segment ranks above nothing that could swallow it.
 */
export function accountPaymentPlanPath(accountId: string): string {
  return `${accountDetailPath(accountId)}/payment-plan`;
}

/** BR-SHL-025 / A4: "Premises / Accounts" — Admin Full · Clerk Full · Exec View. */
export const ACCOUNTS_PERMISSION = PREMISES_PERMISSION;

// ── BR-CUS-018 — the two statuses the write path can put on a new account ──
// `services.create_account` defaults to the seeded draft; naming an occupying
// status makes the account the unit's occupant in the SAME transaction. Both
// codes are `services.SEED_ACCOUNT_STATUSES` verbatim (BR-CUS-055).

export const DRAFT_STATUS_CODE = "pending_activation";
export const ACTIVE_STATUS_CODE = "active";

// ── BR-CUS-055 — the seeded status vocabulary ──────────────────────────────
// The five codes and their order are `apps/customers/services.SEED_ACCOUNT_STATUSES`
// verbatim, which is BR-CUS-055 verbatim. They are the FILTER's options only.
//
// REPORTED, not worked around: BR-CUS-055 makes the list tenant-EXTENSIBLE, and
// a tenant-added status is therefore missing from this filter. The only route
// that enumerates them (`GET /lookups/account_statuses`) is System-Admin-only,
// and S17 must work for a Billing Clerk — so the filter offers the ratified
// seed and the ROW still renders whatever label the server sends (below).
export const ACCOUNT_SEED_STATUSES = [
  "pending_activation",
  "active",
  "marked_disconnect",
  "vacation_hold",
  "closed",
] as const;

/**
 * ⛔ **`ACCOUNT_CATEGORIES` IS DELETED — DEF-684, 2026-08-26.** It was a
 * four-code tuple (`residential · commercial · industrial · government`) under
 * this reasoning, which was sound the day it was written:
 *
 * > *"r5 #12 [D5]: `account_types` is a PLATFORM table — four rows, identical
 * > for every tenant, read-only even to a tenant admin. Hardcoding them here is
 * > therefore not a guess about a tenant's data; it is the platform catalog."*
 *
 * **The reasoning held and the FACT under it moved.** BR-CUS-094 (PO
 * 2026-08-24) expanded the signed vocabulary from four to SEVEN — Residential ·
 * Commercial · Industrial · Agricultural · Institutional · Municipal · Builder
 * or developer — and made `government` **LEGACY**: unselectable on a new
 * record, lawful everywhere else. The tuple was then one code short in one
 * direction and one refused code long in the other, and **four screens read
 * it**: S18 New account, S19 Move-in, the S14 common-areas master modal, and
 * S17's own category filter.
 *
 * A hardcoded platform catalogue cannot notice a ruling. This one is FETCHED
 * from the platform table itself, which is the only version that cannot go
 * stale again — the posture `ServiceRequestCapturePage` already took for
 * REQ-03.2, and the reason it was the one screen BR-CUS-094 did not break.
 *
 * The cross-stack pin is `06-backend/tests/test_def_684_category_vocabulary.py`:
 * no gate in this repo compared a frontend constant against a backend
 * vocabulary, which is why tsc, eslint and every screen test passed over the
 * wrong four for two days.
 */

/** One row of the platform `account_types` catalogue, as the server serves it. */
export interface AccountCategoryOption {
  code: string;
  name: string;
}

/**
 * ⚠ **THE SAME KEY `ServiceRequestCapturePage` USES**, deliberately: five
 * surfaces asking one platform table must share one cache entry, or a clerk who
 * opens the capture page and then the New account wizard fetches the same seven
 * rows twice and can be shown two different answers mid-flight.
 */
export const ACCOUNT_CATEGORIES_QUERY_KEY = ["service-request-categories"] as const;

/**
 * BR-CUS-094's two lists, fetched.
 *
 * `selectable` is what a PICKER may offer. `all` is `selectable` + `legacy` and
 * is what a FILTER offers, because the ruling is explicit that a legacy code
 * stays *"still a valid FK, still filterable, still priceable"* — every account
 * already carrying `government` has to remain findable, or the additive
 * migration hid live customers behind a chip.
 *
 * ⚠ **THE ORDER IS THE RULING'S, NEVER ALPHABETICAL.** The server returns
 * `selectable` in BR-CUS-094's own order and nothing here re-sorts it; sorting
 * would put Agricultural first and quietly re-order a screen the PO drew.
 *
 * ⚠ **NO LABEL IS TYPED HERE.** The name rides with the code, because
 * `customers.accounts.category.*` only ever held the superseded four — so a
 * category a future ruling adds renders its real name the day the migration
 * seeds it, rather than its raw slug.
 */
export function useAccountCategories(client: ApiClient = api): {
  selectable: AccountCategoryOption[];
  legacy: AccountCategoryOption[];
  all: AccountCategoryOption[];
  isLoading: boolean;
  failed: boolean;
} {
  const query = useQuery({
    queryKey: ACCOUNT_CATEGORIES_QUERY_KEY,
    queryFn: () => getServiceRequestCategories(client),
    retry: false,
  });
  const selectable = query.data?.selectable ?? [];
  const legacy = (query.data?.legacy ?? []).map((row) => ({ code: row.code, name: row.name }));
  return {
    selectable,
    legacy,
    all: [...selectable, ...legacy],
    isLoading: query.isPending,
    failed: !query.isPending && query.data === undefined,
  };
}

/**
 * The name for a stored category code, from the fetched catalogue.
 *
 * Falls back to the CODE, never to a guess: a row carrying a code the catalogue
 * does not hold is a fact about the data, and inventing a label for it is
 * exactly how `government` would quietly start reading as "Municipal" — the one
 * substitution BR-CUS-094 forbids by name.
 */
export function accountCategoryName(
  code: string,
  categories: readonly AccountCategoryOption[],
): string {
  return categories.find((row) => row.code === code)?.name ?? code;
}

/**
 * ── THE SUB-TYPE PICKER'S LIST — THE TENANT'S OWN ROWS, UNDER ONE PARENT ────
 *
 * `BR-CUS-067` / `CR-010` (PO 2026-08-17, *"add them"*) — `account_subtypes` is
 * the second level of a TWO-LEVEL tree and it is TENANT-DEFINED: the rows are
 * the utility's own vocabulary (*"where you will add Hospital, Church etc"*),
 * so nothing here types a list. `SEED_ACCOUNT_SUBTYPES` exists and is read by
 * the SEEDER alone; a copy of it on a screen would be `DEF-684` again, where a
 * hardcoded four survived a ruling that made them seven and three codes reached
 * a clerk as their raw slug.
 *
 * ⚠ **THE PARENT IS REQUIRED, SO THE CHILD LIST IS FILTERED BY IT.**
 * `AccountSubtypeLookupHandler._resolve_parent` refuses a row with no parent by
 * name (`customers.lookups.parent_required`) — *"a floating sub-type is a
 * sub-type of nothing"* — so Healthcare belongs to Commercial and to nothing
 * else. Offering the whole list under every category would let a clerk write
 * `commercial → light_industrial`, which no rule forbids at the write and no
 * screen would ever show as wrong.
 *
 * ⚠ **A ROW WITH NO PARENT IS OFFERED UNDER NOTHING, AND THAT IS DELIBERATE.**
 * Migration `customers 0011` made the column nullable, so rows that PREDATE the
 * ruling may carry NULL and the lookup card renders them at top level until
 * somebody edits them. There is no parent such a row is the child of, so there
 * is no category it can honestly be offered under. It stays reachable and
 * editable on Settings, which is where it gets a parent.
 *
 * ⚠ **AND `active` IS FILTERED HERE BECAUSE THE SERVER FILTERS IT AT THE WRITE.**
 * `services._resolve_account_subtype` resolves against `active=True` only, so a
 * deactivated row offered in this list is a choice the create would refuse by
 * name — `BR-TEN-034`'s posture, which deactivates rather than deletes.
 */
export const ACCOUNT_SUBTYPES_QUERY_KEY = ["customers", "account-subcategories"] as const;

/**
 * `GET /accounts/subcategories` (`DEF-CUS-6426`) — the ACTIVE sub-categories,
 * readable by every role. The Settings lookup over the same rows answers a
 * Billing Clerk 403 (see `useAccountSubtypes`), so the pickers read this.
 */
export async function getAccountSubcategories(
  client: ApiClient = api,
): Promise<{ results: { id: string; code: string; name: string; parent_code: string | null; active?: boolean }[] }> {
  const response = await client.get<{
    results: { id: string; code: string; name: string; parent_code: string | null; active?: boolean }[];
  }>("/accounts/subcategories");
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

export interface AccountSubtypeRow {
  /**
   * The row's database id.
   *
   * ⚠ **IT IS NEVER A VISIBLE VALUE — B14 rule 31** (*"no Databse ID on screen
   * - that is a rule"*). It is carried because ONE door takes the id where the
   * others take the code: `set_customer_category` on a SERVICE REQUEST
   * resolves `account_subtype_id` against `AccountSubtype.objects.filter(id=…)`
   * and accepts nothing else, while the ACCOUNT doors resolve either through
   * `_resolve_account_subtype`. A screen on that door must send an id, and the
   * alternative was a SECOND copy of this list under a second query key —
   * which is exactly what `ServiceRequestCapturePage` had, and is how it came
   * to offer all thirteen sub-types under every one of the seven categories.
   */
  id: string;
  /** What the picker SENDS on the ACCOUNT doors (B14 rule 31 — the NAME is
   *  what it shows). The CODE and not the id, matching `AccountPanelEdits`'
   *  dialog over this same column and `AccountDetail.account_subtype`; the
   *  server's `_resolve_account_subtype` takes either. */
  code: string;
  name: string;
  /** `account_types.code` of the row this one hangs off — `null` only for a
   *  row that predates the parent ruling. */
  parentCode: string | null;
  active: boolean;
}

export function useAccountSubtypes(client: ApiClient = api): {
  rows: AccountSubtypeRow[];
  isLoading: boolean;
  /**
   * ⛔ **THE READ WAS REFUSED.** ⚠ **FIXED 2026-09-23 (`DEF-CUS-6426`) — THIS
   * SAID *"FOR A BILLING CLERK IT ALWAYS IS"* AND CITED `DEF-CUS-5673`, WHICH
   * WAS NEVER FILED** (the register's 5673 is `DEF-GOV-5673`). The paragraph
   * below is what was measured then; the hook now reads the customers-side
   * `GET /accounts/subcategories`, which every role may read, and the Settings
   * door is untouched. `failed` now means only that THAT read failed. `GET /lookups/{list}` is gated on
   * `SettingsReadAnyWriteSystemAdmin`, whose `allowed_roles` is
   * `{SYSTEM_ADMIN, EXECUTIVE}` — A4's `settings_lookups` row gives a Billing
   * Clerk **no cell at all**, which `DEF-196` established means no access
   * rather than read-only access, and `US-TEN-009 TC-5` has asserted *"clerk
   * denied at the reference-data surface"* since the surface was built. The
   * refusal is CORRECT and signed. What is wrong is that a CLERK-FACING
   * picker reads its vocabulary through a SETTINGS door.
   *
   * ⚠ **MEASURED, NOT REASONED ABOUT.** Signed in as the seeded Billing Clerk
   * on the running stack: `403 /api/brazosbend/lookups/account_subtypes`, and
   * a dropdown holding exactly one option — the placeholder.
   *
   * So the screens tell the clerk, rather than drawing an empty control that
   * looks broken (`BR-SHL-025`, A18 §1). This flag is what lets them tell
   * *the read was refused* apart from *this category has no children*, which
   * are different facts and must not collapse into one blank list.
   */
  failed: boolean;
} {
  const query = useQuery({
    queryKey: ACCOUNT_SUBTYPES_QUERY_KEY,
    queryFn: () => getAccountSubcategories(client),
    retry: false,
  });
  const rows = (query.data?.results ?? []).map((row) => ({
    id: row.id,
    code: row.code,
    name: row.name,
    parentCode: (row.parent_code ?? null) as string | null,
    active: row.active ?? true,
  }));
  return {
    rows,
    isLoading: query.isPending,
    failed: !query.isPending && query.data === undefined,
  };
}

/**
 * The name for a stored sub-type code, from the TENANT'S fetched rows.
 *
 * Falls back to the CODE and never to a guess — `accountCategoryName`'s rule,
 * for the same reason and on the field that actually broke it: `DEF-CUS-5154`
 * and the Accounts blueprint both record `account_subtype` reaching a clerk as
 * `small_commercial`, the one raw enum left on the live product.
 */
export function accountSubtypeName(
  code: string,
  rows: readonly AccountSubtypeRow[],
): string {
  return rows.find((row) => row.code === code)?.name ?? code;
}

/** The rows a clerk may pick once `parentCode` is the chosen category. */
export function accountSubtypesUnder(
  rows: readonly AccountSubtypeRow[],
  parentCode: string,
): AccountSubtypeRow[] {
  if (parentCode === "") return [];
  return rows.filter((row) => row.active && row.parentCode === parentCode);
}

/**
 * The sub-type that SURVIVES a change of category — `""` whenever it does not.
 *
 * ⚠ **IT FAILS CLOSED, AND THAT IS THE WHOLE POINT (hard-won law 3).** A clerk
 * who picks Commercial → Healthcare and then corrects the category to
 * Industrial must not keep Healthcare: the pair would be written, no rule
 * refuses it at the write, and no screen draws it as wrong. An unknown code —
 * which is also what an unloaded list looks like — clears for the same reason:
 * the safe answer is the one we cannot get wrong, and a sub-type is OPTIONAL
 * (`accounts.account_subtype_id` is nullable by design), so clearing it costs
 * the clerk one click and never blocks the commit.
 */
export function accountSubtypeAfterCategoryChange(
  rows: readonly AccountSubtypeRow[],
  chosenSubtype: string,
  nextCategory: string,
): string {
  if (chosenSubtype === "") return "";
  const keeps = rows.some(
    (row) => row.code === chosenSubtype && row.active && row.parentCode === nextCategory,
  );
  return keeps ? chosenSubtype : "";
}

/**
 * ── THE STATUS PILL'S COLOUR ────────────────────────────────────────────────
 *
 * **One colour per account status, with the BEHAVIOUR CLASS as the fallback.**
 * Both, in that order, and the order is the whole design:
 *
 *   · a status we seeded gets the colour ruled for that status;
 *   · a status a TENANT added gets its class's colour, because BR-CUS-055
 *     makes this list tenant-extensible and a code-keyed map would hand every
 *     tenant-added status the grey fall-through;
 *   · a class we do not know gets `neutral`, which claims nothing.
 *
 * **PO RULING 2026-08-26 (DEF-722), verbatim:** *"have differnt color for diff
 * pill - you can define colors - recommendation: A"* — option A of three, "add
 * a colour" rather than let two statuses share one, and the second clause is an
 * explicit grant to choose the palette. Decision log, 2026-08-26.
 *
 * **THE PALETTE, AND WHY EACH ONE, READ AS A CLERK SCANNING S17 READS IT.**
 * The list is scanned for one thing: *where is money at risk, and where must I
 * act*. So the hues rank exactly that, and the two states that need nobody sit
 * together in grey:
 *
 * | status              | class              | tone      | what it says          |
 * |---------------------|--------------------|-----------|-----------------------|
 * | `active`            | billable           | `success` | running, billing      |
 * | `marked_disconnect` | billable           | `warning` | a clock is running    |
 * | `vacation_hold`     | billable_base_only | `info`    | paused, on request    |
 * | `disconnected`      | non_billable       | `danger`  | CUT, owes money       |
 * | `pending_activation`| non_billable       | `neutral` | never started         |
 * | `closed`            | terminal           | `muted`   | finished              |
 *
 * ⚠ **RED MOVED, AND THAT IS THE POINT RATHER THAN A SIDE EFFECT.** It used to
 * mark `Closed` — a customer who moved out, owes nothing and needs no one — so
 * the loudest colour on the screen was the one state that never wants a clerk,
 * on the rows that outnumber every other kind. It now marks `Disconnected`, the
 * single status where the service is off AND the debt is live AND the account
 * can still be recovered (BR-CUS-107: *"it holds a debt, it can pay, and it
 * comes back"*). `Closed` takes `muted` instead: same grey family as `Pending
 * activation`, because both mean *nothing is owed and nothing is due from you*,
 * separated by weight — pale is "not started", solid is "over".
 *
 * ⚠ **`Marked disconnect` WAS GREEN, WHICH WAS THE SECOND COLLAPSE AND IS NOT
 * THE ONE THAT WAS REPORTED.** It shares class `billable` with `Active` (OQ-064
 * closure: the account is *"consuming until the cut"*), so both rendered
 * `success`. An account queued to have its service cut read exactly as healthy
 * as one that is fine. Amber is the rung between green and red for the same
 * reason a traffic light has one.
 *
 * ⚠ **COLOUR IS NEVER THE ONLY CHANNEL HERE, AND NOTHING BELOW MAY MAKE IT
 * ONE.** `StatusPill` always renders the LABEL — `accountStatusLabel`, the
 * tenant's own `status_name` (BR-CUS-055) — so every distinction above is
 * carried in words first and colour second. That is what keeps this legible to
 * a colour-blind clerk and in a black-and-white print of the list; the tones
 * rank and group, they do not inform. If a future change makes a pill that is
 * colour-only, it needs a second channel of its own, not a seventh hue.
 *
 * ⚠ **THE CLASS FALLBACKS ARE UNCHANGED ON PURPOSE — `billable` → success,
 * `billable_base_only` → warning, `terminal` → danger, anything else →
 * neutral.** The ruling was about the six statuses we seed. A tenant's own
 * status is not one of them, so re-tinting it would be a change nobody asked
 * for, applied to data we cannot see. It leaves a deliberate asymmetry:
 * `vacation_hold` is `info` while a tenant-added base-only status is `warning`,
 * and `closed` is `muted` while a tenant-added terminal status is `danger`.
 * That is the fallback doing its job — a colour for a meaning we do not know —
 * and it is the PO's to revisit, not a lane's.
 *
 * ── SUPERSEDED 2026-08-26 · THE ARGUMENT FOR CHANGING NOTHING ──────────────
 * Kept, dated, because it is the record of why this function has the shape it
 * now has and every one of its constraints still binds. Lane ACCTSTALE, having
 * measured the same collapse, deliberately left this function alone and wrote:
 *
 *   *"`StatusPill` has FOUR tones (A12 semantic tokens — status meaning only,
 *   never decoration) and BR-CUS-055 now seeds SIX statuses, tenant-extensibly.
 *   Six into four collapses something whatever we do, and every available move
 *   trades this collapse for a worse one: `disconnected → danger` makes 'cut,
 *   owes money, can come back' look identical to 'moved out, finished', and
 *   only one of them needs a clerk; `disconnected → warning` puts it with
 *   `Vacation hold`, which is benign, temporary and customer-requested. A fifth
 *   tone is a new visual vocabulary across every list in the product (B14 rule
 *   8 fixes the pill set), not a change to one function."*
 *
 * That was right on all three counts, and the ruling answers the arithmetic
 * rather than refuting it: the PO chose the move ACCTSTALE could not make on
 * its own — a fifth tone, and therefore a new visual vocabulary, deliberately.
 * Its two traps are both avoided above rather than sprung: `Disconnected` does
 * take `danger`, and it is `Closed` that moved off it so the pair is not
 * identical; `Vacation hold` moved to `info` so nothing shares amber with it.
 * Its third warning — that keying on the CODE is not free, because a
 * tenant-added status would fall to grey — is why the class fallback below
 * survives unchanged.
 *
 * ⚠ **THE SYMPTOM IS STILL LATENT AND THIS IS STILL NOT VERIFIABLE BY LOOKING.**
 * Nothing assigns `disconnected` — `commit_cut` writes no `accounts` column
 * (DEF-701, open) — and nothing assigns `marked_disconnect` either; both are
 * seeded rows waiting for a writer. So no running screen shows this fixed, and
 * the tests that prove it construct the statuses directly
 * (`accountStatusTone.test.tsx`). Do not "verify" this in a browser and
 * conclude it does not work.
 */
export interface AccountStatusIdentity {
  /** the account-status lookup CODE (BR-CUS-016) — `AccountRow.status` */
  status: string;
  /** non_billable | billable | billable_base_only | terminal */
  status_behavior_class: string;
}

/**
 * The six statuses BR-CUS-055 seeds, in seed order, and the tone ruled for each.
 *
 * ⚠ **THE KEYS ARE THE SEEDED CODES AND THE SERVER OWNS THEM** —
 * `apps/customers/services.SEED_ACCOUNT_STATUSES`, mirrored in migration
 * `customers/0025_br_cus_107_disconnected_status.py`. A tenant may RENAME any
 * of them (the label is `status_name`, reference data); it cannot renumber the
 * code, which is why the code is what this map is keyed on and the label is not.
 */
const STATUS_TONE: Readonly<Record<string, StatusTone>> = {
  pending_activation: "neutral",
  active: "success",
  marked_disconnect: "warning",
  vacation_hold: "info",
  closed: "muted",
  disconnected: "danger",
};

/** The fallback for a status this build has never heard of. See the asymmetry
 *  note above: these four are byte-for-byte what they were before DEF-722. */
const CLASS_TONE: Readonly<Record<string, StatusTone>> = {
  billable: "success",
  billable_base_only: "warning",
  terminal: "danger",
};

export function accountStatusTone(status: AccountStatusIdentity): StatusTone {
  const byCode = STATUS_TONE[status.status];
  if (byCode !== undefined) {
    return byCode;
  }
  return CLASS_TONE[status.status_behavior_class] ?? "neutral";
}

/**
 * The label on the pill. Account statuses are REFERENCE DATA (BR-CUS-055), so
 * the tenant owns the wording and the server's `status_name` is the answer —
 * exactly the posture S14 takes for `premises_type_name` (BR-MET-034). The
 * catalog key is the fallback for a server that sent no name, never an
 * override of one it did send.
 */
export function accountStatusLabel(row: AccountRow, t: Translator): string {
  if (row.status_name !== null && row.status_name !== "") {
    return row.status_name;
  }
  return t(`customers.accounts.status.${row.status}`, { defaultValue: row.status });
}

// ── Honest absence (hard-won law 2, and the metering `notCollected` shape) ──

/**
 * A value the server CANNOT know yet, as distinct from a value that is empty.
 * "—" would read as "no bills"; 0 would read as "nothing outstanding". Both
 * are claims. This renders a short muted token and carries the reason on hover
 * so the whole sentence is one key, never a concatenation (B8).
 */
export function AwaitsCell(props: { label: string; why: string }) {
  return (
    <span className="cus-awaits" title={props.why}>
      {props.label}
    </span>
  );
}

/** A value the server DID answer with nothing. Quieter than data, never blank. */
export function Dash(props: { children?: ReactNode }) {
  return <span className="cus-muted">{props.children ?? "—"}</span>;
}

/**
 * A value the server REFUSES to hold, with the rule that owns the refusal.
 * Different from `AwaitsCell` on purpose: "awaiting" means a writer is coming,
 * "refused" means the endpoint answers a reason today and this is that reason,
 * rendered where the value would have been. The rule id is the SERVER's own
 * (`plan_snapshot_unavailable`, `REFUSED_FIELDS[…][0]`), never one typed here.
 *
 * ── DEF-332, THE SECOND SITE (2026-08-21) ─────────────────────────────────
 * This printed the id in a `.cus-rule` span — *"Not recorded
 * (plan_snapshot_unavailable)"* — which is the same shape the PO refused on
 * 2026-08-19, on a screen the defect row never named. Found by the stated-
 * absence sweep, not by the defect. The id now travels on `data-rule-ref`
 * beside `RefusalNotice`'s `data-br-ref`, for the same reason and to the same
 * reader: it is still in the DOM for support, and out of the sentence.
 */
export function NotRecorded(props: { label: string; why: string; ruleRef?: string | null }) {
  const ref =
    props.ruleRef !== undefined && props.ruleRef !== null && props.ruleRef !== ""
      ? props.ruleRef
      : null;
  return (
    <span className="cus-refused" title={props.why} {...(ref !== null ? { "data-rule-ref": ref } : {})}>
      {props.label}
    </span>
  );
}

// ── The server's own J2 handoff warnings (BR-CUS-029 / BR-CUS-023) ─────────

/**
 * `create_account` / `activate_account` answer with the handoffs they could NOT
 * perform — today always `plan_snapshot_not_recorded` and `deposit_not_applied`
 * on any call that makes the account occupy its unit. They are RENDERED, not
 * swallowed: a create that silently dropped the plan snapshot would read as a
 * complete account (the metering `history_recorded: false` precedent).
 *
 * An unknown code still renders — the codes are the server's and this catalog
 * must not decide which of them a user is allowed to see.
 */
export function warningText(warning: ServerWarning, t: Translator): string {
  // `DEF-CUS-9785` — a warning that names its OWN sentence (`message_key`, as
  // Work's `work_orders_not_raised`, `work_order_not_assigned` and
  // `work_order_not_scheduled` do) is read through that key when this catalog
  // has no `customers.account.warning.<code>` for it. Until 2026-10-06 the
  // lookup asked for the code alone and a clerk read `work_orders_not_raised`.
  const ownKey = typeof warning.message_key === "string" ? warning.message_key : "";
  const params =
    warning.params !== null && typeof warning.params === "object"
      ? (warning.params as Record<string, unknown>)
      : {};
  const fallback = ownKey === "" ? warning.code : t(ownKey, { ...params, defaultValue: warning.code });
  return t(`customers.account.warning.${warning.code}`, { ...params, defaultValue: fallback });
}

export function WarningList(props: {
  warnings: readonly ServerWarning[];
  title: string;
  t: Translator;
}) {
  if (props.warnings.length === 0) {
    return null;
  }
  return (
    <div className="cus-warnings" role="status">
      <h4>{props.title}</h4>
      <ul>
        {props.warnings.map((warning) => (
          // DEF-332 — the sentence, and the rule id on `data-br-ref` for
          // support. Same treatment as `RefusalNotice`; the id is not lost.
          <li
            key={warning.code}
            {...(typeof warning.br_ref === "string" && warning.br_ref !== ""
              ? { "data-br-ref": warning.br_ref }
              : {})}
          >
            {warningText(warning, props.t)}
          </li>
        ))}
      </ul>
    </div>
  );
}

// ── Identity ──

/**
 * The primary contact on an account — the PERSON the utility talks to. Not the
 * account's name: since `DEF-CUS-9776` that is the customer's (`accountHeadline`).
 */
export function primaryContact(contacts: readonly AccountContact[]): AccountContact | null {
  return contacts.find((contact) => contact.is_primary) ?? contacts[0] ?? null;
}

/**
 * The S21 H1: the account's NAME — its customer's (a company's legal name, a
 * person's own), falling back to the primary contact, then the account number.
 *
 * ⚠ `DEF-CUS-9776`: this read the CONTACT first, so *Grace Fellowship of Cedar
 * Ford* was titled *Ruth Okafor*. `detail.name` is the server's one rule
 * (`selectors.primary_contact_name`: current customer, else contact), so the
 * title, the list, the unit and the meter name an account the same way.
 */
export function accountHeadline(detail: AccountDetail, t: Translator): string {
  if (detail.name !== null && detail.name !== "") {
    return detail.name;
  }
  const contact = primaryContact(detail.contacts);
  if (contact?.full_name != null && contact.full_name !== "") {
    return contact.full_name;
  }
  return detail.account_no ?? t("customers.accounts.noName");
}

/**
 * BR-CUS-045: only the LAST FOUR of a government id is stored, so the masked
 * form is all there is to render — there is no fuller value on the server to
 * reveal. The ID TYPE the prototype prints ("DL ****4218") is PROPOSED-SCHEMA
 * `contacts.gov_id_type` and is not built, so the type is absent, not guessed.
 */
export function maskedGovId(last4: string | null): string | null {
  if (last4 === null || last4 === "") {
    return null;
  }
  return `••••${last4}`;
}

/** BR-CUS-055: an account whose behaviour class is terminal is closed. */
export function isClosedAccount(detail: AccountDetail): boolean {
  return detail.status_behavior_class === "terminal";
}

/**
 * BR-CUS-018's platform draft status. A CODE and not a class, deliberately —
 * see `isDraftAccount`.
 */
export const DISCONNECTED_STATUS_CODE = "disconnected";

/**
 * BR-CUS-018: a draft occupies nothing, so it is the one thing S21 can activate.
 *
 * ⚠ **NARROWED 2026-08-25 — BR-CUS-107.** This read
 * `status_behavior_class === "non_billable"` and nothing else, which was right
 * while `pending_activation` was the ONLY `non_billable` status. BR-CUS-107 (PO
 * ruling closing DEF-701) seeds a second one — `disconnected`, the state a CUT
 * account is in — and under the old line S21 would have called a cut account a
 * DRAFT: the ONE primary action on the page becomes a live **"Activate
 * account"**, one click, on a customer whose service is off and whose debt is
 * unpaid. Restoration is an explicit, audited staff act through the reconnect
 * flow (BR-PAY-036; B18 §5.8.4 — *"payment confirmed → visit scheduled →
 * restored"*), never a status flip on a detail page.
 *
 * ⚠ **AND THE EXCLUSION IS BY CODE WHILE THE RULE STAYS BY CLASS.** The
 * behaviour class is what billing keys off and a tenant may rename any status,
 * so the class is still the boundary for *"is this billed"* and *"does this
 * occupy"*. This one question — *"is this the draft S21 may activate"* — cannot
 * be answered by the class any more, because two PLATFORM statuses now share
 * it. Naming the seeded code is the server's own precedent
 * (`services._default_active_status`: *"Chosen by CODE, not by behaviour
 * class"*).
 *
 * ⚠ **THIS IS A DISPLAY GUARD AND NOT THE FIX.** `POST /accounts/{id}/activate`
 * does not read the account's CURRENT status at all, so the server would still
 * accept the call. That hole is REPORTED, not closed here.
 */
export function isDraftAccount(detail: AccountDetail): boolean {
  return (
    detail.status_behavior_class === "non_billable" &&
    detail.status !== DISCONNECTED_STATUS_CODE
  );
}

/**
 * BR-CUS-017 / BR-MET-036 — the behaviour classes that OCCUPY a unit, verbatim
 * from `services.OCCUPYING_BEHAVIOR_CLASSES`. Keyed off the CLASS, never the
 * tenant's label, exactly as the server is: a tenant may rename "Vacation
 * hold/Suspended" or add a status of its own and this boundary does not move.
 */
export const OCCUPYING_BEHAVIOR_CLASSES = ["billable", "billable_base_only"] as const;

/**
 * BR-CUS-030: only an OCCUPANT can move out. A draft never took the unit and a
 * closed account has already left it — the server refuses both, so S21 offers
 * the control disabled WITH that reason rather than opening a page whose commit
 * cannot succeed.
 */
export function isOccupyingAccount(detail: AccountDetail): boolean {
  return (OCCUPYING_BEHAVIOR_CLASSES as readonly string[]).includes(
    detail.status_behavior_class,
  );
}

/**
 * BR-CUS-056 (CONFIRMED — PO OQ-060 option a): "the OUTGOING account pays the
 * move day; the incoming account starts the NEXT day from the same reading."
 * So the earliest a move-in may start is the day AFTER the outgoing account's
 * `closed_at`, and the server refuses anything on or before it.
 *
 * Pure, and computed in UTC on the calendar date's own parts — a calendar date
 * never routes through a timezone (the DateCell law), and `new Date("YYYY-MM-DD")`
 * plus a local-time getter is exactly how an off-by-one day is born.
 * Returns null when there is nothing to compare: a predecessor closed without a
 * date (slice 2 had no way to write one) is not a boundary, and inventing one
 * would block a legitimate start.
 */
export function earliestMoveInDate(outgoingClosedAt: string | null): string | null {
  if (outgoingClosedAt === null || !/^\d{4}-\d{2}-\d{2}$/.test(outgoingClosedAt)) {
    return null;
  }
  const [year, month, day] = outgoingClosedAt.split("-").map(Number);
  const next = new Date(Date.UTC(year, month - 1, day + 1));
  return next.toISOString().slice(0, 10);
}

/**
 * The currency for the header roll-up. `accounts_rollup()` serves `outstanding`
 * as a bare decimal string with NO currency code, and MoneyCell must not guess
 * one (CLAUDE.md #2: the CHAR(3) code rides WITH the amount). The rows on the
 * page do carry it, and every account in a tenant shares one by BR-TEN-042's
 * currency lock — so a UNANIMOUS answer is the tenant's currency and anything
 * else (no rows, or a disagreement) is honestly unknown and returns null.
 */
export function rollupCurrency(rows: readonly AccountRow[]): string | null {
  const codes = new Set(rows.map((row) => row.currency).filter((code) => code !== ""));
  return codes.size === 1 ? [...codes][0] : null;
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-CUS-001@a2e1d59 (story+rules snapshot — EP-CUS-01 lead story; co-packet customers 02-business-rules@f125a9c)
// generated: 2026-08-10 by story-coder (W2 customers FRONTEND lane — the S17 accounts list; the backend slice landed the same day with no screen on it) · AMENDED 2026-08-11 by story-coder (W2 customers FRONTEND lane 2 — the S18/S21 routes, the two BR-CUS-018 create statuses, the refused-value and server-warning renderers, and the BR-CUS-045 masked government id) · AMENDED 2026-08-11 by story-coder (W2 customers FRONTEND lane 3 — the S19/S20 account-scoped route builders, the BR-CUS-017 occupying-class predicate and BR-CUS-056's earliest-move-in-date computation)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ · eslint --max-warnings 0✔ · vitest 622 passed / 148 todo across 47 files✔ (604 passed / 142 todo across 46 files was the pre-lane baseline — the suite grew by 18 passing + 6 todo and nothing was dropped) · vite build✔ · run_gates 14 PASS · 0 FAIL · 1 SKIP✔ (G13/G14/G15 included) · [S18/S21 lane 2026-08-11] tsc✔ · eslint --max-warnings 0✔ · vitest 670 passed / 160 todo across 49 files✔ (622 passed / 148 todo across 47 files was the pre-lane baseline) · vite build✔ · run_gates 14 PASS · 0 FAIL · 1 SKIP✔
// exceptions: E3 the status FILTER offers the five BR-CUS-055 SEEDED codes; a tenant-ADDED status is not offered because the only route that enumerates the list (`GET /lookups/account_statuses`) is System-Admin-only and S17 must work for a Billing Clerk — the ROW still renders the server's own `status_name`, so a renamed or added status displays correctly · E3 `rollupCurrency` infers the roll-up's currency from the served rows because the endpoint sends none; BR-TEN-042's currency lock is what makes a unanimous answer safe, and a non-unanimous one renders as unknown rather than assumed · E4 the A4 permission is imported from meteringShared: A4 has ONE "Premises / Accounts" row and three screens must not key off three copies of its code · E3 [2026-08-11] `NotRecorded` renders the SERVER's own rule id (`plan_snapshot_unavailable`, and the BR ids on its warnings) rather than one typed here, so every refusal on a customers screen stays traceable to the rule that produced it · E3 `primaryContact`/`accountHeadline` name the primary CONTACT because BR-CUS-054's `customers` table does not exist — no customer display name is invented · E3 [2026-08-11 lane 3] `accountMoveOutPath`/`accountMoveInPath` hang off the ACCOUNT because both endpoints do (11b §S19/§S20): move-out closes the account in the path and move-in creates the next occupant of THAT account's unit, so no top-level S19/S20 route is invented · E4 `earliestMoveInDate` computes BR-CUS-056's boundary in UTC from the calendar date's own parts — `new Date("YYYY-MM-DD")` plus a local-time getter is exactly how an off-by-one day is born — and returns null when the predecessor closed with no date, because inventing a boundary would block a legitimate start · E3 `maskedGovId` renders `••••NNNN` and there is deliberately no reveal affordance: the server stores four digits and nothing fuller exists to reveal (BR-CUS-045); the ID TYPE the prototype prints is PROPOSED-SCHEMA `contacts.gov_id_type` and is absent, not guessed
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
