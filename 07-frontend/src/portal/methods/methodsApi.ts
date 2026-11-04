// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-046 (EP-CWP-09) · US-CWP-022 (EP-CWP-05). Screen: CWP-039
// Rules:    BR-CWP-011 (the signed-in surface calls the PORTAL edge and nothing
//           else) · BR-CWP-057 (a token with a brand and a last four — READ THE
//           TYPE AS THE RULE: there is no card-number field on it because there
//           is none on the wire) · BR-CWP-040 (step-up before a method changes)
// Tests:    src/portal/methods/Methods.dom.test.tsx
// Impacts:  06-backend/apps/portal/api.py (`payment_methods`,
//           `payment_method_step_up`, `payment_method_remove`)
// ───────────────────────────────────────────────────────
// Hand-written against `06-backend/apps/portal/api.py`.
//
// ⚠ **ITS OWN FILE RATHER THAN FOUR MORE FUNCTIONS IN `portalClient.ts`, AND
// THAT IS HARD-WON LAW 11 RATHER THAN A PREFERENCE.** Four lanes are building
// six payment screens against one branch at once, and a pathspec commit takes
// the WHOLE working-tree content of every path it names — so the second lane to
// commit a 1,900-line shared client silently reverts the first, with a correct
// file count and its own hunks present. This file is touched by one lane.

import { api } from "@/api/client";
import type { ApiClient, ApiResponse } from "@/api/client";

function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === undefined || response.data === null) {
    throw new Error("empty 200 body where the contract promises one (portal edge)");
  }
  return response.data;
}

/**
 * One saved card or mandate, exactly as the server serves it.
 *
 * ⚠ **READ THE FIELDS AS THE RULE** (`BR-CWP-057`). There is no `card_number`,
 * no `gateway_token` and no `cvv` on this type because there is none on the
 * wire and none in the database: the product holds the gateway's token, and the
 * only digits it ever stores are the four below. A screen cannot render a
 * number the server does not send.
 *
 * `ref` is a row id and belongs in a URL only — B14 rule 31 forbids a database
 * id as the visible value of a field, and `Methods.dom.test.tsx` asserts it
 * never reaches the DOM as text.
 */
export interface PortalPaymentMethod {
  ref: string;
  brand: string;
  /** The ONLY digits. Four characters, always. */
  last_four: string;
  /** `card` · `bank` — a mandate has no expiry. */
  kind: string;
  /** `active` · `verified` · `expired`. `expired` is DERIVED on the server. */
  status: string;
  /** `autopay` · `one_off`, in the order the customer chose them. */
  used_for: string[];
  added_on: string;
  /** `11/27`, or null on a bank mandate. */
  expires: string | null;
  /** Whether `CWP-038` may offer it. False once it has expired. */
  usable: boolean;
}

/**
 * Whether autopay may be turned on, and — when it may not — WHY.
 *
 * ⚠ **`reason` IS A KEY AND NEVER A SENTENCE** (B14 rule 35). `cash_only` and
 * `bounced` are the two the server answers; eleven catalogues each write the
 * words, at five or six of them (rule 33).
 */
export interface PortalAutopayStance {
  allowed: boolean;
  reason: string | null;
  bounces: number;
}

/**
 * Who pays the card fee, and whether a figure exists. It does not.
 *
 * `OQ-1394` was CLOSED on 2026-09-04 taking BOTH stances behind a per-tenant
 * switch, so `payer` is the utility's own setting. `priced` is false for
 * everybody: pricing a surcharge needs a processor's fee schedule and there is
 * no processor, so the screen states the stance and shows no number.
 */
export interface PortalCardFee {
  payer: string;
  priced: boolean;
  reason: string;
}

export interface PortalPaymentMethods {
  methods: PortalPaymentMethod[];
  autopay: PortalAutopayStance;
  card_fee: PortalCardFee;
}

export async function getPaymentMethods(
  client: ApiClient = api,
): Promise<PortalPaymentMethods> {
  return requireData(await client.get<PortalPaymentMethods>("/portal/payment-methods"));
}

export interface PortalStepUpSent {
  sent: boolean;
  /** `••• ••• 0144` — the MASKED contact and nothing more. */
  sent_to?: string;
  channel?: string;
  expires_in_minutes?: number;
  reason?: string;
}

/** `POST payment-methods/step-up` — the fresh code `BR-CWP-040` demands. */
export async function askForStepUpCode(client: ApiClient = api): Promise<PortalStepUpSent> {
  return requireData(await client.post<PortalStepUpSent>("/portal/payment-methods/step-up", {}));
}

export interface PortalMethodSaved {
  saved: boolean;
  method?: PortalPaymentMethod;
  /** `code_needed` · `wrong` · `expired` · `locked` · `not_a_reference`. */
  reason?: string;
}

/**
 * `POST payment-methods` — save what the card page handed back.
 *
 * ⚠ **`reference` IS THE VENDOR'S HANDLE, NEVER A CARD NUMBER.** The number is
 * typed on the vendor's own page and never enters this application; the server
 * refuses a reference carrying a long run of digits precisely because the way a
 * card number arrives in a product like this is somebody typing one into the
 * wrong box.
 */
export async function savePaymentMethod(
  body: { code: string; reference: string; used_for?: string[] },
  client: ApiClient = api,
): Promise<PortalMethodSaved> {
  return requireData(await client.post<PortalMethodSaved>("/portal/payment-methods", body));
}

export interface PortalMethodRemoved {
  removed: boolean;
  reason?: string;
}

/** `POST payment-methods/{ref}/remove` — a POST, because the code travels in
 *  the body rather than in a browser history. */
export async function removePaymentMethod(
  ref: string,
  body: { code: string },
  client: ApiClient = api,
): Promise<PortalMethodRemoved> {
  return requireData(
    await client.post<PortalMethodRemoved>(`/portal/payment-methods/${ref}/remove`, body),
  );
}
