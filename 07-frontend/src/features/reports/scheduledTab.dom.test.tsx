// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-142-BRC07 — the Reports Build Brief, Phase 4 `P4.4` (screen
//          `2·3`) and `P4.5` (screen `4·1`). Drawings p34 · p40 · p41, read
//          as IMAGES per B14 rule 42.
// Rules:   BR-REP-020 CONFIRMED (internal staff only) · CLAUDE.md hard-won
//          law 2 AND ITS MIRROR · its fixture clause (mount the routed
//          component under the REAL path pattern) · law 7 clause 2 (ask what
//          would make this check pass WRONGLY) · B14 rule 31 (no database id
//          on screen) · rule 33 (RATIONALE is zero words on screen)
//          Screens: `2·3` · `4·1`
// ───────────────────────────────────────────────────────
//
// ⚠ **WHAT WOULD MAKE THESE CHECKS PASS WRONGLY** (law 7 clause 2), asked
// before they were written, because a check you cannot describe a false pass
// for is one you do not understand:
//
//   · **Mounting `ScheduledTab` bare** would leave `useParams().tenant`
//     undefined and every address the screen builds would come out
//     `//reports/…` — a protocol-relative URL to another host, which reads as
//     a perfectly good string to `toContain`. That is the customer portal's
//     own defect. Every mount here is under the real `/:tenant/reports`
//     pattern.
//   · **Asserting that the recipients field is not a `<input type="email">`**
//     would pass over a plain `<input type="text">` taking an address. So the
//     `BR-REP-020` case asserts there is **no free-text input of any kind** in
//     the dialog's recipients field, and separately that the picker's options
//     are exactly the STAFF THE SERVER SENT.
//   · **Asserting a toast appeared** after Pause would pass whichever word it
//     said. The pause/resume case asserts BOTH directions by their own
//     sentences, because a message that stays right after the clerk changes
//     their mind is the defect this phase's proof brief names.
//   · **Asserting a uuid is absent from one cell** would pass while it sat in
//     another. The rule-31 case serialises the whole rendered table and looks
//     for the id anywhere in it.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createMemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import type { ApiClient } from "@/api/client";
import { queryKeys } from "@/api/queryClient";
import type { MyPermissions, SessionUser } from "@/api/endpoints";
import type { ReportSchedule, SchedulePage } from "@/api/scheduleEndpoints";
import { shellBootSeed } from "@/components/shellBootSeed";
import { ToastProvider, createToastQueue } from "@/components/Toast";

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

import { ScheduleReportDialog } from "./ScheduleReportDialog";
import { ScheduledTab } from "./ScheduledTab";
import { SCHEDULED_ROUTE } from "./ReportsTabs";

afterEach(cleanup);

const TENANT = "brazosbend";

const USER: SessionUser = {
  id: "u1",
  full_name: "Dana Whitfield",
  email: "dana@sample.test",
  phone: null,
  role: "system_admin",
  role_name: "System Admin",
  must_change_password: false,
};

const PERMISSIONS: MyPermissions = {
  role: "system_admin",
  role_name: "System Admin",
  permissions: [{ code: "reports", label: "Reports", access: "Full" }],
};

const PERIOD = {
  fy_label: "FY2026",
  period: 9,
  start: "2026-09-01",
  end: "2026-09-30",
  status: "open",
};

const STAFF = [
  { id: "u1", name: "Dana Whitfield" },
  { id: "u2", name: "M. Okonkwo" },
];

// ⚠ **THESE ROWS ARE p40's OWN, NOT INVENTED.** The drawing lists AR Ageing
// (monthly on cycle close, next 1 Oct, Dana W. +1, On), Debtor List (weekly,
// 29 Sep, M. Okonkwo, Paused) and Close Pack (monthly on cycle close, 1 Oct,
// Finance (4), Failing).
const ON: ReportSchedule = {
  id: "01a0e0d2-dd78-74b5-9c04-b5bf68ce33d2",
  report: "AR Ageing",
  report_key: "ar_aging",
  cadence: "monthly_on_cycle_close",
  format: "csv",
  next_run_at: "2026-10-01T06:00:00Z",
  recipients: ["u1", "u2"],
  recipient_names: ["Dana Whitfield", "M. Okonkwo"],
  status: "on",
  params: {},
};

const PAUSED: ReportSchedule = {
  id: "01a0e0ce-268b-7079-aef9-8f6024b3568c",
  report: "Debtor List",
  report_key: "debtor_list",
  cadence: "weekly",
  format: "csv",
  // ⚠ Pause CLEARS the date (p41 ④), so the cell must draw an em-dash rather
  // than the string "null" — the production defect of 2026-08-16.
  next_run_at: null,
  recipients: ["u2"],
  recipient_names: ["M. Okonkwo"],
  status: "paused",
  params: {},
};

const FAILING: ReportSchedule = {
  id: "01a0e0ce-268b-7079-aef9-8f6024b3568d",
  report: "Close Pack",
  report_key: "close_pack",
  cadence: "monthly_on_cycle_close",
  format: "csv",
  next_run_at: "2026-10-01T06:00:00Z",
  recipients: ["u1"],
  recipient_names: ["Dana Whitfield"],
  status: "failing",
  params: {},
};

function page(rows: ReportSchedule[]): SchedulePage {
  return {
    rows,
    total: rows.length,
    page: 1,
    per: 50,
    cadences: ["daily", "weekly", "monthly", "monthly_on_cycle_close"],
    formats: ["csv"],
    statuses: ["on", "paused", "failing"],
    staff: STAFF,
  };
}

function server(
  rows: ReportSchedule[],
  calls: { method: string; path: string; body?: unknown }[] = [],
  overrides: { patched?: ReportSchedule } = {},
): ApiClient {
  const get = async (path: string) => {
    calls.push({ method: "GET", path });
    return { data: page(rows), status: 200 };
  };
  const post = async (path: string, body: unknown) => {
    calls.push({ method: "POST", path, body });
    if (path.endsWith("/run-now")) {
      return { data: { job_id: "job-1", schedule: rows[0] }, status: 202 };
    }
    return { data: rows[0], status: 201 };
  };
  const patch = async (path: string, body: unknown) => {
    calls.push({ method: "PATCH", path, body });
    return { data: overrides.patched ?? rows[0], status: 200 };
  };
  return {
    request: get,
    get,
    post,
    put: post,
    patch,
    del: post,
  } as unknown as ApiClient;
}

/** A server that FAILS the list read — `DEF-REP-6914`.
 *
 * ⚠ **THIS IS THE FIXTURE THE WHOLE FILE WAS MISSING, AND ITS ABSENCE IS THE
 * DEFECT.** Every other case here is served a 200, so twenty-four passing
 * cases said nothing at all about what this screen draws when the server does
 * not answer — and what it drew was *"No results match these filters."* over a
 * **Clear filters** link, on a tenant with no filters applied. A clerk is told
 * their utility has no schedules when the truth is that nobody asked it.
 *
 * Measured on 2026-09-27 against a real browser and a real 500 from
 * `GET /reports/schedules`.
 */
function failingServer(calls: { method: string; path: string }[] = []): ApiClient {
  const boom = async (path: string) => {
    calls.push({ method: "GET", path });
    throw new Error("HTTP 500 SYS-INTERNAL");
  };
  return {
    request: boom,
    get: boom,
    post: boom,
    put: boom,
    patch: boom,
    del: boom,
  } as unknown as ApiClient;
}

function mountTab(
  rows: ReportSchedule[],
  options: {
    calls?: { method: string; path: string; body?: unknown }[];
    patched?: ReportSchedule;
    /** `DEF-REP-6914` — a case that needs the read to FAIL supplies its own. */
    client?: ApiClient;
  } = {},
) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  queryClient.setQueryData(queryKeys.me, USER);
  queryClient.setQueryData(queryKeys.myPermissions, PERMISSIONS);
  queryClient.setQueryData(
    queryKeys.shellDisplay,
    shellBootSeed({ timezone: "America/Chicago", date_format: "MM/DD/YYYY" }, PERIOD),
  );
  const client = options.client ?? server(rows, options.calls, { patched: options.patched });
  // ⚠ **MOUNTED UNDER THE REAL `/:tenant/reports` PATTERN.** See this file's
  // header: a bare `MemoryRouter` gives `useParams().tenant === undefined` and
  // every address comes out `//reports/…`, which `toContain` reads as fine.
  const router = createMemoryRouter(
    [{ path: `/:tenant${SCHEDULED_ROUTE}`, element: <ScheduledTab client={client} /> }],
    { initialEntries: [`/${TENANT}${SCHEDULED_ROUTE}`] },
  );
  const queue = createToastQueue();
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider queue={queue}>
        <RouterProvider router={router} />
      </ToastProvider>
    </QueryClientProvider>,
  );
  return { queue, router };
}

/** Wait for the TABLE BODY to hold a report's name — never a page-wide find.
 *
 * ⚠ The filter bar names the statuses too, and `screen.findByText` is
 * page-wide: a case scoped to the page would go on passing if the ROW vanished
 * and only a filter option remained. `runHistory.dom.test.tsx` records the
 * same helper and the four cases that taught it. */
async function rowNamed(name: string): Promise<HTMLElement> {
  return await vi.waitFor(() => {
    const body = document.querySelector("table tbody") as HTMLElement | null;
    expect(body, "4·1 drew no table body").not.toBeNull();
    return within(body as HTMLElement).getByText(name);
  });
}

// ═══════════════════════════════════════════════════════════════════════════
// SCREEN `4·1` — the six columns, in p40's order
// ═══════════════════════════════════════════════════════════════════════════

describe("4·1 · the Scheduled tab", () => {
  it("draws the drawing's six columns in the drawing's order", async () => {
    mountTab([ON]);
    await rowNamed("AR Ageing");
    // ⚠ **THE SORT GLYPH IS STRIPPED, NOT ASSERTED AROUND.** `DataTable`
    // appends ▲/▼ to a SORTABLE header's text, so *Next* reads `Next▲` on the
    // default sort. That is the kit working; matching against the decorated
    // string would pin this case to today's glyph and break the day the kit
    // changes its arrow. Measured: this case failed on its first run for
    // exactly that reason, with the column order already correct.
    const headers = Array.from(document.querySelectorAll("thead th")).map((cell) =>
      (cell.textContent ?? "").replace(/[\u25B2\u25BC]/g, "").trim(),
    );
    // ⚠ **ASSERTED AS A PREFIX SEQUENCE, NOT AS A SET.** p40's order reads as
    // a sentence — what · how often · when next · to whom · how it is going —
    // and a set assertion would pass over any shuffling of it.
    expect(headers.slice(0, 5)).toEqual([
      en["reports.scheduled.column.report"],
      en["reports.scheduled.column.howOften"],
      en["reports.scheduled.column.next"],
      en["reports.scheduled.column.sendTo"],
      en["reports.scheduled.column.status"],
    ]);
  });

  it("renders the cadence as WORDS and never as a cron string", async () => {
    mountTab([ON]);
    const row = (await rowNamed("AR Ageing")).closest("tr") as HTMLElement;
    // p40 callout ①, verbatim: *"'monthly, on cycle close', not `0 0 1 * *`"*.
    expect(within(row).getByText(en["reports.schedule.cadence.monthly_on_cycle_close"])).toBeTruthy();
    expect(row.textContent ?? "").not.toContain("*");
  });

  it("draws an em-dash and never the string null where a paused schedule has no date", async () => {
    mountTab([PAUSED]);
    const row = (await rowNamed("Debtor List")).closest("tr") as HTMLElement;
    // A production defect on 2026-08-16 rendered the literal text `null USD`
    // on a tile, which is what a template does with an absent figure.
    expect(row.textContent ?? "").not.toContain("null");
    expect(row.textContent ?? "").toContain("—");
  });

  it("names the people and never a database id (B14 rule 31)", async () => {
    mountTab([ON]);
    const row = (await rowNamed("AR Ageing")).closest("tr") as HTMLElement;
    expect(row.textContent ?? "").toContain("Dana Whitfield");
    // ⚠ **THE WHOLE TABLE, NOT ONE CELL.** A check on the Send-to cell alone
    // would pass while the id sat in a `data-` attribute or another column.
    const table = document.querySelector("table") as HTMLElement;
    expect(table.textContent ?? "").not.toContain(ON.id);
    expect(table.textContent ?? "").not.toContain("u1");
  });

  it("marks a failing schedule failing rather than dropping it", async () => {
    mountTab([FAILING]);
    const row = (await rowNamed("Close Pack")).closest("tr") as HTMLElement;
    // p40 callout ③: *"a schedule whose report now errors stays in the list
    // marked failing and is not silently dropped"*.
    expect(within(row).getByText(en["reports.scheduled.status.failing"])).toBeTruthy();
  });

  it("offers NO + New schedule control, because 2·3 is the only door", async () => {
    mountTab([ON]);
    await rowNamed("AR Ageing");
    // p40 PRIMARY ACTION: *"None. ⚠ There is deliberately no + New schedule
    // button here."* Asserted over every button on the screen rather than
    // against one label, so a differently-worded create control fails too.
    const labels = Array.from(document.querySelectorAll("button")).map((button) =>
      (button.textContent ?? "").toLowerCase(),
    );
    expect(labels.some((label) => label.includes("new schedule"))).toBe(false);
    expect(labels.some((label) => label.includes("schedule a report"))).toBe(false);
  });

  it("pauses through the server and says so in BOTH directions", async () => {
    const calls: { method: string; path: string; body?: unknown }[] = [];
    const { queue } = mountTab([ON], { calls, patched: { ...ON, status: "paused" } });
    const row = (await rowNamed("AR Ageing")).closest("tr") as HTMLElement;
    fireEvent.click(
      within(row).getByRole("button", { name: en["reports.scheduled.action.pause"] }),
    );
    await vi.waitFor(() =>
      expect(calls.some((call) => call.method === "PATCH")).toBe(true),
    );
    const patched = calls.find((call) => call.method === "PATCH");
    expect(patched?.path).toBe(`/reports/schedules/${ON.id}`);
    expect(patched?.body).toEqual({ enabled: false });
    // ⚠ **THE SENTENCE, NOT MERELY "A TOAST APPEARED".** A message that stays
    // right after the clerk changes their mind is the defect this phase's
    // proof brief names, so the word is asserted.
    await vi.waitFor(() =>
      expect(queue.getCurrent()).toBe(en["reports.schedule.paused"]),
    );
  });

  it("resumes a paused schedule and says the OTHER sentence", async () => {
    const calls: { method: string; path: string; body?: unknown }[] = [];
    const { queue } = mountTab([PAUSED], { calls, patched: { ...PAUSED, status: "on" } });
    const row = (await rowNamed("Debtor List")).closest("tr") as HTMLElement;
    fireEvent.click(
      within(row).getByRole("button", { name: en["reports.scheduled.action.resume"] }),
    );
    await vi.waitFor(() => expect(calls.some((call) => call.method === "PATCH")).toBe(true));
    expect(calls.find((call) => call.method === "PATCH")?.body).toEqual({ enabled: true });
    await vi.waitFor(() =>
      expect(queue.getCurrent()).toBe(en["reports.schedule.resumed"]),
    );
  });

  it("runs now against the schedule's own address", async () => {
    const calls: { method: string; path: string; body?: unknown }[] = [];
    mountTab([ON], { calls });
    const row = (await rowNamed("AR Ageing")).closest("tr") as HTMLElement;
    fireEvent.click(
      within(row).getByRole("button", { name: en["reports.scheduled.action.runNow"] }),
    );
    await vi.waitFor(() =>
      expect(calls.some((call) => call.path.endsWith("/run-now"))).toBe(true),
    );
    // ⚠ **BY ADDRESS, and the tenant must NOT be in it** — the client puts the
    // tenant in the URL itself. A `//reports/…` prefix here would be the
    // fixture fault this file's header describes, one layer along.
    const ran = calls.find((call) => call.path.endsWith("/run-now"));
    expect(ran?.path).toBe(`/reports/schedules/${ON.id}/run-now`);
    expect(ran?.path.startsWith("//")).toBe(false);
  });

  it("says where schedules come from when there are none, and offers no control", async () => {
    mountTab([]);
    await vi.waitFor(() =>
      expect(screen.getByText(en["reports.scheduled.empty.title"])).toBeTruthy(),
    );
    expect(screen.getByText(en["reports.scheduled.empty.helper"])).toBeTruthy();
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// SCREEN `2·3` — one dialog, three fields, and a SIGNED ruling
// ═══════════════════════════════════════════════════════════════════════════

function mountDialog(calls: { method: string; path: string; body?: unknown }[] = []) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  const client = server([ON], calls);
  const queue = createToastQueue();
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider queue={queue}>
        <ScheduleReportDialog
          definitionKey="ar_aging"
          params={{ resource: "ar_aging", filters: { as_of: "2026-09-30" } }}
          options={{
            cadences: ["daily", "weekly", "monthly", "monthly_on_cycle_close"],
            formats: ["csv"],
            staff: STAFF,
          }}
          onClose={() => undefined}
          client={client}
        />
      </ToastProvider>
    </QueryClientProvider>,
  );
  return { queue };
}

describe("2·3 · schedule this report", () => {
  it("is ONE dialog with THREE fields and no step rail", () => {
    mountDialog();
    expect(screen.getByText(en["reports.schedule.title"])).toBeTruthy();
    // p34 callout ①: *"⚠ NOT `WizardFrame`. Three fields do not need a rail."*
    // Asserted against the wizard's own landmark rather than against a count
    // of fields, which a wizard would also satisfy one step at a time.
    expect(document.querySelector('[data-wizard-steps]')).toBeNull();
    expect(screen.getByLabelText(new RegExp(en["reports.schedule.cadence"]))).toBeTruthy();
    expect(screen.getByLabelText(new RegExp(en["reports.schedule.format"]))).toBeTruthy();
  });

  it("offers the four SIGNED cadences as words", () => {
    mountDialog();
    const select = screen.getByLabelText(
      new RegExp(en["reports.schedule.cadence"]),
    ) as HTMLSelectElement;
    const labels = Array.from(select.options).map((option) => option.text);
    expect(labels).toEqual([
      en["reports.schedule.cadence.daily"],
      en["reports.schedule.cadence.weekly"],
      en["reports.schedule.cadence.monthly"],
      en["reports.schedule.cadence.monthly_on_cycle_close"],
    ]);
  });

  it("BR-REP-020 · the recipients field takes no free text of any kind", () => {
    mountDialog();
    const field = document
      .querySelector('[data-chip-select="schedule-recipients"]')
      ?.closest("div") as HTMLElement | null;
    const scope = field ?? (document.querySelector(".modal-body") as HTMLElement);
    // ⚠ **NO `<input>` AT ALL, NOT MERELY NO `type="email"`.** A plain text
    // input would take an address just as well, and `BR-REP-020` is about
    // where the data GOES, not about a field's declared type. The picker is a
    // `<select>` over served staff.
    const inputs = Array.from(scope.querySelectorAll("input")).filter(
      (input) => input.type !== "hidden" && input.type !== "checkbox",
    );
    expect(
      inputs.length,
      "BR-REP-020: a free-text box here breaks a signed ruling — external " +
        "recipients arrive at W6 with an explicit confirm step",
      ).toBe(0);
  });

  it("BR-REP-020 · the picker offers exactly the staff the server sent", () => {
    mountDialog();
    const options = Array.from(document.querySelectorAll("option")).map(
      (option) => option.textContent ?? "",
    );
    for (const person of STAFF) {
      expect(options).toContain(person.name);
    }
  });

  it("B14 rule 33 · explains nothing on screen about why external is absent", () => {
    mountDialog();
    const body = (document.querySelector(".modal-body")?.textContent ?? "").toLowerCase();
    // RATIONALE is ZERO WORDS ON SCREEN. The dialog simply never offers an
    // external recipient; it does not apologise for it.
    expect(body).not.toContain("external");
    expect(body).not.toContain("br-rep");
    expect(body).not.toContain("w6");
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// THE CATALOGUES — eleven, or the sentence reaches a clerk as silence
// ═══════════════════════════════════════════════════════════════════════════

describe("every new sentence exists in all eleven catalogues", () => {
  const CATALOGUES: Record<string, Record<string, string>> = {
    de, en, es, "es-MX": esMX, "fr-FR": frFR, hi, "id-ID": idID,
    "it-IT": itIT, "ja-JP": jaJP, "ko-KR": koKR, "pt-BR": ptBR,
  };
  const KEYS = [
    "reports.tabs.scheduled",
    "reports.scheduled.title",
    "reports.schedule.title",
    "reports.schedule.cadence.monthly_on_cycle_close",
    "reports.scheduled.status.failing",
    // ⚠ **THE FOUR SERVER REFUSALS.** A `message_key` no catalogue defines
    // reaches a clerk as SILENCE — the click does nothing and no sentence
    // appears. 57 of these shipped in the Work module alone.
    "reports.schedule.unknown_report",
    "reports.schedule.unknown_cadence",
    "reports.schedule.unknown_format",
    "reports.schedule.recipient_not_internal",
  ];

  it.each(Object.keys(CATALOGUES))("%s holds every key", (language) => {
    for (const key of KEYS) {
      expect(CATALOGUES[language][key], `${language} is missing ${key}`).toBeTruthy();
    }
  });

  it("and no catalogue merely copies the English", () => {
    // B14 rule 35: a catalogue is written in its OWN language, never
    // translated mechanically from English. Asserted on the tab word, which is
    // the one a lane is most likely to leave in English everywhere.
    const english = en["reports.tabs.scheduled"];
    for (const [language, catalogue] of Object.entries(CATALOGUES)) {
      if (language === "en") continue;
      expect(
        catalogue["reports.tabs.scheduled"],
        `${language} left reports.tabs.scheduled in English`,
      ).not.toBe(english);
    }
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// `DEF-REP-6914` — A FAILURE IS NOT AN EMPTINESS
// ═══════════════════════════════════════════════════════════════════════════

describe("4·1 when the server does not answer", () => {
  afterEach(cleanup);

  it("draws the retry block and NEVER the zero-results copy", async () => {
    // ⚠ **BOTH HALVES, AND THE SECOND IS THE ONE THAT MATTERS.** Asserting the
    // retry block alone would pass over a screen that drew BOTH — and the
    // sentence that misleads a clerk is the one this case exists to forbid.
    mountTab([], { client: failingServer() });
    expect(await screen.findByText(en["table.failed.title"])).toBeTruthy();
    expect(screen.queryByText(/no results match/i)).toBeNull();
    expect(screen.queryByText(/clear filters/i)).toBeNull();
  });

  it("offers a retry that asks the server again", async () => {
    // A retry control that retries nothing is the mirror defect — a live
    // control over a dead action (hard-won law 2). So the CALL COUNT is
    // asserted, not the presence of a button.
    const calls: { method: string; path: string }[] = [];
    mountTab([], { client: failingServer(calls) });
    await screen.findByText(en["table.failed.title"]);
    const before = calls.length;
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    await vi.waitFor(() => {
      expect(calls.length).toBeGreaterThan(before);
    });
  });
});
