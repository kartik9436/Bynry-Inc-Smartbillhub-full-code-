// ── Trace ──────────────────────────────────────────────
// Component: FI-01 typed API client (B13 §2)
// Story:    US-TEN-001 · US-IDN-001 (the contract their screens depend on)  Screens: S1, S3, S62, S110–S114
// Rules:    BR-TEN-010 (idempotent commit — the SERVER's guarantee, never a client replay) · BR-SHL-020 (plain-language failure) ·
//           BR-TEN-003 (the tenant is in the REQUEST — since PO 2026-08-10, in the URL path this client builds)
// ───────────────────────────────────────────────────────
// Contract tests for the FI-01 transport. No network anywhere: every case
// drives `createApiClient` with a stub fetch and a stub sleep, so the retry
// curve, the envelope mapping, the 304 pass-through and the job poller are all
// provable in milliseconds. Named for the ratified contract rows they prove
// (B12 §3 · B12 r1 §3-expanded · 11b §3 G1/G2/G3/G6) — this component has no
// story TCs of its own.
import { describe, expect, it } from "vitest";

import i18n from "@/i18n";

import {
  API_PREFIX,
  ApiError,
  BLOCKED_KEY,
  MAX_ATTEMPTS,
  NETWORK_ERROR_KEY,
  NO_RESPONSE_STATUS,
  RATE_LIMITED_KEY,
  RETRY_BASE_MS,
  UNEXPECTED_ERROR_KEY,
  acceptedJobId,
  apiPath,
  createApiClient,
  currentTenant,
  formErrorEnvelope,
  isApiError,
  isRetryable,
  isTerminalJob,
  isUntenantedPath,
  parseRetryAfter,
  retryDelayMs,
} from "./client";
import type { JobRecord } from "./client";

const noSleep = () => Promise.resolve();

// The tenant every tenant-scoped call in this file is made under. In a browser
// it is read off `/{tenant}/…`; a test states it so the URLs are visible.
const TENANT = "brazosbend";

function json(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init,
  });
}

interface RecordedCall {
  url: string;
  init: RequestInit;
}

/** A client whose every call is recorded — no network, no mock framework. */
function recordingClient(responder: (attempt: number) => Response, maxAttempts?: number) {
  const calls: RecordedCall[] = [];
  const sleeps: number[] = [];
  const client = createApiClient({
    tenant: TENANT,
    fetchImpl: async (input: RequestInfo | URL, init?: RequestInit) => {
      calls.push({ url: String(input), init: init ?? {} });
      return responder(calls.length);
    },
    sleep: async (ms: number) => {
      sleeps.push(ms);
    },
    maxAttempts,
  });
  return { client, calls, sleeps };
}

// The ratified envelope (11b §3 G1) as the backend renders it — all six keys.
const SUBDOMAIN_TAKEN = {
  code: "BIZ-STATE",
  message_key: "signup.subdomain_taken",
  params: { subdomain: "brazosbend" },
  field_errors: [],
  br_ref: "BR-TEN-011",
  trace_id: "5f2b9c1d",
};

describe("FI-01 client — error envelope (B12 §3 / 11b G1)", () => {
  it("G1: a 4xx envelope becomes a typed ApiError carrying code, message_key, params, br_ref and trace_id", async () => {
    const client = createApiClient({
      fetchImpl: async () => json(SUBDOMAIN_TAKEN, { status: 409 }),
      sleep: noSleep,
    });
    const error = await client.post("/tenants", {}).catch((caught: unknown) => caught);
    expect(isApiError(error)).toBe(true);
    const apiError = error as ApiError;
    expect(apiError.status).toBe(409);
    expect(apiError.code).toBe("BIZ-STATE");
    expect(apiError.messageKey).toBe("signup.subdomain_taken");
    expect(apiError.params).toEqual({ subdomain: "brazosbend" });
    expect(apiError.brRef).toBe("BR-TEN-011");
    expect(apiError.traceId).toBe("5f2b9c1d");
  });

  it("G1: a body that is NOT the envelope still surfaces as a translatable ApiError, never raw text", async () => {
    const client = createApiClient({
      tenant: TENANT,
      fetchImpl: async () => new Response("<html>502 from a proxy</html>", { status: 502 }),
      sleep: noSleep,
      maxAttempts: 1,
    });
    const error = (await client.get("/tenants/checklist").catch((c: unknown) => c)) as ApiError;
    expect(error.code).toBeNull();
    expect(error.messageKey).toBe(UNEXPECTED_ERROR_KEY);
  });

  it("G1: a dead connection is status 0 with the network key — never a thrown TypeError", async () => {
    const client = createApiClient({
      fetchImpl: () => Promise.reject(new TypeError("Failed to fetch")),
      sleep: noSleep,
    });
    const error = (await client.get("/public/pricing-plans").catch((c: unknown) => c)) as ApiError;
    expect(error.status).toBe(NO_RESPONSE_STATUS);
    expect(error.messageKey).toBe("api.error.network");
  });

  it("field_errors map to the FormModal envelope; non-field errors (field: null) stay out of the field map", () => {
    const error = new ApiError(422, {
      code: "VAL-001",
      message_key: "errors.val-001",
      field_errors: [
        { field: "owner.email", code: "VAL-002", message_key: "signup.owner_email_invalid" },
        { field: null, code: "VAL-002", message_key: "signup.payload_not_object" },
      ],
    });
    const envelope = formErrorEnvelope(error);
    expect(envelope.field_errors).toEqual([
      { field: "owner.email", message_key: "signup.owner_email_invalid", params: undefined },
    ]);
    expect(envelope.message_key).toBe("errors.val-001");
  });
});

describe("FI-01 client — retry policy (B12 r1 §3-expanded)", () => {
  it("retries 429/502/503/504 on GET only — a mutation is NEVER replayed (CLAUDE.md #6)", () => {
    for (const status of [429, 502, 503, 504]) {
      expect(isRetryable("GET", status)).toBe(true);
      expect(isRetryable("POST", status)).toBe(false);
      expect(isRetryable("PUT", status)).toBe(false);
      expect(isRetryable("PATCH", status)).toBe(false);
      expect(isRetryable("DELETE", status)).toBe(false);
    }
    expect(isRetryable("GET", 409)).toBe(false); // a business refusal is an answer
    expect(isRetryable("GET", 422)).toBe(false);
  });

  it("backoff doubles, and a Retry-After header wins over the curve", () => {
    expect(retryDelayMs(1, null)).toBe(RETRY_BASE_MS);
    expect(retryDelayMs(2, null)).toBe(RETRY_BASE_MS * 2);
    expect(retryDelayMs(3, null)).toBe(RETRY_BASE_MS * 4);
    expect(retryDelayMs(1, 2)).toBe(2000); // 429 + Retry-After: 2
    expect(parseRetryAfter("30")).toBe(30);
    expect(parseRetryAfter("Wed, 21 Oct 2026 07:28:00 GMT")).toBeNull(); // date form is not guessed
    expect(parseRetryAfter(null)).toBeNull();
  });

  it("DEF-SHL-10621: a throttled GET is retried ONCE after Retry-After, then says 'Too many requests'", async () => {
    const { client, calls, sleeps } = recordingClient(() =>
      json(
        { code: null, message_key: "errors.throttled" },
        { status: 429, headers: { "Retry-After": "1" } },
      ),
    );
    const error = (await client.get("/public/pricing-plans").catch((c: unknown) => c)) as ApiError;
    expect(calls).toHaveLength(2); // the first try + ONE retry, never MAX_ATTEMPTS on a 429
    expect(MAX_ATTEMPTS).toBeGreaterThan(2); // …which is still the curve for 502/503/504
    expect(sleeps).toEqual([1000]); // Retry-After honoured
    expect(error.status).toBe(429);
    expect(error.retryAfterSeconds).toBe(1);
    expect(error.messageKey).toBe(RATE_LIMITED_KEY);
  });

  it("DEF-SHL-10621: a throttled POST is never replayed, and a 429 with no envelope (the WAF) still reads as rate limited", async () => {
    const { client, calls } = recordingClient(
      () => new Response("Too Many Requests", { status: 429, headers: { "Retry-After": "300" } }),
    );
    const error = (await client.post("/premises", {}).catch((c: unknown) => c)) as ApiError;
    expect(calls).toHaveLength(1);
    expect(error.status).toBe(429);
    expect(error.messageKey).toBe(RATE_LIMITED_KEY);
    expect(error.retryAfterSeconds).toBe(300);
  });

  it("DEF-SHL-10621: the server's own rate-limit sentence is the one shown", async () => {
    const { client } = recordingClient(() =>
      json(
        { code: null, message_key: "api.error.rate_limited", params: { retry_after_seconds: 12 } },
        { status: 429, headers: { "Retry-After": "12" } },
      ),
    );
    const error = (await client.post("/exports", {}).catch((c: unknown) => c)) as ApiError;
    expect(error.messageKey).toBe("api.error.rate_limited");
    expect(i18n.t(error.messageKey)).toBe("Too many requests. Wait a moment.");
  });

  it("DEF-SHL-10619: a firewall block (403 WAF-BLOCK) says it was blocked, not that we could not connect", async () => {
    for (const body of [
      { code: "WAF-BLOCK", message_key: "api.error.blocked" },
      { code: "WAF-BLOCK" }, // the code alone is enough
      { message_key: "api.error.blocked" }, // …and so is the key
    ]) {
      const { client } = recordingClient(() => json(body, { status: 403 }));
      const error = (await client.post("/settings/company/logo", {}).catch((c: unknown) => c)) as ApiError;
      expect(error.status).toBe(403);
      expect(error.messageKey).toBe(BLOCKED_KEY);
      expect(error.code).toBe("WAF-BLOCK");
      expect(i18n.t(error.messageKey)).toBe("This request was blocked for security. Contact support.");
    }
    // An ordinary permission refusal is NOT rewritten.
    const { client } = recordingClient(() =>
      json({ code: "AUTH-002", message_key: "errors.auth-002" }, { status: 403 }),
    );
    const denied = (await client.get("/premises").catch((c: unknown) => c)) as ApiError;
    expect(denied.messageKey).toBe("errors.auth-002");
    expect(denied.code).toBe("AUTH-002");
  });

  it("DEF-SHL-10619: a connection that fails outright still says 'couldn't reach' (unchanged)", async () => {
    const client = createApiClient({
      tenant: TENANT,
      fetchImpl: async () => {
        throw new TypeError("Failed to fetch");
      },
      sleep: noSleep,
    });
    const error = (await client.get("/premises").catch((c: unknown) => c)) as ApiError;
    expect(error.status).toBe(NO_RESPONSE_STATUS);
    expect(error.messageKey).toBe(NETWORK_ERROR_KEY);
  });

  it("a 503 POST is answered immediately — one attempt, no replay of the write", async () => {
    const { client, calls } = recordingClient(() =>
      json({ code: "SYS-PROVIDER", message_key: "errors.sys-provider" }, { status: 503 }),
    );
    await client.post("/tenants", { subdomain: "brazosbend" }).catch(() => undefined);
    expect(calls).toHaveLength(1);
  });

  it("a GET that recovers on the second attempt returns the data, not the 503", async () => {
    const { client, calls } = recordingClient((attempt) =>
      attempt === 1
        ? json({ code: "SYS-PROVIDER", message_key: "errors.sys-provider" }, { status: 503 })
        : json([{ code: "growth" }]),
    );
    const response = await client.get<{ code: string }[]>("/public/pricing-plans");
    expect(calls).toHaveLength(2);
    expect(response.data).toEqual([{ code: "growth" }]);
  });
});

describe("FI-01 client — HTTP series + session (B12 r1 · 11b G6/G18)", () => {
  it("G6: If-None-Match goes out and a 304 comes back as notModified with the ETag, no data", async () => {
    const { client, calls } = recordingClient(
      () => new Response(null, { status: 304, headers: { ETag: '"v7"' } }),
    );
    const response = await client.get("/public/pricing-plans", { ifNoneMatch: '"v7"' });
    expect(response.notModified).toBe(true);
    expect(response.data).toBeNull();
    expect(response.etag).toBe('"v7"');
    const headers = calls[0].init.headers as Record<string, string>;
    expect(headers["If-None-Match"]).toBe('"v7"');
  });

  it("204 answers with a null body and does not try to parse one", async () => {
    const client = createApiClient({
      tenant: TENANT,
      fetchImpl: async () => new Response(null, { status: 204 }),
      sleep: noSleep,
    });
    const response = await client.del("/auth/session");
    expect(response.status).toBe(204);
    expect(response.data).toBeNull();
  });

  it("every request includes credentials (the httpOnly session cookie) and puts the tenant ONLY in the URL (BR-TEN-003)", async () => {
    const { client, calls } = recordingClient(() => json({ ok: true }));
    await client.get("/tenants/checklist", { query: { q: "x" } });
    expect(calls[0].init.credentials).toBe("include");
    // PO 2026-08-10: `/api/{tenant}/…`, with the query string still last.
    expect(calls[0].url).toBe("/api/brazosbend/tenants/checklist?q=x");
    // …and nowhere else: no tenant header, no tenant in the body.
    expect(JSON.stringify(calls[0].init.headers)).not.toContain("tenant");
    expect(calls[0].init.body).toBeUndefined();
  });
});

// ── §API URL shape (PO ruling 2026-08-10 — path tenancy) ───────────────────
// The ONE place a tenant enters a URL. These are the laws the concurrent
// backend lane is mounting to; if they change, they change here and nowhere
// else, which is the point of having the function.

describe("FI-01 client — the /api/{tenant} URL shape", () => {
  it("a tenant-scoped contract path becomes /api/{tenant}/…", () => {
    expect(API_PREFIX).toBe("/api");
    expect(apiPath("brazosbend", "/settings/company")).toBe(
      "/api/brazosbend/settings/company",
    );
    expect(apiPath("brazosbend", "/auth/session")).toBe("/api/brazosbend/auth/session");
    // A READ of the caller's own tenant is tenant-scoped like everything else.
    expect(apiPath("brazosbend", "/tenants/checklist")).toBe(
      "/api/brazosbend/tenants/checklist",
    );
    // Same code, another tenant — no per-tenant branch exists.
    expect(apiPath("lonestar", "/settings/company")).toBe("/api/lonestar/settings/company");
  });

  it("the public and platform paths carry NO tenant — exactly the ruling's list", () => {
    for (const path of [
      "/tenants", // POST — provisioning, before a tenant exists
      "/public/pricing-plans",
      "/public/subdomain-check",
      "/jobs/job-7",
      "/exports",
      "/exports/job-7/file",
    ]) {
      expect(isUntenantedPath(path)).toBe(true);
      expect(apiPath("brazosbend", path)).toBe(`/api${path}`);
    }
    // …and everything else is tenant-scoped, including the checklist read that
    // merely LOOKS like the provisioning path.
    for (const path of ["/tenants/checklist", "/auth/session", "/publicly-visible", "/me"]) {
      expect(isUntenantedPath(path)).toBe(false);
    }
  });

  it("a tenant-scoped call with NO tenant in scope throws — it is never sent somewhere else", async () => {
    expect(() => apiPath("", "/settings/company")).toThrow(ApiError);
    // The un-tenanted paths still work with no tenant: that is what makes
    // signup and the public catalog reachable from the root surface.
    expect(apiPath("", "/public/pricing-plans")).toBe("/api/public/pricing-plans");
    expect(apiPath("", "/tenants")).toBe("/api/tenants");

    // Through the client it surfaces as the ordinary typed failure — the screen
    // renders a state, the request never reaches the network.
    let reached = false;
    const client = createApiClient({
      tenant: "",
      fetchImpl: async () => {
        reached = true;
        return json({ ok: true });
      },
      sleep: noSleep,
    });
    const error = (await client.get("/settings/company").catch((c: unknown) => c)) as ApiError;
    expect(isApiError(error)).toBe(true);
    expect(error.status).toBe(NO_RESPONSE_STATUS);
    expect(reached).toBe(false);
  });

  it("the default tenant is READ from the browser's URL, per request — never held in a variable", async () => {
    // No window in this environment, so the default resolver answers "" — the
    // honest answer for "no route in scope", and the reason a test states one.
    expect(currentTenant()).toBe("");

    // A resolver is re-consulted on EVERY call, so a client-side navigation
    // from one tenant's screen to another's is followed without rebuilding the
    // client (the browser's URL is the single source of truth).
    let where = "brazosbend";
    const urls: string[] = [];
    const client = createApiClient({
      tenant: () => where,
      fetchImpl: async (input: RequestInfo | URL) => {
        urls.push(String(input));
        return json({ ok: true });
      },
      sleep: noSleep,
    });
    await client.get("/me");
    where = "lonestar";
    await client.get("/me");
    expect(urls).toEqual(["/api/brazosbend/me", "/api/lonestar/me"]);
  });
});

describe("FI-01 client — 202 + job polling (11b §2.17 / G3)", () => {
  it("reads the job id off a 202 and polls until a terminal status", async () => {
    const running: JobRecord = {
      id: "job-1",
      kind: "bill_run",
      status: "running",
      progress: { done: 4, total: 10 },
      result_link: null,
      error: null,
    };
    const done: JobRecord = { ...running, status: "succeeded", progress: { done: 10, total: 10 } };
    const bodies = [running, running, done];
    const { client } = recordingClient((attempt) => json(bodies[attempt - 1]));
    const seen: number[] = [];
    const job = await client.pollJob("job-1", {
      onProgress: (record) => seen.push(record.progress?.done ?? 0),
    });
    expect(job.status).toBe("succeeded");
    expect(seen).toEqual([4, 4, 10]);
    expect(isTerminalJob("queued")).toBe(false);
    expect(isTerminalJob("failed")).toBe(true);
  });

  it("acceptedJobId reads a 202 body and refuses to invent one from a 200", () => {
    expect(
      acceptedJobId({ status: 202, data: { job_id: "job-7" }, etag: null, notModified: false }),
    ).toBe("job-7");
    expect(
      acceptedJobId({ status: 200, data: { job_id: "job-7" }, etag: null, notModified: false }),
    ).toBeNull();
  });

  it("giving up on a job is an honest failure, never a fabricated success", async () => {
    const client = createApiClient({
      tenant: TENANT,
      fetchImpl: async () =>
        json({
          id: "job-1",
          kind: "import",
          status: "running",
          progress: null,
          result_link: null,
          error: null,
        }),
      sleep: noSleep,
    });
    const error = (await client
      .pollJob("job-1", { maxPolls: 2 })
      .catch((c: unknown) => c)) as ApiError;
    expect(isApiError(error)).toBe(true);
    expect(error.messageKey).toBe(UNEXPECTED_ERROR_KEY);
  });

  it("the poller uses the PLATFORM path — a job is not tenant-scoped (PO 2026-08-10)", async () => {
    const { client, calls } = recordingClient(() =>
      json({
        id: "job-1",
        kind: "import",
        status: "succeeded",
        progress: null,
        result_link: null,
        error: null,
      }),
    );
    await client.pollJob("job-1");
    expect(calls[0].url).toBe("/api/jobs/job-1");
  });

  it.todo(
    "polls a REAL job: GET /api/jobs/{id} has no route in 06-backend/config/urls.py yet (11b §2.17) — activates with the first 202 endpoint",
  );
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-TEN-001@d5f8c32 (story+rules snapshot hash — EP-TEN-03)
// generated: 2026-08-09 by story-coder v1 · AMENDED 2026-08-10 by story-coder v1 (path-tenancy lane — PO ruling 2026-08-10: SPA `/{tenant}/…`, API `/api/{tenant}/…`)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: trace_lint✔ run_gates✔ (11 PASS · 0 FAIL · 1 SKIP) tsc✔ eslint✔ vitest 144/144✔ (13 todo this packet — browser/journey/v2-deferred scope) · 2026-08-10 path-tenancy re-run: tsc✔ eslint✔ vitest 529 passed / 134 todo across 44 files✔ (509 passed / 132 todo was the pre-lane baseline — the suite grew, nothing was dropped) · vite build✔ · run_gates 11 PASS · 0 FAIL · 1 SKIP · trace_lint✔
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
