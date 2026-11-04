// ── Trace ──────────────────────────────────────────────
// Change:   CR-030 W5 task 5.2 — move-in step 3's ASSET PANEL, the frontend
//           half of `GET /units/{id}/assets` (B18 §5.5.5, marked NEW there).
//           ⚠ NO STORY OWNS IT — hard-won law 8. B18 widens US-CUS-004 §S19
//           step 3 and `05-user-stories.md` carries no story for the panel;
//           the backend half reported the same gap. REPORTED, not invented.
//           Screens: S19 (step 3)
// Rules:    BR-AST-004 (exactly ONE tab per asset — `asset_types.category` is
//           the grouping key, never the (sub)/(master) qualifier) ·
//           BR-MET-100 (a unit with nothing installed is a real state, not an
//           error) · BR-RAT-081 / DEF-495 (the metered declaration has no
//           reader, so "which of these needs a reading" is a STATED ABSENCE) ·
//           BR-CUS-021 (readings commit through metering's own service — this
//           panel LISTS, it never collects) · hard rule 3 (consumption always
//           travels with its explicit unit) · B14 rule 21 (new UI is Tailwind
//           utilities and adds NO class to a stylesheet)
// ───────────────────────────────────────────────────────
// B18 §5.5.3 step 3, verbatim: *"Every meter, sub-meter and behind-the-meter
// device at the unit, then a reading per billable meter"* — filed there as a
// **DEFECT** rather than a change, because *"BR-CUS-021 and the S19 contract
// both assume the clerk can see what is installed"* and today step 3 shows
// reads only.
//
// THIS FILE IS THE FIRST CALLER OF THAT ENDPOINT. It landed with no screen
// reading it, which is hard-won law 2 — *"built is not wired"* — so the panel
// exists to close that, and the paths are written out in `unitAssetsPath` so
// exactly one string in this app names the route.
//
// ⚠ **THREE THINGS THIS PANEL REFUSES TO DRAW, EACH FOR A DIFFERENT REASON.**
//
//   1. **A `0` for a register that has never been read.** `last_read` is `null`
//      there, and null is not zero: a fresh install genuinely has no position,
//      and printing `0` claims the register was read and stood at nothing. The
//      panel renders `metering.unit.assets.last_read.never` instead.
//   2. **A consumption figure without its unit.** Hard rule 3, and the server
//      already honours it (`_last_read_position` sends `consumption` and `unit`
//      together or not at all). If the unit is absent for any reason the figure
//      is withheld too — a bare "684" is a number nobody can act on.
//   3. **Which meters a reading is asked for.** `reading_expected` arrives as a
//      stated absence carrying `DEF-495`, because `tenant_services.metered` —
//      BR-RAT-081's declaration — has no reader anywhere in the product.
//      Deriving it from the category would be a guess: a sub-meter is read and
//      a cart is not, and both are known only through that declaration.
//
// ⚠ **AND ONE MORE: THIS PANEL COLLECTS NOTHING.** B18 step 3 wants a reading
// per billable meter after the list. `initial_reads` is a REFUSED field on
// `POST /accounts/{id}/move-in` (BR-CUS-021 — reads commit through metering's
// append-only service), and `MoveInWizard` already says so beside the panel.
// Adding an input here would be a control that saves nowhere.
import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { formatQuantity } from "@/components/UnitCell";

// ── The wire (read off apps/metering/selectors.unit_assets) ────────────────
//
// ⚠ TYPED HERE AND NOT IN `src/api/endpoints.ts`, AND THAT IS A LANE BOUNDARY
// RATHER THAN A DESIGN CHOICE — REPORTED. `endpoints.ts` is the app's one
// typed-client file (B13 §2) and this pair belongs in it beside
// `getUnitDetail`; this lane does not own that file, so the shapes live beside
// their only consumer for now and the move is owed. Nothing is duplicated: no
// other module types these two payloads today.

/** The newest COMMITTED lineage head on one asset — where the register stood.
 *  `consumption` NEVER travels without `unit` (hard rule 3). */
export interface UnitAssetLastRead {
  read_id: string;
  read_at: string | null;
  channel: string;
  current_value: string | null;
  /** DEF-1086 — the server's composed "<reading> <unit>" (BR-SHL-250). */
  current_value_display: string | null;
  consumption: string | null;
  unit: string | null;
}

export interface UnitAssetRow {
  id: string;
  asset_no: string | null;
  type: string | null;
  type_name: string | null;
  /** `asset_types.category` — the BR-AST-004 grouping key. */
  category: string | null;
  /** The S15 cell's `(sub)`/`(master)` tag, BESIDE the category and never
   *  instead of it: a master meter is a `meters` row that others hang off. */
  qualifier: string | null;
  service: string | null;
  /** `null` = no committed read exists. NOTHING may read that as a zero. */
  last_read: UnitAssetLastRead | null;
}

export interface UnitAssetGroup {
  category: string;
  assets: UnitAssetRow[];
}

/** A payload field that says WHY a fact is missing, and names the row that
 *  will close it. `tracks` is a `data-` attribute, never part of the sentence
 *  (DEF-332, PO 2026-08-19: our ids do not belong on a user's screen). */
export interface StatedAbsence {
  served: boolean;
  reason: string;
  tracks: string | null;
}

export interface UnitAssets {
  unit: {
    id: string;
    unit_no: string | null;
    label: string | null;
    premises_id: string;
    premise_no: string | null;
    premise_address: string | null;
  };
  groups: UnitAssetGroup[];
  counts?: Record<string, number>;
  reading_expected: StatedAbsence;
}

/** The ONE place this route is spelled. */
export function unitAssetsPath(unitId: string): string {
  return `/units/${encodeURIComponent(unitId)}/assets`;
}

export const unitAssetsQueryKey = (unitId: string) =>
  ["metering", "unit", unitId, "assets"] as const;

export async function getUnitAssets(
  unitId: string,
  client: ApiClient = api,
): Promise<UnitAssets> {
  const response = await client.get<UnitAssets>(unitAssetsPath(unitId));
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

/**
 * B18 §5.5.5's own words: *"grouped meters / sub-meters / behind-the-meter"*.
 * `unclassified` is the fourth and it is NOT a design flourish — the server
 * serves it for a row whose type resolves to none of the three (an assets
 * catalog that publishes nothing yields it for every asset), and dropping it
 * would hide installed equipment from the clerk taking the unit over.
 *
 * ⚠ THE ORDER IS FIXED HERE AND NOT TAKEN FROM THE PAYLOAD. The server sends
 * them in this order today; reading the panel's order off the response would
 * mean a server-side reorder silently reorders a screen. This list is the
 * screen's own contract and `groupsInOrder` reconciles the two.
 */
export const UNIT_ASSET_GROUP_ORDER = [
  "meters",
  "sub_meters",
  "behind_the_meter",
  "unclassified",
] as const;

/**
 * The served groups in THIS screen's declared order, with any group the server
 * did not send rendered as an empty one.
 *
 * ⚠ A group the panel does not know about is APPENDED rather than dropped. A
 * fifth category added to `asset_types` reaches the clerk as its own section
 * with its raw code as the heading, which is ugly and honest; dropping it would
 * silently hide equipment installed at a unit somebody is moving into.
 */
export function groupsInOrder(groups: UnitAssetGroup[]): UnitAssetGroup[] {
  const byCategory = new Map(groups.map((group) => [group.category, group]));
  const declared = UNIT_ASSET_GROUP_ORDER.map(
    (category) => byCategory.get(category) ?? { category, assets: [] },
  );
  const extra = groups.filter(
    (group) => !(UNIT_ASSET_GROUP_ORDER as readonly string[]).includes(group.category),
  );
  return [...declared, ...extra];
}

/**
 * HARD RULE 3, AS A FUNCTION SO IT IS TESTABLE WITHOUT A BROWSER.
 *
 * A consumption figure is renderable only when it arrives WITH its explicit
 * unit. Both present → the pair. Either missing → `null`, and the caller draws
 * the absence sentence rather than a bare number.
 */
export function consumptionWithUnit(read: UnitAssetLastRead): string | null {
  if (read.consumption === null || read.unit === null || read.unit === "") {
    return null;
  }
  // ⚠ **THE SHARED COMPOSER, NOT AN f-STRING (DEF-1120, BR-SHL-250 §4).**
  // This used to interpolate the served decimal directly, so it printed
  // `684.000000 kWh` where every other consumption in the product now reads
  // `684 kWh`. `formatQuantity` is the CLIENT's one implementation of
  // BR-MET-144 and it is lawful here because the row carries its own `unit` —
  // the fact the rule is about is present, so the server does not have to
  // compose this one.
  return `${formatQuantity(read.consumption)} ${read.unit}`;
}

// ── The panel ──────────────────────────────────────────────────────────────

// ⚠ **THE `UnitAssetsPanel` COMPONENT IS DELETED (`DEF-CUS-6362`, PO
// 2026-09-23).** It was the move-in's grouped *"Meters on this unit"*
// inventory, and its one caller now mounts ONE table instead —
// `MoveInReadingsTable`, which lists the same rows with the reading beside
// them. The wire types, the route and `groupsInOrder` above stay: that table
// and the move-out capture read them. The four points in the header remain
// true of the table: never a `0` for an unread register, never a quantity
// without its unit, and no guess at which meters need a reading.

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-030 W5 task 5.2 (B18 §5.5.3 step 3 + §5.5.5) — NO STORY OWNS IT, reported (hard-won law 8)
// generated: 2026-08-25 by the CR-030 W5 R1 lane (the FRONTEND half of `GET /units/{id}/assets`, which shipped 2026-08-25 with no caller — hard-won law 2)
// checklist: A✔ B=n/a(no-backend-half) C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: see MoveInWizard.tsx's trailer — this file and UnitPricingPanel.tsx are that lane's two new components. This file's OWN two: G31 declared-classes goes 0→14 because it is written in Tailwind utilities per B14 rule 21 and `src/styles/route-b-migrated.txt` (not this lane's file) has no line for it yet — the line owed is `features/customers/UnitAssetsPanel.tsx`; and G27 i18n-keys names 6 new keys, handed over as `newkeys-R1.json`, every call site carrying a `defaultValue` so nothing renders a raw key meanwhile. ⚠ Every utility this file names was compiled through the REAL Tailwind compiler against `src/styles/tailwind.css` — the stricter question `routeBUtilities.test.ts` will ask the day the ledger lists it — and all of them generate a rule. tsc✔ · eslint --max-warnings 0✔ · vitest via MoveInWizard.test.tsx✔ · G13✔ G38✔ (its stated absence cites a real id) G40✔
// exceptions: E4 the payload shapes are typed HERE rather than in `src/api/endpoints.ts`: that file is the app's one typed client (B13 §2) and this lane does not own it. The move is OWED and nothing is duplicated — no other module types these two payloads
// exceptions: E4 the four group headings render even when a group is empty, so a clerk reads "sub-meters: none" rather than inferring it from an absence; the group ORDER is this screen's own declared list, not the payload's, so a server-side reorder cannot silently reorder a screen
// exceptions: E3 no reading is COLLECTED here (BR-CUS-021 — `initial_reads` is a refused field on the move-in endpoint); the panel lists the registers so the unread ones are visible, which is what B18 §5.5.3 step 3 asks for and all it can honestly offer
// exceptions: E3 `reading_expected` is a STATED ABSENCE carrying DEF-495 and is not derived from the asset category — a sub-meter is read and a cart is not, and only BR-RAT-081's declaration knows which
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
