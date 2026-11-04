// ── Trace ──────────────────────────────────────────────
// Component: FI-01 typed API client (B13 §2) — the ONE HTTP path out of this app
// Story:    US-IDN-001 · US-TEN-001 · US-TEN-003 (its first consumers) ·
//           US-TEN-005 (multipart body — the S8 logo upload) ·
//           US-AUD-004 (contract-bearing response headers — the audit window)
//           Screens: S1, S3, S8, S61, S62, S110–S114
// Rules:    BR-TEN-003 (tenant comes from the REQUEST, never client input — PO 2026-08-10 moves the
//           source from the Host's first label to the URL's first path segment) ·
//           BR-SHL-019 (one transactional commit call) · BR-SHL-020 (plain-language failure) ·
//           BR-TEN-019 (the logo rides as multipart, not JSON) · BR-AUD-013 (which audit
//           window answered a query is a HEADER, so the transport must surface it)
// ───────────────────────────────────────────────────────
// FI-01 (B13 §2): every request this app makes goes through this file. The
// contract it implements is ratified, not invented:
//   · error envelope `{code, message_key, params, field_errors[], br_ref,
//     trace_id}` — B12 §3 / 11b §3 G1 — surfaced as a typed ApiError;
//   · full HTTP series (B12 r1 §3-expanded): 200/201/202/204 · 304 + ETag ·
//     4xx envelope · 429 + Retry-After · 5xx;
//   · 202 + job_id → poll `GET /jobs/{id}` (11b §2.17 / G3);
//   · retry with backoff on 429/502/503/504 for IDEMPOTENT GETs only — never
//     a mutation, because a retried POST is a second write (CLAUDE.md #6);
//   · `credentials: "include"` so the httpOnly session cookie rides along.
// BR-TEN-003 / 11b G4: the tenant is resolved SERVER-SIDE from the request —
// since the PO's 2026-08-10 path-tenancy ruling, from the URL's first path
// segment rather than the Host's first label. This client therefore still sends
// NO tenant id in a body or header, ever: it puts the tenant where the contract
// puts it, in the URL (`/api/{tenant}/…`), read from the route the browser is
// actually on (see §API URL shape below and src/routing/tenantPath.ts).
//
// Types are hand-written against `schema.json` (the drf-spectacular export) and
// the payload builders behind those routes — see README.md. Only the endpoints
// the shipped screens use are typed (endpoints.ts); the rest arrive with their
// screens.

import { noteFailedRequest } from "@/api/failedRequests";
import { currentScreenId, track } from "@/analytics/client";
import { tenantFromPathname } from "@/routing/tenantPath";
import { SESSION_EXPIRED_STATUS, announceSessionExpired } from "@/api/sessionExpiry";

// ── Error envelope (B12 §3 / 11b §3 G1) ────────────────────────────────────

export interface ApiFieldError {
  // The backend renders `field: null` for non-field (whole-payload) errors —
  // forms drop those into the form-level message instead of under an input.
  field: string | null;
  code: string | null;
  message_key: string;
  params?: Record<string, unknown>;
}

export interface ApiErrorEnvelope {
  code: string | null; // B12 §3 catalog code; null for 400/404/405/415/429
  message_key: string; // TD-16: the server sends KEYS, the UI renders language
  params?: Record<string, unknown>;
  field_errors?: ApiFieldError[];
  br_ref?: string | null;
  trace_id?: string | null;
}

// Copy keys owned by this client for the two cases the server cannot answer
// (the connection failed, or something answered that is not the envelope).
export const NETWORK_ERROR_KEY = "api.error.network";
export const UNEXPECTED_ERROR_KEY = "api.error.unexpected";
/**
 * `DEF-SHL-10619` — the API firewall (AWS WAF) refused the request: *"This
 * request was blocked for security. Contact support."* The WAF's custom
 * response is a 403 whose JSON names `code: "WAF-BLOCK"` and this key
 * (`09-infra/06-vapt-remediation-2026-10.md` step 1-A, which also adds the
 * CORS header that lets the browser read it at all). Without that header the
 * browser hides the block and `NETWORK_ERROR_KEY` is all anyone can say.
 */
export const BLOCKED_KEY = "api.error.blocked";
export const WAF_BLOCK_CODE = "WAF-BLOCK";
/** `DEF-SHL-10621` — every 429, ours or the WAF's: *"Too many requests. Wait a moment."* */
export const RATE_LIMITED_KEY = "api.error.rate_limited";

// Status 0 marks "no HTTP answer at all" (DNS/offline/CORS) — distinct from
// every row of the B12 r1 table, all of which carry a real status.
export const NO_RESPONSE_STATUS = 0;

/** The ONE error type every screen catches. Never a raw Response, never text. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string | null;
  readonly messageKey: string;
  readonly params: Record<string, unknown>;
  readonly fieldErrors: readonly ApiFieldError[];
  readonly brRef: string | null;
  readonly traceId: string | null;
  readonly retryAfterSeconds: number | null; // 429/503 Retry-After, when sent
  /**
   * ⛔ **`DEF-965` — THE REFERENCE THIS CLIENT *SENT*, WHICH IS THE ONLY ONE
   * THAT SURVIVES A REQUEST THE SERVER NEVER ANSWERS.**
   *
   * `traceId` above is minted by `core.errors.drf_exception_handler`, so it
   * exists only when Django got as far as forming a response. The production
   * failure this exists for did not: `DEF-1075` was a **gunicorn worker
   * timeout** — the worker was killed at sixty seconds, mid-transaction, and
   * the browser got a gateway page with no envelope in it. The refusal strip
   * read *"Something went wrong. Nothing was saved — try again."* and the
   * operator had nothing to quote, so two reports of the same failure
   * (`DEF-965`, `DEF-1080`) could not be diagnosed from the repo at all.
   *
   * ⚠ **SO IT IS MINTED BEFORE THE REQUEST LEAVES AND TRAVELS AS
   * `X-Support-Ref`.** The server writes it into its own log the moment the
   * request arrives — before any work, which is the point: a worker killed
   * later still leaves that line. Same alphabet and same grouping as
   * `supportRef`, because the human act is identical (reading it aloud), and
   * one shape is what stops the product having two.
   *
   * It is a LABEL, never an authority: nothing reads it back, nothing is keyed
   * on it, and a server that answers properly still wins — `diagnosticOf`
   * prints the server's `traceId` whenever there is one.
   */
  readonly sentRef: string | null;

  constructor(
    status: number,
    envelope: ApiErrorEnvelope,
    retryAfterSeconds: number | null = null,
    sentRef: string | null = null,
  ) {
    // The Error message is for logs/stack traces only — user-facing text is
    // always rendered from messageKey through the i18n catalog (TD-16/B8).
    super(`${envelope.code ?? "HTTP"} ${status} (${envelope.message_key})`);
    this.name = "ApiError";
    this.status = status;
    this.code = envelope.code;
    this.messageKey = envelope.message_key;
    this.params = envelope.params ?? {};
    this.fieldErrors = envelope.field_errors ?? [];
    this.brRef = envelope.br_ref ?? null;
    this.traceId = envelope.trace_id ?? null;
    this.retryAfterSeconds = retryAfterSeconds;
    this.sentRef = sentRef;
  }
}

// ── The support reference (PO ruling 2026-08-19 · DEF-328) ─────────────────
// `trace_id` has been generated per refusal, written to the BR-AUD-018 attempt
// row and returned in every envelope since B12 §3 — and rendered to a person
// only as a raw 32-hex string on a failed-load diagnostic. The PO's ruling is
// that a system error hands the user "some identifier that they can report to
// support", and that it must be readable aloud.
//
// ⚠ THE SHORT FORM IS THE SEARCHABLE FORM, and that is the whole constraint.
// `apps/audit/selectors.audit_queryset` matches `f.entity_id` by PREFIX with
// dashes and case ignored, so `5F2B-9C1D` finds the attempt row carrying the
// full trace id. A shortened id support cannot look up would be worse than
// none: the user reads it out and the call stalls.

/** How many hex characters of the trace id a person is asked to read aloud. */
export const SUPPORT_REF_HEX = 8;

/** What `{{ref}}` renders as when a refusal arrived with no trace id at all. */
export const SUPPORT_REF_ABSENT = "—";

/** `5f2b9c1d3e…` → `5F2B-9C1D`. Uppercase and grouped, because it is dictated. */
export function supportRef(traceId: string | null | undefined): string {
  const hex = (traceId ?? "").replace(/[^0-9a-fA-F]/g, "").slice(0, SUPPORT_REF_HEX);
  if (hex.length < SUPPORT_REF_HEX) {
    return SUPPORT_REF_ABSENT;
  }
  return `${hex.slice(0, 4)}-${hex.slice(4)}`.toUpperCase();
}

/** The header a request carries its own reference in (`DEF-965`). */
export const SUPPORT_REF_HEADER = "X-Support-Ref";

/**
 * ⚠ **`DEF-IDN-10024` — A REQUEST NOBODY ASKED FOR DOES NOT KEEP A SESSION
 * AWAKE.** HUMAN-REVIEW-PENDING (🔒 identity/sessions, PO ruling 2026-10-08:
 * *"automatic refreshes stop counting as activity, only a real request from the
 * person slides the idle clock"*).
 *
 * Until 2026-10-08 every request slid the server's idle clock, so a page that
 * polls — the bill run every 30 s, an import every 2 s, `pollJob`, the field
 * app's queue sync — was never signed out however long it sat unattended.
 *
 * **ONE MECHANISM, DECIDED HERE AND NOWHERE ELSE (decision log 2026-10-08):** a
 * request leaves with `X-Background-Refresh: 1` when nobody has pressed, typed,
 * scrolled or touched this page for `BACKGROUND_AFTER_MS`. Not a tag on each
 * polling query: a tag is what the next poll forgets (hard-won law 2), and two
 * of today's polls are plain `setInterval`s that never pass through TanStack.
 * The server still authenticates such a request fully and still refuses it 401
 * once the person has been idle past the utility's limit; it just does not
 * slide the clock (`identity/auth.py`, `BACKGROUND_REFRESH_HEADER`).
 */
export const BACKGROUND_REFRESH_HEADER = "X-Background-Refresh";

/**
 * How recent a person's input must be for a request to count as theirs. A
 * minute covers a click and the chain of reads it starts, and is a quarter of
 * the shortest idle limit a utility can choose (15 minutes), so it can never
 * hold a session open on its own.
 */
export const BACKGROUND_AFTER_MS = 60_000;

/** The browser events that mean a person is here. Passive, capture phase. */
const ACTIVITY_EVENTS = ["pointerdown", "keydown", "wheel", "touchstart"] as const;

// A page load is a person's act (they opened or reloaded it), so the clock
// starts now rather than at zero — otherwise the first reads after a reload
// would all be called background.
let lastActivityAt = Date.now();

if (typeof window !== "undefined") {
  const mark = () => {
    lastActivityAt = Date.now();
  };
  for (const name of ACTIVITY_EVENTS) {
    window.addEventListener(name, mark, { capture: true, passive: true });
  }
}

/** Test seam and the one reader of the clock above. */
export function markUserActivity(at: number = Date.now()): void {
  lastActivityAt = at;
}

/** True when a request now would be one nobody asked for. */
export function isBackgroundMoment(now: number = Date.now()): boolean {
  return now - lastActivityAt > BACKGROUND_AFTER_MS;
}

/**
 * ⛔ **A REFERENCE FOR A REQUEST, MINTED BEFORE IT LEAVES (`DEF-965`).**
 *
 * `supportRef` above shortens a trace id the SERVER minted, which exists only
 * once Django has formed a response. The failure this is for produced no
 * response at all: `DEF-1075` was a gunicorn worker killed at sixty seconds,
 * so the import's refusal strip had one generic sentence and nothing to quote,
 * twice (`DEF-965`, `DEF-1080`).
 *
 * Same eight characters, same grouping, same uppercase — a person reads this
 * aloud exactly as they read the other, and one shape is what stops the
 * product having two. `crypto.getRandomValues` where it exists; `Math.random`
 * is a legitimate fallback because this is a LABEL and not a secret — nothing
 * authorises on it, nothing is keyed on it, and a collision costs one extra
 * log line to read past.
 */
export function newRequestRef(): string {
  const bytes = new Uint8Array(SUPPORT_REF_HEX / 2);
  const web = globalThis.crypto;
  if (web !== undefined && typeof web.getRandomValues === "function") {
    web.getRandomValues(bytes);
  } else {
    for (let index = 0; index < bytes.length; index += 1) {
      bytes[index] = Math.floor(Math.random() * 256);
    }
  }
  const hex = [...bytes].map((byte) => byte.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 4)}-${hex.slice(4)}`.toUpperCase();
}

/**
 * The params i18next is allowed to see: everything the server sent EXCEPT
 * `detail`, plus the `ref` the system-error copy quotes (BR-SHL-020 r2,
 * DEF-322). `detail` is not deleted — it still reaches the audit row and the
 * server log, where support reads it. It stops being RENDERED.
 *
 * `ref` is added for every refusal rather than only the system-error ones,
 * because which refusals are system errors is a property of the CATALOGUE
 * VALUE — only those twelve sentences mention `{{ref}}` — not of the transport.
 * A param nothing interpolates is invisible, so the PO's "no id on a
 * correctable mistake" is enforced where the copy is written.
 */
export function refusalParams(
  params: Record<string, unknown> | undefined,
  traceId: string | null | undefined,
): Record<string, unknown> {
  const rest = { ...(params ?? {}) };
  delete rest.detail; // BR-SHL-020 r2 — never rendered, still in the audit row
  return { ...rest, ref: supportRef(traceId) };
}

/** True when `value` came out of this client (screens narrow with it). */
export function isApiError(value: unknown): value is ApiError {
  return value instanceof ApiError;
}

/**
 * True when the failure is the SESSION ending — 401, `AUTH-001` — which no
 * screen owns (`DEF-SHL-6378`). A screen never branches on this: the shell
 * answers it for every screen at once (`components/SessionExpired.tsx`).
 */
export function isSessionExpired(error: unknown): boolean {
  return isApiError(error) && error.status === SESSION_EXPIRED_STATUS;
}

// A body that is not the ratified envelope is a contract violation upstream
// ("a response outside this table = a bug by definition") — the client still
// has to answer the screen with something typed and translatable.
export function asEnvelope(body: unknown): ApiErrorEnvelope {
  if (typeof body !== "object" || body === null) {
    return { code: null, message_key: UNEXPECTED_ERROR_KEY };
  }
  const record = body as Record<string, unknown>;
  if (typeof record.message_key !== "string") {
    return { code: null, message_key: UNEXPECTED_ERROR_KEY };
  }
  return {
    code: typeof record.code === "string" ? record.code : null,
    message_key: record.message_key,
    params: (record.params as Record<string, unknown> | undefined) ?? {},
    field_errors: Array.isArray(record.field_errors)
      ? (record.field_errors as ApiFieldError[])
      : [],
    br_ref: typeof record.br_ref === "string" ? record.br_ref : null,
    trace_id: typeof record.trace_id === "string" ? record.trace_id : null,
  };
}

/**
 * The subset of the envelope a FormModal consumes (US-SHL-009): field errors
 * keyed by a real field name. Non-field errors (`field: null`) stay out of the
 * field map — they belong to the form-level message.
 */
export function formErrorEnvelope(error: ApiError): {
  code: string;
  message_key: string;
  params: Record<string, unknown>;
  field_errors: { field: string; message_key: string; params?: Record<string, unknown> }[];
  br_ref?: string;
  trace_id?: string;
} {
  const fields = [];
  for (const fieldError of error.fieldErrors) {
    if (fieldError.field !== null) {
      fields.push({
        field: fieldError.field,
        message_key: fieldError.message_key,
        params: fieldError.params,
      });
    }
  }
  return {
    code: error.code ?? "",
    message_key: error.messageKey,
    params: error.params,
    field_errors: fields,
    br_ref: error.brRef ?? undefined,
    trace_id: error.traceId ?? undefined,
  };
}

/**
 * `DEF-SHL-10619` / `DEF-SHL-10621` — the two answers that may come from IN
 * FRONT of the server rather than from it, read by what they are and not by
 * whether they carry our envelope. A firewall block (403 + `WAF-BLOCK` or
 * `api.error.blocked`) and any 429 each get their own sentence; everything
 * else is exactly `asEnvelope` — an ordinary 403 is never rewritten.
 */
export function failureEnvelope(status: number, body: unknown): ApiErrorEnvelope {
  const envelope = asEnvelope(body);
  const record = typeof body === "object" && body !== null ? (body as Record<string, unknown>) : {};
  if (status === 403 && (record.code === WAF_BLOCK_CODE || record.message_key === BLOCKED_KEY)) {
    return { ...envelope, code: WAF_BLOCK_CODE, message_key: BLOCKED_KEY };
  }
  if (status === 429) {
    return { ...envelope, message_key: RATE_LIMITED_KEY };
  }
  return envelope;
}

// ── Retry policy (pure, so its laws are provable without a network) ─────────

export type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

// B12 r1: "retry w/ backoff on 429/502/503/504 idempotent GETs".
export const RETRYABLE_STATUSES: readonly number[] = [429, 502, 503, 504];
export const MAX_ATTEMPTS = 3; // the first try + 2 retries
/**
 * `DEF-SHL-10621` (PO 2026-10-27): a 429 is retried ONCE, after `Retry-After`.
 * The server has just said *slow down*; a second retry is the client adding
 * to the very burst the limit exists to stop.
 */
export const MAX_RATE_LIMITED_ATTEMPTS = 2;
export const RETRY_BASE_MS = 500;
export const RETRY_CAP_MS = 8000;

/**
 * GETs only. A mutation is NEVER retried here: re-POSTing a bill run or a
 * provisioning commit is a second write, and idempotency is the SERVER's
 * guarantee to give (CLAUDE.md #6), not something a client may assume.
 */
export function isRetryable(method: HttpMethod, status: number): boolean {
  return method === "GET" && RETRYABLE_STATUSES.includes(status);
}

/** Retry-After (seconds form) wins over the backoff curve when the server sends it. */
export function retryDelayMs(attempt: number, retryAfterSeconds: number | null): number {
  if (retryAfterSeconds !== null && retryAfterSeconds >= 0) {
    return Math.min(RETRY_CAP_MS, retryAfterSeconds * 1000);
  }
  return Math.min(RETRY_CAP_MS, RETRY_BASE_MS * 2 ** (attempt - 1));
}

/** `Retry-After: 30` → 30. The HTTP-date form is ignored (null) rather than guessed. */
export function parseRetryAfter(header: string | null): number | null {
  if (header === null) {
    return null;
  }
  const seconds = Number(header.trim());
  return Number.isFinite(seconds) && seconds >= 0 ? seconds : null;
}

// ── API URL shape (PO 2026-08-10 path tenancy) ─────────────────────────────
// Endpoint wrappers name the CONTRACT path (`/settings/company`, `/tenants`,
// `/public/pricing-plans`). This section — and nothing else in the app — turns
// that into the URL that goes on the wire:
//
//   tenant-scoped  →  /api/{tenant}/settings/company
//   un-tenanted    →  /api/public/pricing-plans · /api/tenants · /api/jobs/{id}
//                     /api/exports · /api/exports/{job_id}/file
//
// Doing it here (one function, one list) is what keeps the FE and the BE from
// drifting per endpoint, and it is why endpoints.ts needed no path edits when
// tenancy moved: a wrapper states WHAT it calls, the transport states WHERE.

export const API_PREFIX = "/api";

/**
 * The contract paths that carry NO tenant segment. `POST /tenants` provisions a
 * tenant (there is none yet); `/public/…` is the pre-signup catalog; `/jobs` and
 * `/exports` are PLATFORM services the ruling keeps outside the tenant path.
 * Everything else is tenant-scoped — including `/tenants/checklist`, which is a
 * READ of the caller's own tenant and therefore lands at
 * `/api/{tenant}/tenants/checklist`.
 */
export function isUntenantedPath(path: string): boolean {
  return (
    path === "/tenants" ||
    path.startsWith("/public/") ||
    path === "/jobs" ||
    path.startsWith("/jobs/") ||
    path === "/exports" ||
    path.startsWith("/exports/")
  );
}

/** The tenant of the URL the browser is on ("" server-side/in tests). */
export function currentTenant(): string {
  return typeof window === "undefined" ? "" : tenantFromPathname(window.location.pathname);
}

/**
 * Contract path → wire URL. A tenant-scoped call with no tenant in scope is a
 * BUG (a screen outside `/{tenant}/…` reaching for tenant data), and it throws
 * rather than quietly posting to an un-tenanted URL the server would answer for
 * somebody: a wrong-tenant request is exactly what this ruling makes possible
 * and exactly what must never be sent.
 */
export function apiPath(tenant: string, path: string): string {
  if (isUntenantedPath(path)) {
    return `${API_PREFIX}${path}`;
  }
  if (tenant === "") {
    throw new ApiError(NO_RESPONSE_STATUS, {
      code: null,
      message_key: UNEXPECTED_ERROR_KEY,
      params: { path },
    });
  }
  return `${API_PREFIX}/${tenant}${path}`;
}

// ── Requests ───────────────────────────────────────────────────────────────

export type QueryValue = string | number | boolean | undefined;

export interface RequestOptions {
  method?: HttpMethod;
  // JSON-serialized; omit for GET/DELETE. A `FormData` body is passed to fetch
  // UNTOUCHED and its Content-Type is left unset, because only the browser can
  // write the multipart boundary (the S8 logo upload is the first such row).
  body?: unknown;
  query?: Record<string, QueryValue>;
  ifNoneMatch?: string; // ETag pass-through on cacheable GETs (11b G6)
  signal?: AbortSignal;
  /**
   * The media type this call asks for and reads back. Defaults to
   * `application/json`; anything else is read as TEXT and handed over verbatim.
   *
   * ⚠ ADDED 2026-08-15 (DEF-121). Two endpoints in this product serve a real
   * file — `GET /reads/template` and `GET /accounts/imports/template`, the two
   * PUBLISHED CSV templates (BR-MET-032 / BR-CUS-046) — and until today every
   * response body went through `JSON.parse`, which returns null on a CSV. So
   * `requireData` threw *"empty 200 body where the contract promises one"* and
   * the Download-template button on S68 failed on a healthy 200. The template is
   * the file an operator fills in; without it the import wizard behind it is a
   * drop zone with no format. Reading a CSV as text is not a special case — it
   * is what the endpoint's own `Content-Type: text/csv` has always said.
   */
  accept?: string;
}

export const JSON_MEDIA_TYPE = "application/json";

export interface ApiResponse<T> {
  status: number;
  data: T | null; // null on 204 (no content) and 304 (not modified)
  etag: string | null;
  notModified: boolean; // 304 — the caller keeps the copy it already had
  // The raw response headers, for the few contract rows that carry meaning
  // OUTSIDE the body (`X-Audit-Window` / `X-Audit-Window-From`, BR-AUD-013).
  // Optional so a hand-built response in a test stays valid — read it through
  // `responseHeader`, never by indexing.
  headers?: Headers;
}

/** The ONE reader for a contract-bearing response header. Absent = null. */
export function responseHeader(response: ApiResponse<unknown>, name: string): string | null {
  return response.headers?.get(name) ?? null;
}

/** True when the body must ride as multipart (the browser owns the boundary). */
function isMultipart(body: unknown): body is FormData {
  return typeof FormData !== "undefined" && body instanceof FormData;
}

export interface ApiClientOptions {
  // Defaults to the API origin this bundle was BUILT for (`DEFAULT_BASE_URL`
  // below). The tenant still travels in the path the client builds
  // (BR-TEN-003); only the ORIGIN moved.
  baseUrl?: string;
  // The tenant every tenant-scoped call is made under. Default: whatever the
  // browser's own URL says (`/{tenant}/…`), re-read per request so a client-side
  // navigation is picked up without rebuilding the client. Tests name it.
  tenant?: string | (() => string);
  fetchImpl?: typeof fetch; // test seam (same posture as the Toast queue prop)
  sleep?: (ms: number) => Promise<void>; // test seam for the backoff
  maxAttempts?: number;
}

/**
 * THE ORIGIN EVERY API CALL GOES TO — a fact of the BUILD, not of the page.
 *
 * ⚠ **CHANGED 2026-09-28 (CR-144-BRC07, PO ruling). IT WAS `""` — SAME-ORIGIN —
 * AND THAT STOPPED BEING TRUE.** The product is now static files on S3 behind a
 * CDN with no Node server, so there is nothing on the frontend origin to answer
 * `/api`. The PO's reason for two hosts rather than CDN path-routing, verbatim:
 * *"I dont want to get locked in with the cdn from an cloud provider later if I
 * move out from this cloud I dont want this to be a blocker."*
 *
 * `API_PREFIX` is UNCHANGED and still `/api`: only the origin in front of it
 * moved, so every contract path in `endpoints.ts` is untouched.
 *
 * An empty value means same-origin and is still the right answer for
 * `npm run dev` and for the local docker-compose stack, where `server.mjs`
 * proxies `/api`. `vite.config.ts` REFUSES an empty value for the three
 * deployed modes — a bundle that falls back to a relative URL calls its own
 * static host and every screen fails at once, with nothing red in CI
 * (hard-won law 3).
 *
 * ⚠ **THE SESSION COOKIE IS NOW CROSS-SITE**, which is a fact about the API's
 * `Set-Cookie` and its CORS answer, not about this line: the cookie needs
 * `SameSite=None; Secure` and the API must allow this origin with credentials.
 * That is lane DEP-BACKEND's half, and it is named here so a reader of this
 * constant does not conclude the move is complete once the URL is right.
 */
export const DEFAULT_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? "";

function buildUrl(baseUrl: string, path: string, query?: Record<string, QueryValue>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined) {
      search.set(key, String(value));
    }
  }
  const qs = search.toString();
  return `${baseUrl}${path}${qs === "" ? "" : `?${qs}`}`;
}

async function readJson(response: Response): Promise<unknown> {
  const text = await response.text();
  if (text === "") {
    return null;
  }
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return null; // a non-JSON body is handled as "not the envelope"
  }
}

export interface ApiClient {
  request<T>(path: string, options?: RequestOptions): Promise<ApiResponse<T>>;
  get<T>(path: string, options?: Omit<RequestOptions, "method" | "body">): Promise<ApiResponse<T>>;
  post<T>(
    path: string,
    body?: unknown,
    options?: Omit<RequestOptions, "method" | "body">,
  ): Promise<ApiResponse<T>>;
  put<T>(
    path: string,
    body?: unknown,
    options?: Omit<RequestOptions, "method" | "body">,
  ): Promise<ApiResponse<T>>;
  /**
   * PARTIAL update. Added 2026-08-16, and the reason it was missing is worth
   * keeping: `HttpMethod` has listed "PATCH" since this file was written and
   * `request()` has always been able to send one — only the convenience verb
   * was absent. That one gap made a SERVED, AUDITED endpoint unreachable:
   * `PATCH /accounts/{id}/notes/{noteId}` (11b §2.6) pins, unpins and corrects
   * a note, and `api/endpoints.ts` recorded that it could not be wrapped
   * because "ApiClient has no PATCH verb", so the note pin was set at creation
   * and never afterwards. A transport gap became a missing feature.
   *
   * NOT RETRIED, exactly like post/put: `isRetryable` allows GET only, because
   * re-sending a mutation is a second write and idempotency is the server's
   * guarantee to give (CLAUDE.md rule 6), never a client's to assume.
   */
  patch<T>(
    path: string,
    body?: unknown,
    options?: Omit<RequestOptions, "method" | "body">,
  ): Promise<ApiResponse<T>>;
  del<T>(path: string, options?: Omit<RequestOptions, "method" | "body">): Promise<ApiResponse<T>>;
  // 11b §2.17 / G3: poll a 202's job to a terminal state.
  pollJob(jobId: string, options?: JobPollOptions): Promise<JobRecord>;
}

export function createApiClient(options: ApiClientOptions = {}): ApiClient {
  const baseUrl = options.baseUrl ?? DEFAULT_BASE_URL;
  const tenantOption = options.tenant;
  const resolveTenant =
    tenantOption === undefined
      ? currentTenant
      : typeof tenantOption === "function"
        ? tenantOption
        : () => tenantOption;
  const fetchImpl = options.fetchImpl ?? fetch;
  const sleep =
    options.sleep ?? ((ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms)));
  const maxAttempts = options.maxAttempts ?? MAX_ATTEMPTS;

  async function request<T>(
    path: string,
    requestOptions: RequestOptions = {},
  ): Promise<ApiResponse<T>> {
    const method = requestOptions.method ?? "GET";
    // The ONE place the tenant enters a URL (see §API URL shape).
    const url = buildUrl(baseUrl, apiPath(resolveTenant(), path), requestOptions.query);
    const accept = requestOptions.accept ?? JSON_MEDIA_TYPE;
    // ⛔ **`DEF-965` — EVERY REQUEST CARRIES ITS OWN REFERENCE.** Minted here
    // rather than per screen because the failure it exists for is one where
    // the screen never hears back at all, and because a reference that only
    // some calls carry is one support has to ask about. The server logs it on
    // arrival, so a worker killed later still leaves a line naming it.
    const sentRef = newRequestRef();
    const headers: Record<string, string> = {
      Accept: accept,
      [SUPPORT_REF_HEADER]: sentRef,
      // DEF-IDN-10024 — see `BACKGROUND_REFRESH_HEADER`.
      ...(isBackgroundMoment() ? { [BACKGROUND_REFRESH_HEADER]: "1" } : {}),
    };
    const multipart = isMultipart(requestOptions.body);
    if (requestOptions.body !== undefined && !multipart) {
      headers["Content-Type"] = "application/json";
    }
    if (requestOptions.ifNoneMatch !== undefined) {
      headers["If-None-Match"] = requestOptions.ifNoneMatch; // 11b G6
    }

    for (let attempt = 1; ; attempt += 1) {
      let response: Response;
      try {
        response = await fetchImpl(url, {
          method,
          headers,
          // The session is an httpOnly cookie (BR-IDN-006) — it only rides
          // along when credentials are included.
          credentials: "include",
          body:
            requestOptions.body === undefined
              ? undefined
              : multipart
                ? (requestOptions.body as FormData)
                : JSON.stringify(requestOptions.body),
          signal: requestOptions.signal,
        });
      } catch {
        // No HTTP answer at all. Not retried: the B12 r1 retry row is about
        // named statuses, and a silent client-side replay of a mutation is
        // exactly what CLAUDE.md #6 forbids.
        throw new ApiError(
          NO_RESPONSE_STATUS,
          { code: null, message_key: NETWORK_ERROR_KEY },
          null,
          sentRef,
        );
      }

      const etag = response.headers.get("ETag");

      if (response.status === 304) {
        // 11b G6: the caller's cached copy is still valid; no body is sent.
        return { status: 304, data: null, etag, notModified: true, headers: response.headers };
      }

      if (!response.ok) {
        const retryAfter = parseRetryAfter(response.headers.get("Retry-After"));
        const attemptLimit =
          response.status === 429 ? Math.min(maxAttempts, MAX_RATE_LIMITED_ATTEMPTS) : maxAttempts;
        if (isRetryable(method, response.status) && attempt < attemptLimit) {
          await sleep(retryDelayMs(attempt, retryAfter));
          continue;
        }
        const failure = new ApiError(
          response.status,
          failureEnvelope(response.status, await readJson(response)),
          retryAfter,
          sentRef,
        );
        // ⛔ **`DEF-SHL-6378` — A 401 IS THE SESSION, NEVER THE SCREEN.** Said
        // HERE, before the throw, rather than only by the query cache, because
        // not every request is a query: a wizard's autosave and a form's
        // imperative `await client.post(…)` never pass through TanStack, and
        // each of those would otherwise show a dead session as an inline
        // refusal under one field. The error is still thrown unchanged — the
        // caller's own state is not this file's business — and with no shell
        // mounted (sign-in, the portal, the phone) nothing is listening.
        if (failure.status === SESSION_EXPIRED_STATUS) {
          announceSessionExpired();
        }
        throw failure;
      }

      // A non-JSON Accept reads the body VERBATIM (DEF-121). The error path
      // above still parses as JSON, because a refusal is the ratified envelope
      // whatever the happy path's media type is (11b §3 G1).
      const data =
        response.status === 204
          ? null
          : accept === JSON_MEDIA_TYPE
            ? ((await readJson(response)) as T | null)
            : ((await response.text()) as unknown as T);
      return { status: response.status, data, etag, notModified: false, headers: response.headers };
    }
  }

  /**
   * ⛔ **`DEF-SHL-6377` — EVERY REFUSAL IS NOTED ON ITS WAY OUT, FOR THE ERROR
   * REPORT.** The failure panel is handed two sentences and never the error, so
   * this is the only place that can say which request was refused. Codes only:
   * the method, the contract path (the query string is cut off in
   * `noteFailedRequest`), the status, `code`, `message_key` and the short
   * reference — never the body, never `params`. The error is rethrown
   * untouched; nothing about what a screen receives changes.
   */
  async function noted<T>(
    path: string,
    requestOptions: RequestOptions = {},
  ): Promise<ApiResponse<T>> {
    try {
      return await request<T>(path, requestOptions);
    } catch (error) {
      if (isApiError(error)) {
        noteFailedRequest({
          method: requestOptions.method ?? "GET",
          path,
          status: error.status,
          code: error.code,
          messageKey: error.messageKey,
          ref: error.traceId ? supportRef(error.traceId) : error.sentRef,
        });
        // CR-169-BRC10 — `action_refused`: an ACTION (not a read) the server
        // said no to, by the screen's id and the refusal's code. Never the
        // body, the params or the path. A 401 is the session, not a refusal,
        // and a sign-in failure has its own event.
        const method = requestOptions.method ?? "GET";
        if (
          method !== "GET" &&
          error.status >= 400 &&
          error.status < 500 &&
          error.status !== SESSION_EXPIRED_STATUS &&
          path !== "/auth/session"
        ) {
          track("action_refused", {
            screen: currentScreenId() ?? "unregistered",
            code: error.code ?? error.messageKey ?? "unknown",
            status: error.status,
          });
        }
      }
      throw error;
    }
  }

  const client: ApiClient = {
    request: noted,
    get: (path, opts) => noted(path, { ...opts, method: "GET" }),
    post: (path, body, opts) => noted(path, { ...opts, method: "POST", body }),
    put: (path, body, opts) => noted(path, { ...opts, method: "PUT", body }),
    patch: (path, body, opts) => noted(path, { ...opts, method: "PATCH", body }),
    del: (path, opts) => noted(path, { ...opts, method: "DELETE" }),
    pollJob: (jobId, opts) => pollJob(client, jobId, { sleep, ...opts }),
  };
  return client;
}

/** The app-wide instance. Screens import this; tests build their own. */
export const api = createApiClient();

// ── 202 + job polling (B12 r1 · 11b §2.17/G3) ──────────────────────────────
// Every async operation answers 202 with a job id and the client polls
// `GET /jobs/{id}` until a terminal status. The record shape is BE-07's
// contract (06-backend/core/jobs.py docstring); no /jobs route is registered
// in config/urls.py yet — reported with this packet, implemented here because
// the CONTRACT is ratified and the first 202 endpoint must find it ready.

export const JOBS_PATH = "/jobs";

export type JobStatus = "queued" | "running" | "succeeded" | "failed";

/**
 * ONE of the twenty-eight steps of the sample-data plant, as the server names it.
 *
 * CR-064 (PO 2026-09-02): *"list down all 17 steps and show 1 by 1 when they
 * finish"*. `key` is `module:seam` — a stable NAME, never a database id
 * (B14 rule 31) — and it is what joins the catalogue on the commit response to
 * the outcomes on the poll. `label` is the server's English source string and
 * is a FALLBACK only: the screen renders the operator's own language from its
 * catalogue, and falls back to this so an EIGHTEENTH step is visible on the
 * day it is added rather than silently missing (hard-won law 2).
 */
export interface SampleStep {
  position: number;
  key: string;
  module: string;
  block: string;
  label: string;
  tables: string[];
}

/**
 * What the run RECORDED for one step — the same entry plus its outcome.
 *
 * `outcome` is `seeded` | `skipped` | `failed` | `not_started`, and the fourth
 * is served and never stored: it is what the server says about a step the run
 * has not reached. `detail` is the server's OWN sentence for that step and is
 * rendered verbatim and untranslated, exactly as `SettingsSampleData` already
 * renders it — that is the whole of what the PO asked for in the words *"you
 * ahve to provide specific error on the screen itself"*.
 */
export interface SampleStepState extends SampleStep {
  outcome: "seeded" | "skipped" | "failed" | "not_started";
  count: number;
  reason_code: string | null;
  error_code: string | null;
  failure_class: string | null;
  root_block: string | null;
  root_label: string | null;
  detail: string | null;
  finished_at: string | null;
}

export interface JobRecord {
  id: string;
  kind: string;
  status: JobStatus;
  progress: { done: number; total: number } | null;
  /**
   * The label of the last unit of work the job finished.
   *
   * ⚠ THE SERVER HAS WRITTEN THIS SINCE 2026-08-19 AND SERVED IT SINCE
   * DEF-3280 (2026-09-02). The sample-data plant records the block it just
   * completed here after every one of its seventeen; nothing could read it, so
   * a poll could answer *"11 of 17"* and never *"Meter reads"*. Optional
   * because a server that predates the fix omits the key entirely, and because
   * a job that has done no work yet has no checkpoint to report.
   */
  checkpoint?: string | null;
  /**
   * CR-064 — the sample-data plant's twenty-eight steps and what each one did.
   * PRESENT FOR THAT KIND ALONE and absent (never empty) for every other: an
   * export job has no blocks, and an empty list would read as an answer about
   * a job that never had any.
   */
  steps?: SampleStepState[];
  result_link: string | null;
  error: string | null;
}

/** The 202 body: the job id the poller needs. */
export interface AcceptedJob {
  job_id: string;
}

export function isAccepted<T>(response: ApiResponse<T>): boolean {
  return response.status === 202;
}

export function acceptedJobId(response: ApiResponse<unknown>): string | null {
  const data = response.data;
  if (response.status !== 202 || typeof data !== "object" || data === null) {
    return null;
  }
  const jobId = (data as Record<string, unknown>).job_id;
  return typeof jobId === "string" ? jobId : null;
}

/** `succeeded` and `failed` are terminal; `failed → running` is a legal resume. */
export function isTerminalJob(status: JobStatus): boolean {
  return status === "succeeded" || status === "failed";
}

export const JOB_POLL_INTERVAL_MS = 1000;
export const JOB_POLL_MAX_POLLS = 300; // ~5 minutes at the default interval

export interface JobPollOptions {
  intervalMs?: number;
  maxPolls?: number;
  onProgress?: (job: JobRecord) => void; // wizards render this (B12 §1)
  sleep?: (ms: number) => Promise<void>;
  signal?: AbortSignal;
}

export async function pollJob(
  client: ApiClient,
  jobId: string,
  options: JobPollOptions = {},
): Promise<JobRecord> {
  const intervalMs = options.intervalMs ?? JOB_POLL_INTERVAL_MS;
  const maxPolls = options.maxPolls ?? JOB_POLL_MAX_POLLS;
  const sleep =
    options.sleep ?? ((ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms)));

  for (let poll = 1; poll <= maxPolls; poll += 1) {
    const response = await client.get<JobRecord>(`${JOBS_PATH}/${encodeURIComponent(jobId)}`, {
      signal: options.signal,
    });
    const job = response.data;
    if (job !== null) {
      options.onProgress?.(job);
      if (isTerminalJob(job.status)) {
        return job;
      }
    }
    await sleep(intervalMs);
  }
  // Giving up is an honest failure, never an invented "succeeded".
  throw new ApiError(NO_RESPONSE_STATUS, {
    code: null,
    message_key: UNEXPECTED_ERROR_KEY,
    params: { job_id: jobId },
  });
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-TEN-001@d5f8c32 (story+rules snapshot hash — EP-TEN-03, the lead consumer; co-packet EP-IDN-01@402b6db)
// generated: 2026-08-09 by story-coder v1 · AMENDED 2026-08-09 by story-coder (frontend integration lane: multipart bodies + contract-bearing response headers) · AMENDED 2026-08-10 by story-coder v1 (path-tenancy lane — PO ruling 2026-08-10: SPA `/{tenant}/…`, API `/api/{tenant}/…`)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: trace_lint✔ run_gates✔ (11 PASS · 0 FAIL · 1 SKIP) tsc✔ eslint✔ vitest 296 passed / 83 todo across 30 files✔ (239+72 baseline unchanged and green; this packet adds 57 passing + 11 todo — the todos are browser-interaction, server/RLS and unbuilt-neighbour-screen scope) · 2026-08-10 path-tenancy re-run: tsc✔ eslint✔ vitest 529 passed / 134 todo across 44 files✔ (509 passed / 132 todo was the pre-lane baseline — the suite grew, nothing was dropped) · vite build✔ · run_gates 11 PASS · 0 FAIL · 1 SKIP · trace_lint✔
// exceptions: E3 GET /jobs/{id} STILL has no registered route in 06-backend/config/urls.py, and core.jobs has no registered store on this deployment — the poller implements the ratified 11b §2.17/G3 contract and its first consumer (the S61 audit export) therefore fails loudly rather than promising a poll URL with no record behind it (reported by the backend packets too) · E4 `ApiResponse.headers` is OPTIONAL so a hand-built response in a test stays valid; read it through `responseHeader`, never by indexing
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────

// ── Support-grade diagnostic line (PO report, 2026-08-10) ──────────────────
// "unable to see what is the error on screen — hence as user I'm unable to see
// what is happening." Found on the first real deployment: the pricing page
// showed "Something went wrong. Nothing was saved — try again." while the real
// event was a 502 from the API pass-through, i.e. the backend was not up. Every
// fact needed to say so was already on the ApiError — status, code, trace_id —
// and no screen rendered any of it.
//
// This returns the SHORT technical line a user can read aloud to support, or
// paste into a ticket. It is codes and identifiers only, never server prose:
// TD-16/G14 still hold, because none of this is a translated sentence.
// Returns null when there is genuinely nothing to say, so a caller can render
// nothing rather than an empty row.
export function diagnosticOf(error: unknown): string | null {
  if (!isApiError(error)) {
    // Not from this client: a thrown TypeError from fetch means the request
    // never got an answer at all — DNS, TLS, or nothing listening.
    return error instanceof Error && error.message ? `${error.name}: ${error.message}` : null;
  }
  const parts = [`HTTP ${error.status}`];
  if (error.code) parts.push(error.code);
  // ⚠ NO `br_ref` HERE — DEF-332, 2026-08-21. It used to be pushed between the
  // code and the reference, which put `BR-IDN-013` on a utility's screen by a
  // second route: this line RENDERS, in `StateFrame` and on the public pricing
  // page. The PO's standing ruling (2026-08-19) is that our internal ids do not
  // belong on a user's screen, and the support need the 2026-08-10 ruling asked
  // for — *an identifier a user can quote* — is met by the shortened trace
  // reference below, which DID NOT EXIST when the two rulings collided.
  // The value itself is untouched: it stays on `ApiError.brRef`, in the
  // envelope, in the audit row and in the server log, and it is rendered as
  // `data-br-ref` by `RefusalNotice` for support to read from the DOM.
  // ⚠ THE SHORT REFERENCE, not the raw 32-hex trace id (PO ruling 2026-08-19,
  // DEF-328). The whole point of this line is that a user reads it aloud to
  // support, and nobody dictates thirty-two hex characters correctly. The
  // short form is the SEARCHABLE one — `GET /audit-log?f.entity_type=request
  // &f.entity_id=5F2B-9C1D` matches the BR-AUD-018 attempt row by prefix — so
  // the product now shows ONE identifier for a refusal instead of two.
  if (error.traceId) {
    // A trace id too short to shorten (a hand-built envelope in a test, an
    // upstream that sent something else) still says what it says — dropping it
    // would trade a readable line for an empty one, which is DEF-320's shape.
    const shortened = supportRef(error.traceId);
    parts.push(shortened === SUPPORT_REF_ABSENT ? `trace ${error.traceId}` : `ref ${shortened}`);
  } else if (error.sentRef) {
    // ⛔ **`DEF-965` — THE CASE THAT COULD NOT BE DIAGNOSED, AND THE ONLY ONE
    // THE SERVER CANNOT NAME ITSELF.** No `trace_id` means Django never formed
    // a response: a gunicorn worker killed at sixty seconds (`DEF-1075`), a
    // gateway page, a socket that closed. The reference the CLIENT sent is
    // then the one artefact tying the screen to a server log line, and it was
    // written there before any work began. Never printed BESIDE a server trace
    // — one refusal shows one identifier, which is what DEF-332 bought.
    parts.push(`ref ${error.sentRef}`);
  }
  return parts.join(" · ");
}
