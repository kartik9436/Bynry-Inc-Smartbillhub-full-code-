// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-073 (EP-CWP-12) — tips: the editor behind ✎ and *New tip* ·
//           US-CWP-074 — service centres: *New centre*.
//           Screens: CWP-073 (list + editor) · CWP-074 · CWP-075
// Defect:   DEF-CWP-3820 (`POST/PUT/DELETE settings/portal/tips` reachable by
//           nothing) · DEF-CWP-3821 (`POST settings/reference-data/
//           service-centres` reachable by nothing)
// Rules:    BR-CWP-095 (one tip per screen; on AND in season) · BR-CWP-096
//           (hidden is a state) · hard-won law 2 (built is not wired) ·
//           hard-won law 3 (defaults fail closed)
// ───────────────────────────────────────────────────────
/**
 * THE ONE THING A `node` SUITE CANNOT ASSERT: that the button **sends
 * something**.
 *
 * The static suite next door proves the controls are on the screen and are not
 * disabled. That is exactly what a `ctaReason` over `onCta: () => undefined`
 * also proves — a live-looking control wired to nothing renders identically to
 * a live one in `renderToStaticMarkup`, which is why wave D's two dead CTAs
 * survived a full green suite, `tsc`, eslint and a walkthrough. Hard-won law 2
 * has no static form.
 *
 * So this file clicks, types and reads back what reached the transport: the
 * METHOD, the PATH and the BODY. A regression that re-broke either creator
 * would have to keep sending the right POST to pass here.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@testing-library/jest-dom/vitest";
import "@/i18n";

import type { ApiClient, ApiResponse } from "@/api/client";
import type {
  HelpAnswerDetail,
  HelpAnswerRow,
  ServiceCentreDetail,
  ServiceCentresView,
  TipRow,
  TipsView,
} from "@/api/publishedContentEndpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import { PortalHelpList } from "./SettingsPortalHelp";
import { PortalTipsList } from "./SettingsPortalTips";
import { ServiceCentresView as CentresList } from "./SettingsServiceCentres";

interface Sent {
  method: string;
  path: string;
  body: unknown;
}

/**
 * A transport that RECORDS instead of fetching.
 *
 * ⚠ Keyed by `"METHOD path"` and not by path alone, deliberately: the centres
 * list and the centre creator are the SAME path under two verbs answering two
 * different shapes, and a path-keyed stub would have made one of them wrong in
 * a way that looks like a screen bug. Only the four verbs these screens use are
 * real; the rest throw, so a call this file did not plan for cannot pass
 * quietly.
 */
function recorder(answers: Record<string, unknown>): { client: ApiClient; sent: Sent[] } {
  const sent: Sent[] = [];
  const answer = <T,>(method: string, path: string): ApiResponse<T> => {
    const key = `${method} ${path}`;
    if (!(key in answers)) throw new Error(`unplanned call: ${key}`);
    return { status: 200, data: answers[key] as T, headers: new Headers() } as unknown as ApiResponse<T>;
  };
  const client = {
    request: () => {
      throw new Error("unplanned request()");
    },
    get: <T,>(path: string) => {
      sent.push({ method: "GET", path, body: undefined });
      return Promise.resolve(answer<T>("GET", path));
    },
    post: <T,>(path: string, body?: unknown) => {
      sent.push({ method: "POST", path, body });
      return Promise.resolve(answer<T>("POST", path));
    },
    put: <T,>(path: string, body?: unknown) => {
      sent.push({ method: "PUT", path, body });
      return Promise.resolve(answer<T>("PUT", path));
    },
    patch: () => {
      throw new Error("unplanned patch()");
    },
    del: <T,>(path: string) => {
      sent.push({ method: "DELETE", path, body: undefined });
      return Promise.resolve(answer<T>("DELETE", path));
    },
    pollJob: () => {
      throw new Error("unplanned pollJob()");
    },
  } as unknown as ApiClient;
  return { client, sent };
}

const TIP: TipRow = {
  id: "1",
  text: "A running toilet can use 4,000 gallons a month.",
  target_screen: "usage_looks_high",
  month_from: null,
  month_to: null,
  is_on: true,
  position: 1,
  in_season: true,
  showing_today: true,
  word_count: 9,
  word_guidance: 15,
};

const TIPS: TipsView = {
  tips: [TIP],
  all_screens: ["portal_home", "usage", "usage_looks_high", "send_a_reading", "overdue", "every_reading"],
  word_guidance: 15,
};

const CENTRES: ServiceCentresView = {
  centres: [],
  all_actions: ["pay_a_bill", "open_or_close_an_account", "report_a_problem", "hand_in_a_document", "ask_a_question"],
  all_payment_methods: ["cash", "cheque", "card", "money_order"],
};

const NEW_CENTRE: ServiceCentreDetail = {
  slug: "north-counter",
  name: "North counter",
  address: "1190 Palm Ct, Austin TX 78758",
  phone: null,
  directions_note: null,
  allowed_actions: [],
  all_actions: CENTRES.all_actions,
  payment_methods_accepted: [],
  all_payment_methods: CENTRES.all_payment_methods,
  is_shown_to_customers: false,
  position: 1,
  hours: [0, 1, 2, 3, 4, 5, 6].map((day) => ({
    day_of_week: day,
    is_closed: true,
    opens_at: null,
    closes_at: null,
  })),
  last_changed_on: null,
};

function mount(node: React.ReactElement, seed: [readonly unknown[], unknown][]) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  for (const [key, value] of seed) queryClient.setQueryData(key, value);
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={["/pine-hill/settings/reference-data/customer-portal/tips"]}>
          {node}
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

afterEach(cleanup);

describe("CWP-073 · a clerk can write a tip (US-CWP-073, DEF-CWP-3820)", () => {
  it("*New tip* opens the editor, and Save POSTs the whole tip", async () => {
    const { client, sent } = recorder({
      "GET /settings/portal/tips": TIPS,
      "POST /settings/portal/tips": { tips: [TIP] },
    });
    const user = userEvent.setup();
    mount(<PortalTipsList readOnly={false} client={client} />, [[queryKeys.portalTips, TIPS]]);

    await user.click(screen.getByRole("button", { name: "New tip" }));
    // ⚠ Law 3 made visible: a brand-new tip is OFF and Save is held until it
    // says something.
    const save = screen.getByRole("button", { name: "Save" });
    expect(save).toBeDisabled();

    await user.type(
      screen.getByRole("textbox"),
      "Read the dials left to right, and ignore the red ones.",
    );
    await user.selectOptions(screen.getByRole("combobox"), "send_a_reading");
    await user.click(save);

    await waitFor(() => {
      expect(sent.some((one) => one.method === "POST" && one.path === "/settings/portal/tips")).toBe(
        true,
      );
    });
    const post = sent.find((one) => one.method === "POST");
    expect(post?.body).toEqual({
      text: "Read the dials left to right, and ignore the red ones.",
      target_screen: "send_a_reading",
      month_from: null,
      month_to: null,
      is_on: false,
    });
  });

  it("✎ opens the row, and a month range travels as a PAIR (BR-CWP-095)", async () => {
    const { client, sent } = recorder({
      "GET /settings/portal/tips": TIPS,
      "PUT /settings/portal/tips/1": { tips: [TIP] },
    });
    const user = userEvent.setup();
    mount(<PortalTipsList readOnly={false} client={client} />, [[queryKeys.portalTips, TIPS]]);

    await user.click(screen.getByRole("button", { name: "Edit" }));
    expect(screen.getByRole("textbox")).toHaveValue(TIP.text);

    // ⚠ HALF A RANGE IS NOT A STATE. Turning *Only some months* on sets BOTH
    // ends at once, so a tip can never stop showing for a reason the screen
    // does not draw (US-CWP-073 TC-3, read backwards).
    await user.click(screen.getByRole("switch", { name: "Only some months" }));
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(sent.some((one) => one.method === "PUT")).toBe(true));
    const put = sent.find((one) => one.method === "PUT");
    expect(put?.path).toBe("/settings/portal/tips/1");
    expect(put?.body).toMatchObject({ month_from: 6, month_to: 9 });
  });

  it("− then confirm DELETEs it, and the confirm names what cannot be undone", async () => {
    const { client, sent } = recorder({
      "GET /settings/portal/tips": TIPS,
      "DELETE /settings/portal/tips/1": { tips: [] },
    });
    const user = userEvent.setup();
    mount(<PortalTipsList readOnly={false} client={client} />, [[queryKeys.portalTips, TIPS]]);

    await user.click(screen.getByRole("button", { name: "Remove" }));
    // The row action opens the editor; the destructive commit is behind the
    // confirm, where the consequence can be a sentence (B14 rule 6).
    await user.click(screen.getByRole("button", { name: "Remove" }));
    expect(screen.getByText(/cannot be brought back/i)).toBeInTheDocument();

    await user.click(screen.getAllByRole("button", { name: "Remove" }).at(-1) as HTMLElement);
    await waitFor(() => expect(sent.some((one) => one.method === "DELETE")).toBe(true));
    expect(sent.find((one) => one.method === "DELETE")?.path).toBe("/settings/portal/tips/1");
  });
});

describe("CWP-074 · a utility can get its FIRST centre (US-CWP-074, DEF-CWP-3821)", () => {
  it("the empty state's CTA POSTs a centre, and it arrives HIDDEN", async () => {
    const { client, sent } = recorder({
      "GET /settings/reference-data/service-centres": CENTRES,
      "POST /settings/reference-data/service-centres": NEW_CENTRE,
    });
    const user = userEvent.setup();
    mount(<CentresList readOnly={false} client={client} />, [[queryKeys.serviceCentres, CENTRES]]);

    // ⚠ THE EMPTY STATE IS THE ONE THAT MATTERS: a utility with no centres has
    // no visit page at all (BR-CWP-093), so this is the only door in.
    await user.click(screen.getAllByRole("button", { name: "New center" }).at(-1) as HTMLElement);
    await user.type(screen.getByLabelText(/^Name/), "North counter");
    await user.type(screen.getByLabelText(/^Address/), "1190 Palm Ct, Austin TX 78758");
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(sent.some((one) => one.method === "POST")).toBe(true));
    const post = sent.find((one) => one.method === "POST");
    expect(post?.path).toBe("/settings/reference-data/service-centres");
    expect(post?.body).toMatchObject({
      name: "North counter",
      address: "1190 Palm Ct, Austin TX 78758",
      // Law 3: publishing an address a customer will drive to is the option
      // somebody has to type.
      is_shown_to_customers: false,
    });
    expect((post?.body as { hours: unknown[] }).hours).toHaveLength(7);
  });
});

const ANSWER: HelpAnswerRow = {
  slug: "why-is-my-bill-higher",
  question: "Why is my bill higher?",
  topic: "billing",
  status: "published",
  position: 1,
  also_show_on_screen: null,
  languages_published: 3,
  languages_total: 11,
  // ⚠ **A COUNT, NOT A FLAG (`DEF-CWP-4017`).** `HelpAnswerRow.needs_translating`
  // is `number` — how many of the eleven catalogues still need this answer —
  // and `SettingsPortalHelp.tsx`'s filter reads it as `row.needs_translating > 0`.
  // `true` here left `npx tsc --noEmit` RED on the whole branch for every lane,
  // and no test caught it because vitest does not typecheck. Eleven published in
  // three languages is eight outstanding.
  needs_translating: 8,
  reads_this_month: 12,
  last_changed_by: null,
  last_changed_on: null,
};

const NEW_ANSWER: HelpAnswerDetail = {
  slug: "when-do-you-read-my-meter",
  question: "When do you read my meter?",
  topic: "readings",
  status: "draft",
  position: 2,
  also_show_on_screen: null,
  reads_this_month: 0,
  last_changed_by: null,
  last_changed_on: null,
  body: "",
  variants: [],
  publish_is_immediate: true,
  has_approval_step: false,
};

describe("CWP-071 · a clerk can write an answer (US-CWP-071, DEF-CWP-3824)", () => {
  /**
   * ⚠ **THE HOLD THAT USED TO BE HERE SAID *"Writing answers arrives later"*
   * OVER `create_answer`, WHICH HAS BEEN ROUTED, AUDITED AND TESTED SINCE
   * `2.138.0`.** That is hard-won law 2's mirror in its most durable form — a
   * refusal that was true the day it was written and false from the day the
   * endpoint landed, with `tsc`, eslint and a full green suite over it, because
   * a `ctaReason` above `onCta: () => undefined` renders identically to a live
   * control. It was the THIRD of its kind in two days (`DEF-CWP-3820`,
   * `DEF-CWP-3821` are the two next door, in this same file).
   *
   * These cases assert the release rather than pinning the hold: the control
   * SENDS something, and the words are gone. `G103` is the other half — it
   * fails the merge if a hold ever again claims a capability that
   * `06-backend/apps/` serves.
   */
  it("*New answer* is a live primary, and it POSTs the answer", async () => {
    const { client, sent } = recorder({
      "GET /settings/portal/help": { answers: [ANSWER] },
      "POST /settings/portal/help": NEW_ANSWER,
    });
    const opened: string[] = [];
    const user = userEvent.setup();
    mount(<PortalHelpList readOnly={false} client={client} onOpen={(slug) => opened.push(slug)} />, [
      [queryKeys.portalHelp, [ANSWER]],
    ]);

    // ⚠ THE PRIMARY IN THE HEADER, WHICH DID NOT EXIST AT ALL BEFORE THIS
    // COMMIT. The only control was the empty state's CTA, drawn only when a
    // tenant has NO answers — so a utility that wrote one answer could never
    // write a second, and the seeded demo tenant has four.
    await user.click(screen.getByRole("button", { name: "New answer" }));
    // ⚠ SCOPED TO THE DIALOG, and not for tidiness: the list's own column
    // heading is *Question* and its toolbar carries a second *New answer*
    // once the modal is open, so an unscoped query matches two nodes and the
    // assertion cannot say which one it meant.
    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText(/^Question/), "When do you read my meter?");
    await user.click(within(dialog).getByRole("button", { name: "New answer" }));

    await waitFor(() => expect(sent.some((one) => one.method === "POST")).toBe(true));
    const post = sent.find((one) => one.method === "POST");
    expect(post?.path).toBe("/settings/portal/help");
    expect(post?.body).toMatchObject({ question: "When do you read my meter?", topic: "billing" });
    // The modal ends by opening the editor on the row it just made — the answer
    // TEXT is written per language on CWP-072, which is where that table lives.
    await waitFor(() => expect(opened).toEqual(["when-do-you-read-my-meter"]));
  });

  it("the held sentence is gone, and the control is not disabled", async () => {
    const { client } = recorder({ "GET /settings/portal/help": { answers: [ANSWER] } });
    const { container } = mount(
      <PortalHelpList readOnly={false} client={client} onOpen={() => undefined} />,
      [[queryKeys.portalHelp, [ANSWER]]],
    );
    expect(container.textContent).not.toContain("Writing answers arrives later");
    expect(screen.getByRole("button", { name: "New answer" })).not.toBeDisabled();
  });

  it("read-only still refuses, and says why — BR-SHL-025, not a rotted hold", async () => {
    const { client } = recorder({ "GET /settings/portal/help": { answers: [ANSWER] } });
    mount(<PortalHelpList readOnly client={client} onOpen={() => undefined} />, [
      [queryKeys.portalHelp, [ANSWER]],
    ]);
    // ⚠ A refusal about THIS USER'S PERMISSION is re-answered on every draw and
    // cannot rot — which is exactly why `holds.ts` classifies it `server`/`form`
    // rather than deleting it along with the sentence above.
    expect(screen.getByRole("button", { name: "New answer" })).toBeDisabled();
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-CWP-073@b50adaa0 · US-CWP-074@b50adaa0 (EP-CWP-12 + the wave D as-built note)
// generated: 2026-09-05 by the CR-068 wave D close-out lane
// checklist: A✔ B✔ C✔ D=n/a E✔ F✔ G✔ H=n/a
// gates: npx vitest run src/features/tenancy · G31 · routeBUtilities · G15/G18
// exceptions: the row's 👁 of `08-screen-layouts.md` CWP-073 is folded into the editor as a live preview rather than shipped as a third icon onto the same destination — stated, not silently dropped
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
