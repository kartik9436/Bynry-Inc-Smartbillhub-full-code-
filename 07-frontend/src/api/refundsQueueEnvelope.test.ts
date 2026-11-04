// ── Trace ────────────────────────────────────────────────────────────────
// Defect: `DEF-PAY-6644` — `GET /refunds` began paging (`965ed8fed`, `P1.3`)
//         and the client went on reading `rows`. The Revenue & AR refunds
//         panel drew *"Nothing is waiting here."* over a refund that was
//         waiting, beside its own badge reading **1** — and the only door to
//         the new refund screen was behind that empty list.
// Rules:  `NFR-3` (server pagination) · hard-won law 2's mirror — a live
//         screen behind a control that reports nothing to do.
// Screen: S36 Revenue & AR → Refunds · S58 Refunds
// Tests:  this file. `getRefunds` had NO test of its own.
// ─────────────────────────────────────────────────────────────────────────
/**
 * ⚠ **THE BODY BELOW IS A RECORDED RESPONSE, NOT A HAND-WRITTEN ONE.** It was
 * copied from the running API on 2026-09-24 —
 * `GET /api/brazosbend/refunds?f.status=requested` against a seeded clone —
 * with the row trimmed to the members the screens read. That is the whole point
 * of the defect: every existing fixture for this endpoint was written from the
 * TYPE, so all of them described a shape the server had stopped sending, and
 * every one of them passed.
 *
 * ⚠ **THE FIX IS NOT HERE AND THIS FILE DOES NOT ASSERT ONE.** Two lanes found
 * this within the same hour; lane FIN-PAY's landed first and it is the right
 * one — `RefundQueueResponse` now declares the server's own `{count, next,
 * previous, results}` and the panel reads `results`, rather than a wrapper
 * translating the envelope back into `rows` for one caller. What was missing
 * either way is a test that reads the WIRE, so that is what this is.
 */
import { describe, expect, it, vi } from "vitest";

import type { ApiClient } from "./client";
import { getRefunds } from "./endpoints";

/** What the server actually sent, trimmed. `count` and `pending` are different
 *  numbers by design — the pager states one, the view label's badge the other,
 *  and asking one number to be both is how a badge starts lying. */
const RECORDED = {
  count: 1,
  next: null,
  previous: null,
  results: [
    {
      id: "01a0d45e-df50-7f39-be7b-6f79ce185d89",
      payment_id: null,
      account_id: "01a0d3f1-f4ce-7750-ac16-845414e59f58",
      amount: "0.550000",
      currency: "USD",
      status: "requested",
      method: "check",
      reference: null,
      reason: "Overpayment",
    },
  ],
  pending: 1,
};

function client(body: unknown): ApiClient & { get: ReturnType<typeof vi.fn> } {
  const get = vi.fn().mockResolvedValue({ data: body });
  return { get, post: vi.fn() } as unknown as ApiClient & { get: ReturnType<typeof vi.fn> };
}

describe("DEF-PAY-6644 · the refunds queue reads the envelope the server sends", () => {
  it("hands the screen the page in `results`", async () => {
    const out = await getRefunds({ status: "requested" }, client(RECORDED));
    expect(out.results).toHaveLength(1);
    expect(out.results[0]?.status).toBe("requested");
    expect(out.results[0]?.amount).toBe("0.550000");
  });

  it("carries `count` and `pending` separately — the pager's number and the badge's", async () => {
    const out = await getRefunds({ status: "requested" }, client(RECORDED));
    expect(out.count).toBe(1);
    expect(out.pending).toBe(1);
  });

  it("asks for the status as `f.status`, which is what the view reads", async () => {
    const api = client(RECORDED);
    await getRefunds({ status: "requested" }, api);
    const [path, options] = api.get.mock.calls[0] as [string, { query: Record<string, unknown> }];
    expect(path).toBe("/refunds");
    expect(options.query["f.status"]).toBe("requested");
  });

  it("an empty page is an empty queue, not a crash", async () => {
    const out = await getRefunds({}, client({ count: 0, next: null, previous: null, results: [] }));
    expect(out.results).toEqual([]);
  });
});
