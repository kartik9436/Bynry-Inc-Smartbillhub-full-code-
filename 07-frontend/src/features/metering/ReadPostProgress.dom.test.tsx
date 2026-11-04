// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defects:  DEF-MET-8106 (a 480-reading post ran inside the request and the
//           clerk saw Internal Server Error) · DEF-MET-8109 (one bad reading
//           value failed the whole file with a 500)
// Ruling:   PO 2026-09-30, "READS UPLOAD 500 ON 480 READINGS" — fixes (A)
//           and (D): the post runs as a job with progress; a bad value is a
//           ROW error with a plain message.
// Rules:    BR-MET-055 · BR-MET-032 · B14 rule 33
// ───────────────────────────────────────────────────────
// What the screen half must do, and what nothing else checks:
//
//   1. The post's TWO answers — the receipt (200) and the job (202) — are told
//      apart, and a 202 is followed to its receipt through the job, never read
//      as a receipt with every figure missing (which would print "0 posted").
//   2. The job's `N of M` is drawn from the two integers the server wrote.
//   3. A reading too long for the column is named on its row in plain words.
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { createApiClient } from "@/api/client";
import type { JobRecord } from "@/api/client";
import {
  isDeferredPost,
  postReadBatch,
  receiptAfterPostJob,
} from "@/api/endpoints";
import type { ReadImportBatchRow } from "@/api/endpoints";

import { ReadPostProgress } from "./ReadPostProgress";
import { rowReasonText } from "./UploadReadsWizard";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

afterEach(cleanup);

function job(over: Partial<JobRecord> = {}): JobRecord {
  return {
    id: "job-1",
    kind: "metering.read_batch_post",
    status: "running",
    progress: { done: 240, total: 480 },
    result_link: null,
    error: null,
    ...over,
  };
}

describe("DEF-MET-8106 — the background post's progress", () => {
  it("draws N of M from the job while it runs", () => {
    render(<ReadPostProgress job={job()} t={t} />);
    expect(screen.getByRole("status")).toHaveTextContent("Posting 240 of 480");
  });

  it("says it is waiting before a worker has picked it up", () => {
    render(<ReadPostProgress job={job({ status: "queued", progress: null })} t={t} />);
    expect(screen.getByRole("status")).toHaveTextContent("Waiting for a worker.");
  });

  it("says 'so far' rather than 'of 0' before the first report", () => {
    render(<ReadPostProgress job={job({ progress: { done: 25, total: null as unknown as number } })} t={t} />);
    expect(screen.getByRole("status")).toHaveTextContent("Posting — 25 so far");
  });

  it("draws nothing at all for a post that ran while the clerk waited", () => {
    const { container } = render(<ReadPostProgress job={null} t={t} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("follows a 202 through its job to the receipt — never reads the job as a receipt", async () => {
    const calls: string[] = [];
    const client = createApiClient({
      tenant: "brazosbend",
      sleep: async () => undefined,
      fetchImpl: async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        calls.push(`${init?.method ?? "GET"} ${url}`);
        const json = (status: number, body: unknown) =>
          new Response(JSON.stringify(body), {
            status,
            headers: { "Content-Type": "application/json" },
          });
        if (url.endsWith("/read-batches/b-1/post")) {
          return json(202, {
            id: "b-1",
            deferred: true,
            async: true,
            job_id: "job-1",
            status_url: "/jobs/job-1",
            receipt_url: "/read-batches/b-1/post-receipt",
            rows_to_post: 480,
          });
        }
        if (url.endsWith("/jobs/job-1")) {
          return json(200, job({ status: "succeeded", progress: { done: 480, total: 480 } }));
        }
        if (url.endsWith("/read-batches/b-1/post-receipt")) {
          return json(200, { id: "b-1", status: "posted", posted_reads: 480, held_reads: 0 });
        }
        return json(404, {});
      },
    });
    const answer = await postReadBatch("b-1", { certified: true }, client);
    expect(isDeferredPost(answer)).toBe(true);
    if (!isDeferredPost(answer)) throw new Error("unreachable");
    const receipt = await receiptAfterPostJob(answer, client);
    expect(receipt.posted_reads).toBe(480);
    // `/jobs/{id}` is a platform resource and carries no tenant segment.
    expect(calls.map((c) => c.replace(/^.*\/api(\/brazosbend)?/, ""))).toEqual([
      "/read-batches/b-1/post",
      "/jobs/job-1",
      "/read-batches/b-1/post-receipt",
    ]);
  });

  it("a receipt at or below the bar is not mistaken for a job", () => {
    expect(
      isDeferredPost({ id: "b-2", posted_reads: 12 } as unknown as Parameters<typeof isDeferredPost>[0]),
    ).toBe(false);
  });
});

describe("DEF-MET-8109 — a bad reading value is a row error in plain words", () => {
  it("names a reading with more digits than the column holds", () => {
    const row = {
      row_no: 2,
      rule_outcomes: [
        {
          rule: "parse",
          severity: "error",
          detail: { code: "reading_too_large", field: "reading", value: "1234567890123" },
        },
      ],
    } as unknown as ReadImportBatchRow;
    expect(rowReasonText(row, t)).toBe("Too many digits for a reading");
  });

  it("names NaN and Infinity as a number the upload cannot read", () => {
    const row = {
      row_no: 3,
      rule_outcomes: [
        {
          rule: "parse",
          severity: "error",
          detail: { code: "reading_unparseable", field: "reading", value: "NaN" },
        },
      ],
    } as unknown as ReadImportBatchRow;
    expect(rowReasonText(row, t)).toBe("That is not a number we can read");
  });
});
