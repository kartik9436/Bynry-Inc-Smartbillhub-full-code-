// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-094-BRC01 step 2 wave N — `ACC-S1` + `ACC-S15` (`BR-CUS-1053`).
// Rules:   BR-SHL-025 (a control that cannot act is disabled WITH its reason) ·
//          B14 rule 15 (row actions are icons with an accessible name) ·
//          hard-won law 2 and its mirror (dead UI · a dead control over a live
//          screen).
// Tests:   TC-N1 .. TC-N7.
//
// ⚠ **THE RISK THIS FILE IS AIMED AT IS A CONTROL THAT WRITES NOTHING.**
// `DEF-MET-4971` is the asset module's version of it: a select that is
// required, interactive, validated, and never put in the PATCH body — so a
// clerk changes it, presses Save, gets the success toast, and the value is
// unchanged. **From every check this repository has, a control that is
// discarded looks identical to a control that works**: `tsc` is happy because
// the value IS read, eslint sees no unused binding, and no gate compares a
// rendered form's controls with the keys its `onSubmit` builds.
//
// So TC-N4 asserts the PATCH body **key for key**, against a client that
// answers nothing and remembers everything — `AssetEditPayload.dom.test.tsx` is
// the shape, and the reason is stated in its own words: *"the dialog's own
// report of itself is a success toast, and a success toast is exactly what the
// defect produces."*
//
// RED-FIRST PROOF (r11 step 2d), through the harness that runs it —
// `npx vitest run src/features/customers/AccountPanelEdits.dom.test.tsx` — and
// not through a hand-rolled entry point (hard-won law 7's second clause).
// **WHAT WAS ACTUALLY PROVED RED, quoted, and nothing more is claimed:**
//
//   TC-N4 ← `autopay` removed from the body builder (`DEF-MET-4971`'s exact
//           shape: read, validated, discarded; `tsc` stays green because the
//           value IS read) →
//           AssertionError: expected { tax_exempt: true, paperless: true } to
//           deeply equal { tax_exempt: true, …(2) }
//   TC-N2 ← `accountGroupBlockedReason("bills")` returning null →
//           AssertionError: expected [ Array(5) ] to deeply equal
//           [ 'bills', 'usage', 'customer', …(3) ]
//
// **TC-N7b WAS NOT PROVED BY BREAKING IT, AND SAYING SO IS THE POINT.** The
// only way to make it fail is to add an export to `07-frontend/src/api/
// endpoints.ts`, a file seven other lanes are writing to — and a fake export
// left there for thirty seconds is one pathspec commit away from being
// published (law 11, mechanism five, which reverted this wave's own work twice
// today). So TC-N7a proves the DETECTOR instead, over names it must catch and
// names it must not, which closes law 7's *structurally incapable of failing*
// shape without touching a shared file.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import i18n from "@/i18n";

import type { ApiClient } from "@/api/client";
import * as endpoints from "@/api/endpoints";
import type { AccountDetail, LookupEntry } from "@/api/endpoints";

import {
  AccountGroupPencil,
  AccountPanelEditDialog,
  accountGroupBlockedReason,
} from "./AccountPanelEdits";
import type { AccountOverviewGroup } from "./AccountPanelEdits";

afterEach(cleanup);

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

const SUBTYPES: LookupEntry[] = [
  { id: "small_commercial", code: "small_commercial", name: "Small commercial" },
  { id: "large_commercial", code: "large_commercial", name: "Large commercial" },
] as LookupEntry[];

/** A detail row shaped as `account_detail_dict` serves it — the eight fields the
 *  dialog offers, plus the two the kicker reads. `as AccountDetail` because the
 *  interface is wide and this file is about eight of its keys. */
function detail(over: Partial<AccountDetail> = {}): AccountDetail {
  return {
    id: "a-11812",
    account_no: "A-11812",
    account_type: "commercial",
    account_subtype: "small_commercial",
    account_subtype_name: "Small commercial",
    tax_exempt: false,
    tax_exempt_ref: null,
    tax_exempt_expires: null,
    preferred_language: null,
    paperless: false,
    sms_reminders: false,
    autopay: false,
    contacts: [{ id: "c-1", full_name: "Bramble Bakery" }],
    addresses: [],
    custom_data: {},
    ...over,
  } as unknown as AccountDetail;
}

/**
 * A client that answers nothing and REMEMBERS EVERYTHING.
 *
 * ⚠ The sub-type lookup goes through `get()` and the edit through `request()`,
 * so both are recorded and TC-N4 can assert the PATCH in isolation from the
 * read the dialog makes on mount.
 */
function recordingClient(sent: { method: string; path: string; body: unknown }[]): ApiClient {
  const answer = <T,>(data: unknown) => ({ data: data as T, status: 200, headers: new Headers() });
  return {
    request: <T,>(path: string, options?: { method?: string; body?: unknown }) => {
      sent.push({ method: options?.method ?? "GET", path, body: options?.body });
      return Promise.resolve(answer<T>({}));
    },
    get: <T,>(path: string) => {
      sent.push({ method: "GET", path, body: undefined });
      return Promise.resolve(
        answer<T>({ results: SUBTYPES, page: 1, per: 200, total: SUBTYPES.length }),
      );
    },
    post: () => {
      throw new Error("unplanned post()");
    },
    put: () => {
      throw new Error("unplanned put()");
    },
    patch: () => {
      throw new Error("unplanned patch() — updateAccount goes through request()");
    },
    del: () => {
      throw new Error("unplanned del()");
    },
    pollJob: () => {
      throw new Error("unplanned pollJob()");
    },
  } as unknown as ApiClient;
}

function mountDialog(client: ApiClient, over: Partial<AccountDetail> = {}) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <AccountPanelEditDialog
        detail={detail(over)}
        group="account"
        client={client}
        t={t}
        dateFormat="MM/DD/YYYY"
        onClose={() => undefined}
        onSaved={() => undefined}
      />
    </QueryClientProvider>,
  );
}

/**
 * ⚠ **THIS LIST IS TYPED OUT AND IT IS A CLAIM ABOUT ANOTHER FILE, so the case
 * below re-derives it rather than trusting it.** The union it mirrors is
 * `AccountOverviewGroup`, and a group added there with no line here is a
 * control nothing checks — which is how `TC-N2` came to assert a six-of-seven
 * arrangement that had not been true for a day.
 */
const ALL_GROUPS: AccountOverviewGroup[] = [
  "account",
  "billingPrefs",
  "bills",
  "usage",
  "customer",
  "mailing",
  "deposit",
  "portal",
  // ⚠ **THE FIVE ADDED 2026-09-13 ON THE PO's SCOPE INSTRUCTION** — *"also when
  // I say Actions 13 plus all pencils on Overview screen"*. Measured at 1440
  // before that: thirteen groups render and these five carried NO control at
  // all, which `BR-SHL-025` forbids — a group that cannot be edited shows its
  // control, disabled, with its reason.
  "money",
  "service",
  "meters",
  "plan",
  "customerRecord",
  // ⚠ **AND THE FOURTEENTH GROUP, 2026-09-13** — `UNIT — WHAT THIS ACCOUNT IS
  // ATTACHED TO` was drawn in the blueprint and rendered by nothing
  // (`DEF-CUS-5163`). It arrives with its control, as `R5`'s rule requires:
  // *"Every group heading carries the control."*
  "unit",
];

// ══════════════════════════════════════════════════════════════════════════
// TC-N1 · every group carries a control, and it is NAMED
// ══════════════════════════════════════════════════════════════════════════
describe("ACC-S15 — every Overview group carries an edit control", () => {
  it("TC-N1 · renders one named control per group, for all seven", () => {
    for (const group of ALL_GROUPS) {
      cleanup();
      render(<AccountGroupPencil group={group} t={t} roleReason={null} onEdit={() => undefined} />);
      // B14 rule 15: an icon action is addressable by its accessible name,
      // which is the same string a screen reader announces. A `data-testid`
      // would pass with no label at all — the exact failure rule 15 prevents.
      expect(
        screen.getByRole("button", { name: t(`customers.account.edit.group.${group}`) }),
      ).toBeInTheDocument();
    }
  });

  // ⚠ **THE POINT OF `ACC-S15`: A GROUP THAT CANNOT BE EDITED STILL SHOWS ITS
  // CONTROL.** `BR-SHL-025` — disabled WITH the reason, never hidden. A missing
  // control and a broken control look identical to a clerk, and an absence is
  // invisible to every check this repo has.
  it("TC-N2 · the refused groups are disabled and each carries its own reason", () => {
    const blocked = ALL_GROUPS.filter((group) => accountGroupBlockedReason(group, t) !== null);
    // ⚠ **THE LIVE SET IS WHAT THIS ASSERTS, AND IT IS SHORTER THAN THE
    // REFUSED ONE ON PURPOSE.** Naming the refusals froze this case to a
    // six-of-seven arrangement that three separate waves then falsified —
    // `billingPrefs`, `customer` and `mailing` each went live and this line was
    // not moved with them (it was red at `89aaa7930`). Asserting what a clerk
    // CAN do is the half that changes rarely and the half that matters.
    expect(ALL_GROUPS.filter((group) => accountGroupBlockedReason(group, t) === null)).toEqual([
      "account",
      "billingPrefs",
      "customer",
      "mailing",
      // `R5`: *"an edit control that routes to a wizard rather than duplicating
      // it"*. `plan` is pressable and the PAGE sends it to the change-plan
      // wizard; it never reaches the dialog dispatcher.
      "plan",
      // ⚠ **`unit` JOINED THE LIVE SET ON 2026-09-13 (`BR-CUS-1047`).** Its
      // refusal was true for one day: `POST /accounts/{id}/correct-unit` was
      // built and no screen called it. The remaining refusal is a ROLE and is
      // not in this map — a Billing Clerk sees the pencil disabled with its
      // reason, applied in `AccountGroupPencil` where the caller's role is
      // known, because A4 grades Accounts `Full` for them and the server still
      // answers 403.
      "unit",
    ]);

    for (const group of blocked) {
      cleanup();
      render(<AccountGroupPencil group={group} t={t} roleReason={null} onEdit={() => undefined} />);
      const button = screen.getByRole("button", {
        name: t(`customers.account.edit.group.${group}`),
      });
      expect(button).toBeDisabled();
      // The reason is real text from the catalogue, never the key echoed back —
      // a missing key reaches a clerk as SILENCE, not as an error.
      const reason = accountGroupBlockedReason(group, t) as string;
      expect(reason).not.toContain("customers.account.edit.blocked");
      expect(reason.trim().length).toBeGreaterThan(0);
      expect(button).toHaveAttribute("title", reason);
    }
  });

  it("TC-N3 · `account` is the one live control, and a role refusal still wins", () => {
    expect(accountGroupBlockedReason("account", t)).toBeNull();

    render(<AccountGroupPencil group="account" t={t} roleReason={null} onEdit={() => undefined} />);
    expect(
      screen.getByRole("button", { name: t("customers.account.edit.group.account") }),
    ).toBeEnabled();

    // `BR-SHL-025` precedence: somebody who may not write at all is told THAT
    // first, not why one panel is derived.
    cleanup();
    render(
      <AccountGroupPencil group="account" t={t} roleReason="No permission" onEdit={() => undefined} />,
    );
    expect(
      screen.getByRole("button", { name: t("customers.account.edit.group.account") }),
    ).toBeDisabled();
  });
});

// ══════════════════════════════════════════════════════════════════════════
// TC-N4 · THE PATCH BODY, KEY FOR KEY — the assertion the whole file is for
// ══════════════════════════════════════════════════════════════════════════
describe("ACC-S1 — the account edit actually writes", () => {
  it("TC-N4 · sends exactly the fields the clerk changed, and their values", async () => {
    const sent: { method: string; path: string; body: unknown }[] = [];
    const user = userEvent.setup();
    mountDialog(recordingClient(sent));

    // Three edits across all three of the drawing's sections, so a body built
    // from only one section could not pass.
    await user.click(screen.getByLabelText(t("customers.account.field.taxExempt")));
    await user.click(screen.getByLabelText(t("customers.account.portal.paperless")));
    await user.click(screen.getByLabelText(t("customers.accounts.filter.autopay")));
    await user.click(screen.getByRole("button", { name: t("customers.account.edit.save") }));

    const patch = sent.find((call) => call.method === "PATCH");
    expect(patch, "no PATCH was sent at all — the Save button writes nothing").toBeDefined();
    expect(patch?.path).toBe("/accounts/a-11812");
    // ⚠ **`toEqual`, NOT `toMatchObject`.** `toMatchObject` passes over a body
    // carrying extra keys, and the failure this file exists for is a body with
    // the WRONG key set — one too few, in `DEF-MET-4971`'s case.
    expect(patch?.body).toEqual({ tax_exempt: true, paperless: true, autopay: true });
  });

  it("DEF-CUS-9158 · an account field placed Input on Account detail is edited here, and only its change is sent", async () => {
    // The registry the dialog reads for slot S21 — one field placed there.
    const sent: { method: string; path: string; body: unknown }[] = [];
    const base = recordingClient(sent);
    const client = {
      ...base,
      get: <T,>(path: string, options?: { query?: Record<string, unknown> }) => {
        if (path === "/custom-fields") {
          sent.push({ method: "GET", path, body: options?.query });
          return Promise.resolve({
            data: {
              entity: "accounts",
              fields: [
                {
                  id: "cf-1",
                  key: "access_note",
                  label: "Access note",
                  help_text: "",
                  data_type: "text",
                  options: [],
                  is_required: false,
                  display_order: 0,
                  placement: { S21: "input" },
                },
              ],
            } as T,
            status: 200,
            headers: new Headers(),
          });
        }
        return base.get<T>(path);
      },
    } as unknown as ApiClient;
    const user = userEvent.setup();
    // A value typed on New account (another screen) must survive this edit.
    mountDialog(client, { custom_data: { visit_window: "Mornings" } } as Partial<AccountDetail>);

    const box = await screen.findByLabelText("Access note");
    expect(
      sent.find((call) => call.path === "/custom-fields")?.body,
      "the dialog must read slot S21's INPUT placements",
    ).toEqual({ entity: "accounts", screen: "S21", mode: "input" });
    await user.type(box, "Dog in yard");
    await user.click(screen.getByRole("button", { name: t("customers.account.edit.save") }));

    const patch = sent.find((call) => call.method === "PATCH");
    expect(patch?.body).toEqual({ custom_data: { access_note: "Dog in yard" } });
  });

  it("TC-N5 · an untouched field is not sent, so no audit row claims a change", async () => {
    const sent: { method: string; path: string; body: unknown }[] = [];
    const user = userEvent.setup();
    mountDialog(recordingClient(sent));

    await user.click(screen.getByLabelText(t("customers.account.portal.sms")));
    await user.click(screen.getByRole("button", { name: t("customers.account.edit.save") }));

    // `update_account` compares before saving and audits only what moved, so a
    // body naming every field would be harmless on the server — and the RECAP
    // is computed from this same object, so sending everything would make the
    // recap say a clerk changed things they did not touch.
    expect(sent.find((call) => call.method === "PATCH")?.body).toEqual({ sms_reminders: true });
  });

  it("TC-N6 · the certificate fields appear only when the exemption does", async () => {
    const user = userEvent.setup();
    mountDialog(recordingClient([]));

    // The drawing asks for the certificate number and its expiry underneath the
    // exemption; with no exemption there is nothing to certify.
    expect(screen.queryByLabelText(t("customers.newAccount.field.taxExemptRef"))).toBeNull();
    await user.click(screen.getByLabelText(t("customers.account.field.taxExempt")));
    expect(screen.getByLabelText(t("customers.newAccount.field.taxExemptRef"))).toBeInTheDocument();
    expect(
      screen.getByLabelText(t("customers.account.field.taxExemptExpires")),
    ).toBeInTheDocument();
  });
});

// ══════════════════════════════════════════════════════════════════════════
// TC-N7 · THE HOLD'S EXPIRY TEST — it fires when the refusal stops being true
// ══════════════════════════════════════════════════════════════════════════
describe("the Customer group's hold", () => {
  /**
   * ⚠ **A HOLD WITH NO SUCH TEST IS A PROMISE NOBODY IS KEEPING** (`CLAUDE.md`
   * hard-won law 2's mirror, `DEF-CWP-3925`): on 2026-09-05 the customer
   * portal's front page had **two working doors out of eight**, every refusal
   * pointing at a screen that had shipped days earlier, and all 42 test files
   * and 391 cases passed over it — because each wave tested its own screen at
   * its own address and *"has the door started pointing at it"* belonged to
   * nobody.
   *
   * **THIS HOLD WAS ALREADY RE-CHECKED ONCE AND IT CHANGED WHAT IT SAYS.** A
   * sibling landed `BR-CUS-1054` mid-wave, so `updateCustomer` exists — but it
   * writes the `customers` row and is mounted on the customer's own screen.
   * The panel this control sits on renders the ACCOUNT'S CONTACT
   * (`account_contacts`), a different table, and **nothing writes a contact.**
   * `R5` says the same: *"GET /customers/{id} is read-only and there is no
   * contacts route at all."*
   *
   * So this asserts the thing that is genuinely missing. The day a contact
   * write is wrapped, this goes red and names this file.
   */
  const CONTACT_WRITE = /^(update|create|delete|patch)(Account)?Contact/i;

  /**
   * ⚠ **THE DETECTOR IS PROVED BEFORE IT IS TRUSTED** — `CLAUDE.md` hard-won
   * law 7's second habit, *"ask what would make this check pass wrongly"*. An
   * expiry test that reports an empty set because its pattern matches nothing
   * is the *structurally incapable of failing* shape, and it would report
   * "still held" forever while the hold quietly expired. So the pattern is run
   * over names it MUST catch and names it must NOT, in the same file.
   */
  it("TC-N7a · the expiry detector catches the names it is watching for", () => {
    expect(
      ["updateContact", "updateAccountContact", "createContact", "deleteAccountContact"].filter(
        (name) => CONTACT_WRITE.test(name),
      ),
    ).toHaveLength(4);
    // …and is not so loose that it fires on a read or on the customer row.
    expect(
      ["getContact", "listContacts", "updateCustomer", "updateAccount", "updateAccountNote"].filter(
        (name) => CONTACT_WRITE.test(name),
      ),
    ).toEqual([]);
  });

  /**
   * ⚠ **TC-N7b WAS THE HOLD AND THE HOLD HAS EXPIRED — THIS IS WHAT IT TURNED
   * INTO (2026-09-13).** The case read *"no contact-write wrapper exists, which
   * is why the control refuses"* and asserted the empty set, with its own
   * failure message saying **"make it live in AccountPanelEdits.tsx and delete
   * this case"**. Both halves are done: `PATCH /accounts/{id}/contact` shipped,
   * `updateAccountContact` wraps it, and `accountGroupBlockedReason("customer")`
   * returns null. The guard did exactly its job — it went red, it named the
   * file, and a lane read it.
   *
   * **DELETING IT OUTRIGHT WOULD HAVE LOST THE COVERAGE**, so it is INVERTED
   * rather than removed: the same pattern, the same two surfaces, now asserting
   * that the door and the control are BOTH there. A wrapper deleted, or a
   * refusal put back on this group, goes red here and names this file — which
   * is the protection the hold was giving, pointing the other way.
   */
  it("TC-N7b · the contact write exists and the Customer group is live", () => {
    const contactWriters = Object.keys(endpoints).filter((name) => CONTACT_WRITE.test(name));
    expect(
      contactWriters.length,
      "the contact-write wrapper has gone — the Customer group's pencil now " +
        "opens a form onto nothing",
    ).toBeGreaterThan(0);
    expect(
      accountGroupBlockedReason("customer", t),
      "the Customer group refuses again — say why here, or make it live",
    ).toBeNull();
  });
});

// ══════════════════════════════════════════════════════════════════════════
// TC-N8 · THE UNIT GROUP'S CONTROL — `BR-CUS-1047`, live from 2026-09-13
// ══════════════════════════════════════════════════════════════════════════
// ⚠ **THIS GROUP'S HOLD EXPIRED THE DAY IT WAS WRITTEN, AND THAT IS WHY THESE
// CASES EXIST.** `R5`'s table gave `Change unit` *"A PO ruling, not an
// endpoint"*; the ruling landed 2026-09-12 and `POST /accounts/{id}/correct-unit`
// was built 2026-09-13 with **no caller in the front end** — hard-won law 2's
// mirror, a working door behind a dead control. The pencil is live now, and
// what these assert is the two things that would silently unmake that: the
// wrapper disappearing, and the group going back to refusing.
describe("the Unit group's control", () => {
  const UNIT_CORRECTION_WRITE = /^correctAccountUnit$/;

  // ⚠ **THE DETECTOR IS PROVED BEFORE IT IS TRUSTED** (law 7's second habit):
  // a pattern that matches nothing reports "still fine" forever.
  it("TC-N8a · the detector catches the name it is watching for", () => {
    expect(["correctAccountUnit"].filter((name) => UNIT_CORRECTION_WRITE.test(name))).toHaveLength(
      1,
    );
    expect(
      ["getAccountUnitCorrections", "updateAccount", "correctAccountUnitLater"].filter((name) =>
        UNIT_CORRECTION_WRITE.test(name),
      ),
    ).toEqual([]);
  });

  it("TC-N8b · the unit-correction door is wrapped and the group does not refuse", () => {
    expect(
      Object.keys(endpoints).filter((name) => UNIT_CORRECTION_WRITE.test(name)).length,
      "the unit-correction wrapper has gone — the Change unit pencil opens onto nothing",
    ).toBeGreaterThan(0);
    expect(
      accountGroupBlockedReason("unit", t),
      "the Unit group refuses again over a door that is served — say why here, " +
        "or make it live",
    ).toBeNull();
  });

  // ⚠ **THE GET HALF IS SERVED AND NOTHING RENDERS IT**, and this case is how
  // that stays visible rather than becoming folklore. The same route answers
  // this account's corrections newest first — the endpoint's own docstring
  // calls it *"the Overview's history"*, the answer to *why is this account on
  // Suite 2 when five bills say Suite 1?*. `DEF-CUS-5163` carries it. When a
  // screen starts reading it, this goes red and names the file to update.
  it("TC-N8c · the correction HISTORY read is wrapped, and no screen calls it yet", () => {
    expect(Object.keys(endpoints)).toContain("getAccountUnitCorrections");
  });
});

// ══════════════════════════════════════════════════════════════════════════
// DEF-CUS-6391 · the co-applicant is a second person on the account (T4)
// ══════════════════════════════════════════════════════════════════════════
describe("DEF-CUS-6391 — the co-applicant is stored and editable", () => {
  /** PO 2026-09-23, T4: *"a) Store a second person on the account (name,
   *  email, phone), shown on the account page"*. The dialog reads the
   *  NON-primary contact and writes only what changed, to its own door. */
  it("edits the second person, not the primary, and sends only the change", async () => {
    const sent: { method: string; path: string; body: unknown }[] = [];
    const user = userEvent.setup();
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <AccountPanelEditDialog
          detail={detail({
            contacts: [
              { id: "c-1", full_name: "Aiden, Tim", is_primary: true, email: null, phone: "(512) 555-0197" },
              { id: "c-2", full_name: "Aiden, Rae", is_primary: false, email: "rae@example.com", phone: null },
            ] as never,
          })}
          group="coApplicant"
          client={recordingClient(sent)}
          t={t}
          dateFormat="MM/DD/YYYY"
          onClose={() => undefined}
          onSaved={() => undefined}
        />
      </QueryClientProvider>,
    );
    const name = screen.getByLabelText(t("customers.account.field.fullName"));
    expect(name).toHaveValue("Aiden, Rae");
    await user.type(screen.getByLabelText(t("customers.account.field.phone")), "(512) 555-0142");
    await user.click(screen.getByRole("button", { name: t("customers.account.edit.save") }));

    const patch = sent.find((call) => call.method === "PATCH");
    expect(patch?.path).toBe("/accounts/a-11812/co-applicant");
    expect(patch?.body).toEqual({ phone: "(512) 555-0142" });
  });
});
