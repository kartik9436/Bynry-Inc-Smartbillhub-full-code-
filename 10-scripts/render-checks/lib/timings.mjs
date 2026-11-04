/**
 * RESPONSE-TIME INSTRUMENT — what a walkthrough uses to print a number instead
 * of a claim. `CR-071`, `04-docs/05-modules/15-portal/11-response-times.md` §5.
 *
 * ⚠ **WHY THIS EXISTS.** §5 of the specification asks every portal endpoint's
 * walkthrough to *"record the measured time and print it, rather than asserting
 * that a target was met — a number a person can read beats a claim"*, and then
 * says what that costs: *"A failure here is reported, never rounded. If p95 for
 * the balance screen is 900 ms, the report says 900 ms against a 600 ms target
 * — it does not say 'meets target'."* Nothing in this repository did that, so
 * a target that reads as a specification was, until this file, a wish.
 *
 * ╔═══════════════════════════════════════════════════════════════════════════╗
 * ║ WHAT THIS FIGURE IS, AND — MORE IMPORTANTLY — WHAT IT IS NOT              ║
 * ╚═══════════════════════════════════════════════════════════════════════════╝
 *
 * The number in the table is `responseEnd − requestStart`, read from the
 * browser engine's own Resource Timing for the request: **the wire time**, from
 * the moment the bytes went out to the moment the last byte of the body came
 * back. `ttfb` is `responseStart − requestStart` — the closest thing a browser
 * can see to *"the server stopped thinking"*, and the figure `RT-5` asks for by
 * name.
 *
 * **IT IS NOT THE SERVER'S OWN TIME, WHICH IS WHAT §3 SPECIFIES.** §3 measures
 * *"from request received to response finished — excluding network and
 * rendering"*. A browser is on the wrong side of the wire to see that. So the
 * figure here is the server's time **plus** everything between the two, and a
 * later lane must not cite it as proof of §3:
 *
 *   INCLUDED and NOT the server's fault: one network round trip each way · the
 *   SPA's own `/api` pass-through hop (`07-frontend/server.mjs`) · any reverse
 *   proxy · TLS record processing · the kernel's socket buffers at both ends.
 *
 *   EXCLUDED and therefore NOT PROVEN by any figure here: DNS, connection and
 *   TLS handshake (they precede `requestStart`) · **the browser's own queueing
 *   and connection-limit stalling**, which is real latency a customer feels and
 *   this table cannot see · React rendering, layout and paint · the customer's
 *   phone, their signal, and the 80–600 ms of mobile network §1 of the
 *   specification says to leave room for.
 *
 * **THEREFORE:** a green-looking table here does NOT prove `RT-1`..`RT-8` are
 * met, and a run on this box proves nothing at all about `NFR-38`'s 500
 * concurrent users — §5 requires that figure under load, *"not on an idle
 * machine"*. What this instrument proves is narrower and still worth having:
 * *this endpoint, on this build, answered in this many milliseconds, this many
 * times.* Anything more is a claim, and §5 is about not making claims.
 *
 * There is one way to get closer, and it is left open rather than faked: if the
 * server ever emits a `Server-Timing: app;dur=…` header, `serverMs` below
 * carries it and the table prints it in its own column, clearly labelled as the
 * server's own report. Until then that column is absent, and its absence is the
 * honest statement that nobody measured the server directly.
 *
 * ╔═══════════════════════════════════════════════════════════════════════════╗
 * ║ THE SMALL-SAMPLE RULE — why a `p95` from three clicks is not a `p95`      ║
 * ╚═══════════════════════════════════════════════════════════════════════════╝
 *
 * A walkthrough clicks a screen once or twice. `p95` is the number §3 gates a
 * build on, and computed over two samples it is **arithmetically identical to
 * the slower of the two** — nearest rank `ceil(0.95 × 2) = 2`, which is the
 * maximum. It looks like a percentile and carries none of the information one
 * implies. Printed bare it will eventually be quoted as though it were.
 *
 * So every percentile is printed with the rank it came from, and two markers
 * derived from one rule — *how many observed requests sit at or above that
 * rank* — say what it is worth:
 *
 *   `!`  the rank IS the largest sample: there is no such percentile at this
 *        sample size. `p95` collapses to the maximum below **n = 20**, `p99`
 *        below **n = 100**. The row is also called out in words under the
 *        table, because a marker is easy to skim past.
 *   `~`  fewer than five samples sit at or above the rank, so one or two slow
 *        requests decide the figure on their own. (`p95` needs about **n = 80**
 *        before five do; `p99` about **n = 400**.)
 *   none five or more samples back it.
 *
 * The threshold is five, chosen once and applied to every percentile rather
 * than hand-tuned per column. Nothing magic about five; it is the point where a
 * single unlucky request stops being able to move the answer by itself, and
 * naming one rule beats three thresholds nobody can re-derive.
 * (Decision log 2026-09-04, with the worked figures.)
 *
 * **Nearest rank, never interpolation.** `pctl(p)` returns the
 * `ceil(p/100 × n)`-th smallest sample — a request that actually happened.
 * Interpolation invents a millisecond value nothing observed, which on a
 * two-sample screen is a comforting number between two real ones, and that is
 * the failure mode this whole file exists to avoid.
 *
 * ╔═══════════════════════════════════════════════════════════════════════════╗
 * ║ IT REPORTS. IT DOES NOT JUDGE.                                            ║
 * ╚═══════════════════════════════════════════════════════════════════════════╝
 *
 * `report()` never throws, never exits, and never prints a verdict on its own.
 * Pass `targets` and it prints the comparison — **measured figure first, target
 * second, and a miss reads as a miss with the gap in milliseconds.** There is
 * deliberately no `failOnMiss` option: an instrument that can fail a build on a
 * latency figure is an assertion, and §5 asked for the opposite. The caller
 * gets `result.misses` and decides for itself.
 *
 * And a comparison carries the marker's own sentence. Against a `!` percentile
 * it reads *"this comparison is not evidence either way"*, in BOTH directions —
 * a 120 ms "under" a 600 ms target drawn from two requests is not proof the
 * target is met. Against a `~` it reads *"treat the margin as softer than it
 * looks"*, which is a different and weaker statement on purpose: a 294 ms p95
 * under a 2000 ms target across 50 samples IS evidence. Giving both markers the
 * same sentence would teach a reader to skip the line.
 *
 * ── HOW TO USE IT ───────────────────────────────────────────────────────────
 *
 *   import { attachTimings } from "./lib/timings.mjs";
 *
 *   const timings = attachTimings(context);        // a Page or a BrowserContext
 *   …sign in, click the screens…
 *
 *   // To get a p95 that is a p95, ask for the screen twenty-plus times. A
 *   // reload is a real request through the real stack; a loop over
 *   // `page.goto()` is the cheapest honest sample there is:
 *   for (let i = 0; i < 30; i += 1) {
 *     await page.goto(`${BASE}/${TENANT}/accounts`, { waitUntil: "networkidle" });
 *   }
 *
 *   const result = await timings.report({
 *     title: "cr068 wave C — the balance screen",
 *     targets: [{ id: "RT-3", match: "/portal/me/balance", p95: 600 }],
 *   });
 *
 * ⚠ `report()` is **async** — `responseEnd` only exists once the request has
 * finished, so the recorder listens for `requestfinished` and settles its
 * pending status lookups before it prints. `await` it or the table is short.
 *
 * ⚠ **IT SEES ONLY WHAT THE BROWSER FETCHED.** `context.request.get(…)`
 * (Playwright's `APIRequestContext`) does not raise page events and is invisible
 * here, by design: those calls skip the SPA proxy and are a different
 * measurement. Drive the browser, or measure the two separately and say which
 * is which.
 *
 * ── Trace ──────────────────────────────────────────────
 * Rules:    `CR-071` · `11-response-times.md` §3 (what is measured), §5 (printed
 *           not asserted; reported never rounded) · `NFR-38` (the load figure
 *           this CANNOT prove) · CLAUDE.md hard-won law 1 of the first
 *           deployment (a comment claiming a guarantee is not the guarantee —
 *           hence the paragraph above about what this excludes)
 * Tests:    `10-scripts/tests/test_cr071_timings.mjs`
 * Impacts:  `10-scripts/render-checks/cr068-*.mjs` (G82) and any walkthrough
 *           that wants a number rather than a claim
 * ───────────────────────────────────────────────────────
 */

// ── The rank rule, in one place, so the tests and the table agree ────────────

/** How many samples must sit at or above a rank before it stops being decided
 *  by one unlucky request. One threshold, every percentile. */
export const BACKING_SAMPLES_WANTED = 5;

/** Nearest rank, 1-indexed: the `ceil(p/100 × n)`-th smallest sample. */
export function rankFor(p, n) {
  if (n <= 0) return 0;
  return Math.min(n, Math.max(1, Math.ceil((p / 100) * n)));
}

/**
 * The `p`-th percentile of `sorted` (ascending) by nearest rank — a value that
 * was actually observed, never an interpolated one.
 */
export function percentile(sorted, p) {
  if (sorted.length === 0) return null;
  return sorted[rankFor(p, sorted.length) - 1];
}

/**
 * What a percentile is worth at this sample size.
 *
 * Returns `{ rank, n, backing, marker, note }` where `backing` is how many
 * samples sit at or above the rank, `marker` is "!" (the rank IS the maximum,
 * so there is no such percentile here), "~" (fewer than five back it) or "",
 * and `note` is the sentence a person can read.
 */
export function rankHonesty(p, n) {
  if (n <= 0) return { rank: 0, n: 0, backing: 0, marker: "!", note: "no samples" };
  const rank = rankFor(p, n);
  const backing = n - rank + 1;
  if (rank >= n) {
    return {
      rank,
      n,
      backing,
      marker: "!",
      note: `NOT A p${p} — n=${n}, so this is simply the slowest of ${n}`,
    };
  }
  if (backing < BACKING_SAMPLES_WANTED) {
    return {
      rank,
      n,
      backing,
      marker: "~",
      note: `${ordinal(rank)} of ${n} — only the ${backing} slowest requests decide it`,
    };
  }
  return { rank, n, backing, marker: "", note: "" };
}

function ordinal(k) {
  const rest = k % 100;
  if (rest >= 11 && rest <= 13) return `${k}th`;
  return `${k}${["th", "st", "nd", "rd"][k % 10] ?? "th"}`;
}

// ── Grouping: many URLs, one endpoint ───────────────────────────────────────

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/**
 * The endpoint a URL belongs to: `GET /api/brazosbend/accounts/{id}/bills`.
 *
 * Identifier-looking segments — all digits, a uuid, or a long hex token —
 * become `{id}`, because `…/accounts/12` and `…/accounts/4471` are one endpoint
 * and one budget. The query string is dropped: `?page=2` is the same endpoint,
 * and `RT-4` is a statement about the endpoint, not about page two.
 *
 * The tenant slug is deliberately LEFT ALONE. It is a word, not an id, and a
 * table that hides which tenant was asked cannot show what `BR-CWP-005` and
 * hard rule 1 care about.
 */
export function endpointKey(method, rawUrl) {
  let pathname = rawUrl;
  try {
    pathname = new URL(rawUrl).pathname;
  } catch {
    pathname = String(rawUrl).split("?")[0];
  }
  const shaped = pathname
    .split("/")
    .map((segment) => {
      if (segment === "") return segment;
      if (/^\d+$/.test(segment)) return "{id}";
      if (UUID.test(segment)) return "{id}";
      if (/^[0-9a-f]{16,}$/i.test(segment)) return "{id}";
      return segment;
    })
    .join("/");
  return `${method} ${shaped}`;
}

// ── The recorder ────────────────────────────────────────────────────────────

/**
 * Attach to a Playwright `Page` or `BrowserContext` and record the wire time of
 * every matching response.
 *
 * @param target  a Page or a BrowserContext (a context covers every page it
 *                opens, which is what a walkthrough with a second tab wants)
 * @param options.match     RegExp or predicate over the URL. Default: `/\/api\//`
 * @param options.log       where lines go. Default: `console.log`
 */
export function attachTimings(target, options = {}) {
  const match = options.match ?? /\/api\//;
  const log = options.log ?? ((line) => console.log(line));
  const matches =
    typeof match === "function" ? match : (url) => match.test(url);

  const samples = [];
  const pending = [];
  let unmeasurable = 0;
  let attached = true;

  const onFinished = (request) => {
    let url;
    try {
      url = request.url();
    } catch {
      return;
    }
    if (!matches(url)) return;

    const t = request.timing();
    // `responseEnd` is only populated once the request has finished; a served-
    // from-cache or aborted request reports -1 and is counted, not invented.
    if (!t || t.requestStart < 0 || t.responseEnd < 0) {
      unmeasurable += 1;
      return;
    }
    const entry = {
      key: endpointKey(request.method(), url),
      url,
      method: request.method(),
      totalMs: t.responseEnd - t.requestStart,
      ttfbMs: t.responseStart >= 0 ? t.responseStart - t.requestStart : null,
      status: null,
      serverMs: null,
      at: Date.now(),
    };
    samples.push(entry);
    pending.push(
      (async () => {
        try {
          const response = await request.response();
          if (!response) return;
          entry.status = response.status();
          const header = await response.headerValue("server-timing");
          const dur = header && /dur\s*=\s*([\d.]+)/i.exec(header);
          if (dur) entry.serverMs = Number(dur[1]);
        } catch {
          // a navigation that tore the page down takes the status with it; the
          // wire time is still true and is kept.
        }
      })(),
    );
  };

  target.on("requestfinished", onFinished);

  const recorder = {
    samples,

    /** Stop listening. Safe to call twice. */
    detach() {
      if (!attached) return;
      attached = false;
      target.off("requestfinished", onFinished);
    },

    /** Await the status/`Server-Timing` lookups still in flight. */
    async settle() {
      while (pending.length > 0) {
        const batch = pending.splice(0, pending.length);
        await Promise.allSettled(batch);
      }
    },

    /** Throw away everything recorded so far — e.g. after signing in, when the
     *  interesting screen has not been opened yet. */
    reset() {
      samples.length = 0;
      unmeasurable = 0;
    },

    /** One row per endpoint, sorted slowest-p95 first. Pure data, no printing. */
    rows() {
      return buildRows(samples);
    },

    /**
     * Print the table. Never throws, never exits, never returns a verdict.
     * @returns `{ rows, misses, unmeasurable }`
     */
    async report(reportOptions = {}) {
      await recorder.settle();
      return printReport(buildRows(samples), {
        ...reportOptions,
        unmeasurable,
        log,
      });
    },
  };

  return recorder;
}

function buildRows(samples) {
  const byKey = new Map();
  for (const sample of samples) {
    if (!byKey.has(sample.key)) byKey.set(sample.key, []);
    byKey.get(sample.key).push(sample);
  }
  const rows = [];
  for (const [key, group] of byKey) {
    const totals = group.map((s) => s.totalMs).sort((a, b) => a - b);
    const ttfbs = group
      .map((s) => s.ttfbMs)
      .filter((v) => v !== null)
      .sort((a, b) => a - b);
    const servers = group
      .map((s) => s.serverMs)
      .filter((v) => v !== null)
      .sort((a, b) => a - b);
    rows.push({
      key,
      n: totals.length,
      p50: percentile(totals, 50),
      p95: percentile(totals, 95),
      p99: percentile(totals, 99),
      min: totals[0],
      max: totals[totals.length - 1],
      ttfbP95: percentile(ttfbs, 95),
      serverP95: percentile(servers, 95),
      serverSamples: servers.length,
      nonOk: group.filter((s) => s.status !== null && (s.status < 200 || s.status >= 300)).length,
      honesty: {
        p50: rankHonesty(50, totals.length),
        p95: rankHonesty(95, totals.length),
        p99: rankHonesty(99, totals.length),
      },
    });
  }
  rows.sort((a, b) => (b.p95 ?? 0) - (a.p95 ?? 0));
  return rows;
}

const ms = (v) => (v === null || v === undefined ? "—" : `${Math.round(v)}`);
const pad = (s, width) => String(s).padEnd(width);
const padLeft = (s, width) => String(s).padStart(width);

/**
 * Render the table. Split out from `attachTimings` so the tests can drive it
 * over a known set of rows without a browser.
 */
export function printReport(rows, options = {}) {
  const log = options.log ?? ((line) => console.log(line));
  const targets = options.targets ?? [];
  const unmeasurable = options.unmeasurable ?? 0;

  log("");
  log(`── ${options.title ?? "measured response times"} ──`);

  if (rows.length === 0) {
    log("   nothing measured — no matching response reached the browser.");
    log("   (a report with no rows is not a fast product; it is an instrument that saw nothing)");
    return { rows, misses: [], unmeasurable };
  }

  const anyServer = rows.some((r) => r.serverSamples > 0);
  const keyWidth = Math.max(8, ...rows.map((r) => r.key.length));

  const head =
    `   ${pad("endpoint", keyWidth)}  ${padLeft("n", 4)}  ${padLeft("p50", 7)}  ` +
    `${padLeft("p95", 7)}  ${padLeft("p99", 7)}  ${padLeft("max", 6)}  ${padLeft("ttfb p95", 9)}` +
    (anyServer ? `  ${padLeft("server p95", 11)}` : "");
  log(head);
  log(`   ${"─".repeat(head.length - 3)}`);

  for (const row of rows) {
    const cell = (value, honesty) => padLeft(`${ms(value)}${honesty.marker}`, 7);
    log(
      `   ${pad(row.key, keyWidth)}  ${padLeft(row.n, 4)}  ` +
        `${cell(row.p50, row.honesty.p50)}  ${cell(row.p95, row.honesty.p95)}  ` +
        `${cell(row.p99, row.honesty.p99)}  ${padLeft(ms(row.max), 6)}  ` +
        `${padLeft(ms(row.ttfbP95), 9)}` +
        (anyServer
          ? `  ${padLeft(row.serverSamples > 0 ? ms(row.serverP95) : "—", 11)}`
          : ""),
    );
  }

  log("");
  log("   all figures are MILLISECONDS of wire time (responseEnd − requestStart) as the");
  log("   browser saw it — the server's time PLUS both network legs and the SPA's /api hop.");
  log("   It is not the server-only figure §3 specifies, and it proves nothing about load.");
  if (!anyServer) {
    log("   No Server-Timing header was served, so nobody measured the server directly.");
  }
  if (unmeasurable > 0) {
    log(`   ${unmeasurable} matching request(s) reported no usable timing (cache or abort) and are not counted.`);
  }
  const badRows = rows.filter((r) => r.nonOk > 0);
  for (const row of badRows) {
    log(`   ⚠ ${row.key}: ${row.nonOk} of ${row.n} answered outside 2xx — a fast error is not a fast endpoint.`);
  }

  // ── the small-sample sentences, in words, not just as markers ─────────────
  log("");
  log("   ! this percentile IS the largest sample — at this n there is no such rank.");
  log("   ~ fewer than five samples sit at or above the rank, so one or two decide it.");
  const notReally = rows.filter((r) => r.honesty.p95.marker === "!");
  if (notReally.length > 0) {
    log("");
    log("   READ THIS BEFORE QUOTING A p95 FROM THIS TABLE:");
    for (const row of notReally) {
      log(`   · ${row.key} — ${row.honesty.p95.note}. Ask for the screen 20+ times for a p95, 100+ for a p99.`);
    }
  }

  // ── targets: measured first, always, and a miss reads as a miss ───────────
  const misses = [];
  if (targets.length > 0) {
    log("");
    log("   against the targets in 11-response-times.md §3 — reported, never rounded:");
    for (const target of targets) {
      const row = rows.find((r) => matchesTarget(r.key, target.match));
      if (!row) {
        log(`   · ${target.id ?? target.match}: NOT MEASURED on this run — no matching request was made.`);
        continue;
      }
      for (const p of [50, 95, 99]) {
        const wanted = target[`p${p}`];
        if (wanted === undefined) continue;
        const got = row[`p${p}`];
        const honesty = row.honesty[`p${p}`];
        const gap = Math.round(got - wanted);
        const verdict =
          gap > 0 ? `OVER by ${gap} ms` : `under by ${Math.abs(gap)} ms`;
        let line =
          `   · ${target.id ?? ""} ${row.key} — p${p} MEASURED ${Math.round(got)} ms` +
          ` against a ${wanted} ms target · ${verdict}`;
        // ⚠ THE TWO MARKERS DESERVE DIFFERENT SENTENCES, AND THE FIRST DRAFT GAVE
        // THEM THE SAME ONE. "!" means there is no such percentile at this sample
        // size, so the comparison decides nothing in either direction. "~" means
        // the percentile is real but a couple of requests carry it — a 294 ms p95
        // under a 2000 ms target across 50 samples IS evidence; it is just not a
        // figure to quote to four significant places. Calling both "not evidence"
        // would train a reader to skip the line.
        if (honesty.marker === "!") {
          line += `\n       …but ${honesty.note}, so this comparison is not evidence either way.`;
        } else if (honesty.marker === "~") {
          line += `\n       …though ${honesty.note}, so treat the margin as softer than it looks.`;
        }
        log(line);
        if (gap > 0) {
          misses.push({ id: target.id ?? null, key: row.key, p, measured: got, target: wanted, gap });
        }
      }
    }
    log("");
    log("   Nothing above fails this run. §5: the walkthrough reports the number; a");
    log("   target that is missed is a defect somebody files, not an exception thrown here.");
  }

  return { rows, misses, unmeasurable };
}

function matchesTarget(key, match) {
  if (match instanceof RegExp) return match.test(key);
  return key.includes(String(match));
}
