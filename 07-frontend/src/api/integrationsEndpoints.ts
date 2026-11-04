// ── Trace ──────────────────────────────────────────────
// Story:    US-INT-001 (EP-INT-01) — `GET /integrations`, the grid's data
//           source (A11 addendum). US-INT-013 · US-INT-018 (the read model:
//           every manifest, this tenant's state, `operations[]` per card).
//           Screens: S8
// Rules:    BR-INT-002 (`GET /integrations`) · BR-INT-003 (masked refs only —
//           the wire carries a hint and never a payload) · BR-INT-028 (a
//           provider is a set of operations) · BR-INT-037 (the seventeen come
//           from the registry — nothing here names a provider)
// Tests:    src/features/integrations/IntegrationsTab.test.tsx
// Impacts:  06-backend/apps/integrations/selectors.py (the shape these types
//           are written against) · src/api/queryClient.ts (`queryKeys.integrations`)
// ───────────────────────────────────────────────────────
// Hand-written against `06-backend/openapi/schema.json` + `selectors.grid()`
// (src/api/README.md: the export carries no body shapes, so every field below
// is typed from the payload builder and commented with the rule it carries).

import { api } from "./client";
import type { ApiClient, ApiResponse } from "./client";

/** `integration_connection.status` — five values, never a sixth (03-field-map §5). */
export type ConnectionState = "not_set_up" | "untested" | "working" | "not_working" | "off";

/**
 * The card's word. `reading_from_us` is COMPUTED by the server for a
 * connection whose operations are all the partner's reads and that has seen
 * one — never a stored status (08-screen-layouts.md S8, state 6).
 */
export type DisplayState = ConnectionState | "reading_from_us";

/** BR-INT-001 made into data: LIVE, or COMING_SOON with the wave label the card shows. */
export interface Disposition {
  kind: "live" | "coming_soon";
  wave: string | null; // "W7" · "v1.1" · "v2" — shown beside *Coming soon*
  phase: number | null; // which CR-069 phase makes a live provider connectable
}

/** Which way the data moves, and who starts it — the card's three-word kicker. */
export interface Kicker {
  direction: "in" | "out";
  initiative: "us" | "them";
}

/** One thing a provider does (BR-INT-028), with its OWN state and last run. */
export interface OperationRow {
  name: string; // the manifest's operation name — the catalogue key stem
  label: string; // the manifest's English label — the fallback when no catalogue line exists
  description: string;
  direction: "in" | "out";
  initiative: "us" | "them";
  state: ConnectionState;
  last_run_at: string | null;
  last_outcome: string | null;
  trace_id: string | null;
  /**
   * ── `CR-115-BRC05` §7 · WHICH API THIS ROW IS ────────────────────────────
   *
   * ⚠ **A HANDLE FOR AN ACTION AND NEVER A VISIBLE VALUE** (B14 rule 31 — *"no
   * database id is ever the visible value of a field"*). `null` on a STANDARD
   * row, which has no stored row until somebody touches its switch — absence
   * means ON.
   */
  api_id?: string | null;
  /** OURS or THEIRS. The table marks ours as standard (§7.4); it does not
   *  infer it from whether a name happens to differ from a label. */
  is_standard?: boolean;
  /** The clerk's own name. `null` where the manifest's label is the name —
   *  *"THE KIND IS OURS. THE NAME IS THEIRS"* (§7.2). */
  custom_name?: string | null;
  /** What KIND of call this is, from the closed list WE ship. `null` on a
   *  connector that offers none, which is twenty-seven of twenty-eight. */
  api_kind?: string | null;
  /**
   * §7.5 rule 3 — *"A disabled API is NOT scheduled and NOT called"*.
   *
   * ⚠ **THE RUNNERS OBEY THIS TOO, AND THAT IS THE WHOLE POINT.** A screen
   * that drew the switch while `gis.search` went on calling the layer would be
   * hard-won law 2's mirror exactly: a control that renders and changes nothing
   * looks identical to a working one.
   */
  enabled?: boolean;
  /** BR-INT-019 — what `test()` does, in the manifest's words; null = *cannot be tested until first use*. */
  test_action: string | null;
  /** BR-INT-026 — the test sends to an address a person TYPES (a mail test), never a customer list. */
  test_needs_recipient: boolean;
  /** `BR-INT-048` / `C14` — WHO PLACES THE CALL. `browser` carries no tenant
   *  secret; `browser_credentialed` is the page the processor hosts. */
  executor: "server" | "browser" | "browser_credentialed";
  /** `C15` — an INLINE operation has a budget instead of a job. `null` on
   *  every other kind, which is the honest answer rather than a default. */
  latency_budget_ms: number | null;
  /** `C16` — `offer` shows the answer and writes nothing until a person picks. */
  result_disposition: "load" | "offer" | null;
  /**
   * CR-110-BRC04 wave A — WHEN this operation happens, the vendor's fact and
   * not the clerk's. `S147` draws it as a column and turns it into the drawn
   * words; the enum never reaches a screen.
   *
   * ⚠ **OPTIONAL BECAUSE A CACHED PAYLOAD FROM BEFORE THIS WAVE HAS NEITHER
   * FIELD**, and a type that promises what the wire may not carry is the same
   * lie as a comment claiming a guarantee (hard-won law 1).
   */
  trigger?: "manual" | "scheduled" | "dispatcher" | "webhook" | "partner" | "inline";
  /** Which CONFIGURED FIELD holds this operation's host — not the host itself.
   *  The screen walks it into the connection's own `settings` and draws
   *  nothing when it is not there (`DEF-INT-5488`: 15 of 18 manifests name a
   *  field they never declare). */
  host_field?: string;
  /**
   * `CR-110-BRC04` wave B — the RESOLVED host, where `host_field` above is the
   * NAME of the field that holds it. Both travel on purpose: wave A's set-up
   * screen walks the name, and `S142` needs the value.
   *
   * ⚠ **THE RESOLUTION IS WHY THE COLUMN IS NOT EMPTY.** 15 of 18 manifests
   * name `base_url` and never declare it (`DEF-INT-5488`), so a screen that
   * only walks `host_field` draws a dash on every connector we ship — a column
   * structurally incapable of showing anything, which is hard-won law 7. The
   * server falls back to the manifest's own single field of kind `host`.
   * `null` is a real absence, never a guess.
   */
  endpoint?: string | null;
  /**
   * `CR-115-BRC05` lane 1 — HOW `endpoint` above was decided.
   *
   * `operation_field` — the field this operation names · `connector_field` —
   * the connector's single address field, because the operation's named
   * nothing · `served_path` — the address WE publish for a door a partner
   * dials · `none` — nothing named one.
   *
   * ⚠ **A SCREEN MUST NEVER WORK THIS OUT FOR ITSELF.** The per-API work has
   * to tell a clerk *using the connector's address* apart from *its own*, and
   * a screen deriving that from `host_field` and `settings` is a second source
   * by another name — which is literally what `DEF-INT-5613` was: this file's
   * own `ConnectorSetupPage.endpointText` climbed one rung of a three-rung
   * ladder and printed a dash on 9 of 91 operations where `S142` printed an
   * address.
   *
   * Optional for wave A's reason: a payload cached from before this change
   * carries neither field.
   */
  /** ⚠ **`api_row` ADDED WITH THE RUNG IT NAMES (`CR-115-BRC05` §7).** The
   *  ladder grew a rung zero — the address a clerk typed on this API's own row
   *  — and a union that did not know the word made every comparison against it
   *  **structurally false**: `TS2367`, *"this comparison appears to be
   *  unintentional … have no overlap"*. The set-up screen's footnote check read
   *  that way for about an hour, and it is hard-won law 7's *incapable of
   *  failing* wearing a type's clothes.
   *  ⚠ **`tsc --noEmit -p tsconfig.json` DID NOT CATCH IT AND `npm run build`
   *  DID** (`DEF-2464`, and `G54` is what reported it): a narrower invocation
   *  sees a different file set, and vitest never type-checks at all. */
  endpoint_source?:
    | "api_row"
    | "operation_field"
    | "connector_field"
    | "served_path"
    | "none";
  /** Which config key answered, or `null` when no config key did (a
   *  `served_path` is ours and lives on the manifest, not in a setting). */
  endpoint_field?: string | null;
  /**
   * The RATE LIMIT column, DISPLAY ONLY — PO 2026-09-16, *"we cant allow clark
   * to reset it … keep the check in code - thats it"*. There is no input and
   * no Save anywhere on this screen.
   *
   * ⚠ **`null` ON EVERY OUTWARD OPERATION, AND THAT IS THE HONEST ANSWER.**
   * The enforced ceiling guards a partner calling US. Nothing throttles the
   * calls we place at a vendor, so an outward row draws a dash rather than
   * borrowing the inbound number.
   *
   * Optional for wave A's own reason: a payload cached from before this wave
   * carries neither field, and a type that promises what the wire may not
   * carry is the same lie as a comment claiming a guarantee.
   */
  rate_limit_per_minute?: number | null;
  /**
   * `CR-115-BRC05` R31 — **does this operation have a *Run now* door?**
   *
   * ⚠ **THE SERVER DECIDES AND THE SCREEN OBEYS.** The shape of a runnable row
   * is visible on this very interface — inbound, ours, `trigger: "scheduled"`,
   * `executor: "server"` — and FIVE shipped connectors declare exactly that
   * with no service behind them. A screen that worked it out for itself would
   * draw a live button over a route that answers 404, which is hard-won law 2's
   * mirror and the fault that left the customer portal with two working doors
   * out of eight.
   *
   * Optional for this file's standing reason: a payload cached from before this
   * wave carries no such field, and a type promising what the wire may not
   * carry is the same lie as a comment claiming a guarantee.
   */
  can_run_now?: boolean;
}

/**
 * BR-INT-043 — the CLOSED vocabulary of field kinds. The modal's field slot is
 * an exhaustive map over this union: a kind missing from the map is a `tsc`
 * error, never a fallback branch, and a manifest declaring a kind outside it
 * is refused by the registry at load (US-INT-019 TC-5).
 */
export type FieldKind =
  | "text"
  | "email"
  | "host"
  /**
   * A WHOLE SERVICE ADDRESS — scheme, host, optional port, optional path
   * (`DEF-INT-5589`, PO 2026-09-17). Not `host` widened: an ArcGIS layer is
   * named by its PATH, while SMTP and the file drops dial a bare host and a
   * port. Nineteen *Service address* fields carry this kind; five genuinely
   * host-only fields keep `host`.
   */
  | "url"
  | "port"
  | "secret"
  | "select"
  | "redirect"
  | "mapping_editor"
  | "issued_secret";

/** One entry of the modal's field slot, rendered from `manifest.fields` and from nothing in React. */
export interface ManifestField {
  name: string; // the key the value is posted under
  label: string; // English fallback; `integrations.provider.<key>.field.<name>` wins when present
  kind: FieldKind;
  required: boolean;
  options: string[]; // `select` only — the closed list of values
  /** CR-173-BRC10 — the named section this field is drawn and saved in
   *  (`send_file` is New World's *Send to City folder*), or null/absent for
   *  the connection's own details. */
  group?: string | null;
}

/** The ACTIVE credential as a screen may see it: a hint, never a payload (BR-INT-003). */
export interface CredentialHint {
  version: number;
  hint: string; // "••••3F9A"
  expires_at: string | null;
}

export interface ConnectionRow {
  id: string; // a handle for Manage — never a visible value (B14 rule 31)
  label: string | null;
  describe: string | null; // US-INT-015 `describe()` — the masked line on the card, never a secret
  /** Wave J (`CR-069`) — the connection's own NON-SECRET settings, filtered by
   *  the manifest's own `Field.kind` on the server (`selectors.settings_for`).
   *
   *  ⚠ `describe` ABOVE IS A SENTENCE AND THIS IS THE VALUES. A screen that
   *  has to SET a control — S43 defaulting its format picker to the saved
   *  export target — cannot read a sentence, and parsing one back into values
   *  would be a second source of truth that breaks on the first translation.
   *
   *  ⚠ A SECRET CANNOT ARRIVE HERE. The filter is the same `is_secret` reading
   *  `split_fields` applies on the way IN, so a field that cannot be written
   *  into `config` cannot be read out of it — one rule, both directions. */
  settings: Record<string, unknown>;
  connected_by: string | null; // a NAME (rule 31), read off identity by the selector
  environment: "production" | "sandbox";
  status: ConnectionState;
  enabled: boolean;
  cadence: "nightly" | "hourly" | "manual";
  next_run_at: string | null;
  last_test_at: string | null;
  last_test_ok: boolean | null;
  last_test_text: string | null;
  connected_at: string | null;
  credential: CredentialHint | null;
  /** Wave H (US-INT-027 · BR-INT-042) — the credential's LIFECYCLE, which is a
   *  different fact from the credential itself.
   *
   *  ⚠ `expires_at` arrives as ISO-8601 and is NOT formatted by the server.
   *  The tenant's regional format belongs to the screen (BR-SHL-023 keeps ONE
   *  formatting path), so every consumer runs it through `formatDate` — a
   *  server-rendered date would be a second path no locale change could reach.
   *
   *  Both S142's `WarningBox` and the S7 attention strip read THIS, so the
   *  boundary between *warning* and *lapsed* is decided once, on the server,
   *  and two screens cannot disagree about which side of it a date falls on. */
  expiry: CredentialExpiry;
}

/** Where an active credential is in its life (`apps/integrations/expiry.py`). */
export interface CredentialExpiry {
  /** `unknown` is not `ok`: `ok` claims the secret is good, and there isn't one. */
  state: "ok" | "warning" | "lapsed" | "unknown";
  expires_at: string | null; // ISO-8601, or null when it does not expire
  days_left: number | null; // negative once it has passed
  window_days: number; // the provider's own warning window, from its manifest
  version: number | null;
}

/**
 * One Kind the Add form may offer — `CR-115-BRC05` §7.3's closed list, served.
 *
 * ⚠ **THE SERVER DECIDES IT, NOT THIS FILE.** A React array of three kinds
 * would be the front end deciding what the product can do, which is the shape
 * `BR-INT-037` forbids and the shape that let a set-up screen answer
 * differently from a view screen on 9 of 91 operations (`DEF-INT-5613`).
 *
 * `refusal` is a catalogue key or `null`. `null` means Add will work; a key is
 * the sentence a clerk reads instead — today only rule 1's second scheduled
 * sync. ⚠ **A Kind already configured is simply ABSENT from this list** (§7.4,
 * *"one configuration per API, never two"*), which is a different state from
 * refused and is why they are not one flag.
 */
export interface AddableKind {
  kind: string;
  refusal: string | null;
}

export interface ProviderCard {
  key: string; // the manifest key — `integrations.provider.<key>.*` catalogue stem
  category: string; // `integrations.category.<category>` — the chips are generated from these
  display_name: string; // English fallback
  summary: string; // English fallback — one sentence (B14 rule 32)
  fields: ManifestField[]; // BR-INT-043 — the field slot's source
  disposition: Disposition;
  kicker: Kicker;
  auth: { mode: string; placement: string };
  codecs: string[];
  // Wave D (US-INT-037): the kinds of THEIR words this provider ships, so the
  // card can offer *Mappings*. Data from the manifest, never a per-provider branch.
  vocabularies: { entity_type: string; label: string; count: number }[];
  adapter_registered: boolean;
  /** `CR-198-BRC10` — present only for a provider the PLATFORM holds
   *  (`auth.mode === "platform_holds_ours"`); never connected by a utility. */
  platform?: Omit<PlatformTexts, "last_sent_at" | "last_error" | "last_error_at"> | null;
  connection: ConnectionRow | null; // the production row, or null when *Not set up*
  connections: ConnectionRow[]; // production first, then the sandbox twin (BR-INT-026)
  state: ConnectionState;
  display_state: DisplayState;
  operations: OperationRow[];
  /** `CR-115-BRC05` §7.3 — what the Add form may offer. `[]` on a connector
   *  that offers none, and the screen then draws no form at all. */
  custom_api_kinds?: AddableKind[];
  // Wave E (US-INT-024 · US-INT-025) — hints and counts, never a payload.
  credentials: CredentialVersion[];
  disconnect: DisconnectPreview | null;
  // Wave R (US-INT-040) — the keys WE issued, for S144. `[]` on every card
  // whose manifest has no `issued_secret` field, which is sixteen of eighteen.
  issued_keys: IssuedKey[];
}

/** One key WE issued to a partner, as S144 may see it (`US-INT-040` §5).
 *
 *  ⚠ THERE IS NO FIELD ON THIS TYPE THAT COULD HOLD THE KEY, and that is
 *  deliberate in exactly the way `CredentialVersion` above is: the key is
 *  shown once, in the body of the request that minted it (`IssuedKeyResult`),
 *  and no read path serves it again — because the server has not stored it.
 *  `hint` is the whole of what a screen ever gets. */
export interface IssuedKey {
  version: number;
  hint: string; // `••••7Q2F` — the mask and four characters
  state: "active" | "revoked";
  issued_at: string;
  revoked_at: string | null;
  last_used_at: string | null; // null = *never used*, and never a zero-date
  /** ⚠ **WHICH OF OUR APIS THIS KEY MAY CALL — the drawn `MAY CALL` column.**
   *  `CR-110-BRC04`'s key-scope wave put it on the credential and served it on
   *  the card, and NO SCREEN HAS EVER READ IT (`DEF-INT-5533`). It is
   *  OPERATION NAMES, not the clerk's words: one vocabulary for the ticks and
   *  for the door (`DEF-INT-5504`). Optional because a payload cached from
   *  before that wave carries no such field and the WIRE decides that, not
   *  this type — the same reasoning `disposition` carries below, and the same
   *  white screen if it is got wrong. */
  scope?: string[];
}

/** `POST /integrations/{key}/key` — the ONE response that carries a key.
 *
 *  ⚠ `key` HERE IS THE ONLY COPY THAT WILL EVER EXIST. Nothing stores it —
 *  not the server, not this client, not the query cache — so a screen that
 *  receives this must show it immediately and must not re-fetch expecting it
 *  back. Losing it is not recoverable and is not meant to be: the answer is
 *  to issue another key, which is what pressing the button again does. */
export interface IssuedKeyResult {
  key: string;
  hint: string;
  version: number;
  issued_at: string;
  card: ProviderCard;
}

/** One stored credential VERSION, as a screen may see it (frame 54.2).
 *
 *  ⚠ `hint` IS THE WHOLE OF WHAT A SCREEN EVER GETS — `••••kbox`, the mask and
 *  the last four characters. There is no field on this type that could hold a
 *  password, which is why the type is here rather than a `secret?: string`
 *  somebody could optionally populate later (BR-INT-003). */
export interface CredentialVersion {
  version: number;
  is_active: boolean;
  hint: string;
  expires_at: string | null;
  rotated_at: string | null;
  created_at: string;
}

/** What the disconnect confirm states BEFORE anything is destroyed (US-INT-003).
 *
 *  ⚠ `messages_waiting` IS `null` WHEN NOBODY COULD COUNT, and the screen must
 *  not render that as a zero — "nothing is waiting" and "we could not count"
 *  are different sentences and only one of them is reassuring. */
export interface DisconnectPreview {
  category: string;
  label: string | null;
  versions: number;
  runs_kept: number;
  channel: string | null;
  messages_waiting: number | null;
}

export interface IntegrationsGrid {
  categories: { key: string }[]; // first-appearance order, from the registry
  providers: ProviderCard[]; // registration order — the order the grid draws
  counts: { providers: number; connected: number };
}

function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

// ── Wave D (US-INT-037) — their words for our things, S143 ────────────────

/** One of THEIR words and what it means here. `local_value` is a CODE (a payment
 *  method's code, a reversal reason), never a database id (B14 rule 31). */
export interface MappingRow {
  entity_type: string;
  external_value: string; // their word — CASH, ACHCHECK, R01, 001.100.44100
  local_value: string | null; // our code, or null when unmapped
  local_label: string | null; // our word, as the tenant spells it
  state: "mapped" | "unmapped";
  shipped: boolean; // listed by the manifest (false = arrived on the wire, or typed)
  last_seen_at: string | null; // ISO, from the connection's non-secret config
  stays_other: boolean; // R02 — ruled 2026-09-04: it always records as Other
}

/** One kind of thing (a tab on S143) with the choices of ours beside it. */
export interface MappingType {
  entity_type: string;
  label: string; // English fallback — `integrations.mappings.type.<entity_type>` wins
  summary: string;
  open: boolean; // their words are typed, not shipped
  choices: { value: string; label: string }[];
  counts: { rows: number; unmapped: number };
  beside_the_chart: boolean; // ledger accounts: the chart's own refs stay where they are, permanently (OQ-INT-1480 held)
}

export interface MappingsPayload {
  provider: { key: string; display_name: string };
  target_key: string;
  types: MappingType[];
  rows: MappingRow[]; // unmapped first, then their word
  counts: { rows: number; unmapped: number };
}

/** What `PUT` sends: their word → our code; `local_value: null` unmaps. */
export interface MappingWrite {
  entity_type: string;
  external_value: string;
  local_value: string | null;
}

/** `GET /integrations/{key}/mappings` — every row for the provider's target. */
export async function getMappings(client: ApiClient, key: string): Promise<MappingsPayload> {
  const response = await client.get<MappingsPayload>(
    `/integrations/${encodeURIComponent(key)}/mappings`,
  );
  return requireData(response);
}

/** `PUT /integrations/{key}/mappings` — set one or more rows; answers the refreshed view. */
export async function putMappings(
  client: ApiClient,
  key: string,
  rows: MappingWrite[],
): Promise<MappingsPayload> {
  const response = await client.put<MappingsPayload>(
    `/integrations/${encodeURIComponent(key)}/mappings`,
    { rows },
  );
  return requireData(response);
}

// ── the run record (wave C — US-INT-020 · 021) ───────────────────────────────
// ⚠ TWO SHAPES, AND THE DIFFERENCE IS THE STORY'S MITIGATION. `RunRow` has NO
// `provider_error` and no items; `RunDetail` has both. A list payload is the
// thing that gets logged, cached and forwarded, and `provider_error` is the one
// column where another utility's customer can arrive — quoted back at us by a
// mail server. The split is the server's (`apps/integrations/runs.py`); these
// two types are it, restated where a screen can be typed against it.

/**
 * The EIGHT outcomes (`03-field-map.md` §5). `unconfirmed` is never green.
 *
 * ⚠ `skipped` WAS MISSING FROM THIS UNION WHILE THE BACK END EMITTED IT
 * (added CR-069 wave I; the value has existed since wave `F1`'s breaker,
 * `BR-INT-024`). A word the server can send and the client's type does not
 * know is not a type error anywhere — the value simply arrives, every
 * `switch` falls through to its default, and the screen renders whatever the
 * default happens to be. It rendered *0 of 0*.
 *
 * The three not-knowings are deliberately distinct and the difference is the
 * whole point of having three: `unconfirmed` is *they would not say*,
 * `indeterminate` is *we asked and cannot tell*, `skipped` is *we did not
 * ask*. Only the last has an action attached to it.
 */
export type RunOutcome =
  | "queued"
  | "running"
  | "succeeded"
  | "partial"
  | "failed"
  | "unconfirmed"
  | "indeterminate"
  | "skipped";

/** One item the run could not do — named, because a batch boolean is not a result. */
export interface RunItem {
  /** The number a clerk would search for — an account number, never an id. */
  ref: string | null;
  /** The thing itself in their words: the address, the file, the meter. */
  detail: string | null;
  outcome: string;
  /** The provider's own sentence for THIS item, scrubbed at the write seam. */
  provider_text: string | null;
}

/** A run as the LIST serves it. */
export interface RunRow {
  /** Carried so the row action can fetch the detail — NEVER rendered (rule 31). */
  id: string;
  /** The eight characters support is read down the phone, labelled *Support reference*. */
  trace_id: string;
  provider_key: string;
  provider_name: string;
  connection_label: string;
  environment: string | null;
  operation: string;
  operation_label: string;
  direction: string;
  trigger: string;
  /** `CR-115-BRC05` R31 — **what this run was allowed to change.** `null` on
   *  every run with no such choice to make, which is every run in the product
   *  today except the parcel reconciliation. A table of runs where half
   *  changed nothing and half changed everything, with no way to tell which,
   *  is worse than no column at all. */
  mode?: "preview" | "apply" | null;
  /** WHICH PERSON pressed it. `trigger` already says WHETHER a person did, so
   *  this carries only the half the existing columns cannot. */
  started_by_name?: string | null;
  outcome: RunOutcome | null;
  attempted: number;
  succeeded: number;
  failed: number;
  skipped: number;
  changed: number;
  /** `C13` — the fifth count is *revised*, and only a reconcile operation revises. */
  show_changed: boolean;
  summary: string | null;
  started_at: string;
  finished_at: string | null;
  has_artifact: boolean;
  named_items: number;
  /** How many unsuccessful items the cap left out — said in words, never a silent gap. */
  unnamed_items: number;
}

/** What a RUNNING collection has told us so far (CR-069 wave K, frame 53.2).
 *
 *  Both shapes come off the job's own checkpoint, written by `runners/fetch.py`
 *  as the work happens — so a clerk who closed the page reads them on return
 *  (`US-INT-031` TC-3). `asked` / `next_in_s` is a vendor building a file;
 *  `window` / `of` is a walk through their windows. A finished run serves
 *  `null` rather than a stale last value. */
export interface RunCollecting {
  done: number | null;
  total: number | null;
  asked?: number | null;
  next_in_s?: number | null;
  window?: number | null;
  of?: number | null;
}

/** A run as the DETAIL serves it: the row, plus the things a list may not carry. */
export interface RunDetail extends RunRow {
  provider_error: string | null;
  artifact_link: string | null;
  content_hash: string | null;
  items: RunItem[];
  /** Frame 83.1 — the request parameters whose default is unsafe, stated
   *  explicitly on every request (`US-INT-035`, `C18`). Empty for an operation
   *  that has none, and the panel is then absent rather than empty. */
  asked_for: string[];
  /** Frame 53.2 — present only while the run is still going. */
  collecting: RunCollecting | null;
}

/** S142's whole payload: the head, the operations and the runs, in one call. */
export interface ConnectionRuns {
  provider: {
    key: string;
    display_name: string;
    category: string;
    /** Wave H — whether this connection has a PASSWORD or is SIGNED IN TO.
     *  `placement === "redirect"` means the second. S142 reads it so the
     *  panel does not offer to replace a password that does not exist
     *  (`DEF-INT-4237`); it is manifest data, never a branch on a key. */
    auth: { mode: string; placement: string };
    /** `CR-110-BRC04` wave B — whether this connector can be connected at all.
     *  The grid has said *Not ready to connect yet* since wave A and this page
     *  did not, so a clerk opening a placeholder's own page saw a screen that
     *  read as ready over a connect the server refuses. */
    /**
     * ⚠ **OPTIONAL, AND IT WHITE-SCREENED THE WHOLE PAGE BEFORE IT WAS.** A
     * payload cached from before this wave carries no `disposition`, and a
     * screen reading `.kind` off it threw *Cannot read properties of undefined*
     * into the error boundary — the connector page replaced by *Unexpected
     * Application Error*. `tsc` cannot see it: the type said the field is
     * always there and the WIRE decides that, not the type. Same reasoning
     * wave A gives for `trigger` one interface up, and it is the honest shape
     * rather than a promise the server has not always kept.
     */
    disposition?: { kind: "live" | "coming_soon"; wave: string | null };
    /** `CR-174-BRC10` — their-words vocabularies this connector ships; a
     *  non-empty list is what puts *Map their words →* on S142. Optional for
     *  the reason `disposition` is: a cached payload may predate it. */
    vocabularies?: { entity_type: string; label: string; count: number }[];
  };
  describe: string | null;
  display_state: DisplayState;
  connection: ConnectionRow | null;
  operations: OperationRow[];
  /** `CR-115-BRC05` §7.3 — what the Add form may offer on THIS connector. */
  custom_api_kinds?: AddableKind[];
  /** Wave E — the same two off the same card, so S142 and the grid agree. */
  credentials: CredentialVersion[];
  /** `CR-110-BRC04` phase 2 — the keys WE issue, for the drawn *Keys we issue*
   *  panel (p062, p066). `[]` on the twelve connectors we dial, because the
   *  card serves it only where the manifest declares an `issued_secret` field,
   *  so the panel is ABSENT there rather than empty. Optional for the cached
   *  payload, exactly as `disposition` above. */
  issued_keys?: IssuedKey[];
  disconnect: DisconnectPreview | null;
  filters: {
    operations: { name: string; label: string }[];
    outcomes: string[];
    triggers: string[];
  };
  applied: { q: string; operation: string | null; outcome: string | null; trigger: string | null };
  rows: RunRow[];
  page: { page: number; per: number; count: number; pages: number };
  /** Rows on this page belonging to ANOTHER connection — only ever from a trace search. */
  elsewhere: number;
}

export interface RunQuery {
  q?: string;
  operation?: string;
  outcome?: string;
  trigger?: string;
  page?: number;
  /** One of the product's five page sizes (`tableTypes.PAGE_SIZES`). */
  per?: number;
}

/** `GET /integrations/{key}/runs` — the last twenty, newest first. */
export async function getConnectionRuns(
  client: ApiClient,
  key: string,
  query: RunQuery = {},
): Promise<ConnectionRuns> {
  const params = new URLSearchParams();
  if (query.q !== undefined && query.q !== "") params.set("q", query.q);
  if (query.operation !== undefined && query.operation !== "") {
    params.set("f.operation", query.operation);
  }
  if (query.outcome !== undefined && query.outcome !== "") params.set("f.outcome", query.outcome);
  if (query.trigger !== undefined && query.trigger !== "") params.set("f.trigger", query.trigger);
  if (query.page !== undefined && query.page > 1) params.set("page", String(query.page));
  if (query.per !== undefined) params.set("per", String(query.per));
  const suffix = params.toString() === "" ? "" : `?${params.toString()}`;
  const response = await client.get<ConnectionRuns>(
    `/integrations/${encodeURIComponent(key)}/runs${suffix}`,
  );
  return requireData(response);
}

/** `GET /integrations/{key}/runs/{run_id}` — one run, its items and their words. */
export async function getRun(client: ApiClient, key: string, runId: string): Promise<RunDetail> {
  const response = await client.get<RunDetail>(
    `/integrations/${encodeURIComponent(key)}/runs/${encodeURIComponent(runId)}`,
  );
  return requireData(response);
}

/** `GET /integrations` — every manifest joined to THIS tenant's connection state. */
export async function getIntegrationsGrid(client: ApiClient = api): Promise<IntegrationsGrid> {
  const response = await client.get<IntegrationsGrid>("/integrations");
  return requireData(response);
}

// ── the writes (wave B — US-INT-002 · 017 · 016) ─────────────────────────────
// Every write refuses a coming-soon key at the server (BR-INT-001) and an
// unknown key as a plain 404; the modal renders the refusal it gets back and
// never decides one itself. None of these is retried (a mutation is a second
// write — CLAUDE.md rule 6 is the server's guarantee, never the client's).

/** The modal's one mapping: environment, cadence, and every field by name. */
export interface ConnectBody {
  environment: "production" | "sandbox";
  cadence: "nightly" | "hourly" | "manual";
  label?: string;
  fields: Record<string, string>;
}

/** The 202 body (B12 r1 §3): the job id and where to poll — nothing else. */
export interface Accepted {
  job_id: string;
  status_url: string;
}

/** `POST /integrations/{key}/connect` → 201 and the card. A refusal stores nothing. */
export async function connectIntegration(
  client: ApiClient,
  key: string,
  body: ConnectBody,
): Promise<ProviderCard> {
  const response = await client.post<ProviderCard>(`/integrations/${key}/connect`, body);
  return requireData(response);
}

/** `POST /integrations/{key}/test` → 202. The `jobs` row exists before the reply. */
export async function testIntegration(
  client: ApiClient,
  key: string,
  recipient?: string,
): Promise<Accepted> {
  const body = recipient === undefined || recipient === "" ? {} : { recipient };
  const response = await client.post<Accepted>(`/integrations/${key}/test`, body);
  return requireData(response);
}

/** `PATCH /integrations/{key}` — non-secret settings only; a secret goes through `rotateCredential`. */
export async function updateIntegration(
  client: ApiClient,
  key: string,
  changes: {
    label?: string | null;
    cadence?: ConnectBody["cadence"];
    enabled?: boolean;
    config?: Record<string, string>;
  },
): Promise<ProviderCard> {
  const response = await client.patch<ProviderCard>(`/integrations/${key}`, changes);
  return requireData(response);
}

/** `DELETE /integrations/{key}` — every credential version destroyed, the runs kept. */
export async function disconnectIntegration(client: ApiClient, key: string): Promise<ProviderCard> {
  const response = await client.del<ProviderCard>(`/integrations/${key}`);
  return requireData(response);
}

/** `POST /integrations/{key}/credential` — v(n+1); 202 when a test was queued behind it. */
export async function rotateCredential(
  client: ApiClient,
  key: string,
  fields: Record<string, string>,
): Promise<ProviderCard | Accepted> {
  const response = await client.post<ProviderCard | Accepted>(`/integrations/${key}/credential`, {
    fields,
  });
  return requireData(response);
}

/** `POST /integrations/{key}/credential/rollback` — the previous version active
 *  again in one row, and nobody re-authorises (US-INT-024). Answers the CARD:
 *  the screen wants the connection's new word and the refreshed history, and a
 *  credential row is not a thing this API ever serves. */
export async function rollbackCredential(client: ApiClient, key: string): Promise<ProviderCard> {
  const response = await client.post<ProviderCard>(
    `/integrations/${encodeURIComponent(key)}/credential/rollback`,
    {},
  );
  return requireData(response);
}

/** What `POST /integrations/{key}/oauth/start` answers — where to send the
 *  person, and the nonce that proves the trip back is the same trip. */
export interface OAuthStart {
  authorize_url: string;
  /** A one-time nonce. Not a secret to protect — a value to echo. */
  state: string;
}

/**
 * `POST /integrations/{key}/oauth/start` — the redirect kind's button.
 *
 * ⚠ THIS REFUSED EVERY CALL UNTIL 2026-09-06 and this comment said so. Wave H
 * built the round trip, so the refusal went in the same commit: a control still
 * refusing over a feature that has landed is the mirror of hard-won law 2, and
 * it costs more than dead UI because every check passes over it.
 *
 * `redirectUri` is the browser's own return address. It is the CALLER's because
 * the front end knows its origin and the server does not — a hardcoded one
 * would work on the demo host and silently send every production sign-in to
 * the wrong place.
 */
// ── CR-198-BRC10 — a provider the PLATFORM holds (texts, one Twilio account) ──

/** Why the platform cannot fully text — CODES, translated on screen. */
export type PlatformProblem =
  | "no_account"
  | "no_send_credential"
  | "no_sender"
  | "no_callback_address"
  | "callbacks_unverifiable";

/** `GET /integrations/{key}/platform` — booleans, codes and a masked tail;
 *  there is no field on this type that could hold a secret. */
export interface PlatformTexts {
  provided_by_platform: true;
  configured: boolean;
  sender_kind: "messaging_service" | "from_number" | null;
  sender_hint: string | null;
  own_sender: boolean;
  callbacks: boolean;
  problems: PlatformProblem[];
  last_sent_at: string | null;
  last_error: string | null;
  last_error_at: string | null;
}

export interface PlatformTestResult {
  ok: boolean;
  sentence?: string;
  sentence_key?: string;
  provider_text: string | null;
}

export async function getPlatformTexts(client: ApiClient, key: string): Promise<PlatformTexts> {
  const response = await client.get<PlatformTexts>(
    `/integrations/${encodeURIComponent(key)}/platform`,
  );
  return requireData(response);
}

export async function sendPlatformTestText(
  client: ApiClient,
  key: string,
  to: string,
): Promise<PlatformTestResult> {
  const response = await client.post<PlatformTestResult>(
    `/integrations/${encodeURIComponent(key)}/platform-test`,
    { to },
  );
  return requireData(response);
}

export async function startOAuth(
  client: ApiClient,
  key: string,
  redirectUri: string,
): Promise<OAuthStart> {
  const response = await client.post<OAuthStart>(
    `/integrations/${encodeURIComponent(key)}/oauth/start`,
    { redirect_uri: redirectUri },
  );
  return requireData(response);
}

/**
 * `GET /integrations/{key}/oauth/return?code=…&state=…` — the trip back.
 *
 * Answers the CARD rather than a credential, exactly as `rollbackCredential`
 * does: the screen wants the connection's new word and its refreshed history,
 * and a credential is not a thing this API ever serves (BR-INT-003).
 *
 * ⚠ A GET because a PROVIDER redirects a browser here; it is not our form post.
 * The `state` nonce is what makes that safe, and the server refuses before the
 * code is exchanged when it does not match the one it minted.
 */
export async function completeOAuth(
  client: ApiClient,
  key: string,
  code: string,
  state: string,
): Promise<ProviderCard> {
  const query = new URLSearchParams({ code, state }).toString();
  const response = await client.get<ProviderCard>(
    `/integrations/${encodeURIComponent(key)}/oauth/return?${query}`,
  );
  return requireData(response);
}

/**
 * `POST /integrations/{key}/key` — issue or replace the key we give a partner.
 *
 * ⚠ THE RESPONSE IS THE ONLY TIME THE KEY IS EVER RENDERED. It is deliberately
 * NOT put in the query cache: a cached key would be a copy of a secret sitting
 * in browser memory for the life of the tab, which is the thing wave R exists
 * to avoid. The caller holds it in component state for as long as the panel is
 * open and drops it on close (`US-INT-040` TC-1).
 */
export async function issuePartnerKey(
  client: ApiClient,
  key: string,
  scope: readonly string[],
): Promise<IssuedKeyResult> {
  const response = await client.post<IssuedKeyResult>(
    `/integrations/${encodeURIComponent(key)}/key`,
    { scope },
  );
  return requireData(response);
}

/** `DELETE /integrations/{key}/key` — revoke. The partner's very next call is
 *  refused, not their next collection. Answers the CARD, the shape
 *  `rollbackCredential` established: the screen wants the refreshed key list. */
export async function revokePartnerKey(client: ApiClient, key: string): Promise<ProviderCard> {
  const response = await client.del<ProviderCard>(
    `/integrations/${encodeURIComponent(key)}/key`,
  );
  return requireData(response);
}

// ── CR-069 wave S (US-INT-041) — who has been reading, and the register ────

/** One page a partner took: when, what they took, how many, under which key.
 *
 *  ⚠ `detail` CARRIES THE KEY'S HINT AND THERE IS NO FIELD HERE THAT COULD HOLD
 *  THE KEY — the same reasoning as `CredentialVersion` above. The server never
 *  had the plaintext past the moment it checked it, so there is nothing on this
 *  type to forget to strip.
 *
 *  `unusual` is a DISPLAY judgment the server makes once (a page of 10,000 rows
 *  or more), so the screen and an export cannot disagree about which row is
 *  drawn in amber. Nothing is ever refused because of it. */
export interface AccessLogRow {
  when: string;
  what: string; // *Payments, 1–30 Sep* — words, because a person reads it
  rows: number;
  detail: string | null; // the whole summary, the hint included
  /** `••••7Q2F` — WHO, and the only form of the key that ever leaves the
   *  server. Its own field rather than something this file parses out of
   *  `detail`, so a rewritten summary cannot silently empty the column. */
  hint: string | null;
  unusual: boolean;
  outcome: string | null;
}

export interface AccessLog {
  items: AccessLogRow[];
  total_records: number;
  unusual_rows_at: number;
}

/** `GET /integrations/{key}/access-log` — *Who has been reading* (S142). */
export async function getAccessLog(client: ApiClient, key: string): Promise<AccessLog> {
  const response = await client.get<AccessLog>(
    `/integrations/${encodeURIComponent(key)}/access-log`,
  );
  return requireData(response);
}

/** One relationship in the subprocessor register — derived, never typed.
 *
 *  `sentence` is the whole row as a person reads it: *Aclarian — reads payments
 *  and bills — authorised by Alex Reed on 2026-09-03*. The structured fields
 *  beside it exist so a table can sort; the sentence is the answer, and a
 *  register that printed only the fields would not be one. */
export interface SubprocessorRow {
  party: string;
  direction: "inward" | "outward";
  what: string;
  authorised_by: string | null;
  authorised_on: string | null;
  environment: string;
  sentence: string;
}

/* ── CR-115-BRC05 R31 · RUN NOW ─────────────────────────────────────────────
 *
 * PO, verbatim: *"i dont have Run button here"*.
 *
 * ⚠ **TWO MODES ON ONE ROUTE, NOT TWO ROUTES.** `preview` and `apply` are one
 * code path on the server up to the last step (`gis_parcels.run`'s own
 * docstring says why: a preview built as its own branch proves nothing about
 * the apply it previews and drifts the first time somebody fixes one of them).
 * A second endpoint here would re-introduce exactly that split on this side.
 */

/** What a preview or an apply did. Every count is present at zero — a run that
 *  examined nothing and a run that found nothing wrong are different facts. */
export interface ReconcileCounts {
  city_rows: number;
  city_pages: number;
  /** `DEF-INT-9849` — the City's whole register in pages. Equal to
   *  `city_pages` on a complete walk, larger when a person limited the pages,
   *  `null` when the City would not say how many rows it holds. */
  city_pages_total: number | null;
  city_page_size: number;
  premises_examined: number;
  units_examined: number;
  differences_found: number;
  differences_to_apply: number;
  /** ⚠ **R28 — *"(c) never touch by default"*.** On every tenant today this is
   *  the whole field list, so `differences_to_apply` is 0 and the screen must
   *  say WHY or a clerk reports correct behaviour as a defect. */
  fields_set_to_never_touch: number;
  queued: number;
  unmatched_ours: number;
  /** R27 — a City address we have no premises for is IGNORED. Counted so the
   *  deliberate silence carries a number. */
  city_rows_ignored: number;
  /** ⚠ OUR bug, not the City's: a key that changes on a row we already changed. */
  thrash: number;
}

/** What was actually written. **Empty on a preview, by construction.** */
export interface ReconcileApplied {
  keys_taken?: number;
  keys_replaced?: number;
  fields_applied?: number;
  verified_stamped?: number;
  rows_refused?: number;
}

export interface ReconcileReport {
  run_id: string;
  trace_id: string;
  mode: "preview" | "apply";
  started_by: "schedule" | "person";
  started_by_name: string | null;
  /** The pull failed and NOTHING was written, in either mode. A half snapshot
   *  reconciles as *the City deleted the rows it did not send*. */
  stopped: boolean;
  /** `DEF-INT-9849` — `false` when a by-hand Preview stopped after a few pages
   *  (`?pages=3`, the route's default). The screen then says *Stopped after 3
   *  of 70 pages* and never presents the counts as the register. */
  complete?: boolean;
  /** `DEF-INT-9846` — when the City REFUSED us (a key, a moved layer, their
   *  error), the catalogue key that says which; `null` for silence and for
   *  every other stop, where the screen keeps its general sentence. */
  stop_reason_key?: string | null;
  /** The server's own English sentence. ⚠ **STORED ON THE RUN ROW, NEVER
   *  RENDERED** — this screen composes its own from the counts, for the reason
   *  `ConnectionDetailPage`'s header already records: a server that sent the
   *  sentence would send it in English to eleven catalogues. */
  headline: string;
  detail?: string;
  applied: ReconcileApplied;
  counts: Partial<ReconcileCounts>;
  /** The runbook that works the differences a PERSON has to judge. A KEY, so
   *  the screen builds the address from the router's own pattern rather than
   *  carrying a second copy of it. */
  queue_runbook_key?: string;
}

/**
 * `POST /integrations/{key}/reconcile` → **200 and the report itself**, not 202.
 *
 * ⚠ **THE OPPOSITE OF `POST /integrations/{key}/run` ON PURPOSE.** That one
 * enqueues and hands back a job id and a poll url; a `core.jobs` record carries
 * a result LINK and no payload, so a clerk pressing *Preview* to find out what
 * would happen would be handed a link to nothing. The answer is the point here.
 */
export async function reconcileNow(
  client: ApiClient,
  key: string,
  mode: "preview" | "apply",
): Promise<ReconcileReport> {
  const response = await client.post<ReconcileReport>(`/integrations/${key}/reconcile`, { mode });
  return requireData(response);
}


// ── CR-115-BRC05 §7 · the per-API table and form ─────────────────────────────
//
// ⚠ **THESE GO ROUND `PATCH /integrations/{key}` ON PURPOSE, AND THAT IS §3
// RISK 1's ANSWER.** That route's save path prunes `config` to what the
// manifest still declares (`DEF-INT-5582` — the defect that broke the PO's
// allowed addresses), so per-API rows kept in `config` would be silently
// deleted by the next Edit save. Their own table cannot be pruned by a field
// validator.
//
// ⚠ **EVERY ONE ANSWERS THE CARD**, not the row it touched. The screen then
// re-renders from one shape it already knows how to draw, and the dropdown's
// contents and the table's contents cannot disagree about what was just added.

/** `POST /integrations/{key}/apis` — add one custom API (§7.3's form).
 *
 * ⚠ **NO `field_mapping` PARAMETER, AND NO SMALLER VERSION OF ONE.** PO R35,
 * verbatim: *"DOnt add field Mapping here - remove it"* — removed BY NAME. */
export async function addCustomApi(
  client: ApiClient,
  key: string,
  body: { kind: string; name: string; url: string },
): Promise<ProviderCard> {
  const response = await client.post<ProviderCard>(
    `/integrations/${encodeURIComponent(key)}/apis`,
    body,
  );
  return requireData(response);
}

/** `PATCH /integrations/{key}/apis/{id}` — rename, re-point, or switch a
 *  CUSTOM API. A standard row is refused BY NAME for the first two (R36). */
export async function updateCustomApi(
  client: ApiClient,
  key: string,
  apiId: string,
  body: { name?: string; url?: string; enabled?: boolean },
): Promise<ProviderCard> {
  const response = await client.patch<ProviderCard>(
    `/integrations/${encodeURIComponent(key)}/apis/${encodeURIComponent(apiId)}`,
    body,
  );
  return requireData(response);
}

/** `DELETE /integrations/{key}/apis/{id}` — remove a custom API. Ours cannot
 *  be deleted: it ships with the connector (§7.4). */
export async function deleteCustomApi(
  client: ApiClient,
  key: string,
  apiId: string,
): Promise<ProviderCard> {
  const response = await client.del<ProviderCard>(
    `/integrations/${encodeURIComponent(key)}/apis/${encodeURIComponent(apiId)}`,
  );
  return requireData(response);
}

/** `PATCH /integrations/{key}/apis/standard/{operation}` — the switch on an
 *  API that SHIPS with the connector.
 *
 * ⚠ **A SEPARATE ROUTE BECAUSE A STANDARD API HAS NO ROW UNTIL NOW.** Absence
 * means ON, so there is no id to address until somebody first disagrees with
 * that default. The operation name is the MANIFEST's own name and not a
 * database id — the same string `…/runs` and the catalogue stem already use
 * (B14 rule 31). */
export async function switchStandardApi(
  client: ApiClient,
  key: string,
  operationName: string,
  enabled: boolean,
): Promise<ProviderCard> {
  const response = await client.patch<ProviderCard>(
    `/integrations/${encodeURIComponent(key)}/apis/standard/${encodeURIComponent(operationName)}`,
    { enabled },
  );
  return requireData(response);
}

/** `GET /integrations/subprocessors` — who else touches our customers' data. */
export async function getSubprocessors(client: ApiClient): Promise<SubprocessorRow[]> {
  const response = await client.get<{ items: SubprocessorRow[] }>(
    // three segments — `integrations/subprocessors` was swallowed by
    // `integrations/<key>` and answered 405 (see partner_api.py)
    "/integrations/register/subprocessors",
  );
  return requireData(response).items;
}


// ── Lifecycle ─────────────────────────────────────────────
// packet: US-INT-001@a63a1b7 (EP-INT-01 story + BR-INT-001..017 snapshot; co-packets US-INT-013@62d3643 · US-INT-018@62d3643)
// generated: 2026-09-03 by the CR-069 wave A build lane
// checklist: A✔ B✔ C✔ D✔ E✔(IntegrationsTab.tsx) F✔ G✔ H=n/a(a typed read)
// gates: tsc · vitest src/features/integrations · G18/G27 (the key stems named here have catalogue lines)
// exceptions: none — one GET and six writes, typed from the selector and the services (EXTENDED 2026-09-03 by the wave B lane; wave S added the access log and the register; wave R added the issued key — and RESTORED this trailer, which its own repair of a bad merge had dropped, found by reading `git diff --numstat` as arithmetic rather than glancing at it)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
