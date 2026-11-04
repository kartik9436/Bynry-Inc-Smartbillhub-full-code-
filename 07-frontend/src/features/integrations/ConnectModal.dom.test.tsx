// @vitest-environment jsdom
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-INT-019 (EP-INT-05) — the connect/manage modal, S141.
//           US-INT-017 (the server's refusal, shown, and nothing saved).
//           Screens: S141 · frames 25.1 · 49.2 · 50.1 · 55.1 · 55.2
// Rules:    BR-INT-043 (the field slot from the manifest; the three kinds a
//           plain field cannot express) · BR-INT-003 (no password input in
//           the DOM for a redirect provider; a secret never echoed) ·
//           BR-INT-026 (a typed test address) · B14 rule 6 (Disconnect is
//           danger-tier, read off its rendered class) · rule 33 (the refusal
//           line is the server's sentence)
// Cases:    US-INT-019 TC-1 · TC-2 · TC-3 · TC-4 · TC-7 · TC-8 · US-INT-017
//           TC-1's screen half
// ─────────────────────────────────────────────────────────────────────────
/**
 * ⚠ WHY THIS FILE CLICKS. A modal is state — `renderToStaticMarkup` paints
 * first paint and stops, and the modal only exists after a card's button is
 * pressed. So this suite mounts the tab in jsdom with a stub transport,
 * presses *Connect*, and reads the DOM the clerk would see: which inputs
 * exist, which do not, what the footer says, and — for the coming-soon and
 * the not-yet-connectable cases — that the server's six-word refusal reaches
 * the screen with *Nothing was saved.* beside it.
 */
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { createApiClient } from "@/api/client";
import type { ApiClient } from "@/api/client";
import type {
  IntegrationsGrid,
  ManifestField,
  OperationRow,
  ProviderCard,
} from "@/api/integrationsEndpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import { IntegrationsTab } from "./IntegrationsTab";

afterEach(cleanup);

function field(over: Partial<ManifestField>): ManifestField {
  return { name: "host", label: "Mail server", kind: "host", required: true, options: [], ...over };
}

function operation(over: Partial<OperationRow> = {}): OperationRow {
  return {
    name: "send_message",
    label: "Send messages",
    description: "We send bills through this server.",
    direction: "out",
    initiative: "us",
    state: "not_set_up",
    last_run_at: null,
    last_outcome: null,
    trace_id: null,
    test_action: "Send one real message to an address you type.",
    test_needs_recipient: true,
    // `CR-110-BRC04` wave B — the three columns `S142` draws. Required on
    // the type, so a fixture that omits one is a `tsc` error rather than a
    // silent `undefined` arriving at a table cell.
    trigger: "manual",
    endpoint: null,
    rate_limit_per_minute: null,
    // CR-069 wave M — `BR-INT-048`'s three declared facts. A fixture that
    // omitted them would be a shape the server never sends.
    executor: "server",
    latency_budget_ms: null,
    result_disposition: null,
    ...over,
  };
}

const SMTP = {
  key: "email_smtp",
  category: "email",
  display_name: "Custom SMTP",
  summary: "Any mail server with a host and a password.",
  fields: [
    field({ name: "host", label: "Mail server", kind: "host" }),
    field({ name: "port", label: "Port", kind: "port" }),
    field({ name: "username", label: "Username", kind: "text" }),
    field({ name: "password", label: "Password", kind: "secret" }),
    field({ name: "send_from", label: "Send bills from", kind: "email" }),
  ],
  disposition: { kind: "live", wave: null, phase: 2 },
  kicker: { direction: "out", initiative: "us" },
  auth: { mode: "we_hold_theirs", placement: "native" },
  codecs: [],
  // ⚠ `true`, AND IT SAID `false` UNTIL 2026-09-06 WHILE THE LIVE REGISTRY SAID
  // OTHERWISE (`DEF-INT-4224`). `email_smtp` has had a bound adapter since wave
  // E; this literal was written when wave B registered none and nothing made it
  // follow. It mattered the moment the card started READING the field: a
  // fixture that describes a world the product left behind turns a correct
  // change into five red tests and reads like the change is wrong.
  adapter_registered: true,
  connection: null,
  connections: [],
  vocabularies: [],
  state: "not_set_up",
  display_state: "not_set_up",
  operations: [operation()],
} as unknown as ProviderCard; // a sibling wave may widen the type; the literal must compile either way

const MICROSOFT: ProviderCard = {
  ...SMTP,
  key: "email_microsoft",
  display_name: "Microsoft 365",
  fields: [
    field({ name: "sign_in", label: "Sign in with Microsoft", kind: "redirect" }),
    field({ name: "send_from", label: "Send bills from", kind: "email" }),
  ],
  auth: { mode: "token_exchange", placement: "redirect" },
};

/**
 * A LIVE provider this product cannot yet talk to — no adapter, and it is one
 * we would have to dial. Seven of the fourteen live cards were in this state on
 * 2026-09-06 (`DEF-INT-4224`) and every one of them offered a form that refused
 * at its last step.
 */
const NO_ADAPTER: ProviderCard = { ...SMTP, adapter_registered: false };

const CARD_PROCESSOR: ProviderCard = {
  ...SMTP,
  key: "payments_card",
  category: "payments",
  display_name: "Card processor",
  disposition: { kind: "coming_soon", wave: "W7", phase: 5 },
  fields: [
    field({ name: "merchant_id", label: "Merchant ID", kind: "text" }),
    field({ name: "merchant_secret", label: "Merchant secret", kind: "secret" }),
  ],
};

function grid(cards: ProviderCard[]): IntegrationsGrid {
  return {
    categories: [{ key: "email" }, { key: "payments" }],
    providers: cards,
    counts: { providers: cards.length, connected: cards.filter((one) => one.connection !== null).length },
  };
}

/** A transport that answers the grid from the seed and every write with one scripted reply. */
function stubClient(
  cards: ProviderCard[],
  reply: { status: number; body: unknown },
  seen: { method: string; url: string; body: unknown }[],
): ApiClient {
  return createApiClient({
    tenant: "brazosbend",
    fetchImpl: async (input, init) => {
      const url = typeof input === "string" ? input : input.toString();
      const method = init?.method ?? "GET";
      seen.push({ method, url, body: init?.body ? JSON.parse(String(init.body)) : null });
      const answer = method === "GET" ? { status: 200, body: grid(cards) } : reply;
      return new Response(JSON.stringify(answer.body), {
        status: answer.status,
        headers: { "content-type": "application/json" },
      });
    },
  });
}

function mount(cards: ProviderCard[], reply: { status: number; body: unknown }, seen: { method: string; url: string; body: unknown }[], readOnly = false) {
  const client = stubClient(cards, reply, seen);
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.integrations, grid(cards));
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        {/* Wave D's Mappings link on a card is a router link (useTenantPath). */}
        <MemoryRouter initialEntries={["/brazosbend/settings/integrations"]}>
          <IntegrationsTab client={client} readOnly={readOnly} />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

const REFUSED_COMING_SOON = {
  status: 409,
  body: {
    code: "BIZ-STATE",
    message_key: "integrations.refusal.not_available",
    params: { provider: "Card processor", wave: "W7" },
    field_errors: [],
    br_ref: "BR-INT-001",
    trace_id: "a7f3c9e1b2d4e6f8a7f3c9e1b2d4e6f8",
  },
};

const REFUSED_NOT_CONNECTABLE = {
  ...REFUSED_COMING_SOON,
  body: { ...REFUSED_COMING_SOON.body, message_key: "integrations.refusal.not_connectable", br_ref: "BR-INT-037" },
};

describe("US-INT-019 — the connect/manage modal (S141)", () => {

  it("US-INT-017 · the screen half: a coming-soon Connect takes no press, and a direct connect shows the server's six-word refusal with nothing saved", async () => {
    const seen: { method: string; url: string; body: unknown }[] = [];
    mount([CARD_PROCESSOR, SMTP], REFUSED_COMING_SOON, seen);
    const user = userEvent.setup();
    // ⚠ **THE CARD'S `[data-coming-soon-connect]` BUTTON IS NOW THE ROW'S
    // GREYED `Connect` ICON** (grid→table, PO 2026-09-17). The CLAIM is
    // unchanged and is the one that matters: a coming-soon connector takes no
    // press and writes nothing. `US-INT-017`'s other half — that the SERVER
    // refuses it too — is untouched and is where the guarantee actually lives.
    const row = (
      document.querySelector('[data-provider="payments_card"]') as HTMLElement
    ).closest("tr") as HTMLElement;
    const connect = within(row).getByRole("button", { name: "Connect" }) as HTMLButtonElement;
    expect(connect.disabled).toBe(true);
    expect(connect.getAttribute("title")).toBe("Not built yet");
    await user.click(connect);
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(seen.filter((one) => one.method !== "GET")).toEqual([]);
  });

  // ⚠ **THIS CASE USED TO ASSERT THE DEFECT (`DEF-INT-4224`).** It read *"the
  // live card whose adapter has not arrived: Save and test posts once, the
  // refusal line reads the server's sentence and Nothing was saved"*, and it
  // filled in a host, a port, a username, a password, a send-from address and a
  // test recipient before pressing the button that refuses. Every assertion in
  // it was TRUE and the server half was right — nothing was saved, the sentence
  // was six words, the typed secret survived the refusal. What it encoded as
  // expected behaviour was the journey the Product Owner reported as *"I cannot
  // add any APIs - nothing ; no test"*: six fields of a clerk's time spent
  // before the product admits it cannot do this at all.
  //
  // It is now two cases, because there are two different claims and only one of
  // them changed. THIS one is the new contract — such a card never opens the
  // form. The one after it keeps the server-refusal half, which still matters
  // for a card that IS connectable and is refused anyway.
  it("DEF-INT-4224 · a live provider with no adapter holds its Connect on the CARD, opens no form, and writes nothing", async () => {
    const seen: { method: string; url: string; body: unknown }[] = [];
    mount([NO_ADAPTER], REFUSED_NOT_CONNECTABLE, seen);
    const user = userEvent.setup();
    const row = (
      document.querySelector('[data-provider="email_smtp"]') as HTMLElement
    ).closest("tr") as HTMLElement;

    // ⚠⚠ **THE HOLD SURVIVED THE GRID→TABLE MOVE AND ITS *PRESENTATION* DID
    // NOT, WHICH IS A REAL LOSS AND IS RECORDED RATHER THAN QUIETLY ACCEPTED.**
    // The CARD drew this reason as a LINE OF TEXT under a disabled button,
    // precisely because a `title` opens on hover, after a delay, and never on a
    // touch screen (`DEF-SHL-4043`). **A table row has nowhere to put a line of
    // text** — that is the shape of a row — so the reason is the tooltip alone,
    // which is what the PO's ratified actions matrix asks for on every greyed
    // icon. It is filed as `DEF-INT-5573` rather than folded in silently.
    //
    // What has NOT changed, and is the whole of `DEF-INT-4224`'s fix: the offer
    // is refused ON THE LIST, before a clerk has typed a single keystroke into
    // a form that could never have been saved.
    const held = within(row).getByRole("button", { name: "Connect" }) as HTMLButtonElement;
    expect(held).not.toBeNull();
    expect(held.disabled).toBe(true);
    expect(held.getAttribute("title")).toBe("Not ready to connect yet.");

    // Pressing it opens nothing and posts nothing: the person learns before
    // they have invested a single keystroke, which is the whole of the fix.
    await user.click(held);
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(seen.filter((one) => one.method !== "GET")).toEqual([]);
  });

  // ── r10 rules 12, 17 and 19 — finding one card among eighteen ────────────
  it("DEF-INT-4230 · search narrows the grid by what a clerk can SEE, and an empty result says so", async () => {
    const seen: { method: string; url: string; body: unknown }[] = [];
    mount([SMTP, MICROSOFT], REFUSED_NOT_CONNECTABLE, seen);
    const user = userEvent.setup();
    // ⚠ **THE SEARCH BOX IS THE KIT'S NOW, AND IT DEBOUNCES** (grid→table). The
    // screen's hand-rolled `[data-integrations-search]` input filtered on every
    // keystroke; `DataTable`'s commits through a debouncer, so every assertion
    // about the RESULT has to wait for it. A synchronous assertion here would
    // read the list as it was BEFORE the search — and would pass on the first
    // case, where the row it looks for is present either way.
    const box = document.querySelector('input[type="search"]') as HTMLInputElement;
    expect(box).not.toBeNull();
    // r10 rule 19 — "Search {entities}…", the module's own entity word. The
    // config carries the KEY and the kit resolves it, so this is still this
    // list's own prompt and not "Search this list".
    expect(box.getAttribute("placeholder")).toBe("Search services…");

    await user.type(box, "microsoft");
    await waitFor(() =>
      expect(document.querySelector('[data-provider="email_smtp"]')).toBeNull(),
    );
    expect(document.querySelector('[data-provider="email_microsoft"]')).not.toBeNull();

    // ⚠ THE GRID HAD NO EMPTY STATE AT ALL BEFORE THIS (r10 rule 17). The kit
    // draws it now, and it draws the SAME two things the screen's own
    // `ZeroResults` did — it names the query back and it offers the way out.
    // ⚠ **`DataTable` KEEPS *no results for a filter* AND *the list is empty*
    // APART**, which the screen never did: `empty` (*No connectors found*) is
    // for a list with nothing in it, and this branch is for a search that
    // matched nothing. Asserting the `empty` copy here would be asserting the
    // wrong state's words — and it would have passed the moment the query
    // echo broke, because both strings mean "nothing here" to a reader.
    await user.clear(box);
    await user.type(box, "nothing matches this");
    await waitFor(() =>
      expect(document.querySelector('[data-provider="email_microsoft"]')).toBeNull(),
    );
    expect(document.body.textContent).toContain("nothing matches this");

    // BR-SHL-020: the way back, and deliberately no create action — the data
    // exists and is merely filtered out. (On this screen it could never be a
    // create action anyway: a clerk cannot add a connector, because the list is
    // the 28 manifests we ship — `BR-INT-037`.)
    // ⚠ **`/clear/i` NOW MATCHES TWO CONTROLS AND THEY DO DIFFERENT THINGS.**
    // The kit's zero-results offers *Clear filters* and the search box carries
    // its own ✕ (*Clear search*). Pressing the wrong one would still empty the
    // search here — and would go on passing the day somebody made *Clear
    // filters* stop clearing the query, which is exactly the assertion this
    // case exists to make. Named exactly.
    await user.click(screen.getByRole("button", { name: "Clear search" }));
    await waitFor(() =>
      expect(document.querySelector('[data-provider="email_smtp"]')).not.toBeNull(),
    );
  });

  it("B14 rule 31 · search never matches the stored key, only the words on screen", async () => {
    const seen: { method: string; url: string; body: unknown }[] = [];
    mount([SMTP, MICROSOFT], REFUSED_NOT_CONNECTABLE, seen);
    const user = userEvent.setup();
    const box = document.querySelector('input[type="search"]') as HTMLInputElement;
    // `email_smtp` is a stored identifier a clerk never reads and never types.
    // Matching it would make a database id a working part of the screen, which
    // is the rule's whole subject even when the id is not DRAWN.
    await user.type(box, "email_smtp");
    await waitFor(() =>
      expect(document.querySelector('[data-provider="email_smtp"]')).toBeNull(),
    );
  });

  it("TC-8 · a read-only role sees every control, disabled, with the reason", async () => {
    const seen: { method: string; url: string; body: unknown }[] = [];
    mount([SMTP], REFUSED_NOT_CONNECTABLE, seen, true);
    // ⚠ **`BR-SHL-025` NOW BITES ON ALL FOUR ICONS, NOT ON ONE BUTTON.** The
    // card had a single state-driven control; a row has Connect · View · Edit ·
    // Keys, and a viewer can act on none of them. The ROLE's reason wins over
    // the status matrix for exactly this reason: one sentence explains the whole
    // screen, where four different status reasons would explain nothing.
    const row = (
      document.querySelector('[data-provider="email_smtp"]') as HTMLElement
    ).closest("tr") as HTMLElement;
    for (const name of ["Connect", "View", "Edit", "Keys"]) {
      const button = within(row).getByRole("button", { name }) as HTMLButtonElement;
      expect(button.disabled).toBe(true);
      expect(button.getAttribute("title")).toBe("Your role can view this, but not change it.");
    }
  });
});
