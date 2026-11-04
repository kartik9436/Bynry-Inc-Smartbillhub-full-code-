// ── Tests for the response-time instrument's arithmetic and its honesty ─────
//
// Run: node --test 10-scripts/tests/test_cr071_timings.mjs
//      node 10-scripts/tests/test_cr071_timings.mjs        (node's runner does
//                                                           both; no deps)
//
// ⚠ THESE ARE NOT PROOF THAT THE INSTRUMENT WORKS. Hard-won law 6: no gate in
// this repository looks at rendered output, and a unit test over a fake array
// cannot tell you that Playwright's `requestfinished` fires, that
// `request.timing()` is populated, or that the endpoint grouping survives a
// real URL. That proof is
// `10-scripts/render-checks/cr071-response-times-instrument.mjs`, run against a
// running product, and its numbers are quoted in the decision log.
//
// What THIS file is for is the half a browser cannot show you cheaply: that the
// percentile arithmetic is nearest-rank rather than interpolated, and — the
// reason `CR-071` needed a module at all — that a `p95` computed from a handful
// of clicks SAYS SO. `11-response-times.md` §5: *"A failure here is reported,
// never rounded."* A percentile that quietly reports the maximum under a
// percentile's name is a rounding of exactly that kind.
//
// WHY EACH ASSERTION IS WRITTEN AS AN ATTRIBUTION, NOT AN ACCEPTANCE
// ------------------------------------------------------------------
// `assert(percentile(xs, 95) > 0)` passes on every wrong implementation there
// is. So each case below names the value that must come back AND, where a
// plausible alternative implementation would return something else, names that
// too — the linear-interpolation reading in particular, because it is what
// every statistics library does by default and it invents milliseconds nothing
// observed.

import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  BACKING_SAMPLES_WANTED,
  endpointKey,
  percentile,
  printReport,
  rankFor,
  rankHonesty,
} from "../render-checks/lib/timings.mjs";

/** Capture what `printReport` printed, as one string. */
function captured(rows, options = {}) {
  const lines = [];
  const result = printReport(rows, { ...options, log: (line) => lines.push(line) });
  return { text: lines.join("\n"), result };
}

/** A row shaped the way `attachTimings` builds them, from raw samples. */
function rowFrom(key, values) {
  const sorted = [...values].sort((a, b) => a - b);
  return {
    key,
    n: sorted.length,
    p50: percentile(sorted, 50),
    p95: percentile(sorted, 95),
    p99: percentile(sorted, 99),
    min: sorted[0],
    max: sorted[sorted.length - 1],
    ttfbP95: percentile(sorted, 95),
    serverP95: null,
    serverSamples: 0,
    nonOk: 0,
    honesty: {
      p50: rankHonesty(50, sorted.length),
      p95: rankHonesty(95, sorted.length),
      p99: rankHonesty(99, sorted.length),
    },
  };
}

describe("nearest rank, never interpolation", () => {
  it("returns a sample that was actually observed", () => {
    // 1..10. Nearest rank p95 = ceil(0.95 × 10) = 10th = 10.
    // Linear interpolation (numpy's default) returns 9.55 — a millisecond
    // figure no request ever took. On a latency table that is a fabrication,
    // and on a two-sample screen it is a comforting number between two real
    // ones, which is the exact failure §5 exists to prevent.
    const ten = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
    assert.equal(percentile(ten, 95), 10);
    assert.equal(percentile(ten, 50), 5, "ceil(0.5 × 10) = 5th = 5, not the 5.5 midpoint");
    assert.equal(percentile(ten, 99), 10);
    assert.equal(percentile(ten, 1), 1);
    for (const p of [0, 1, 25, 50, 75, 95, 99, 100]) {
      assert.ok(ten.includes(percentile(ten, p)), `p${p} returned a value nothing observed`);
    }
  });

  it("ranks are 1-indexed and clamped to the sample", () => {
    assert.equal(rankFor(95, 100), 95);
    assert.equal(rankFor(99, 100), 99);
    assert.equal(rankFor(50, 3), 2, "ceil(1.5) = 2 — the middle of three");
    assert.equal(rankFor(95, 1), 1, "one sample has one rank");
    assert.equal(rankFor(0, 10), 1, "a rank is never 0 — that would index off the front");
    assert.equal(rankFor(100, 10), 10);
    assert.equal(rankFor(95, 0), 0, "no samples, no rank");
  });

  it("has no percentile of nothing", () => {
    assert.equal(percentile([], 95), null);
  });
});

describe("the small-sample rule — a p95 from a handful of clicks is not a p95", () => {
  it("says so in words when the rank IS the maximum", () => {
    // THE CASE THE MODULE EXISTS FOR. A walkthrough clicks a screen twice.
    // ceil(0.95 × 2) = 2 = n, so the "p95" is the slower of the two requests
    // and carries none of the information the name implies.
    const two = rankHonesty(95, 2);
    assert.equal(two.rank, 2);
    assert.equal(two.marker, "!");
    assert.match(two.note, /NOT A p95/);
    assert.match(two.note, /slowest of 2/);

    // And it holds all the way to the threshold: below n = 20 there is no p95.
    for (let n = 1; n < 20; n += 1) {
      assert.equal(rankHonesty(95, n).marker, "!", `p95 at n=${n} is still the maximum`);
    }
    assert.equal(rankFor(95, 20), 19, "n = 20 is where p95 finally stops being the max");
    assert.notEqual(rankHonesty(95, 20).marker, "!");
  });

  it("puts the same threshold on p99 at n = 100, where it actually falls", () => {
    for (const n of [2, 30, 60, 99]) {
      assert.equal(rankHonesty(99, n).marker, "!", `p99 at n=${n} is the maximum`);
    }
    assert.equal(rankFor(99, 100), 99);
    assert.notEqual(rankHonesty(99, 100).marker, "!");
  });

  it("warns while a rank exists but only a couple of requests decide it", () => {
    // n = 30 — a diligent walkthrough loop. p95 = 29th of 30, so the two
    // slowest requests are the whole answer. It IS a percentile; it is not yet
    // a stable one, and the difference is worth a character.
    const thirty = rankHonesty(95, 30);
    assert.equal(thirty.rank, 29);
    assert.equal(thirty.backing, 2);
    assert.equal(thirty.marker, "~");
    assert.match(thirty.note, /29th of 30/);
    assert.match(thirty.note, /2 slowest/);
  });

  it("goes quiet once five samples back the rank — one rule, every percentile", () => {
    assert.equal(BACKING_SAMPLES_WANTED, 5);
    // n = 80: p95 = 76th, so 5 samples sit at or above it. That is the point
    // where one unlucky request can no longer move the figure by itself.
    assert.equal(rankFor(95, 80), 76);
    assert.equal(rankHonesty(95, 80).backing, 5);
    assert.equal(rankHonesty(95, 80).marker, "", "at n = 80 the p95 stands on its own");
    assert.equal(rankHonesty(95, 79).marker, "~", "…and at 79 it does not");
    // The same rule, unmodified and un-tuned, lands p99 at n = 400 and p50 at
    // n = 8. ⚠ THE p50 FIGURE IS WHY THIS TEST EARNED ITS KEEP: the first draft
    // of this line asserted n = 9 from a threshold worked out in the head, and
    // it went RED. ceil(0.5 × 8) = 4, so 5 of the 8 samples already sit at or
    // above the median's rank and the module is right. A threshold anybody can
    // re-derive is worth more than three anybody has to remember.
    assert.equal(rankHonesty(99, 400).marker, "");
    assert.equal(rankHonesty(99, 399).marker, "~");
    assert.equal(rankHonesty(50, 8).marker, "");
    assert.equal(rankHonesty(50, 7).marker, "~");
  });
});

describe("the table prints numbers, never verdicts", () => {
  it("marks a one-click row and calls it out in words under the table", () => {
    const { text } = captured([rowFrom("GET /api/t/portal/me/balance", [612])], {
      title: "one click",
    });
    assert.match(text, /612!/, "the p95 cell carries the marker");
    assert.match(text, /READ THIS BEFORE QUOTING A p95/);
    assert.match(text, /NOT A p95 — n=1/);
    // The negative that makes the assertion above mean something: a table that
    // printed the figure bare would pass a "contains 612" test perfectly well.
    assert.ok(
      !/^\s*612\s*$/m.test(text),
      "the p95 must never appear as a bare number with no statement of what it is worth",
    );
  });

  it("reports a miss as a miss, with the measured figure FIRST", () => {
    // §5, verbatim: *"If p95 for the balance screen is 900 ms, the report says
    // 900 ms against a 600 ms target — it does not say 'meets target'."*
    const row = rowFrom("GET /api/t/portal/me/balance", Array.from({ length: 100 }, (_, i) => 800 + i));
    const { text, result } = captured([row], {
      targets: [{ id: "RT-3", match: "/portal/me/balance", p95: 600 }],
    });
    assert.match(text, /p95 MEASURED 894 ms against a 600 ms target/);
    assert.match(text, /OVER by 294 ms/);
    assert.equal(result.misses.length, 1);
    assert.equal(result.misses[0].id, "RT-3");
    assert.equal(result.misses[0].gap, 294);
  });

  it("prints the measured figure beside a target that was met, and no ✓ verdict", () => {
    const row = rowFrom("GET /api/t/portal/public/front", Array.from({ length: 100 }, () => 120));
    const { text, result } = captured([row], {
      targets: [{ id: "RT-1", match: "/portal/public/front", p95: 400 }],
    });
    assert.match(text, /p95 MEASURED 120 ms against a 400 ms target/);
    assert.match(text, /under by 280 ms/);
    assert.equal(result.misses.length, 0);
    // The forbidden shape: a helper that turns a number into a claim.
    for (const banned of [/meets target/i, /✓ *under target/i, /within target/i, /PASS/]) {
      assert.ok(!banned.test(text), `the report must not print a verdict: ${banned}`);
    }
  });

  it("refuses to let a one-sample comparison read as evidence", () => {
    // The dangerous combination: a tiny sample that happens to sit under the
    // target. Printed bare it reads as "the balance screen meets RT-3".
    const { text } = captured([rowFrom("GET /api/t/portal/me/balance", [120])], {
      targets: [{ id: "RT-3", match: "/portal/me/balance", p95: 600 }],
    });
    assert.match(text, /under by 480 ms/);
    assert.match(text, /not evidence either way/);
  });

  it("says when a target was never exercised, rather than omitting it", () => {
    const { text } = captured([rowFrom("GET /api/t/accounts", [100])], {
      targets: [{ id: "RT-5", match: "/portal/bills/{id}/document", p95: 1000 }],
    });
    assert.match(text, /RT-5: NOT MEASURED on this run/);
  });

  it("states what the figure excludes every time it prints one", () => {
    const { text } = captured([rowFrom("GET /api/t/accounts", [100])]);
    assert.match(text, /wire time/);
    assert.match(text, /not the server-only figure/);
    assert.match(text, /proves nothing about load/);
    assert.match(text, /No Server-Timing header/);
  });

  it("does not report an empty run as a fast one", () => {
    const { text, result } = captured([]);
    assert.match(text, /nothing measured/);
    assert.match(text, /an instrument that saw nothing/);
    assert.deepEqual(result.misses, []);
  });

  it("calls out a row that answered outside 2xx", () => {
    const row = rowFrom("GET /api/t/accounts", [10, 12, 14]);
    row.nonOk = 2;
    const { text } = captured([row]);
    assert.match(text, /2 of 3 answered outside 2xx/);
    assert.match(text, /a fast error is not a fast endpoint/);
  });
});

describe("grouping: many URLs, one endpoint and one budget", () => {
  it("folds identifiers away and keeps the tenant", () => {
    assert.equal(
      endpointKey("GET", "http://h:4290/api/brazosbend/accounts/12/bills?page=2"),
      "GET /api/brazosbend/accounts/{id}/bills",
    );
    assert.equal(
      endpointKey("GET", "http://h:4290/api/brazosbend/accounts/4471/bills"),
      "GET /api/brazosbend/accounts/{id}/bills",
      "…so /12 and /4471 land in one row — one endpoint, one budget",
    );
    assert.equal(
      endpointKey("GET", "http://h/api/t/x/3fa85f64-5717-4562-b3fc-2c963f66afa6"),
      "GET /api/t/x/{id}",
    );
    assert.equal(
      endpointKey("GET", "http://h/api/oakridge/portal/public/front"),
      "GET /api/oakridge/portal/public/front",
      "the tenant slug is a word, not an id — hiding it would hide what hard rule 1 is about",
    );
    assert.notEqual(
      endpointKey("GET", "http://h/api/oakridge/portal/public/front"),
      endpointKey("GET", "http://h/api/pinehill/portal/public/front"),
      "two tenants must not silently share a row",
    );
  });

  it("keeps the method, because GET and POST on one path are two budgets", () => {
    assert.notEqual(endpointKey("GET", "http://h/api/t/payments"), endpointKey("POST", "http://h/api/t/payments"));
  });

  it("survives a relative or malformed url without throwing", () => {
    assert.equal(endpointKey("GET", "/api/t/accounts?q=1"), "GET /api/t/accounts");
  });
});
