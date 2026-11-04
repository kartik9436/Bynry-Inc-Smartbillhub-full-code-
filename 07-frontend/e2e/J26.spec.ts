// ── Trace ──────────────────────────────────────────────
// Journey:  J26 — 08-qa/01-e2e/journeys/J26-request-to-service.md (tier 2)
//           The front door: a walk-in becomes a numbered request, is matched,
//           priced, decided against evidence and routed. Screens: REQ-01 (the
//           list) · REQ-02 (the detail) · REQ-03 (the six-step capture form).
// Story:    US-CUS-024 (REQ-03, the applicant's form) · US-CUS-025 (REQ-01, the
//           list) · US-CUS-026 (REQ-02, the detail and its decision) —
//           04-docs/05-modules/03-customers/06-epics/EP-CUS-09-service-requests.md
// Rules:    BR-CUS-070 (`address_as_given` kept VERBATIM) · BR-CUS-079 (the
//           acknowledgement's ABSENCE is recorded, never a `sent` state) ·
//           BR-CUS-080 (a refusal stays on the timeline forever) · BR-CUS-089 ·
//           BR-CUS-090 (the counter takes what is handed over; a shortfall is
//           an open balance, never a waiver and never a refusal at the desk) ·
//           BR-CUS-091 (a DISCONNECT is a lawful request) · BR-CUS-092 (no
//           identifier is capturable until its encryptor exists) · BR-CUS-093
//           (numbered AT CREATION; gaps are NORMAL) · BR-CUS-094 (seven
//           categories, in the ruling's order; `government` is legacy) ·
//           BR-CUS-095 (attaching never blocks CREATION; verifying unblocks
//           APPROVAL) · **BR-CUS-106** (the AGE accent — 7 days, INCLUSIVE;
//           PO 2026-08-25, closing decision D4) · BR-SHL-025 (role gate) ·
//           CLAUDE.md rule 2 (money as decimal strings) · rule 6 (idempotency)
// Fixture:  08-qa/01-e2e/stack/seed_journey_fixture.py::seed_j26 — the eight
//           `[shot]` requests, planted through the service path a clerk drives.
// Impacts:  nothing. Every row this spec writes is one its own step table tells
//           a clerk to create, on a per-run applicant nobody else reads.
// ───────────────────────────────────────────────────────
//
// ⛔ **NO LITERAL REQUEST NUMBER IS ASSERTED ANYWHERE IN THIS FILE, AND THAT IS
// THE FIRST THING TO KNOW ABOUT IT.** The journey's own title says *"a phone
// call becomes `SR-26-0044`"* and the fixture draws `SR-26-0039…0048`. **What
// exists is `SR-26-0001…0008`** — BR-CUS-093 numbers at creation from the
// tenant's own series, so seeding the drawn numbers would mean writing behind
// the allocator's back or burning 38 numbers on phantom drafts. A spec
// asserting the string `SR-26-0044` goes RED against a CORRECT fixture. So the
// assertions here are the ORDER, the AGE column, the `CR030_SR_KEY` cross-wires
// and the SHAPE of a number (`SR-<yy>-<nnnn>`) — never its value.
// `06-backend/tests/test_cr031_service_request.py::
// test_the_seeded_numbers_are_allocated_not_the_drawn_ones` pins the same fact.
//
// **HOW THIS SPEC IS SPLIT, AND WHY.** J26's step table is eleven steps and its
// screens are three. The browser drives what a human looks at — REQ-01's order
// and its AGE accent, REQ-02's decision panel — and the product's own HTTP
// doors drive the handoff contracts a screen cannot show (a refusal's
// `message_key`, an idempotent replay's flag, the money at four decimal places).
// Both halves run against the same booted stack and the same session, so a
// browser assertion and an API assertion are statements about one product, the
// way J1 mixes them. Everything the browser cannot honestly reach is in the
// journey file's *"what this cannot yet assert"* table with its reason — a step
// that passes whatever the app does is worse than no step.
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";
import { journey } from "./support/journey";

/** A number this product allocated: `SR-26-0001`. The SHAPE, never the value. */
const REQUEST_NO_SHAPE = /^SR-\d{2}-\d{4}$/;

/** BR-CUS-106 — seven days, inclusive. Read here so the assertion below reads
 *  as the rule rather than as a magic number; the THRESHOLD itself lives on the
 *  server (`apps/customers/service_request.AGE_ACCENT_DAYS`) and this spec
 *  never re-derives it — it asserts that what the screen draws AGREES with it. */
const AGE_ACCENT_DAYS = 7;

/** A per-run applicant, so this spec's own rows can never be confused with the
 *  eight seeded ones and two concurrent runs cannot read each other's work. */
const RUN_STAMP = Date.now().toString(36);
const APPLICANT = `Okonkwo, David (J26 ${RUN_STAMP})`;
const ADDRESS = "14 Willow Bend, Springfield";
const RECEIPT_NO = `RCP-26-${RUN_STAMP.slice(-4)}`;

function apiBase(): string {
  return `/api/${tenant()}`;
}

async function get(page: Page, path: string) {
  const response = await page.request.get(`${apiBase()}${path}`);
  return { status: response.status(), body: await response.json().catch(() => null) };
}

async function post(page: Page, path: string, data: unknown) {
  const response = await page.request.post(`${apiBase()}${path}`, { data });
  return { status: response.status(), body: await response.json().catch(() => null) };
}

/** The journey's own capture payload — REQ-03.1 + REQ-03.3, the two steps that
 *  must both be present before a row may exist (`_clean_capture(partial=False)`
 *  requires `applicant_name` and `address_as_given`). */
function capture(): Record<string, unknown> {
  return {
    channel: "walk_in",
    applicant_kind: "person",
    applicant_name: APPLICANT,
    applicant_email: `j26.${RUN_STAMP}@example.invalid`,
    applicant_phone: "+1 (512) 555-0042",
    address_as_given: ADDRESS,
    property_type: "under_construction",
    what_they_said: "There is nothing here yet — I need service to a new build",
  };
}

async function newRequest(page: Page): Promise<string> {
  const created = await post(page, "/service-requests", capture());
  expect(created.status, "REQ-03 must be able to open a draft").toBe(201);
  return created.body.header.id as string;
}

journey("J26", "Request to service — captured, priced, decided, routed", () => {
  skipUnlessAppServer(test);

  // `signIn` is called INSIDE each test rather than from a shared `beforeEach`:
  // that is this directory's convention (W3-money-render, T5-05), and it keeps
  // the sign-in out of the hook `skipUnlessAppServer` already owns, so a run
  // with no app server skips instead of trying to type into nothing.

  // ── Steps 1 · 1a · 2 ────────────────────────────────────────────────────
  test("steps 1 · 1a · 2 — the number arrives WITH the address, and no identifier may be captured", async ({
    page,
  }) => {
    await signIn(page);

    // ── Step 1 — the form is open and only the name is typed ─────────────
    // ⚠ **THE SCREEN AND THE RULING DISAGREE HERE, AND THE JOURNEY SAYS SO.**
    // BR-CUS-093's worked example is *"a clerk opens the form on Tuesday, the
    // request is SR-26-0048 from that moment"*. The create path requires
    // `address_as_given` — step 3 — so `Save as draft` is disabled with its
    // reason and the footer reads *"not saved yet"*. This asserts WHAT THE
    // PRODUCT DOES, and the journey file carries the defect that is owed.
    // ⛔ It does NOT assert the ruling's first-keystroke half: that would be a
    // step that can only ever be red, which is not a test either.
    const nameOnly = await post(page, "/service-requests", {
      channel: "walk_in",
      applicant_kind: "person",
      applicant_name: APPLICANT,
    });
    expect(nameOnly.status, "a name with no address must not create a row").not.toBe(201);
    expect(nameOnly.body?.message_key).toBe("customers.serviceRequest.fieldRequired");
    expect(nameOnly.body?.params?.field).toBe("address_as_given");

    // ── Step 1a — the `ID` row ───────────────────────────────────────────
    // ✅ **SUPERSEDED 2026-08-27 — DEF-632 closed for the SSN.** This block
    // asserted the request was REFUSED with `identifierNotStorable`, which was
    // right while BR-CUS-092(b)'s encryptor did not exist. It does now, and the
    // PO ruled: *"We need to capture SSN and encript it; we have to ensure it
    // is working"*. So the journey asserts the round trip instead.
    const withSsn = await post(page, "/service-requests", {
      ...capture(),
      ssn: "452-88-4471",
    });
    expect(withSsn.status, "BR-CUS-092(a) — the SSN is accepted now").toBe(201);

    // ⚠ **THE RESPONSE IS SEARCHED FOR THE NUMBER, NOT INSPECTED FOR A MASK.**
    // BR-CUS-092(c): the full value never leaves the server, so the assertion
    // is over the WHOLE serialised body — a mask on one field would not stop
    // the digits riding on another.
    const wire = JSON.stringify(withSsn.body);
    for (const spelling of ["452-88-4471", "452884471", "45288", "88-4471"]) {
      expect(wire, `the wire must not carry ${spelling}`).not.toContain(spelling);
    }
    expect(withSsn.body?.applicant?.identifier?.ssn_last4).toBe("4471");
    expect(withSsn.body?.applicant?.identifier?.stored_encrypted).toBe(true);

    // …and the widening is exactly one field name. The PO ruled on the Social
    // Security number, not on identifiers in general.
    const withGovId = await post(page, "/service-requests", {
      ...capture(),
      gov_id: "D1234567",
    });
    expect(withGovId.status, "every other identifier is still REFUSED").not.toBe(201);
    expect(withGovId.body?.message_key).toBe("customers.serviceRequest.identifierNotStorable");

    // ── Step 2 — the address is typed and the row is created, NUMBERED ───
    const created = await post(page, "/service-requests", capture());
    expect(created.status).toBe(201);
    const header = created.body.header;

    // BR-CUS-093(b) — numbered in the SAME transaction as the row. The number
    // must be a number this product allocated; its VALUE is the series', and
    // asserting one would be the DEF-628 trap (see this file's header).
    expect(header.request_no, "BR-CUS-093 — a draft is numbered at creation").toMatch(
      REQUEST_NO_SHAPE,
    );
    expect(header.number_absence, "a row created today can never carry the absence").toBeNull();
    expect(header.state).toBe("draft");

    // BR-CUS-070 — kept BYTE FOR BYTE, not normalised, not trimmed into a
    // house style. The resolver writes its findings BESIDE this, never over it.
    expect(header.address_as_given).toBe(ADDRESS);

    // ⛔ *"Nothing is created until you submit"* is now FALSE and must appear
    // nowhere. Asserted on the payload the footer is built from, because that
    // is the copy the six steps share.
    expect(JSON.stringify(created.body)).not.toMatch(/nothing is created until you submit/i);

    // The resolver runs and writes EVIDENCE — never a decision. `14 Willow
    // Bend` is deliberately not on the premises register.
    const resolved = await post(page, `/service-requests/${header.id}/resolve-address`, {});
    expect(resolved.status).toBe(200);
    const location = resolved.body.location_and_services;
    expect(location.resolution_kind).toBe("no_premise");
    // The sentence is STORED at resolution, not recomputed on read — step 11's
    // invariance depends on that, and it is what a clerk decided against.
    expect(location.lookup_found, "the lookup's finding is stored as EVIDENCE").toBeTruthy();
    // ⛔ Resolving decides nothing. The outcome is the CLERK's, on the Decision
    // tab, and a resolver that set one would be the product choosing for them.
    expect(resolved.body.header.classification).toBe("not_yet_classified");
  });

  // ── Steps 3 · 4 · 5 ─────────────────────────────────────────────────────
  test("steps 3 · 4 · 5 — seven categories, a step that validates nothing, and $25.00 of a $130.00 quote", async ({
    page,
  }) => {
    await signIn(page);
    const id = await newRequest(page);

    // ── Step 3 — category and services (BR-CUS-094) ──────────────────────
    const categories = await get(page, "/service-requests/categories");
    expect(categories.status).toBe(200);
    const selectable = (categories.body.selectable as { code: string }[]).map((r) => r.code);
    // **THE RULING'S ORDER, NEVER ALPHABETICAL.** Sorting by code would put
    // `agricultural` first and quietly re-order a screen the PO drew.
    expect(selectable).toEqual([
      "residential",
      "commercial",
      "industrial",
      "agricultural",
      "institutional",
      "municipal",
      "builder_developer",
    ]);
    // `government` is UNSELECTABLE on a new record and lawful everywhere else —
    // served apart rather than dropped, so a screen filtering by it can still
    // name it, and NEVER re-labelled.
    const legacy = categories.body.legacy as { code: string; br_ref: string }[];
    expect(legacy.map((r) => r.code)).toEqual(["government"]);
    expect(legacy[0].br_ref).toBe("BR-CUS-094");

    const category = await post(page, `/service-requests/${id}/category`, {
      account_type_code: "residential",
    });
    expect(category.status).toBe(200);

    // ⛔ TC-5: the legacy code is refused BY NAME on a new record.
    const legacyPick = await post(page, `/service-requests/${id}/category`, {
      account_type_code: "government",
    });
    expect(legacyPick.status).not.toBe(200);
    expect(legacyPick.body?.br_ref ?? legacyPick.body?.params?.br_ref).toBeTruthy();

    // ── Step 4 — documents. GATE ONE: attaching never blocks CREATION ─────
    // The step has NO validation at all, and that absence IS the rule
    // (BR-CUS-095, PO 2026-08-24 closing OQ-351). A document is RECORDED with
    // no file: this product has no document store, so `storage_ref` points at
    // nothing and the detail's `View` opens nothing — which is why gate two
    // cannot be walked from the UI (journey file, row b).
    const attached = await post(page, `/service-requests/${id}/documents`, {
      doc_type: "tenancy_agreement_or_deed",
      name: "deed.pdf",
      what_it_proves: "Shows they may build on the plot",
    });
    expect(attached.status, "attaching must never be refused").toBeLessThan(400);

    // ── Step 5 — the fee. BR-CUS-090's own worked case ───────────────────
    // ⚠ These three figures are the PO's ruling of 2026-08-24, not a
    // calculation this spec performs: $130.00 quoted, $25.00 handed over,
    // $105.00 outstanding. The same figures are pinned server-side in
    // `test_br_cus_090_the_counter_accepts_what_is_handed_over`.
    for (const [charge_code, unit_amount] of [
      ["CC-REQFEE", "25.00"],
      ["CC-EXPED", "60.00"],
      ["CC-METERT", "45.00"],
    ]) {
      const line = await post(page, `/service-requests/${id}/fees`, {
        charge_code,
        unit_amount,
        quantity: "1",
      });
      expect(line.status, `the ${charge_code} fee line must be accepted`).toBeLessThan(400);
    }

    // ⛔ **A JSON FLOAT IS REFUSED BY NAME, NEVER COERCED (CLAUDE.md rule 2).**
    // By the time a JSON number reaches the view it is an IEEE double —
    // `25.10` arrives as `25.099999999999998` and would be stored to four
    // places as exactly that. This is a counter taking somebody's cash.
    const asFloat = await post(page, `/service-requests/${id}/fee-collection`, {
      amount: 25.1,
      method: "cash",
      receipt_no: RECEIPT_NO,
    });
    expect(asFloat.status).toBe(422);
    expect(asFloat.body.message_key).toBe("customers.serviceRequest.moneyMustBeString");

    const collected = await post(page, `/service-requests/${id}/fee-collection`, {
      amount: "25.00",
      method: "cash",
      receipt_no: RECEIPT_NO,
    });
    expect(collected.status).toBe(200);
    // Money as EXACT DECIMAL STRINGS, displayed at two (rule 2). Never
    // parseFloat, never a re-derived subtraction.
    expect(collected.body.quoted.display).toBe("130.00");
    expect(collected.body.collected.display).toBe("25.00");
    expect(collected.body.outstanding.display).toBe("105.00");
    // ⛔ The shortfall is NEVER refused at the desk, NEVER drawn as a waiver,
    // and the quote is NEVER adjusted down to match the cash.
    expect(collected.body.shortfall_is_open_balance).toBe(true);

    // Idempotent on the receipt number — a double-click at the counter is a
    // no-op, not a second $25.00 (hard rule 6).
    const doubleClick = await post(page, `/service-requests/${id}/fee-collection`, {
      amount: "25.00",
      method: "cash",
      receipt_no: RECEIPT_NO,
    });
    expect(doubleClick.status).toBe(200);
    expect(doubleClick.body.collected.display, "a repeated receipt must add nothing").toBe("25.00");
  });

  // ── Step 6 ──────────────────────────────────────────────────────────────
  test("step 6 — submit is idempotent, and the acknowledgement's ABSENCE is what is recorded", async ({
    page,
  }) => {
    await signIn(page);
    const id = await newRequest(page);

    const first = await post(page, `/service-requests/${id}/submit`, {});
    expect(first.status).toBe(200);
    expect(first.body.idempotent_replay).toBe(false);
    expect(first.body.request.state).toBe("submitted");
    const numberAtSubmit = first.body.request.request_no;

    // TC-REQ-2 — a second submit allocates NOTHING and sends nothing twice.
    const second = await post(page, `/service-requests/${id}/submit`, {});
    expect(second.status).toBe(200);
    expect(second.body.idempotent_replay).toBe(true);
    expect(second.body.request.request_no).toBe(numberAtSubmit);

    // ⛔ **BR-CUS-079 — the acknowledgement is NOT badged *"Sent
    // automatically"*.** `notifications.SOURCE_TYPES` has no `service_request`
    // kind and cross-module writes are forbidden, so the panel prints the
    // SERVER's own absence sentence. A fabricated `sent` is hard-won law 1.
    expect(first.body.acknowledgement.sent).toBe(false);
    expect(first.body.acknowledgement.reason, "the ABSENCE carries its reason").toBeTruthy();
  });

  // ── Step 7 — REQ-01, in a browser, which is the whole point ─────────────
  test("step 7 — REQ-01 renders oldest first, and BR-CUS-106's accent falls where the server says", async ({
    page,
  }) => {
    await signIn(page);
    await page.goto(`/${tenant()}/requests`);
    const rows = page.locator("table.data-table tr.data-table-row");
    await expect(rows.first()).toBeVisible({ timeout: 60_000 });

    const ages = await page.locator("[data-age-days]").evaluateAll((nodes) =>
      nodes.map((node) => ({
        days: Number((node as HTMLElement).dataset.ageDays),
        accented: (node as HTMLElement).dataset.ageAccented,
        classes: (node as HTMLElement).className,
      })),
    );
    // The fixture is eight requests and this segment is `Open`, so the count is
    // not asserted — other lanes' rows are lawful here. What IS asserted is
    // every invariant the journey names, over whatever is really on screen.
    expect(ages.length, "J26's own fixture must be planted — see seed_j26").toBeGreaterThan(0);

    // BR-SHL-013 — `received_at` ASC is the QUERY's order, so the AGE column
    // must come down the page. A list that sorted any other way would put the
    // oldest thing waiting where nobody looks.
    const sorted = [...ages].sort((a, b) => b.days - a.days).map((a) => a.days);
    expect(ages.map((a) => a.days)).toEqual(sorted);

    // ✅ **BR-CUS-106 (PO 2026-08-25, closing decision D4): SEVEN DAYS,
    // INCLUSIVE.** Asserted as an invariant over every rendered row rather than
    // against the fixture's own ages, so it holds whatever else is in the
    // register — and so it FAILS if the screen ever grows a threshold of its
    // own. The seeded eight are 15 · 11 · 5 · 4 · 3 · 2 · 1 · 0, so the nearest
    // row to the line is `5d`: **the fixture alone cannot tell `>= 7` from
    // `> 7`**, and the boundary is pinned where the arithmetic lives
    // (`test_br_cus_106_the_age_accent_starts_at_seven_days_inclusive`) and in
    // the cell's own vitest case.
    for (const age of ages) {
      const shouldAccent = age.days >= AGE_ACCENT_DAYS;
      expect(
        age.accented,
        `a ${age.days}-day row must ${shouldAccent ? "" : "NOT "}be accented (BR-CUS-106)`,
      ).toBe(shouldAccent ? "true" : "false");
      expect(age.classes.includes("text-accent-700")).toBe(shouldAccent);
    }

    // ⛔ **`0 days` IS NOT AN ANSWER TO "how long has the oldest one waited".**
    // With nothing parked the tile says *"nothing waiting"*; the fixture parks
    // four, so the tile must name a request and what it waits on rather than
    // printing a zero.
    const kpis = await get(page, "/service-requests?segment=open");
    expect(kpis.status).toBe(200);
    const oldest = kpis.body.kpis.oldest_waiting;
    if (oldest.days === null) {
      expect(oldest.request_no).toBeNull();
    } else {
      expect(oldest.request_no).toMatch(REQUEST_NO_SHAPE);
      expect(oldest.waiting_on).toBeTruthy();
    }
  });

  // ── Steps 8 · 9 ─────────────────────────────────────────────────────────
  test("steps 8 · 9 — nothing is preselected, DISCONNECT is enabled, and a blocked approval is not a refusal", async ({
    page,
  }) => {
    await signIn(page);
    const id = await newRequest(page);
    // Attached while the request is still a DRAFT — GATE ONE says attaching
    // never blocks creation, and gate two below is about VERIFYING.
    const attached = await post(page, `/service-requests/${id}/documents`, {
      doc_type: "proof_of_identity",
      name: "licence.jpg",
      what_it_proves: "Confirms who the applicant is",
      required: true,
    });
    expect(attached.status, "attaching must never be refused").toBeLessThan(400);
    await post(page, `/service-requests/${id}/submit`, {});
    await post(page, `/service-requests/${id}/transitions`, { action: "pick_up" });
    await post(page, `/service-requests/${id}/resolve-address`, {});

    // ── Step 8 — the clerk records the search, THEN picks ────────────────
    // `customer_id: null` records *"searched, and there is no prior customer"*
    // — a real answer, and the one a genuine first-time applicant gets. It is
    // what clears the arrears condition; an UNSEARCHED request can never be
    // approved, which is the point of stamping `match_confirmed_at` at all.
    const searched = await post(page, `/service-requests/${id}/customer-link`, {
      customer_id: null,
      basis: "no prior customer on file",
    });
    expect(searched.status).toBe(200);

    const detail = await get(page, `/service-requests/${id}`);
    expect(detail.status).toBe(200);
    const decision = detail.body.decision;
    // ⛔ **NOTHING IS PRESELECTED.** *"Approving creates real service and real
    // charges, so the decision is made deliberately."*
    expect(decision.preselected).toBeNull();
    expect(decision.commit.outcome).toBeNull();

    // ✅ **BR-CUS-091 — DISCONNECT IS DECIDABLE** (PO 2026-08-24, *"Yes
    // customer can request it"*), and the withdrawn *"only ever started by
    // collections"* reason must appear NOWHERE.
    const options = decision.options as {
      outcome: string;
      verdict: string;
      message_key: string | null;
    }[];
    const disconnect = options.find((v) => v.outcome === "disconnect");
    expect(disconnect, "disconnect must be an option at all").toBeTruthy();
    expect(disconnect!.verdict).not.toBe("not_possible");
    expect(JSON.stringify(decision)).not.toMatch(/only ever started by collections/i);
    // ⚠ And the distinction the withdrawal did NOT take with it, served beside
    // the two controls: a move-out CLOSES the account and settles the deposit
    // (BR-CUS-030); a disconnect leaves it OPEN AND ACCRUING (BR-MET-105). The
    // clerk is picking between two different things, not two names for one.
    expect(decision.disconnect_is_not_a_move_out.disconnect).toBe(
      "leaves_the_account_open_and_accruing",
    );
    expect(decision.disconnect_is_not_a_move_out.move_out).toBe(
      "closes_the_account_and_settles_the_deposit",
    );
    // OQ-356 — an undrawn combination is `possible` and carries NO sentence.
    // *The evidence does not rule this out and nothing rules it in* is an open
    // question, not a reason to print.
    for (const option of options) {
      if (option.verdict === "possible") {
        expect(option.message_key ?? null, "OQ-356: no sentence is invented").toBeNull();
      }
    }

    // ── Step 9 — GATE TWO: verifying is what unblocks APPROVAL ───────────
    // The refusal is a REASON ON THE BUTTON, not a hidden button and **not a
    // move to `Refused`**: *"Nothing is refused — it simply cannot be approved
    // yet."* Conflating the two would put a reason on a customer's record that
    // nobody gave.
    const decided = await post(page, `/service-requests/${id}/decision`, {
      outcome: "new_connection",
    });
    expect(decided.status, "the clerk's pick is stored, not mapped").toBe(200);

    const blocked = await post(page, `/service-requests/${id}/approve`, {});
    expect(blocked.status, "an unverified required document must block approval").toBeGreaterThan(
      399,
    );
    expect(blocked.body?.message_key).toBe(
      "customers.serviceRequest.condition.documentsUnverified",
    );
    const afterBlock = await get(page, `/service-requests/${id}`);
    expect(afterBlock.body.header.state, "a blocked approval is NOT a refusal").not.toBe("refused");
  });

  // ── Step 10 ─────────────────────────────────────────────────────────────
  test("step 10 — a refusal needs a reason, and it stays on the timeline through a reopen", async ({
    page,
  }) => {
    await signIn(page);
    const id = await newRequest(page);
    await post(page, `/service-requests/${id}/submit`, {});
    await post(page, `/service-requests/${id}/transitions`, { action: "pick_up" });

    // TC-REQ-9 — refused at the control AND at the server. Whitespace is not a
    // reason; a refusal with none would put an unexplained decision on a
    // customer's permanent record.
    const noReason = await post(page, `/service-requests/${id}/refuse`, { reason: "   " });
    expect(noReason.status).toBeGreaterThan(399);

    const refused = await post(page, `/service-requests/${id}/refuse`, {
      reason: "Arrears at a previous address",
    });
    expect(refused.status).toBe(200);

    // TC-REQ-10 — `reopen` is allowed from `refused` WITH a reason, and the
    // refusal stays. This is the whole reason the register keeps refused
    // requests: *someone turned down for arrears at a previous address simply
    // reapplies*.
    const reopened = await post(page, `/service-requests/${id}/transitions`, {
      action: "reopen",
      reason: "They brought the letter in",
    });
    expect(reopened.status).toBe(200);

    const detail = await get(page, `/service-requests/${id}`);
    expect(detail.body.header.state).toBe("under_review");
    const notes = (detail.body.history as { note: string | null }[]).map((e) => e.note);
    expect(notes, "BR-CUS-080 — the refusal is kept FOREVER").toContain(
      "Arrears at a previous address",
    );
    // …and the LIVE columns stop claiming the request is finished, or the row
    // would show a refusal while a clerk is working it.
    expect(detail.body.header.classification).toBe("not_yet_classified");
  });

  // ── Step 11 — INVARIANCE ────────────────────────────────────────────────
  test("step 11 — the address, the stored sentence and the number never move, and nothing posted", async ({
    page,
  }) => {
    await signIn(page);
    const id = await newRequest(page);
    const atCapture = await get(page, `/service-requests/${id}`);
    const numberAtCapture = atCapture.body.header.request_no;

    await post(page, `/service-requests/${id}/resolve-address`, {});
    const resolvedSentence = (await get(page, `/service-requests/${id}`)).body.header.lookup_found;

    await post(page, `/service-requests/${id}/submit`, {});

    // ⛔ TC-REQ-6 — once the request has left `draft`, `address_as_given` is
    // REFUSED an edit (BR-CUS-070, `addressAsGivenImmutable`). It is what the
    // applicant SAID, and a house-style rewrite of it is a different claim
    // about a person. The resolver writes its findings beside it, never
    // through it — which is why the resolution above did not disturb it.
    const patched = await page.request.patch(`${apiBase()}/service-requests/${id}`, {
      data: { address_as_given: "14 Willow Bnd" },
    });
    expect(patched.status(), "an edit to address_as_given must be refused").toBeGreaterThan(399);
    expect((await patched.json().catch(() => null))?.message_key).toBe(
      "customers.serviceRequest.addressAsGivenImmutable",
    );

    const after = await get(page, `/service-requests/${id}`);

    expect(after.body.header.address_as_given, "byte-identical to capture").toBe(ADDRESS);
    // The sentence STORED at resolution does not move when the premises record
    // does — it is what was true when the clerk looked.
    expect(after.body.header.lookup_found).toBe(resolvedSentence);
    // BR-CUS-093(a) — never renumbered, never backfilled, never reused. Gaps
    // in the series are NORMAL and no report may present one as a missing
    // record.
    expect(after.body.header.request_no).toBe(numberAtCapture);

    // B18 §4.6 — the fees are a QUOTE. Nothing in this module writes a journal
    // line, and the payload says so rather than leaving a caller to assume it.
    expect(after.body.fees.posts_to_ledger).toBe(false);
  });
});
