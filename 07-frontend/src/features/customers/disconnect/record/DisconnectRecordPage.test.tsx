// ── Trace ──────────────────────────────────────────────
// Change:   CR-125-BRC07 — THE DISCONNECT CASE RECORD, blueprint p143.
// Rules:    B14 rule 31 · rule 33 · rule 43 · BR-SHL-025 · hard-won law 2 and
//           its mirror · hard-won law 7
// ───────────────────────────────────────────────────────
/**
 * What this file holds the record screen to — the six things that could go
 * wrong here and be invisible to `tsc`, to eslint and to every gate.
 *
 * **1 · THE ACTION SET GROWING.** Ten disconnect write paths are mounted on
 * the server with no door, and the PO has ruled *"too many actions - keep
 * critical ones"*. A lane adding `Stop the ladder` here would be building the
 * thing they said is too much, and nothing else in this repository would
 * notice.
 *
 * **2 · `Mark as cut` BECOMING PRESSABLE, OR ITS REASON GOING SILENT.** The
 * button is drawn greyed and the grey carries the server's own sentence. Two
 * ways to break it: enable the button, or move the sentence onto a `title`
 * where a touch or keyboard user never sees it. **Both are asserted, and the
 * second is asserted against VISIBLE TEXT rather than the markup** — a
 * `html.includes(...)` finds the string inside the very attribute that keeps
 * it off the screen, and would pass for the wrong reason.
 *
 * **3 · A DEAD DOOR.** `Open the account` is the one link out. Mounted bare in
 * a `MemoryRouter` with no `/:tenant/…` route, `useParams().tenant` is
 * undefined and every address the page builds comes out `//accounts/…` — a
 * protocol-relative URL to ANOTHER HOST, which reads as a perfectly good
 * string to `toContain`. **That exact fixture hid a broken screen in this
 * repository**, so every case here mounts under the real path pattern and the
 * door is asserted against the same builder `App.tsx` mounts the account
 * detail at.
 *
 * **4 · AN ABSENCE COLLAPSING INTO A DASH.** The two facts with no source, and
 * the *disputed bill* protection, each have to read as their own short
 * sentence. A dash for all three tells a clerk to go and look for something
 * that does not exist.
 *
 * **5 · A DELIVERY CLAIM OR A PRICE APPEARING.** The notices table must draw
 * no `Sent`/`Queued` state, and the cut panel must show no figure where the
 * server sent none.
 *
 * **6 · A CATALOGUE KEY MISSING IN ONE OF ELEVEN LANGUAGES.** A missing key
 * reaches a clerk as SILENCE, not as an error. Every key this directory asks
 * for is read out of the source and checked against all eleven files.
 *
 * ⚠ **RED PROVED FIRST for every case here**, through `vitest` — the harness
 * that will run them.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

// The eleven catalogues, imported the way `@/i18n` imports them — one list,
// so a twelfth language added there and not here goes red rather than silent.
import de from "@/i18n/locales/de.json";
import en from "@/i18n/locales/en.json";
import esMX from "@/i18n/locales/es-MX.json";
import es from "@/i18n/locales/es.json";
import frFR from "@/i18n/locales/fr-FR.json";
import hi from "@/i18n/locales/hi.json";
import idID from "@/i18n/locales/id-ID.json";
import itIT from "@/i18n/locales/it-IT.json";
import jaJP from "@/i18n/locales/ja-JP.json";
import koKR from "@/i18n/locales/ko-KR.json";
import ptBR from "@/i18n/locales/pt-BR.json";

import { accountDetailPath } from "../../customersShared";
import { DISCONNECT_WIZARD_ROUTE } from "../../transferDisconnectShared";
import { DisconnectRecordPage } from "./DisconnectRecordPage";
import type { DisconnectRecordDetail } from "./disconnectRecordEndpoints";
import {
  DISCONNECT_RECORD_ROUTE,
  disconnectRecordKey,
  disconnectRecordPath,
} from "./disconnectRecordEndpoints";

const ACCOUNT_ID = "01a0bf3d-13c5-7cfa-96a1-486d6b84f070";
const CASE_NO = "DSC-26-0003";

/**
 * The rendered TEXT — every tag and attribute stripped, leaving only what a
 * person actually reads.
 *
 * ⚠ **THE ABSENCE SENTENCES RIDE IN `title=`**, so a raw `html.includes(...)`
 * finds the rationale inside the very attribute that keeps it off the screen,
 * and the assertion that rule 33 is obeyed would pass or fail for the wrong
 * reason. Entities are decoded because `renderToStaticMarkup` writes an
 * apostrophe as `&#x27;`.
 */
function visibleText(html: string): string {
  return html
    .replace(/<[^>]*>/g, " ")
    .replace(/&#x27;|&#39;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&amp;/g, "&");
}

const ABSENT = (code: string, detail: string) => ({ code, detail });

function record(over: Partial<DisconnectRecordDetail> = {}): DisconnectRecordDetail {
  return {
    case_no: { value: CASE_NO, unavailable: null },
    customer_name: { value: "Bramble Bakery", unavailable: null },
    address: { value: "142 Bakers Row · Suite 1 · Silver Creek, TX 78611", unavailable: null },
    customer_class: { value: "Commercial", unavailable: null },
    state: { value: "notice_sent", unavailable: null },
    tier: { value: "tier_2_10_day", unavailable: null },
    cut_date: { value: null, unavailable: ABSENT("no_cut_scheduled", "no cut is scheduled") },
    the_case: {
      account_no: { value: "A-11812", unavailable: null },
      owed: { stored: "2410.0000", display: "2410.00", currency: "USD", unavailable: null },
      oldest_debt: {
        value: null,
        unavailable: ABSENT(
          "oldest_debt_age_has_no_source",
          "nothing in this repository records how old the oldest unpaid item is",
        ),
      },
      tier: { value: "tier_2_10_day", unavailable: null },
      cut_date: { value: null, unavailable: ABSENT("no_cut_scheduled", "no cut is scheduled") },
      opened_on: { value: "2026-04-14", unavailable: null },
      raised_by: {
        value: null,
        unavailable: ABSENT("case_opener_not_recorded", "there is no actor column on the table"),
      },
    },
    notices: {
      rows: [
        { tier: "tier_2_10_day", issued_on: "2026-04-24", channel: null, proved: false },
        { tier: "tier_1_reminder", issued_on: "2026-04-14", channel: null, proved: false },
      ],
      state_column_unavailable: ABSENT(
        "notice_delivery_state_is_null_by_rule",
        "delivery_state is written NULL on every row by a deliberate rule",
      ),
      channel_column_empty: ABSENT(
        "service_channel_is_the_proof_channel",
        "service_channel is the proof-of-service channel",
      ),
      delivery: ABSENT("delivery_adapter_absent", "there is no email, SMS or print adapter"),
    },
    protections: {
      as_of: "2026-05-09",
      checks: [
        // p143's drawn order, which is NOT `disconnects.PROTECTIONS`' —
        // the server re-orders it (`disconnect_record.DRAWN_ORDER`) and the
        // fixture carries what ships rather than what the writer declares.
        { check: "medical_certificate", outcome: "pass", reason: "none in force" },
        { check: "weather_moratorium", outcome: "pass", reason: "none in force" },
        { check: "payment_plan", outcome: "pass", reason: "none in force" },
        { check: "dispute", outcome: "unavailable", reason: "nothing stores a disputed amount" },
      ],
      all_clear: true,
    },
    what_a_cut_would_do: {
      services_affected: { value: ["electric", "water"], unavailable: null },
      charge_code_configured: false,
      reconnection_fee: {
        charge_code_configured: false,
        stored: null,
        display: null,
        currency: "USD",
        unavailable: ABSENT("reconnect_charge_code_not_seeded", "no seed creates that code"),
      },
      account_status_becomes: ABSENT("disconnected_status_assigned_at_the_cut", "BR-CUS-107"),
      to_clear_before_reconnection: {
        stored: null,
        display: null,
        currency: "USD",
        unavailable: ABSENT("reconnect_charge_code_not_seeded", "no seed creates that code"),
      },
      base_charges: ABSENT("base_charges_stop_at_the_cut", "BR-CUS-103"),
      not_a_close_out: ABSENT("a_cut_is_not_a_close_out", "the account stays open"),
      // `DEF-CUS-6064` — null on a case whose cut is finished or has not
      // happened. `disconnectRecordDialogs.dom.test.tsx` carries the other arm.
      cut_unfinished: null,
    } as DisconnectRecordDetail["what_a_cut_would_do"],
    actions: {
      available: ["hold", "open_account", "mark_as_cut"],
      account_id: ACCOUNT_ID,
      hold: {
        kinds: ["medical_certificate", "weather_moratorium", "payment_plan"],
        review_date: {
          medical_certificate: "required",
          payment_plan: "refused",
          weather_moratorium: "required",
        },
        dispute_unrecordable: ABSENT("dispute_is_not_a_protection", "nothing stores an amount"),
        effects: [
          { when: "now", code: "ladder_stops" },
          { when: "not_now", code: "cut_date_stays" },
          { when: "not_now", code: "debt_stays_and_ages" },
        ],
        promises_not_kept: ABSENT("hold_clears_no_date_and_moves_no_state", "measured"),
      },
      mark_as_cut: {
        ready: false,
        refusal: {
          code: "cut_not_scheduled",
          br_ref: "B18 §5.8.7",
          detail: "this case is 'notice_sent' and no cut is scheduled on it.",
        },
        blockers: [],
      },
    },
    ...over,
  };
}

/**
 * ⚠ **MOUNTED UNDER THE REAL PATH PATTERN, WITH THE TENANT SEGMENT.** See §3
 * of the file docstring: a bare `MemoryRouter` leaves `useParams().tenant`
 * undefined and every link the page builds becomes a protocol-relative URL to
 * another host, which `toContain` reads as a perfectly good string.
 */
function render(detail: DisconnectRecordDetail, ref = CASE_NO): string {
  const client = { get: async () => ({ status: 200, data: detail }) } as never;
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  qc.setQueryData(disconnectRecordKey(ref), detail);
  return renderToStaticMarkup(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/brazosbend${disconnectRecordPath(ref)}`]}>
        <Routes>
          <Route
            path={`/:tenant${DISCONNECT_RECORD_ROUTE}`}
            element={
              <DisconnectRecordPage client={client} timeZone="UTC" dateFormat="MM/DD/YYYY" />
            }
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("the disconnect record's address", () => {
  it("is a case number and never a uuid", () => {
    // B14 rule 31 — the URL a clerk copies is the NUMBER.
    expect(disconnectRecordPath(CASE_NO)).toBe(`/disconnects/${CASE_NO}`);
    expect(disconnectRecordPath(CASE_NO)).not.toContain(ACCOUNT_ID);
  });

  it("sits beside the wizard and never under /accounts", () => {
    expect(DISCONNECT_RECORD_ROUTE).toBe("/disconnects/:ref");
    expect(disconnectRecordPath(CASE_NO)).not.toContain("/accounts/");
  });

  it("cannot swallow `/disconnects/new`", () => {
    // The wizard's address is a STATIC segment; React Router ranks it above
    // `:ref` and `App.tsx` declares it first as well. This asserts the two are
    // different addresses rather than one pattern eating the other — the trap
    // `App.tsx` carries a comment about, and DEF-520 is a sibling meeting it.
    expect(DISCONNECT_WIZARD_ROUTE).toBe("/disconnects/new");
    expect(DISCONNECT_WIZARD_ROUTE).not.toContain(":");
    expect(disconnectRecordPath("new")).toBe(DISCONNECT_WIZARD_ROUTE);
  });
});

describe("the three actions, and no fourth", () => {
  it("draws Hold, Open the account and Mark as cut", () => {
    const html = render(record());
    expect(html).toContain('data-testid="disconnect-record-hold"');
    expect(html).toContain('data-testid="disconnect-record-open-account"');
    expect(html).toContain('data-testid="disconnect-record-mark-cut"');
  });

  /**
   * ⚠ **THE WAY BACK INTO THE SCHEDULING WIZARD — AND IT IS THE *ABSENCE* THAT
   * MATTERS AS MUCH AS THE PRESENCE (2026-09-25).**
   *
   * A case can reach `scheduled` with nobody having said which services go off.
   * `Mark as cut` then refuses it, correctly — and until this door there was
   * **nowhere to go from that refusal**. The repair is to re-run the scheduling
   * wizard, which the case-record lane established by doing it; the seed
   * script's header calling that *"a dead end by design"* was stale and is
   * corrected in the same commit.
   *
   * **It is offered ONLY where it repairs something**, which is the PO's *"too
   * many actions - keep critical ones"* applied rather than overridden. Both
   * halves are asserted, because a door on every case would be a fifth action
   * on a screen already called too full, and a door on no case is hard-won law
   * 2's dead UI.
   */
  it("offers the way back into the wizard on a case with NO services chosen", () => {
    const html = render(
      record({
        state: { value: "scheduled", unavailable: null },
        actions: {
          ...record().actions,
          available: ["mark_as_cut"],
        },
        what_a_cut_would_do: {
          ...record().what_a_cut_would_do,
          services_affected: { value: [], unavailable: null },
        },
      } as Partial<DisconnectRecordDetail>),
    );
    expect(html).toContain('data-testid="disconnect-record-reschedule"');
    // The ADDRESS, not merely the control — a door that points at nothing is
    // the shape law 2 keeps finding, and a bare MemoryRouter would have made
    // every link here protocol-relative.
    expect(html).toContain(`/brazosbend${DISCONNECT_WIZARD_ROUTE}`);
  });

  it("…and does NOT offer it on a case whose services are already chosen", () => {
    const html = render(
      record({
        state: { value: "scheduled", unavailable: null },
        actions: { ...record().actions, available: ["mark_as_cut"] },
      } as Partial<DisconnectRecordDetail>),
    );
    expect(html).not.toContain('data-testid="disconnect-record-reschedule"');
  });

  it("draws none of the five the PO is consolidating", () => {
    // ⚠ **ASKED OF THE VISIBLE TEXT.** The PO ruled *"too many actions - keep
    // critical ones"*, so the guard is about what a clerk can PRESS, and the
    // five names below are the undrawn write paths: stop the ladder, advance a
    // tier, lift a protection, mark reconnecting, restore service.
    const text = visibleText(render(record()));
    for (const undrawn of ["Stop the ladder", "Advance", "Lift", "Reconnecting", "Restore"]) {
      expect(text).not.toContain(undrawn);
    }
  });

  it("opens the account through the same builder App.tsx mounts it at", () => {
    // §3 — and the `//` assertion is what catches the bare-MemoryRouter trap.
    const html = render(record());
    expect(html).toContain(`href="/brazosbend${accountDetailPath(ACCOUNT_ID)}"`);
    expect(html).not.toContain('href="//');
  });
});

describe("`Mark as cut` is greyed, with its reason where a person reads it", () => {
  it("is disabled and carries the server's reason as VISIBLE TEXT", () => {
    const html = render(record());
    expect(html).toContain('data-testid="disconnect-record-mark-cut"');
    expect(html).toMatch(/data-testid="disconnect-record-mark-cut"[^>]*disabled/);

    // ⚠ **VISIBLE TEXT, NOT MARKUP.** `BR-SHL-025`: a touch or keyboard user
    // never sees a tooltip, and a refusal exists to be READ.
    const text = visibleText(html);
    expect(text).toContain("No cut is scheduled yet.");
    // …and the button points at it, so a screen reader reads them as one.
    expect(html).toContain('aria-describedby="disconnect-record-cut-refusal"');
  });

  it("is pressable, with no refusal line, once the server says ready", () => {
    // ⚠ **THE OTHER ARM, AND WITHOUT IT THE CASE ABOVE PROVES NOTHING** — a
    // button hard-coded `disabled` would pass it. This is law 7's *what would
    // make this check pass wrongly* written down as a second case.
    const ready = record();
    ready.actions.mark_as_cut = { ready: true, refusal: null, blockers: [] };
    const html = render(ready);
    expect(html).not.toMatch(/data-testid="disconnect-record-mark-cut"[^>]*disabled/);
    expect(html).not.toContain('data-testid="disconnect-record-cut-refused"');
  });
});

describe("the cut visit the wizard raised (DEF-CUS-9696)", () => {
  it("names the job by its number and links to it", () => {
    const html = render(
      record({
        work_orders: {
          value: {
            raised: 1,
            done: 0,
            accepted: 0,
            orders: [{ order_no: "WO-0110", state: "planned", done: false, accepted: false }],
          },
          unavailable: null,
        },
      }),
    );
    expect(visibleText(html)).toContain("1 raised · 0 done · 0 accepted");
    expect(html).toContain('href="/brazosbend/work/orders/WO-0110"');
  });

  it("says none yet when the case raised no job", () => {
    const html = render(
      record({
        work_orders: {
          value: null,
          unavailable: { code: "no_work_order_raised", br_ref: "BR-CUS-1098", detail: "x" },
        },
      }),
    );
    expect(visibleText(html)).toContain("Visit");
    expect(html).not.toContain("data-case-visit-order");
  });
});

describe("the reconnect request's status on the case (DEF-CUS-10657, PO C1)", () => {
  it("shows the request's jobs once one exists, by number, with done and accepted", () => {
    const html = render(
      record({
        reconnect_work_orders: {
          value: {
            raised: 1,
            done: 1,
            accepted: 0,
            orders: [{ order_no: "WO-0144", state: "done", done: true, accepted: false }],
          },
          unavailable: null,
        },
      }),
    );
    expect(visibleText(html)).toContain("Reconnect request");
    expect(visibleText(html)).toContain("1 raised · 1 done · 0 accepted");
    expect(html).toContain('href="/brazosbend/work/orders/WO-0144"');
  });

  it("a RESTORED case offers no commit at all — DEF-CUS-10666", () => {
    // The server answers only the two doors for a closed case; the page used
    // to fall back to `Mark as cut`, greyed for ever with "already cut".
    const closed = record();
    closed.actions.available = ["hold", "open_account"];
    closed.actions.mark_as_cut = {
      ready: false,
      refusal: { code: "already_cut", br_ref: "x", detail: "x" },
      blockers: [],
    };
    const html = render(closed);
    expect(html).not.toContain('data-testid="disconnect-record-mark-cut"');
    expect(html).not.toContain('data-testid="disconnect-record-cut-refused"');
    expect(html).not.toContain('data-testid="disconnect-record-reconnect"');
  });

  /**
   * `DEF-CUS-10667` — PO 2026-10-29, *"1A"*. A case awaiting reconnection may
   * still OWE money (`BR-CUS-1097`; DSC-26-0001 owed $8,315.00 and read
   * `Paid`), so its head chip reads `Reconnecting` and claims no payment.
   * RED FIRST: the chip borrowed the register's `Paid`.
   */
  it("a reconnecting case's head chip reads Reconnecting, never Paid — DEF-CUS-10667", () => {
    const text = visibleText(render(record({ state: { value: "reconnecting", unavailable: null } })));
    expect(text).toContain("Reconnecting");
    expect(text).not.toMatch(/\bPaid\b/u);
  });

  /** …and in every one of the eleven languages, the word for this state is not
   *  that language's word for a paid bill — on the case chip AND the register,
   *  which share these two keys. */
  it("no catalogue spells the reconnecting state with its word for paid — DEF-CUS-10667", () => {
    const catalogues: Record<string, Record<string, string>> = {
      de, en, es, esMX, frFR, hi, idID, itIT, jaJP, koKR, ptBR,
    };
    expect(Object.keys(catalogues)).toHaveLength(11);
    const claims: string[] = [];
    for (const [locale, c] of Object.entries(catalogues)) {
      const paidWords = new Set(
        ["billing.bills.status.paid", "portal.bills.state.paid"].map((k) => c[k]).filter(Boolean),
      );
      expect(paidWords.size).toBeGreaterThan(0);
      for (const key of [
        "customers.disconnects.state.reconnecting",
        "customers.disconnects.kpi.reconnections",
      ]) {
        const word = c[key];
        if (!word || paidWords.has(word)) claims.push(`${locale}: ${key} = ${word}`);
      }
    }
    expect(claims).toEqual([]);
  });

  it("draws no reconnect row before a request exists", () => {
    expect(visibleText(render(record({ reconnect_work_orders: null })))).not.toContain(
      "Reconnect request",
    );
  });
});

describe("what the product does not hold, it says", () => {
  it("draws the two facts with no source as their own short sentences", () => {
    const text = visibleText(render(record()));
    expect(text).toContain("Oldest debt");
    expect(text).toContain("Not counted");
    expect(text).toContain("Raised by");
    expect(text).toContain("Name not kept");
    // …and the DATE half, which IS real, is drawn beside them.
    expect(text).toContain("Opened on");
  });

  it("keeps the server's rationale off the screen (B14 rule 33)", () => {
    // The `detail` is WHY a fact is missing, which is RATIONALE and is zero
    // words on screen. It stays on the `title` for anybody debugging.
    const html = render(record());
    expect(html).toContain("nothing in this repository records how old");
    expect(visibleText(html)).not.toContain("nothing in this repository records how old");
  });

  it("answers the disputed-bill question `Not answerable`, never `No`", () => {
    const text = visibleText(render(record()));
    expect(text).toContain("Disputed bill open?");
    expect(text).toContain("Not answerable");
  });

  it("claims no delivery state on any notice", () => {
    const text = visibleText(render(record()));
    expect(text).toContain("Queued is not sent.");
    // The two columns the drawing draws and the product cannot fill.
    expect(text).not.toContain("Channel");
    expect(text).not.toMatch(/\bState\b/);
  });

  it("shows no reconnection figure where the server sent none", () => {
    const text = visibleText(render(record()));
    expect(text).toContain("Reconnection fee");
    expect(text).toContain("No fee set");
    // ⚠ **NEITHER DISPUTED NUMBER REACHES THE SCREEN.** The drawing says one,
    // the seeded catalogue says another, and it is the PO's to settle.
    expect(text).not.toContain("75.00");
    expect(text).not.toContain("45.00");
  });
});

describe("every catalogue key this screen asks for exists in all eleven languages", () => {
  it("has no key that reaches a clerk as silence", () => {
    // ⚠ **A MISSING KEY IS SILENCE, NOT AN ERROR**, which is why this reads the
    // SOURCE rather than the render: a key only reached on a state this fixture
    // does not produce would be invisible to any number of render assertions.
    //
    // ⚠ **`import.meta.glob` AND NOT `node:fs`, BECAUSE THE TWO FAIL
    // DIFFERENTLY.** A `readdirSync` here resolves against the process's
    // working directory, which is whatever a runner happens to set — so the
    // same assertion can read the right directory on one machine and an empty
    // one on another, and an empty one PASSES. The glob is resolved by the
    // bundler against THIS file's own path, so it cannot come back empty
    // without the build failing.
    const modules = import.meta.glob("./*.{ts,tsx}", {
      query: "?raw",
      import: "default",
      eager: true,
    }) as Record<string, string>;
    const source = Object.entries(modules)
      .filter(([name]) => !name.includes(".test."))
      .map(([, text]) => text)
      .join("\n");
    // Only the LITERAL keys — a template key like
    // `customers.disconnect.notice.${…}` is covered by its own family and
    // cannot be read out of source.
    const keys = [...source.matchAll(/t\("([a-zA-Z0-9_.-]+)"/g)].map((match) => match[1]);
    // A guard that found no keys would pass in silence (law 7's *incapable of
    // failing* shape). This directory asks for more than thirty.
    expect(keys.length).toBeGreaterThan(30);

    const catalogues: Record<string, Record<string, string>> = {
      de,
      en,
      es,
      esMX,
      frFR,
      hi,
      idID,
      itIT,
      jaJP,
      koKR,
      ptBR,
    };
    expect(Object.keys(catalogues)).toHaveLength(11);

    // ⚠ **A PLURAL KEY LIVES IN THE CATALOGUE UNDER ITS SUFFIXES AND NEVER
    //    UNDER ITS BARE NAME** — i18next resolves `t("x", {count})` to `x_one`
    //    or `x_other`. This directory got its first one on 2026-09-21
    //    (`cut.daysCount`, the days a cut left unbilled), and without this
    //    clause the check reported eleven "missing" keys over a catalogue that
    //    is correct. It is STRICTER than the bare rule rather than looser: a
    //    plural key has to hold BOTH forms in ALL ELEVEN, and a key that holds
    //    neither is still reported under its own name.
    const held = (catalogue: Record<string, string>, key: string) =>
      key in catalogue || (`${key}_one` in catalogue && `${key}_other` in catalogue);

    const missing: string[] = [];
    for (const [locale, catalogue] of Object.entries(catalogues)) {
      for (const key of keys) {
        if (!held(catalogue, key)) missing.push(`${locale}: ${key}`);
      }
    }
    expect(missing).toEqual([]);
  });
});
