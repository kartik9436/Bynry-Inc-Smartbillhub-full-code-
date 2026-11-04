// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-645 — "you are showing some database keys on audit screen" (PO,
//           2026-08-24, on the deployed v2.42.0). The cell read, verbatim:
//           `account.created · id: 01a01d9a-4609-7637-ad8d-0cbb1cf8d9cc;
//            name: Ana Alvarez; plan: — (+38 more)`
// Story:    US-AUD-004 · US-AUD-005   Screens: S21 (Audit tab) · S61
// Rules:    BR-AUD-003 · BR-AUD-006 · BR-AUD-010
// ───────────────────────────────────────────────────────
//
// THE REGRESSION GUARD IS THE FIRST TEST IN THIS FILE AND IT IS DELIBERATELY
// BLUNT: no UUID-shaped string may appear in what a person READS on an audit
// surface. It was proved RED against the shipped cell before the fix existed —
// with `{row.action}{row.summary}` back in `AuditTab`, it failed with
//
//   AssertionError: the audit tab printed an internal identifier:
//   01a01d9a-4609-7637-ad8d-0cbb1cf8d9cc
//   expected [ '01a01d9a-4609-7637-ad8d-0cbb1cf8d9cc' ] to deeply equal []
//
// ⚠ IT MEASURES TEXT, NOT MARKUP, AND THE DIFFERENCE IS STATED RATHER THAN
// GLOSSED. The tab's "full log" link is `?f.entity_type=account&f.entity_id=<id>`
// — the entity id is the FILTER the S61 viewer needs, so it must stay in the
// href. What DEF-645 is about is what a reader sees, so the guard strips tags
// and asks of the remaining words. A UUID in an href is invisible to a user and
// load-bearing for the link; a UUID in a cell is the defect.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { AuditRow } from "@/api/endpoints";
import { AuditTab, entityAuditQueryKey } from "@/features/metering/PremisesDetailPage";

import {
  AUDIT_EVENT_SENTENCES,
  AuditEventCell,
  MACHINE_FIELDS,
  UUID_SHAPED,
  auditEntityLabel,
  auditEventSentence,
  auditFieldSet,
  formatAuditValue,
  humaniseFieldKey,
  isIdentifierField,
} from "./auditEvents";

const t = (key: string, params?: Record<string, unknown>) => i18n.t(key, params) as string;

/** The account the PO was looking at, and its real primary key. */
const ACCOUNT_ID = "01a01d9a-4609-7637-ad8d-0cbb1cf8d9cc";

/**
 * The row as the server serves it — `summary` is `apps/audit/selectors.summarize`
 * output for a 41-field create snapshot, quoted from the defect report.
 */
function auditRow(over: Partial<AuditRow> = {}): AuditRow {
  return {
    id: "au-1",
    created_at: "2026-08-24T10:04:00Z",
    actor: { id: "u-1", name: "Nilesh Gudhe" },
    action: "account.created",
    entity_type: "account",
    entity_id: ACCOUNT_ID,
    summary: `id: ${ACCOUNT_ID}; name: Ana Alvarez; plan: — (+38 more)`,
    source: null,
    ...over,
  };
}

/** Every UUID a reader can actually SEE — markup stripped, hrefs with it. */
function visibleIdentifiers(html: string): string[] {
  const text = html.replace(/<[^>]*>/g, " ");
  const global = new RegExp(UUID_SHAPED.source, "gi");
  return text.match(global) ?? [];
}

function renderTab(rows: AuditRow[]): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(entityAuditQueryKey("account", ACCOUNT_ID), {
    page: { count: rows.length, next: null, previous: null, results: rows },
    window: { window: "hot", from: "2024-08-24T00:00:00Z" },
  });
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/brazosbend/accounts/01a01d9a"]}>
        <AuditTab entityType="account" entityId={ACCOUNT_ID} t={t} regional={{}} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("DEF-645 — an audit row is a sentence, not a database record", () => {
  it("prints no internal identifier anywhere a person reads (the regression guard)", () => {
    const html = renderTab([auditRow()]);
    expect(visibleIdentifiers(html), "the audit tab printed an internal identifier").toEqual([]);
  });

  it("prints the event as English, never as the action code", () => {
    const html = renderTab([auditRow()]);
    expect(html).toContain("Account opened");
    expect(html.replace(/<[^>]*>/g, " ")).not.toContain("account.created");
    // The code is still one grep away for support — in the DOM, not in the text.
    expect(html).toContain('data-audit-action="account.created"');
  });

  it("never draws the server's `key: value` blob or its dead `(+38 more)`", () => {
    const text = renderTab([auditRow()]).replace(/<[^>]*>/g, " ");
    expect(text).not.toContain("+38 more");
    expect(text).not.toContain("name: Ana Alvarez");
    expect(text).not.toContain("plan: —");
  });

  it("offers the whole set behind one expand, rather than truncating it", () => {
    const html = renderTab([auditRow()]);
    // Disclosure's own control, on the row that has a payload.
    expect(html).toContain("Expand");
    expect(html).toContain('aria-expanded="false"');
  });

  it("a row with nothing recorded is a plain sentence — no dead toggle", () => {
    const html = renderTab([auditRow({ action: "auth.sign_in", summary: "" })]);
    expect(html).toContain("Signed in");
    expect(html).not.toContain("aria-expanded");
  });
});

describe("DEF-645 — an event this build does not know", () => {
  it("says so, and neither prints the code nor invents a verb for it", () => {
    const sentence = auditEventSentence("widget.frobnicated", t);
    expect(sentence.known).toBe(false);
    expect(sentence.text).toBe("Activity recorded");

    const html = renderToStaticMarkup(
      <MemoryRouter>
        <AuditEventCell row={auditRow({ action: "widget.frobnicated" })} t={t} />
      </MemoryRouter>,
    );
    const text = html.replace(/<[^>]*>/g, " ");
    expect(text).toContain("Activity recorded");
    expect(text).toContain("this event type is not described yet");
    // Not the code, and NOT a humanised guess at what it means.
    expect(text).not.toContain("widget.frobnicated");
    expect(text).not.toContain("Widget frobnicated");
    // Still reachable for support.
    expect(html).toContain('data-audit-action="widget.frobnicated"');
  });

  it("still offers the recorded values — only the verb is withheld", () => {
    const html = renderToStaticMarkup(
      <MemoryRouter>
        <AuditEventCell row={auditRow({ action: "widget.frobnicated" })} t={t} />
      </MemoryRouter>,
    );
    expect(html).toContain('aria-expanded="false"');
  });
});

describe("DEF-645 — the recorded values, in words", () => {
  const snapshot = {
    id: ACCOUNT_ID,
    unit_id: "0f3c1e2b-9d44-4c11-8a02-2f6a1b7c9e10",
    account_no: "10432",
    name: "Ana Alvarez",
    status_name: "Active",
    bad_address: false,
    nsf_count: 0,
    plan: null,
    plan_snapshot_unavailable: "BR-CUS-029",
    contacts: [{ id: "c-1" }, { id: "c-2" }],
  };

  it("drops the record's own key and every sideways one — DEF-645 fault (1)", () => {
    const set = auditFieldSet(null, snapshot, t);
    expect(set.fields.map((field) => field.key)).not.toContain("id");
    expect(set.fields.map((field) => field.key)).not.toContain("unit_id");
    // id · unit_id · plan_snapshot_unavailable ("BR-CUS-029" is a rule id, and a
    // rule id is exactly what G28 exists to keep off a screen — but it arrives
    // here as DATA, where G28 cannot see it).
    expect(set.hiddenReferences).toBe(3);
  });

  it("labels fields in words, never as the column — DEF-645 fault (3)", () => {
    const set = auditFieldSet(null, snapshot, t);
    const labels = set.fields.map((field) => field.label);
    expect(labels).toContain("Account number");
    expect(labels).toContain("Name");
    expect(labels).toContain("Returned payments");
    expect(labels).not.toContain("account_no");
    expect(labels).not.toContain("nsf_count");
  });

  it("keeps every remaining field — nothing is cut at three", () => {
    const wide: Record<string, unknown> = {};
    for (let index = 0; index < 41; index += 1) {
      wide[`field_${index}`] = `value ${index}`;
    }
    expect(auditFieldSet(null, wide, t).fields).toHaveLength(41);
  });

  it("reads an update as before → after, changed fields only (BR-AUD-003)", () => {
    const set = auditFieldSet(
      { status_name: "Pending activation", name: "Ana Alvarez" },
      { status_name: "Active", name: "Ana Alvarez" },
      t,
    );
    expect(set.fields).toHaveLength(1);
    expect(set.fields[0]).toMatchObject({
      label: "Status",
      before: "Pending activation",
      after: "Active",
    });
  });

  it("reads a terminal action as before-only (BR-AUD-003)", () => {
    const set = auditFieldSet({ status_name: "Active" }, null, t);
    expect(set.fields[0]).toMatchObject({ before: "Active", after: "Not set" });
  });

  it("says values the way a person reads them, and never dumps JSON", () => {
    expect(formatAuditValue(null, t)).toBe("Not set");
    expect(formatAuditValue("", t)).toBe("Not set");
    expect(formatAuditValue(true, t)).toBe("Yes");
    expect(formatAuditValue(false, t)).toBe("No");
    expect(formatAuditValue([], t)).toBe("None");
    expect(formatAuditValue([{ id: "c-1" }, { id: "c-2" }], t)).toBe("2 recorded");
    expect(formatAuditValue({}, t)).toBe("None");
    expect(formatAuditValue("Ana Alvarez", t)).toBe("Ana Alvarez");
    expect(formatAuditValue("x".repeat(200), t)).toHaveLength(80);
  });

  it("humanises an unlisted key rather than printing it raw", () => {
    expect(humaniseFieldKey("read_window_closes_on")).toBe("Read window closes on");
  });

  it("knows an identifier by its key OR by its value", () => {
    expect(isIdentifierField("id", "10432")).toBe(true);
    expect(isIdentifierField("unit_id", "u-1")).toBe(true);
    expect(isIdentifierField("note", `see ${ACCOUNT_ID}`)).toBe(true);
    expect(isIdentifierField("name", "Ana Alvarez")).toBe(false);
    // A sentence that MENTIONS a rule is not an identifier — dropping it would
    // lose recorded data, which is its own defect on an audit trail.
    expect(isIdentifierField("reason", "refused under BR-CUS-022")).toBe(false);
    expect(isIdentifierField("plan_snapshot_unavailable", "BR-CUS-029")).toBe(true);
  });

  it("DEF-2377: drops the two MACHINE fields whole — br_ref and job", () => {
    // Both are the server obeying a rule: `br_ref` names the rule a refusal
    // enforced (the `data-br-ref` posture, DEF-322), and BR-AUD-003 REQUIRES a
    // system job be named in the payload. Neither is a sentence for a clerk.
    expect(MACHINE_FIELDS.has("br_ref")).toBe(true);
    expect(MACHINE_FIELDS.has("job")).toBe(true);
    expect(isIdentifierField("br_ref", "BR-CUS-103 · PO ruling 2026-08-30")).toBe(true);
    expect(isIdentifierField("job", "payments.allocation_release")).toBe(true);
    const set = auditFieldSet(
      null,
      { status: "Active", br_ref: "BR-PAY-150", job: "payments.record" },
      t,
    );
    expect(set.fields.map((f) => f.key)).toEqual(["status"]);
    expect(set.hiddenReferences).toBe(2);
  });
});

describe("DEF-2377 — no internal reference reaches a value a clerk reads", () => {
  /**
   * THE SERVER'S OWN SENTENCES, AS THEY ARE WRITTEN TODAY.
   *
   * Every one of these is the literal value a `core.audit` payload carries in
   * `06-backend` after the DEF-2377 rewrite, copied here rather than paraphrased.
   * `g71_audit_payload_prose.py` is what keeps the backend from drifting away
   * from them; this is the other half — what the SCREEN does with what arrives.
   */
  const STORED_TODAY: Record<string, unknown> = {
    batch_rollback: "not offered — each bill is corrected on its own",
    replacement_link: "this bill is linked to the bill it replaces",
    affects: "future renders only",
    posts_no_journal_line: "no money moved",
    activated_by: "customer e-signature alone",
    judged_on: "the posting date, never the clearing date",
    what_the_owner_sees: "the setup screen names every part that did not load, and why",
    decided: "every kind of payment is filed to Undeposited funds until the bank confirms it",
  };

  it("no rule id, defect id, open question or table name is left in one", () => {
    const set = auditFieldSet(null, STORED_TODAY, t);
    const readable = set.fields.map((f) => `${f.label} ${f.after}`).join(" | ");
    // The register grammars, with the five-digit ceiling the PO ruled on
    // 2026-08-31 and the `(?!\d)` lookahead DEF-2804 made load-bearing.
    expect(readable).not.toMatch(/\b(?:BR|US|EP|ADR)-[A-Z]{2,4}-\d{2,5}(?!\d)\b/);
    expect(readable).not.toMatch(/\b(?:OQ|DEF|GT|TD|IS|TC|CR)-\d{1,5}(?!\d)\b/);
    // A database table or a column path. `sample_data_runs` is the one the
    // Product Owner actually read on the deployed screen.
    expect(readable).not.toMatch(/sample_data_runs|bill_run_decisions|outbound_messages/);
    expect(readable).not.toMatch(/\b[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*\b/);
    // And every one of the eight still SAYS something — the fix is a rewrite,
    // not a deletion. An empty audit trail would be the worse defect.
    expect(set.fields).toHaveLength(Object.keys(STORED_TODAY).length);
    for (const field of set.fields) {
      expect(field.after.length).toBeGreaterThan(8);
    }
  });

  it("proves the guard bites: the sentence the PO photographed still fails it", () => {
    // ⚠ THIS IS THE RED PROOF, KEPT (hard-won law 7). The value below is what
    // `apps/tenancy/sample_data.py` stored until 2026-09-02 and what the
    // Product Owner read on the deployed audit log. If the assertion above ever
    // stops being able to fail, this is what says so.
    const wasStored = "the named sample_data_runs rows this run stored (BR-TEN-060)";
    const set = auditFieldSet(null, { s62_flag: wasStored }, t);
    const readable = set.fields.map((f) => `${f.label} ${f.after}`).join(" | ");
    expect(readable).toMatch(/\b(?:BR|US|EP|ADR)-[A-Z]{2,4}-\d{2,5}(?!\d)\b/);
    expect(readable).toMatch(/sample_data_runs/);
  });
});

describe("DEF-2378 — the Entity column says what the record IS", () => {
  it("names the kinds worth naming and humanises the rest, never the raw type", () => {
    expect(auditEntityLabel("tenant", t)).toBe("Utility");
    expect(auditEntityLabel("invoices", t)).toBe("Bill");
    expect(auditEntityLabel("payment_plans", t)).toBe("Payment plan");
    // Not in the map: humanised mechanically, the same way an unlisted FIELD
    // key is. Never printed raw, and never invented into a different noun.
    expect(auditEntityLabel("read_import_row", t)).toBe("Imported reading");
    expect(auditEntityLabel("bank_line", t)).toBe("Bank line");
    // A row whose type the server left empty still reads as something.
    expect(auditEntityLabel("", t)).toBe("Record");
    expect(auditEntityLabel("   ", t)).toBe("Record");
  });

  it("carries no id, whatever it is handed", () => {
    for (const type of ["tenant", "wizard_park", "invoices", "bank_line"]) {
      expect(auditEntityLabel(type, t)).not.toMatch(UUID_SHAPED);
      expect(auditEntityLabel(type, t)).not.toMatch(/_id\b/);
    }
  });
});

describe("the event vocabulary", () => {
  it("covers the events the backend actually emits, and says them in English", () => {
    // Spot-checks across six modules; every code here was found at an emitter
    // in 06-backend (see the presenter's header for how).
    expect(AUDIT_EVENT_SENTENCES["invoice.issued"]).toBe("Bill issued");
    expect(AUDIT_EVENT_SENTENCES["read.estimated"]).toBe("Read estimated");
    expect(AUDIT_EVENT_SENTENCES["auth.sign_in_failed"]).toBe("Sign-in failed");
    expect(AUDIT_EVENT_SENTENCES["settings.service.enabled"]).toBe("Service switched on");
    expect(AUDIT_EVENT_SENTENCES["user.role_changed"]).toBe("User role changed");
    // Built from `f"{run.target}.created"` in apps/metering/import_runs.py.
    expect(AUDIT_EVENT_SENTENCES["assets_meters.created"]).toBe("Meters created by an import");
  });

  it("has no sentence that is just the code with the dot removed", () => {
    for (const [code, sentence] of Object.entries(AUDIT_EVENT_SENTENCES)) {
      expect(sentence, `${code} reads like a code`).not.toMatch(/[a-z]_[a-z]|\.[a-z]/);
    }
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-645 · US-AUD-004/005 · BR-AUD-003/006/010
// generated: 2026-08-24 by the DEF-645 lane (M2)
// checklist: A✔ B✔ C=n/a(no API change — the presenter reads two endpoints that already exist) D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ (this lane's files; a sibling lane's ServiceRequestDetailPage.tsx is red in the shared tree) · eslint --max-warnings 0✔ · vitest 2293 passed / 1 skipped / 188 todo across 134 files✔ (the whole suite, green) · routeBUtilities✔ (proved RED first with a planted `itmes-center`) · G28✔ G31✔ G32 G37✔ unchanged by this lane · browser walkthrough in Chromium on the seeded stack (S21 Audit tab collapsed + expanded, S61 list + drawer)
// exceptions: E4 the EXPANDED field list is proved through `auditFieldSet` and
//   `AuditFieldList`'s own inputs rather than by clicking: Disclosure unmounts
//   its body when closed and `renderToStaticMarkup` cannot open it. The open
//   state was proved in Chromium instead (hard-won law 6) — see the defect row.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
