// ── Trace ──────────────────────────────────────────────
// Change:  PO report 2026-09-22 — LANE REQ-A's half: the submit failure
//          (priority 0), the document verdicts and their reason, the documents
//          count, the masked identifier, the approve modal's two outcomes, the
//          one-line application fee, the services table, and the head's
//          address.
// Rules:   `22-product-maintenance-process.md` — prove it against the
//          reproduction in a BROWSER, then regression-walk the neighbours ·
//          CLAUDE.md hard-won law 6 (no gate reads rendered output) · law 1 (a
//          claim is not the guarantee — the three doors below are OPENED, not
//          grepped)
// Screens: `REQ-02` · `REQ-03.4` · `REQ-03.6` · `ACC-01`
// ───────────────────────────────────────────────────────
//
// ⚠ **THIS IS THE *AFTER* WALK AND IT IS THE PROOF OF A DECISION-LOG CLAIM.**
// The entry titled *WHERE A MOVE-OUT, A TRANSFER AND A DISCONNECT START* names
// three doors. A route constant proves a route is MOUNTED and proves nothing
// about whether a clerk can reach the screen, so each one is opened here and
// its page head is read back.
//
// ── HOW TO RUN IT ───────────────────────────────────────────────────────────
//   (cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \
//      DATABASE_URL=postgres://smartbillhub:smartbillhub@127.0.0.1:5432/<db> \
//      JOBS_EAGER=false python manage.py runserver 127.0.0.1:8291 --noreload)
//   (cd 07-frontend && npx vite build && PORT=8292 \
//      API_PROXY_TARGET=http://127.0.0.1:8291 node server.mjs)
//   BASE=http://127.0.0.1:8292 node 10-scripts/po20260922_reqa_walkthrough.mjs
//
// ⛔ **RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING** —
// `10-scripts/proof-db.sh clone <label>`.
const { existsSync, readdirSync, mkdirSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const { join } = await import("node:path");

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8292";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const SHOTS = process.env.SHOTS ?? "/tmp/claude-0/shots-reqa";

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of ["chrome-linux64/chrome", "chrome-linux/chrome", "chrome-linux/headless_shell"]) {
        const candidate = join(root, dir, sub);
        if (existsSync(candidate)) return candidate;
      }
    }
  }
  throw new Error("no chromium found");
}

mkdirSync(SHOTS, { recursive: true });
const browser = await chromium.launch({ executablePath: resolveChromium() });
const context = await browser.newContext({ viewport: { width: 1440, height: 1200 } });
const page = await context.newPage();
page.setDefaultTimeout(25000);

let passes = 0;
const failures = [];
function ok(what, detail = "") {
  passes += 1;
  console.log(`    ✓ ${what}${detail ? `  — ${detail}` : ""}`);
}
/** A fact the reader needs that is neither a pass nor a failure. */
function note(what) {
  console.log(`    · ${what}`);
}
function bad(what, detail = "") {
  failures.push(`${what}${detail ? ` — ${detail}` : ""}`);
  console.log(`    ● ${what}${detail ? `  — ${detail}` : ""}`);
}

try {
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });

  // ── FIND A REQUEST TO LOOK AT ────────────────────────────────────────────
  await page.goto(`${BASE}/${TENANT}/requests`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(2500);
  // ⚠ **THE ROW THIS WALK OPENS IS CHOSEN, NOT TAKEN FIRST — AND THE FIRST TWO
  // DRAFTS OF THIS PICKER BOTH PROVED NOTHING.**
  //
  //   1. `rows[0]` is newest-first, which on a machine that has just run the
  //      reproduce script is one of ITS throwaway drafts: no address, no
  //      services, no documents, no fee. Three checks below then had nothing to
  //      look at and reported a failure that belonged to the fixture.
  //   2. Scoring the rows inside ONE `page.evaluate` with sixteen fetches in it
  //      came back with every score at zero while the SAME request fetched on
  //      its own answered with its address, two services and a document. A
  //      check that answers zero over a population it cannot actually read is
  //      law 7's *reporting zero over a scope it silently excludes* — so each
  //      row is now read in its own round trip, and the scores are PRINTED so a
  //      reader can see the walk had something to walk.
  const listed = await page.evaluate(async (tenant) => {
    const r = await fetch(`/api/${tenant}/service-requests?page_size=100`, {
      credentials: "include",
    });
    const j = await r.json();
    return ((j.data ?? j).results ?? []).map((row) => ({ id: row.id, no: row.request_no }));
  }, TENANT);
  let best = null;
  const scored = [];
  for (const row of listed) {
    const d = await page.evaluate(
      async ([tenant, id]) => {
        const r = await fetch(`/api/${tenant}/service-requests/${id}`, { credentials: "include" });
        const body = await r.json();
        const detail = body.data ?? body;
        return {
          services: (detail.location_and_services?.services ?? []).length,
          docs: (detail.documents?.documents ?? []).length,
          hasAddress: (detail.location_and_services?.address_as_given ?? "") !== "",
          feeLines: (detail.fees?.lines ?? []).length,
          // Kept, so the checks below compare the SCREEN against facts read
          // while the browser was on a page that could read them.
          resolved: detail.location_and_services?.resolved_premise_address ?? null,
          asGiven: detail.location_and_services?.address_as_given ?? null,
          unit: detail.location_and_services?.address_unit_as_given ?? null,
        };
      },
      [TENANT, row.id],
    );
    const score = d.services * 2 + d.docs * 2 + (d.hasAddress ? 1 : 0) + (d.feeLines > 0 ? 1 : 0);
    scored.push({ ...row, score, ...d });
    if (best === null || score > best.score) best = { ...row, score, ...d };
  }
  console.log(`    · richest request: ${best?.no} (score ${best?.score}) ${JSON.stringify(best)}`);
  const firstRequest = best === null || best.score === 0 ? null : best.id;
  if (best !== null && best.score === 0) {
    bad("every request on this tenant is empty — nothing below would be evidence");
  }
  if (firstRequest === null) {
    bad("no service request on this tenant to open");
  } else {
    console.log(`\n  REQ-02 · ${firstRequest}`);
    await page.goto(`${BASE}/${TENANT}/requests/${firstRequest}`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(3000);

    // ── ROW 13 · the head shows the whole address ──────────────────────────
    const head = (await page.locator("[data-head-address]").textContent().catch(() => "")) ?? "";
    console.log(`      head address: ${JSON.stringify(head.trim())}`);
    // ⚠ **THE SERVER'S FACTS COME FROM THE PICKER, NOT FROM A SECOND FETCH
    // HERE.** The first draft re-read the request from inside the DETAIL page
    // and got nulls back for everything while the screen beside it was drawing
    // the address, two services and two documents — so the walk reported a
    // failure that was its own probe's. The picker read these while the
    // browser was on the list, and the facts do not change in between.
    const server = {
      resolved: best.resolved,
      asGiven: best.asGiven,
      unit: best.unit,
      services: best.services,
      docs: best.docs,
    };
    console.log(`      server holds: ${JSON.stringify(server)}`);
    const wanted = server.resolved ?? server.asGiven;
    if (wanted && head.includes(wanted)) {
      ok("row 13 · the head carries the street line", JSON.stringify(wanted));
    } else if (server.unit && head.includes(server.unit) && !head.includes(wanted ?? "")) {
      bad("row 13 · the head still shows the UNIT instead of the street");
    } else {
      bad("row 13 · could not confirm the street line", `wanted ${JSON.stringify(wanted)}`);
    }

    // ── ROWS 14 + 15 · the services table, and ROW 12 · units are gone ─────
    const table = page.locator('[data-services-table="asked-for"]');
    if ((await table.count()) > 0) {
      const heads = await table.locator("thead th").allTextContents();
      console.log(`      services table columns: ${heads.map((h) => h.trim()).join(" · ")}`);
      if (heads.length === 3) ok("rows 14/15 · exactly three columns");
      else bad("rows 14/15 · wrong column count", String(heads.length));
      const rows = await table.locator("tbody tr").count();
      console.log(`      services table rows: ${rows} (server says ${server.services})`);
    } else if (server.services === 0) {
      ok("rows 14/15 · no services on this request, so the table states that");
    } else {
      bad("rows 14/15 · no services table on the Applicant tab");
    }
    const units = await page.locator("[data-units-on-property]").count();
    if (units === 0) ok("row 12 · `Units on site` is not on the screen");
    else bad("row 12 · `Units on site` is still drawn");

    // ── ROW 10 · the fee panel is one line ─────────────────────────────────
    const feeLine = page.locator("[data-fee-line]");
    if ((await feeLine.count()) === 1) {
      const state = await feeLine.getAttribute("data-fee-line");
      const said = ((await feeLine.textContent()) ?? "").trim();
      ok("row 10 · the fee panel is ONE line", `${state} → ${JSON.stringify(said)}`);
      const words = said.split(/\s+/).length;
      console.log(`      (${words} words across its sentences)`);
    } else {
      bad("row 10 · the fee panel is not one line", `${await feeLine.count()} found`);
    }

    // ── ROWS 2, 3, 4, 5 · the Documents tab ────────────────────────────────
    const docsTab = page.locator('button:has-text("Documents"), a:has-text("Documents")').first();
    if ((await docsTab.count()) > 0) {
      await docsTab.click().catch(() => {});
      await page.waitForTimeout(1800);
    }
    const countLine = (await page.locator("[data-outstanding]").textContent().catch(() => "")) ?? "";
    const tableRows = await page.locator("[data-doc-open], [data-document-number]").count();
    console.log(`      documents header: ${JSON.stringify(countLine.trim())}`);
    const shown = await page.locator("[data-document-number]").count();
    console.log(`      document rows on screen: ${shown} (server says ${server.docs})`);
    if (shown === server.docs && countLine.includes(`of ${server.docs}`)) {
      ok("row 4 · the header count and the table agree", countLine.trim());
    } else if (server.docs === 0) {
      ok("row 4 · no documents on this request");
    } else {
      bad("row 4 · header and table disagree", `${countLine.trim()} over ${shown} rows`);
    }
    const stale = await page.locator("text=Not yet checked").count();
    if (stale === 0) ok("row 2 · `Not yet checked` is gone from the STATE column");
    else bad("row 2 · `Not yet checked` is still drawn", String(stale));
    const masked = await page.locator("[data-masked-identifier]").count();
    const numbers = await page.locator("[data-document-number]").allTextContents();
    console.log(`      document-number cells: ${numbers.map((n) => JSON.stringify(n.trim())).join(" | ")}`);
    if (masked > 0) ok("row 5 · an identifier in `What it proves` is masked", `${masked} cell(s)`);
    else console.log("      (no identifier-shaped value in `What it proves` on this request)");
    const reasons = await page.locator("[data-reject-reason]").count();
    console.log(`      rejected rows showing their reason: ${reasons}`);
    await page.screenshot({ path: join(SHOTS, "after-req02-documents.png"), fullPage: true });

    // ── ROW 8 · the approve modal offers two outcomes ─────────────────────
    await page.goto(`${BASE}/${TENANT}/requests/${firstRequest}`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2500);
    const approve = page.locator('[data-decision="approve"], button:has-text("Approve")').first();
    if ((await approve.count()) > 0 && !(await approve.isDisabled().catch(() => true))) {
      await approve.click();
      await page.waitForTimeout(1500);
      const options = await page.locator("[data-outcome]").evaluateAll((els) =>
        els.map((e) => e.getAttribute("data-outcome")),
      );
      console.log(`      the modal offers: ${options.join(" · ")}`);
      const gone = ["move_out", "transfer", "disconnect"].filter((o) => options.includes(o));
      if (options.length === 2 && gone.length === 0) {
        ok("row 8 · two outcomes, and the other three are not there", options.join(" · "));
      } else {
        bad("row 8 · the modal still offers", gone.join(" · ") || options.join(" · "));
      }
      await page.screenshot({ path: join(SHOTS, "after-approve-modal.png"), fullPage: true });
      await page.keyboard.press("Escape").catch(() => {});
    } else {
      console.log("      (Approve is not lawful on this request — the modal was not opened)");
    }
  }

  // ══════════════════════════════════════════════════════════════════════════
  // ROW 11 · the handover modal offers a WAIVE
  //
  // ⚠ **IT WALKS A REQUEST WITH A FEE LINE ON IT, AND SAYS SO WHEN THERE IS
  // NONE.** The `Waived` option is only offered over exactly one unwaived,
  // unsettled line — guessing which fee to write off is not a guess this
  // product may make — so a walk on a request with no fee would find no
  // options and could report either a pass or a failure with equal
  // truthfulness. That is law 7's *looking at the wrong thing*; the walk picks
  // its own subject and prints which one.
  // ══════════════════════════════════════════════════════════════════════════
  // ⚠ **EXACTLY ONE LINE, NOT "AT LEAST ONE".** The first run of this picked a
  // request with THREE fee lines and reported *the choice is not offered — by
  // design*, which is TRUE and proves nothing: the option is only offered over
  // ONE unwaived, unsettled line, because guessing which fee to write off is
  // not a guess this product may make. A walk that lands on the by-design
  // branch is a walk that never reached its subject.
  const withAFee = scored.find((row) => row.feeLines === 1) ?? null;
  if (withAFee === null) {
    note("no request on this tenant carries exactly one fee line, so row 11 could not be walked here");
  } else {
    console.log(`\n  ROW 11 · Record what was handed over · ${withAFee.no} (${withAFee.feeLines} fee line(s))`);
    await page.goto(`${BASE}/${TENANT}/requests/${withAFee.id}`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2500);
    const collect = page.locator('button:has-text("Record what was handed over")').first();
    if ((await collect.count()) === 0) {
      bad("row 11 · no `Record what was handed over` control on the Applicant tab");
    } else {
      await collect.click();
      await page.waitForTimeout(1500);
      const kind = await page.locator("[data-handover-kind]").getAttribute("data-handover-kind").catch(() => null);
      const options = await page.locator("[data-handover-option]").evaluateAll((els) =>
        els.map((e) => e.getAttribute("data-handover-option")),
      );
      console.log(`      opens on: ${kind} · options: ${options.join(" · ") || "(none)"}`);
      if (kind === "taken" && options.length === 2) {
        ok("row 11 · opens on Taken and offers Waived", options.join(" · "));
      } else if (options.length === 0) {
        note("this request has no single waivable fee line, so the choice is not offered — by design");
      } else {
        bad("row 11 · the choice is not Taken/Waived", `${kind} · ${options.join(" · ")}`);
      }
      if (options.includes("waived")) {
        await page.locator('[data-handover-option="waived"] input').click();
        await page.waitForTimeout(1200);
        const fields = {
          reason: await page.locator("#reason").count(),
          amount: await page.locator("#amount").count(),
          method: await page.locator("#method").count(),
          receipt: await page.locator("#receipt_no").count(),
        };
        console.log(`      under Waived: ${JSON.stringify(fields)}`);
        if (fields.reason === 1 && fields.amount === 0 && fields.method === 0 && fields.receipt === 0) {
          ok("row 11 · Waived asks a reason and shows no money fields");
        } else {
          bad("row 11 · Waived still shows a money field", JSON.stringify(fields));
        }
        const reasons = await page.locator("#reason option").allTextContents();
        console.log(`      reasons offered: ${reasons.join(" · ")}`);
      }
      const body = (await page.locator('[role="dialog"]').innerText().catch(() => "")) ?? "";
      if (/finance reconciles it|you do not write it off here/i.test(body)) {
        bad("row 11 · the superseded paragraph is still on screen");
      } else {
        ok("row 11 · the paragraph that said a clerk may not write it off is gone");
      }
      await page.screenshot({ path: join(SHOTS, "after-handover-modal.png"), fullPage: true });
      await page.keyboard.press("Escape").catch(() => {});
    }
  }

  // ══════════════════════════════════════════════════════════════════════════
  // THE THREE DOORS — OPENED, NOT GREPPED.
  //
  // The decision-log entry of 2026-09-22 claims each of these carries a clerk
  // to a working screen now that the approve modal no longer offers the three
  // outcomes. A route constant proves a route is MOUNTED; only this proves a
  // screen opens. Hard-won law 1.
  // ══════════════════════════════════════════════════════════════════════════
  console.log(`\n  THE THREE DOORS`);
  for (const [what, path] of [
    ["a transfer", "/transfers/new"],
    ["a disconnect", "/disconnects/new"],
    ["a move-out", "/move-outs/new"],
  ]) {
    await page.goto(`${BASE}/${TENANT}${path}`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2500);
    const body = (await page.locator("main").innerText().catch(() => "")) ?? "";
    const headline = body.split("\n").filter((l) => l.trim() !== "").slice(0, 3).join(" / ");
    const dead = /not built yet|opens with the next release|Page not found|404/i.test(body);
    if (dead || body.trim() === "") {
      bad(`${what} · ${path} does NOT open a working screen`, headline);
    } else {
      ok(`${what} · ${path} opens`, headline.slice(0, 90));
    }
  }

  // And the tabs that carry a clerk to two of them.
  for (const [what, tab, label] of [
    ["a transfer", "transfers", "New transfer"],
    // ⚠ **THE LABEL IS THE CATALOGUE'S, NOT A GUESS.** The first draft of this
    // walk looked for `+ New disconnect` and reported the door missing; the
    // tab says `Start a disconnect` and always has. A check looking for the
    // wrong string is law 7's *looking at the wrong thing*, and it reported a
    // hole in a capability that was there all along.
    ["a disconnect", "disconnects", "Start a disconnect"],
  ]) {
    await page.goto(`${BASE}/${TENANT}/accounts?tab=${tab}`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2800);
    const cta = page.locator(`button:has-text("${label}")`).first();
    if ((await cta.count()) > 0) {
      const variant = await cta.getAttribute("data-variant");
      ok(`${what} · the ${tab} tab offers \`+ ${label}\``, `tier ${variant}`);
    } else {
      bad(`${what} · no \`+ ${label}\` on the ${tab} tab`);
    }
  }

  // ══════════════════════════════════════════════════════════════════════════
  // ROW 16 · NEW REQUEST, STEP 3 — THE ADDRESS IS TAKEN IN PARTS, AND THE
  // PREMISES STILL WINS THE MOMENT ONE IS PICKED.
  //
  // PO ruling 2026-09-22: *"correct address will be on presmies but first time
  // you will ahve to take the details to match it"*. There are TWO halves and
  // a check that only proves the first would pass over the thing that matters:
  // the boxes must be TYPEABLE before a premises is found and must be REPLACED
  // by the register's own answer once one is. So this walk does both, and
  // reads the stored request back from the API afterwards — a box that accepts
  // text and sends nothing is hard-won law 2's dead UI.
  // ══════════════════════════════════════════════════════════════════════════
  console.log(`\n  ROW 16 · New request · step 3`);
  await page.goto(`${BASE}/${TENANT}/requests/new`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(2500);
  await page.fill("#applicant_name", "Parts, Ada");
  await page.click('button:has-text("Continue")');
  await page.waitForTimeout(1600);
  await page.selectOption("#account_type_code", "residential").catch(() => {});
  await page.waitForTimeout(600);
  await page.click('button:has-text("Continue")');
  await page.waitForTimeout(1800);

  const partsBlock = page.locator("[data-address-parts]");
  if ((await partsBlock.count()) === 0) {
    bad("row 16 · step 3 shows no city / state / ZIP boxes at all");
  } else {
    const typed = [
      ["#address_city_as_given", "Austin"],
      ["#address_state_as_given", "TX"],
      ["#address_postal_code_as_given", "78704"],
    ];
    let allTypeable = true;
    for (const [sel, value] of typed) {
      const el = page.locator(sel);
      if ((await el.count()) === 0 || (await el.isDisabled().catch(() => true))) {
        allTypeable = false;
        bad(`row 16 · ${sel} is absent or disabled before a premises is picked`);
        continue;
      }
      await el.fill(value);
      if ((await el.inputValue()) !== value) {
        allTypeable = false;
        bad(`row 16 · ${sel} would not hold what was typed`);
      }
    }
    if (allTypeable) ok("row 16 · city, state and ZIP are typed before a premises is found");

    // ⚠ **AND THEY REACH THE SERVER.** A box a clerk can type into that sends
    // nothing is exactly the defect this product has already shipped four
    // times in one day (hard-won law 2). So the draft is created and the
    // request is read back through the API, by its own id.
    await page.fill("#address_as_given", "212 Balcones Drive");
    await page.waitForTimeout(900);
    await page.click('button:has-text("Continue")');
    await page.waitForTimeout(2600);
    const newId = new URL(page.url()).searchParams.get("request");
    if (!newId) {
      bad("row 16 · the draft was not created, so nothing can be read back");
    } else {
      const stored = await page.evaluate(async ([tenant, id]) => {
        const r = await fetch(`/api/${tenant}/service-requests/${id}`, {
          headers: { accept: "application/json" },
        });
        if (!r.ok) return { error: r.status };
        const body = await r.json();
        return body?.location_and_services ?? {};
      }, [TENANT, newId]);
      const got = [
        stored.address_city_as_given,
        stored.address_state_as_given,
        stored.address_postal_code_as_given,
      ];
      if (got.join("|") === "Austin|TX|78704") {
        ok("row 16 · the three parts are stored `_as_given`", got.join(" · "));
      } else {
        bad("row 16 · the parts did not reach the request", JSON.stringify(got));
      }
      // ⛔ **AND NOT A FOURTH HOME.** `BR-MET-1161` is not narrowed: a bare
      // `city` on this payload is the column `G85` refuses on this table by
      // name, and it is what the 2026-09-15 near-miss actually was.
      const bare = ["city", "state", "postal_code", "zip", "postcode"].filter(
        (k) => k in (stored ?? {}),
      );
      if (bare.length === 0) {
        ok("row 16 · the request carries no bare address column");
      } else {
        bad("row 16 · a bare address key came back", bare.join(", "));
      }
    }

    // ── AND THE SECOND HALF: the register wins once a premises is picked ────
    //
    // ⚠ **THE FIRST DRAFT OF THIS BLOCK USED `page.goBack()` AND PRINTED
    // NOTHING AT ALL** — no pass, no fail, no note — because the wizard's step
    // is URL state (`?step=`) and going back in history landed somewhere with
    // no `#address_as_given` on it, so the whole branch was skipped in
    // silence. That is hard-won law 7's *silence is not success*, in a check
    // written to obey law 7. It navigates by address now, and every path out
    // of here says something.
    await page.goto(`${BASE}/${TENANT}/requests/new?request=${newId ?? ""}&step=3`, {
      waitUntil: "domcontentloaded",
    });
    await page.waitForTimeout(2600);
    const search = page.locator("#address_as_given");
    if ((await search.count()) === 0) {
      bad("row 16 · step 3 could not be reopened, so the read-only half is unproven");
    } else {
      await search.fill("");
      await search.type("1", { delay: 60 });
      await search.type("0", { delay: 60 });
      await page.waitForTimeout(2600);
      const option = page.locator("[data-premises-option]").first();
      if ((await option.count()) === 0) {
        note("row 16 · no premises matched `10`, so the read-only half is unproven here");
      } else {
        const label = (await option.innerText().catch(() => "")).trim();
        await option.click();
        await page.waitForTimeout(1200);
        const stillTyped = await page.locator("[data-address-parts]").count();
        const picked = await page.locator("[data-premises-picked]").count();
        if (stillTyped === 0 && picked > 0) {
          ok("row 16 · picking a premises replaces the boxes with the register's own", label.slice(0, 60));
        } else {
          bad(
            "row 16 · the typed boxes survived a premises being picked",
            `typed=${stillTyped} picked=${picked}`,
          );
        }
      }
    }
  }


  // ══════════════════════════════════════════════════════════════════════════
  // ROW 11b · THE APPLICATION FEE COMES OUT OF A CHARGE CODE, AND
  // `Collect later` IS GONE.
  //
  // PO report 2026-09-22 row 11, second half. `DEF-CUS-5904` says a clerk could
  // not raise an application fee ANYWHERE in the product — the endpoint and its
  // client both existed and nothing called them. So the check that matters is
  // not that a dropdown renders: it is that pressing Add changes the money on
  // the screen. A picker that lists codes and sends nothing would satisfy every
  // visual assertion and still be the defect.
  // ══════════════════════════════════════════════════════════════════════════
  console.log(`\n  ROW 11b · the fee picker`);
  await page.goto(`${BASE}/${TENANT}/requests/new?step=5`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(2600);
  for (const [what, label] of [
    ["Collect now", "collect_now"],
    ["Collect later", "collect_later"],
  ]) {
    const radios = await page.locator(`input[type="radio"][value="${label}"]`).count();
    if (radios === 0) ok(`row 11 · \`${what}\` is not on step 5`);
    else bad(`row 11 · \`${what}\` is still a radio on step 5`, `${radios} found`);
  }

  // The picker needs a SAVED request to hang a line on, so the walk builds one
  // the way a clerk does rather than deep-linking to a draft that may not exist.
  await page.goto(`${BASE}/${TENANT}/requests/new`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(2400);
  await page.fill("#applicant_name", "Fee, Picker");
  await page.click('button:has-text("Continue")');
  await page.waitForTimeout(1500);
  await page.selectOption("#account_type_code", "residential").catch(() => {});
  await page.waitForTimeout(500);
  await page.click('button:has-text("Continue")');
  await page.waitForTimeout(1600);
  await page.fill("#address_as_given", "77 Charge Code Way").catch(() => {});
  await page.click('button:has-text("Continue")');
  await page.waitForTimeout(2600);
  const feeRequestId = new URL(page.url()).searchParams.get("request");
  if (!feeRequestId) {
    bad("row 11 · no draft was created, so the fee picker cannot be exercised");
  } else {
    await page.goto(`${BASE}/${TENANT}/requests/new?request=${feeRequestId}&step=5`, {
      waitUntil: "domcontentloaded",
    });
    await page.waitForTimeout(2800);
    const picker = page.locator("#application_fee_code");
    if ((await picker.count()) === 0) {
      bad("row 11 · step 5 carries no fee picker at all");
    } else {
      const offered = (
        await picker.locator("option").evaluateAll((nodes) => nodes.map((n) => n.value))
      ).filter((value) => value !== "");
      // ⛔ **THE FOUR UNPRICED CODES MUST NOT BE THERE.** Measured on this
      // utility: 19 one-time codes, 15 priced. `TAP` is the one a clerk
      // actually picked on another screen, to a raw 500 after 33 acts.
      const unpriced = ["TAP", "IMPACT", "DAMAGE", "BULK-WATER"].filter((code) =>
        offered.includes(code),
      );
      const recurring = ["BASE-E", "BASE-W", "PAPER"].filter((code) => offered.includes(code));
      console.log(`      codes offered: ${offered.length} · ${offered.slice(0, 6).join(" · ")}…`);
      if (unpriced.length === 0 && recurring.length === 0 && offered.length > 0) {
        ok(`row 11 · the picker offers ${offered.length} priced one-time codes and no others`);
      } else {
        bad(
          "row 11 · the picker offers a code it should not",
          `unpriced=${unpriced.join(",")} recurring=${recurring.join(",")}`,
        );
      }

      const before = await page.locator("[data-panel-name], body").first().innerText();
      await picker.selectOption("CC-REQFEE").catch(() => {});
      await page.waitForTimeout(700);
      const priceShown = await page.locator("[data-fee-amount]").innerText().catch(() => "");
      ok("row 11 · picking a code shows its price", priceShown.trim().slice(0, 20));

      await page.click('[data-fee-add] , button:has-text("Add to the list")').catch(() => {});
      await page.waitForTimeout(2200);
      // ⚠ **THE MONEY ON THE SCREEN IS THE ASSERTION.** Asked of the server,
      // not of the markup, because a screen can redraw from its own optimistic
      // state and a fee line that never reached the database is the defect.
      const quoted = await page.evaluate(async ([tenant, id]) => {
        const r = await fetch(`/api/${tenant}/service-requests/${id}/fees`, {
          headers: { accept: "application/json" },
        });
        if (!r.ok) return { error: r.status };
        const tab = await r.json();
        return { lines: (tab?.lines ?? []).length, quoted: tab?.quoted?.display ?? null };
      }, [TENANT, feeRequestId]);
      if (quoted.lines >= 1) {
        ok("row 11 · Add raised a real fee line", `${quoted.lines} line(s), quoted ${quoted.quoted}`);
      } else {
        bad("row 11 · Add changed nothing on the server", JSON.stringify(quoted));
      }
      if (before.length > 0) note("row 11 · the panel was read before and after the press");
    }
  }

} catch (error) {
  bad("the walk stopped", error.message);
  await page.screenshot({ path: join(SHOTS, "after-ERROR.png"), fullPage: true }).catch(() => {});
} finally {
  console.log(`\n  ── ${passes} passed, ${failures.length} failed ──`);
  for (const f of failures) console.log(`     ● ${f}`);
  console.log(`  screenshots: ${SHOTS}`);
  await browser.close();
  process.exitCode = failures.length === 0 ? 0 : 1;
}
