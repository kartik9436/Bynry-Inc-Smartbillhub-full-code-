// ── Trace ──────────────────────────────────────────────
// Story:   US-RBS-040 (EP-RBS-01) — CR-075 wave E task E4.
// Screens: RBS-004 (`S150`), all seven tabs.
// Rules:   `07-endpoints.md` row 2 — `GET /runbooks/{key}`, *"Definition,
//          schedule, caps, guards, next run"* · row 3 — `PUT /runbooks/{key}` ·
//          row 8 — `GET /runbooks/runs` (the Runs tab's page) · `NFR-3`.
// Defects: DEF-RBS-4308 (this file is the shape that defect says nobody had
//          written down) · DEF-WRK-4119 / DEF-AST-4120 (a screen describing
//          the SELECTOR's dict instead of the wire, three times).
// Tests:   src/features/runbooks/setupModel.test.ts
// ───────────────────────────────────────────────────────
// WHAT `GET /runbooks/{key}` ACTUALLY SENDS — TRANSCRIBED FROM THE SERVER, NOT
// FROM THE SCREEN.
//
// ══════════════════════════════════════════════════════════════════════════
// WHY THIS FILE EXISTS AT ALL: `DEF-RBS-4308`
// ══════════════════════════════════════════════════════════════════════════
// `api/runbooksEndpoints.ts` declared `Promise<RunbookSetupView>` and cast the
// body straight to it with no mapper, saying in its own docstring that it was
// *"a claim on `D1`"* to be settled with one mapper if `D1` served something
// else. `D1` served something else — and said so in ITS docstring, for a good
// reason: a view model is translated chrome, and serving it from Django would
// put screen copy in Python and out of the eleven locale catalogues.
//
// **Both files were right about their own half and neither closed the gap.**
// Nothing went red: `tsc` is satisfied because an unchecked cast is not a
// runtime check, the screen's own tests pass a hand-built view model as a prop,
// and the render-check painted a fixture. What a browser did was throw —
// `TypeError: Cannot read properties of undefined (reading 'length')` on
// `view.capabilities.length` — and `RBS-004` had been a crashed screen since
// 16:23 on 2026-09-06.
//
// So: this file is the WIRE, `setupModel.ts` is the mapper, and `setupTypes.ts`
// stays the renderer's. Three shapes, two boundaries, each named.
//
// ⚠ **EVERY FIELD BELOW WAS READ OFF `selectors.runbook_detail`, AND THE ONES
// THE SCREEN NEEDS AND THE WIRE DOES NOT CARRY ARE ABSENT HERE RATHER THAN
// OPTIMISTIC.** `purpose` is the one that matters (`DEF-RBS-4309`): the card
// sentence *Finds what stops a bill run before it starts* has no field on
// `RunbookDefinition` at all, so it is not on this interface and the mapper
// draws nothing for it. A `purpose?: string` here would be a promise this wire
// cannot keep.
import { readListPage } from "@/api/paginated";
import { api } from "@/api/client";
import type { ApiClient, ApiResponse } from "@/api/client";
import type { PagedRows } from "@/api/paginated";
import type { RunRow } from "./home/homeEndpoints";

/** One step of the stored definition document (`contract.py`
 *  `as_definition_document`). ⚠ **No `why`** — `DEF-RBS-4285`: the frames draw a
 *  second line under all six steps and `Step` has no field for it. */
export interface WireStep {
  key: string;
  label: string;
  mode: string;
  writes: boolean;
}

/** One guard. `BR-RBS-012`: absolute, so there is no `enabled` to send. */
export interface WireGuard {
  key: string;
  label: string;
}

/** One declared input (`BR-RBS-042` — a tenant sets input VALUES and nothing
 *  else). `label` is the runbook's OWN word and arrives already translated by
 *  the definition, which is why the Scope tab carries DATA labels. */
export interface WireParameter {
  name: string;
  type: string;
  label: string;
  required: boolean;
  default: unknown;
  choices: unknown[];
  setting_key: string | null;
  /** ⚠ **OPTIONAL BECAUSE THIS IS A PINNED SNAPSHOT** (`BR-RBS-038`). Wave `T`
   *  added `domain` and `multi` to the shipped definition document, so a
   *  version written before it simply has neither — and a copy keeps its pinned
   *  version until somebody presses *Review →*. What the SETUP SCREEN reads is
   *  `RunbookDetailBody.parameters`, which is the live declaration; these two
   *  are here so the Steps/history side does not have to pretend they are
   *  absent. */
  domain?: string | null;
  multi?: boolean;
}

/** One INPUT a tenant may set, and what this tenant set it to (`BR-RBS-042`).
 *
 * ⚠ **THIS IS NOT `WireDefinition.parameters` AND THE DIFFERENCE IS THE WHOLE
 * OF `DEF-RBS-4338`.** That list is what the version this copy PINS declares —
 * history, and a past run drew its scope from it. This list is the LIVE
 * declaration plus **what this tenant chose**, which is what the next run will
 * use and what **Change scope** writes. Until wave `T` there was only the first
 * one, so the Scope tab drew each parameter's DECLARED DEFAULT and called it
 * the runbook's scope: accidentally right, because no tenant had set anything,
 * and wrong the first time one did, with no test failing.
 *
 * ⚠ **`value` IS THE STORED FORM, SO *all* ARRIVES AS THE WORD** (clause 1). It
 * is expanded when a run STARTS, against the tenant's domain of that moment —
 * so a utility that set *all services* with Water and Sewer gets **three** the
 * month after Trash is added. A screen that expanded it would draw a frozen
 * list, and saving that back is exactly the freeze the rule forbids.
 *
 * ⚠ **NO DOMAIN MEMBERS TRAVEL HERE.** The rows a picker draws come from
 * `GET /runbooks/{key}/domains/{parameter}`, which pages — `account` is 40,000
 * at the top of T5 and `NFR-3` binds every list. */
export interface WireParameterSetting {
  name: string;
  label: string;
  type: string;
  required: boolean;
  /** The tenant-resolved list this input draws from, or `null` when it has
   *  none (a money box, a toggle) or carries the runbook's own `choices`. */
  domain: string | null;
  /** One value, or several — and *all* is only ever legal on a `multi` one. */
  multi: boolean;
  /** The runbook's OWN fixed vocabulary. Never both this and `domain`. */
  choices: string[];
  setting_key: string | null;
  /** What this runbook runs with: the tenant's answer, or the declared default. */
  value: unknown;
  /** Did the TENANT choose this, or is it what the runbook shipped with? */
  is_set: boolean;
  /** `{stored value: the word for it}` for the values THIS input holds — B14
   *  rule 31. A saved `ref:object` value is an account id and a row that drew it
   *  would put a uuid in front of a clerk. Only the CHOSEN values are resolved:
   *  the picked account may be on page 700 of the domain. */
  value_labels: Record<string, string>;
}

/** One row of a domain — *what a person may pick*, never an id on screen.
 *
 *  `value` is what gets STORED (a service code, an account id); `label` is what
 *  a chip shows. B14 rule 31 is about what a field renders, so the pair is the
 *  shape that satisfies it rather than a violation of it. */
export interface WireDomainRow {
  value: string;
  label: string;
}

/** The stored version document, less the tenant's settings half. */
export interface WireDefinition {
  key: string;
  name: string;
  kind: string;
  category: string;
  subject_type: string;
  unit_of_work: string;
  triggers: string[];
  tags: string[];
  parameters: WireParameter[];
  steps: WireStep[];
  guards: WireGuard[];
  requires: unknown;
  ports: string[];
}

/** One row of the Activity tab, as `selectors.runbook_activity` builds it.
 *
 *  ⚠ **`id` IS THE VERSION NUMBER AND NOT A UUID, DELIBERATELY.** The selector
 *  says so in its own docstring: *"there is no database id on this payload to
 *  render by accident"* — B14 rule 31 held by the shape of the data rather than
 *  by a rule somebody polices.
 *
 *  ⚠ **`changes` ARE FACTS AND NOT A SENTENCE.** *Cap raised to 400* is chrome
 *  in eleven languages; `{field: "cap", from: 100, to: 400}` is the fact. The
 *  composition is `setupModel.ts`'s and it is the whole of task `E4`. */
export interface WireActivity {
  id: number;
  version: number;
  changes: { field: string; from?: unknown; to?: unknown }[];
  actor: { name: string } | null;
  when: string | null;
}

/** The offer `BR-RBS-038` makes and never applies — counts, never English. */
export interface WireTemplateUpdate {
  available: boolean;
  steps_added: number;
  steps_removed: number;
  other_changed: boolean;
}

/** The last run's summary. The Runs TAB is a different read (row 8). */
export interface WireLastRun {
  id: string;
  status: string;
  mode: string;
  trigger: string;
  started_at: string | null;
  finished_at: string | null;
  took_seconds: number | null;
  counts: Record<string, number>;
}

/** `GET /runbooks/{key}` and the body `PUT /runbooks/{key}` answers with. */
export interface RunbookDetailBody {
  key: string;
  name: string;
  kind: "check" | "action";
  category: string;
  tags: string[];
  origin: string;
  template_key: string | null;
  subject_type: string;
  unit_of_work: string;
  enabled: boolean;
  current_version: number;
  schedule: {
    trigger_kind: string;
    cron: string | null;
    event_kind: string | null;
    timezone: string | null;
    /** ⚠ **ALWAYS `null` AND NOT A PLACEHOLDER.** Nothing in this product
     *  schedules a runbook yet and the table carries no `next_run_at` column.
     *  `RB-022` runs both ways: a **Run ▶** a screen offers must actually run,
     *  and a schedule a screen displays must actually fire. */
    next_run: string | null;
  };
  cap: number | null;
  gate_mode: string;
  visible_to_roles: string[] | null;
  roles: string[];
  trusted_version: number | null;
  dry_run_only: boolean;
  template_update: WireTemplateUpdate | null;
  activity: WireActivity[];
  definition: WireDefinition | null;
  guards: WireGuard[];
  ports: string[];
  writes_nothing: boolean | null;
  requires: unknown;
  last_run: WireLastRun | null;
  open_items: number;
  /** `BR-RBS-042` — the inputs and what this tenant set them to. Empty when
   *  the registry holds no module under this runbook's key. */
  parameters: WireParameterSetting[];
}

/** What `PUT /runbooks/{key}` accepts. `services.EDITABLE_SETTINGS` is the
 *  server's own list and every other field is refused BY NAME — a `PUT` that
 *  silently dropped `kind` would leave the caller believing a Check had become
 *  an Action. `accept_template_update` is the same route rather than a
 *  nineteenth address (`api.py::runbook_detail`). */
export interface RunbookEditBody {
  enabled?: boolean;
  trigger_kind?: string;
  cron?: string | null;
  event_kind?: string | null;
  timezone?: string | null;
  cap?: number | null;
  gate_mode?: string;
  visible_to_roles?: string[] | null;
  accept_template_update?: boolean;
  /** ⚠ **THE INPUT VALUES — `BR-RBS-042`, WAVE `T`, AND THIS FIELD IS WHAT
   *  RELEASED **Change scope**.** `services.EDITABLE_SETTINGS` held eight
   *  schedule-and-limit fields and no parameter value, so the button was a
   *  control over a route that could not save what it collected
   *  (`DEF-RBS-4338`).
   *
   *  ⚠ **THE WHOLE DOCUMENT, NEVER A DELTA**, exactly as `visible_to_roles` is
   *  the whole answer: a delta has no way to say *put this input back to what
   *  it shipped with*. A name the caller omits is an input this tenant has not
   *  set, and it runs on the declared default.
   *
   *  ⚠ ***all* IS SENT AS THE WORD.** Sending the expanded list is a freeze,
   *  and the day the utility adds a service it is silently outside every
   *  runbook set to *all* with nothing on any screen to see. */
  parameters?: Record<string, unknown>;
}

/** A 2xx with no body where the contract promises one is a server bug (B12 r1). */
function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

/**
 * `GET /runbooks/{key}` — one runbook's facts, exactly as the server sends them.
 *
 * ⚠ **NO `runs_page` / `runs_per` IN THE QUERY ANY MORE.** The C3 client sent
 * both and the endpoint has never read either: `RBS-004.6`'s Runs tab is
 * `GET /runbooks/runs?f.runbook={key}`, which is already a paged list with a
 * runbook filter, already ordered on a total key and already tested against 51
 * rows. Two paging surfaces over one list is `G114`'s whole subject — three
 * shipped Work screens drew empty tables over exactly that.
 */
export async function getRunbookDetail(
  key: string,
  client: ApiClient = api,
): Promise<RunbookDetailBody> {
  return requireData(
    await client.get<RunbookDetailBody>(`/runbooks/${encodeURIComponent(key)}`),
  );
}

/**
 * `PUT /runbooks/{key}` — the edit that writes a version (`BR-RBS-038`).
 *
 * The whole detail payload comes back rather than a bare ok, because `RBS-004`
 * redraws seven tabs from one object and a 200 with no body would make the
 * screen refetch what it had just been told.
 */
export async function editRunbook(
  key: string,
  body: RunbookEditBody,
  client: ApiClient = api,
): Promise<RunbookDetailBody> {
  return requireData(
    await client.put<RunbookDetailBody>(`/runbooks/${encodeURIComponent(key)}`, body),
  );
}

/**
 * `GET /runbooks/{key}/domains/{parameter}` — what THIS tenant may choose.
 *
 * `BR-RBS-042` clause 2, PO verbatim 2026-09-06: *"every utility will not have
 * all utility services or all combinations of Plans and rates, so we ahve to
 * work in variables"*. A two-service utility's *Services* list offers two.
 *
 * ⚠ **THE SERVER PAGES AND THIS FUNCTION SLICES NOTHING.** `service` would fit
 * in one response for ever; `account` is **40,000 at the top of T5** with no
 * ceiling above it (`NFR-5`), and CLAUDE.md names four shipped lists that are
 * unpaginated *"on purpose"* because a utility under 3,000 connections could
 * carry it — correct at T7 and 13× short of T5. A picker that read the whole of
 * this domain would be the fifth.
 *
 * ⚠ **AN EMPTY DOMAIN IS A 200 WITH ZERO ROWS.** *You have not set any services
 * up yet* is a true answer; an empty dropdown reads as broken.
 */
export function listParameterDomain(
  key: string,
  parameter: string,
  query: { q?: string; page: number; per: number },
  client: ApiClient = api,
): Promise<PagedRows<WireDomainRow>> {
  return readListPage<WireDomainRow>(
    `/runbooks/${encodeURIComponent(key)}/domains/${encodeURIComponent(parameter)}`,
    { q: query.q ?? "", page: query.page, per: query.per },
    client,
  );
}

/** `POST /runbooks/{key}/clone` — `RB-040`, and `RBS-003.1`'s row action. */
export async function cloneRunbook(
  key: string,
  name: string,
  client: ApiClient = api,
): Promise<RunbookDetailBody> {
  return requireData(
    await client.post<RunbookDetailBody>(`/runbooks/${encodeURIComponent(key)}/clone`, { name }),
  );
}

/** What `POST /runbooks/{key}/runs` answers: the queued job (`202`). */
export interface RunAccepted {
  job_id: string;
  status_url: string;
}

/**
 * `POST /runbooks/{key}/runs` — **Run ▶**, a run started by a person
 * (`CR-173-BRC10`, `07-endpoints.md` row 4). `mode` is `dry` (build and
 * report, change nothing) or `live`; the server refuses `live` by name on a
 * runbook that is not turned on. `parameters` are this run's one-off inputs,
 * checked against the runbook's own declaration exactly as a saved one is.
 */
export async function startRun(
  key: string,
  body: { mode: "dry" | "live"; parameters?: Record<string, unknown> },
  client: ApiClient = api,
): Promise<RunAccepted> {
  return requireData(
    await client.post<RunAccepted>(`/runbooks/${encodeURIComponent(key)}/runs`, body),
  );
}

/**
 * `RBS-004.6` — this runbook's page of the run history.
 *
 * ⚠ **THE SERVER PAGES AND THIS FUNCTION SLICES NOTHING.** `NFR-3` is universal
 * server pagination and CLAUDE.md's opening paragraph makes it the deliverable
 * rather than the background. `f.runbook` is `BR-SHL-011`'s filter grammar and
 * `runs_page` orders on `(-started_at, -created_at, -id)` in SQL.
 */
export function listRunsForRunbook(
  key: string,
  query: { page: number; per: number },
  client: ApiClient = api,
): Promise<PagedRows<RunRow>> {
  return readListPage<RunRow>(
    "/runbooks/runs",
    { "f.runbook": key, page: query.page, per: query.per },
    client,
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-RBS-040 (EP-RBS-01; CR-075 wave E task E4) · 07-endpoints.md rows 2, 3, 6, 8 · NFR-3
// generated: 2026-09-06 by the CR-075 wave E · E4/E5/E6 build lane
// checklist: A✔ B=n/a C✔ D✔ E=n/a(no screen in this file) F✔ G✔ H=n/a
// gates: tsc --noEmit (the LOCAL compiler, never npx) · vitest setupModel.test.ts
// exceptions: `purpose` is deliberately absent from the wire (DEF-RBS-4309) —
//         the screen draws nothing rather than a placeholder
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
