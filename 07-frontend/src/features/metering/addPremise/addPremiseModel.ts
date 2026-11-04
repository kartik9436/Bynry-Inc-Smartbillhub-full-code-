// ── Trace ──────────────────────────────────────────────
// Change:   CR-177-BRC10 round B — Add a premise, redesigned (PO GO 2026-10-09).
//           The pure half of the screen: the form, the payload, the address
//           line, the check states and the counts. Nothing here renders.
// Defect:   DEF-MET-10034 (the double comma, the skipped required field, the
//           map fields at a utility with no City map, search while typing).
// Rules:    BR-MET-1190 (the same address) · BR-MET-1191 (Check address) ·
//           BR-MET-1192 (Use these details) · BR-MET-1193 (active services,
//           none ticked) · BR-MET-1194 (required custom fields) · BR-MET-1195
//           (the owner is linked, never opened here) · BR-MET-002 (unit label
//           unique per premise) · BR-MET-036 (no occupancy input) · hard rule 8
//           (the address lives on the premise) · B14 rule 31 (no id is shown)
// Tests:    src/features/metering/addPremise/AddPremisePage.dom.test.tsx ·
//           src/features/metering/addPremise/addPremiseModel.test.ts
// ───────────────────────────────────────────────────────
import type { CityCheckAnswer, GisCandidate, OwnerSearchRow, SameAddressPremise } from "@/api/endpoints";
import type { CustomFieldValues } from "@/components/CustomFields";
import { NO_AREA, areaPayloadCode } from "@/features/metering/meteringShared";
import type { AreaSelection } from "@/features/metering/meteringShared";
import { ownerAccountPayload } from "@/features/metering/premisesOwnerContract";

/** The server's cap for one generator run, restated so a hopeless number is
 *  refused before a round trip (BR-MET-005). The server's refusal is the rule. */
export const UNIT_COUNT_CAP = 3_000;

// The three steps — Property · Units · Review — are declared where they are
// drawn (`AddPremisePage`'s `steps`). Bulk adds are Import only (PO 2026-10-09:
// *"there is seperate improt fucntion for premsies bulk import so step 1 how
// many not required"*).

export interface AddPremiseForm {
  address_line: string;
  city: string;
  state: string;
  postal_code: string;
  premises_type: string;
  /** `null` is *not recorded* — the honest start for a property being typed;
   *  a create that answered this by default would answer it for every address
   *  ever added (CR-039 wave C task 10). */
  inside_city_limits: boolean | null;
  /** The clerk's own pick from the utility's ACTIVE services. NONE ticked to
   *  start (PO 2026-10-09, plan rule 4 approved as written). */
  services: string[];
  area: AreaSelection;
  route: string;
  custom_data: CustomFieldValues;
  unit_count: string;
  unit_type: string;
  unit_custom_data: CustomFieldValues;
  service_point_custom_data: Record<string, CustomFieldValues>;
  common_areas: string[];
}

export function emptyAddPremiseForm(): AddPremiseForm {
  return {
    address_line: "",
    city: "",
    state: "",
    postal_code: "",
    premises_type: "",
    inside_city_limits: null,
    services: [],
    area: NO_AREA,
    route: "",
    custom_data: {},
    // One unit is the common case for a house, and it is the default the old
    // tick-box had — so the answer a clerk gets without touching it is unchanged.
    unit_count: "1",
    unit_type: "",
    unit_custom_data: {},
    service_point_custom_data: {},
    common_areas: [],
  };
}

/**
 * **`3721 S Village Dr, Avenel, NJ 07001` — and never `Dr,, Avenel`.**
 *
 * `DEF-MET-10034`: the review read *"3721 S Village Dr,, Avenel"*, because the
 * street ended in a comma and the join added another. Every part is trimmed of
 * spaces AND commas, an empty part is skipped, and the ZIP follows the state
 * after a space. The server's `metering.services.compose_address` is the same
 * rule, so the screen and the refusal naming another premise punctuate alike.
 */
export function composeAddress(parts: {
  address_line?: string | null;
  city?: string | null;
  state?: string | null;
  postal_code?: string | null;
}): string {
  const tidy = (raw: string | null | undefined) => (raw ?? "").trim().replace(/^[\s,]+|[\s,]+$/g, "");
  const region = [tidy(parts.state), tidy(parts.postal_code)].filter((part) => part !== "").join(" ");
  return [tidy(parts.address_line), tidy(parts.city), region].filter((part) => part !== "").join(", ");
}

/** The four address parts as the server's two address calls take them. */
export function addressParts(form: AddPremiseForm): {
  address_line: string;
  city: string;
  state: string;
  postal_code: string;
} {
  return {
    address_line: form.address_line.trim(),
    city: form.city.trim(),
    state: form.state.trim(),
    postal_code: form.postal_code.trim(),
  };
}

// ── Check address (BR-MET-1191, BR-MET-1192) ────────────────────────────────

/**
 * What *Check address* last said. `none` until the button is pressed, and
 * again the moment the clerk edits the address — an answer about another
 * address is not an answer about this one.
 */
export type AddressCheck =
  | { kind: "none" }
  | { kind: "checking" }
  | { kind: "not_connected" }
  | { kind: "no_match" }
  | { kind: "unavailable"; messageKey: string | null }
  | { kind: "match"; match: GisCandidate; session: string | null; used: boolean; checkedOn: string };

export function checkFromAnswer(answer: CityCheckAnswer, today: string): AddressCheck {
  if (answer.result === "match" && answer.match !== null) {
    return { kind: "match", match: answer.match, session: answer.session, used: false, checkedOn: today };
  }
  if (answer.result === "not_connected") return { kind: "not_connected" };
  if (answer.result === "no_match") return { kind: "no_match" };
  return { kind: "unavailable", messageKey: answer.message_key };
}

/** The summary card's and the review's word for the check — a catalogue KEY. */
export function addressCheckKey(check: AddressCheck): string {
  switch (check.kind) {
    case "not_connected":
    case "unavailable":
      return "metering.addPremise.check.cannot";
    case "no_match":
      return "metering.addPremise.check.noMatchShort";
    case "match":
      return check.used ? "metering.addPremise.check.matches" : "metering.addPremise.check.found";
    default:
      return "metering.addPremise.check.notChecked";
  }
}

/** The City's point as the drawing writes it: `40.582310, −74.284120`. */
export function pointText(lat: string | null | undefined, lng: string | null | undefined): string {
  if (lat === null || lat === undefined || lat === "" || lng === null || lng === undefined || lng === "") {
    return "";
  }
  return `${lat}, ${lng}`;
}

/** *Use these details*: the City's address replaces the typed one, field by
 *  field; a part the City did not send keeps what the clerk typed. */
export function withCityAddress(form: AddPremiseForm, match: GisCandidate): AddPremiseForm {
  return {
    ...form,
    address_line: match.address_line,
    city: match.city ?? form.city,
    state: match.state ?? form.state,
    postal_code: match.postal_code ?? form.postal_code,
  };
}

// ── The same address (BR-MET-1190) ──────────────────────────────────────────

/** What the same-address check found, and what the clerk chose. A box with
 *  `choice: null` holds Continue until the clerk picks *Open it* or *Add it
 *  anyway* (PO 2026-10-09). */
export interface SameAddressState {
  premise: SameAddressPremise;
  choice: "anyway" | null;
}

/** The refusal's params, read back into the box's shape (the save's own
 *  check, when two clerks typed one address in the same minute). */
export function sameAddressFromParams(params: Record<string, unknown> | undefined): SameAddressPremise | null {
  if (params === undefined) return null;
  const premiseNo = params.premise_no;
  const id = params.premises_id;
  if (typeof premiseNo !== "string" || typeof id !== "string") return null;
  return {
    id,
    premise_no: premiseNo,
    address: typeof params.address === "string" ? params.address : "",
    units: typeof params.units === "number" ? params.units : 0,
    status: typeof params.status === "string" ? params.status : "",
  };
}

/** Is the address complete enough to ask about? The street is the only part the
 *  server requires; asking with a street alone would match a premise that has
 *  no city either, which is exactly the duplicate a clerk should be told of. */
export function addressReadyToCompare(form: AddPremiseForm): boolean {
  return form.address_line.trim() !== "";
}

// ── The owner (BR-MET-1195) ─────────────────────────────────────────────────

/** The Owner section's state: nothing linked, or the master account the clerk
 *  LINKED — the only one the save sends. The looking and choosing in between is
 *  the kit's `PickBySearch` (never auto-linked: picking the wrong landlord bills
 *  the wrong landlord). */
export type OwnerState = { kind: "none" } | { kind: "linked"; row: OwnerSearchRow };

export function linkedOwner(owner: OwnerState): OwnerSearchRow | null {
  return owner.kind === "linked" ? owner.row : null;
}

// ── Units ───────────────────────────────────────────────────────────────────

/** `How many units` as labels — `1`, `2`, `3`. A blank, a non-number or `0`
 *  is *none yet* and never refuses (`0 adds units later.`). */
export function unitLabels(count: string): string[] {
  const parsed = Number(count.trim() === "" ? "0" : count);
  if (!Number.isInteger(parsed) || parsed < 1) {
    return [];
  }
  return Array.from({ length: Math.min(parsed, UNIT_COUNT_CAP) }, (_, at) => String(at + 1));
}

export function commonAreaLabels(form: Pick<AddPremiseForm, "common_areas">): string[] {
  return form.common_areas.map((label) => label.trim()).filter((label) => label !== "");
}

/** How many unit rows the save writes — the units plus every common area,
 *  exactly what `addPremisePayload` sends. */
export function unitsCreated(form: AddPremiseForm): number {
  return unitLabels(form.unit_count).length + commonAreaLabels(form).length;
}

/** *Creates 1 premise and 1 unit.* — the review's one line, as a key + count. */
export function outcomeLine(form: AddPremiseForm): { key: string; count: number } {
  const count = unitsCreated(form);
  if (count === 0) return { key: "metering.addPremise.review.outcomeNone", count };
  if (count === 1) return { key: "metering.addPremise.review.outcomeOne", count };
  return { key: "metering.addPremise.review.outcomeMany", count };
}

// ── The save ────────────────────────────────────────────────────────────────

/**
 * The `POST /premises` body. Nothing collected is dropped and nothing the clerk
 * did not answer is claimed:
 *
 *   · `services_available` is ALWAYS sent, because the screen now always ASKS
 *     and an empty pick is an answer (none ticked to start, plan rule 4).
 *   · `inside_city_limits`, `premises_type`, `area_code` and `route` are sent
 *     only when answered — absent is this API's *leave it alone*.
 *   · `master_account_id` only when an account was LINKED. This screen sends no
 *     key that opens an owner account; the server refuses them by name from
 *     this door (`BR-MET-1195`).
 *   · `add_anyway: true` only when the clerk pressed *Add it anyway*.
 *   · `gis_unchecked: true` — a typed address is not a checked one; the City's
 *     door sets its own when *Use these details* was pressed.
 */
export function addPremisePayload(
  form: AddPremiseForm,
  opts: { owner: OwnerSearchRow | null; addAnyway: boolean },
): Record<string, unknown> {
  const parts = addressParts(form);
  const payload: Record<string, unknown> = {
    address_line: parts.address_line,
    city: parts.city,
    state: parts.state,
    postal_code: parts.postal_code,
    services_available: [...form.services],
    gis_unchecked: true,
  };
  if (form.premises_type !== "") payload.premises_type = form.premises_type;
  if (form.inside_city_limits !== null) payload.inside_city_limits = form.inside_city_limits;
  const areaCode = areaPayloadCode(form.area);
  if (areaCode !== "") payload.area_code = areaCode;
  if (form.route !== "") payload.route = form.route;
  if (opts.owner !== null) Object.assign(payload, ownerAccountPayload(opts.owner.id));
  if (opts.addAnyway) payload.add_anyway = true;
  if (Object.keys(form.custom_data).length > 0) payload.custom_data = form.custom_data;

  const units: Record<string, unknown>[] = [];
  for (const [index, label] of unitLabels(form.unit_count).entries()) {
    const unit: Record<string, unknown> = { label };
    if (form.unit_type !== "") unit.unit_type = form.unit_type;
    // The FIRST unit carries the answers typed for it and for its services —
    // the Add a premise slots are *first unit* and *services*.
    if (index === 0) {
      if (Object.keys(form.unit_custom_data).length > 0) unit.custom_data = form.unit_custom_data;
      const points = Object.fromEntries(
        Object.entries(form.service_point_custom_data).filter(
          ([code, answers]) => Object.keys(answers).length > 0 && form.services.includes(code),
        ),
      );
      if (Object.keys(points).length > 0) unit.service_point_custom_data = points;
    }
    units.push(unit);
  }
  // A common area IS a unit (`unit_type: common_area`), in the SAME transaction.
  for (const label of commonAreaLabels(form)) {
    units.push({ label, unit_type: "common_area" });
  }
  if (units.length > 0) payload.units = units;
  return payload;
}
