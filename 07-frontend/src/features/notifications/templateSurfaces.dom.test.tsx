// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  SET-10's five document shapes (PO 2026-09-07).
// Screens: SET-10
// Rules:   B14 rule 32 (one sentence per section) · BR-SHL-020 (an absent fact
//          is named, never faked) · hard-won law 7 (prove a guard RED, and ask
//          what would make it pass WRONGLY)
// Defects: DEF-NOT-4464 · DEF-NOT-4473 · DEF-NOT-4474 · DEF-NOT-4475 ·
//          DEF-NOT-4476
// ───────────────────────────────────────────────────────
//
// WHAT THIS FILE CAN AND CANNOT ANSWER, SAID FIRST SO NOBODY TRUSTS IT TOO FAR.
//
// jsdom performs NO LAYOUT. So every width, every height and every "is the
// document the largest thing on the page" question is unanswerable here and is
// asked in a real browser by
// `10-scripts/cr076_template_designer_walkthrough.mjs` instead. A test in this
// file asserting `190px` would be asserting a STRING, and passing on a bubble
// rendered at any width at all — which is hard-won law 6's whole point.
//
// What this file CAN answer is what is in the document and what is not: that a
// line of the wording is drawn once rather than twice, that an absent utility
// name is stated rather than filled in, that the signature block takes the
// author's own labels, and that the in-app shape has no send-test control. Each
// of those is a fact about content, and content is what jsdom holds.
//
// RED-PROVED BEFORE TRUSTED GREEN, through `vitest run` — the harness that
// actually runs them, not a hand-rolled entry point (DEF-GOV-3733). Each proof
// is named beside its case.
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import "@testing-library/jest-dom/vitest";

import "@/i18n";

import type { TemplateDetail, TemplatePreview } from "@/api/endpoints";

import {
  ContractSurface,
  EmailSurface,
  InAppSurface,
  SmsSurface,
  signatureFields,
} from "./templateSurfaces";

afterEach(cleanup);

function aPreview(overrides: Partial<TemplatePreview> = {}): TemplatePreview {
  return {
    body: "Hello Pat Rivera\n\nYour bill for 12 Oak Street is ready.",
    subject: "Your bill is ready",
    channel: "email",
    sample_data: true,
    sample_data_notice: "Preview only.",
    sample_data_detail: "Rendered from sample data. Nothing is sent.",
    absences: [],
    problems: [],
    unsampled: [],
    rendered_length: 54,
    ...overrides,
  };
}

function aDetail(overrides: Partial<TemplateDetail> = {}): TemplateDetail {
  return {
    code: "email_bill_ready",
    name: "Bill ready",
    category: "billing",
    category_source: "cr_007",
    kind: "Email",
    used_by: "Every bill run",
    group: "email",
    channel: "email",
    preview_surfaces: ["email"],
    merge_fields: [],
    merge_field_rows: [
      {
        token: "utility_name",
        insert: "{utility_name}",
        sample_value: null,
        sample_unavailable: "From Settings → Company",
        derived_spelling: false,
      },
    ],
    sample_identity: { customer_name: "Pat Rivera", account_no: "AC-000000" },
    derived_spelling: [],
    platform_default: null,
    mandatory_content: [],
    custom_field_variables: [],
    catalog_unavailable: null,
    body_unavailable: null,
    variants: [],
    selected_variant: null,
    versions: [],
    preview: null,
    preview_unavailable: null,
    sms_character_counter: 160,
    can_edit: true,
    cannot_edit_reason: null,
    can_test_send: true,
    test_send_reason: "Goes to your own address.",
    can_download_pdf: false,
    download_pdf_reason: "",
    can_set_default: false,
    set_default_reason: "",
    language_selection_reason: "",
    ...overrides,
  } as TemplateDetail;
}

/** Every visible string in the tree, leaf by leaf — the same question the
 *  browser check asks, minus the geometry. */
function leafTexts(root: HTMLElement): string[] {
  const out: string[] = [];
  for (const el of root.querySelectorAll("*")) {
    if (el.children.length > 0) continue;
    const t = (el.textContent ?? "").trim();
    if (t !== "") out.push(t);
  }
  return out;
}

describe("the email shape", () => {
  // RED PROOF: putting `firstLine(preview.body)` back above the paper — the
  // shape DEF-NOT-4464 was filed for — fails this case with "Hello Pat Rivera"
  // counted twice.
  it("draws no line of the wording twice (DEF-NOT-4464)", () => {
    const { container } = render(
      <EmailSurface preview={aPreview()} data={aDetail()} />,
    );
    const counts = new Map<string, number>();
    for (const t of leafTexts(container as unknown as HTMLElement)) {
      counts.set(t, (counts.get(t) ?? 0) + 1);
    }
    expect([...counts.entries()].filter(([, n]) => n > 1)).toEqual([]);
  });

  it("says who it is from and who it is to, and the subject once", () => {
    render(<EmailSurface preview={aPreview()} data={aDetail()} />);
    expect(screen.getByTestId("preview-subject")).toHaveTextContent("Your bill is ready");
    expect(screen.getByTestId("preview-email-to")).toHaveTextContent("Pat Rivera");
  });

  // RED PROOF: returning `{ value: "Your utility" }` from `senderOf` when the
  // server sampled nothing fails this — which is the whole of BR-SHL-020.
  it("STATES an absent utility name instead of inventing one (BR-SHL-020)", () => {
    render(<EmailSurface preview={aPreview()} data={aDetail()} />);
    const absent = screen.getByTestId("preview-email-from-absent");
    expect(absent).toHaveTextContent("—");
    expect(absent).toHaveAttribute("title", "From Settings → Company");
  });

  it("explains no part of this product's own database to a clerk (B14 rule 32)", () => {
    const { container } = render(<EmailSurface preview={aPreview()} data={aDetail()} />);
    const text = (container.textContent ?? "").toLowerCase();
    for (const ours of ["preheader", "field", "database", "column", "schema"]) {
      expect(text, `the inbox header says "${ours}" to a clerk`).not.toContain(ours);
    }
  });
});

describe("the text-message shape", () => {
  // RED PROOF: deleting the `<p data-testid="preview-sms-count">` block leaves
  // the bubble rendering perfectly and fails this — DEF-NOT-4474's exact shape,
  // where every assertion about the METER passed while nobody could see it.
  it("puts the character count and the message count beside the bubble (DEF-NOT-4474)", () => {
    render(
      <SmsSurface
        preview={aPreview({ body: "Your bill is ready.", rendered_length: 19 })}
        data={aDetail({ group: "sms", sms_character_counter: 160 })}
      />,
    );
    expect(screen.getByTestId("preview-sms-bubble")).toHaveTextContent("Your bill is ready.");
    expect(screen.getByTestId("preview-sms-characters")).toHaveTextContent("19");
    expect(screen.getByTestId("preview-sms-messages")).toHaveTextContent("1");
  });

  // The fact that costs money. 161 characters is TWO messages, and the warning
  // is what a person needs before they press send on 2,000 accounts.
  it("says so when the wording has become more than one message", () => {
    render(
      <SmsSurface
        preview={aPreview({ body: "x".repeat(200), rendered_length: 200 })}
        data={aDetail({ group: "sms", sms_character_counter: 160 })}
      />,
    );
    expect(screen.getByTestId("preview-sms-messages")).toHaveTextContent("2");
    expect(screen.getByTestId("preview-sms-cost")).toBeTruthy();
  });

  it("counts what is SENT, not what was typed", () => {
    // `rendered_length` and not `body.length`: a body of `{first_name}` is
    // twelve characters and sends as three.
    render(
      <SmsSurface
        preview={aPreview({ body: "Pat", rendered_length: 3 })}
        data={aDetail({ group: "sms" })}
      />,
    );
    expect(screen.getByTestId("preview-sms-characters")).toHaveTextContent("3");
  });
});

describe("the document-to-sign shape", () => {
  const SIGNED = "Customer signature: (signed electronically)          Date: 31/01/2026";

  it("reads the author's own signature line as fields, in any language", () => {
    expect(signatureFields(SIGNED)).toEqual([
      { label: "Customer signature", ink: "(signed electronically)" },
      { label: "Date", ink: "31/01/2026" },
    ]);
    // The same line written by a utility in its own language still parses,
    // because nothing here matches an English word (B14 rule 35's principle).
    expect(signatureFields("Firma del cliente: (firmado)   Fecha: 31/01/2026")).toEqual([
      { label: "Firma del cliente", ink: "(firmado)" },
      { label: "Fecha", ink: "31/01/2026" },
    ]);
  });

  // RED PROOF, and it is the negative half this file exists for: a version that
  // split on any whitespace turned "By signing, you agree to the terms above."
  // into eight nonsense fields. A line with no colon returns null and is drawn
  // as the prose it is.
  it("refuses to read ordinary prose as a signature block", () => {
    expect(signatureFields("By signing, you agree to the terms above.")).toBeNull();
    expect(signatureFields("")).toBeNull();
  });

  it("draws the block where the author's line falls, with the author's labels", () => {
    const { container } = render(
      <ContractSurface
        body={`Service agreement\n\nBy signing, you agree to the terms above.\n${SIGNED}`}
        data={aDetail({
          group: "contracts",
          merge_field_rows: [
            {
              token: "customer_signature",
              insert: "{customer_signature}",
              sample_value: "(signed electronically)",
              sample_unavailable: null,
              derived_spelling: false,
            },
          ],
        })}
      />,
    );
    const block = screen.getByTestId("preview-signature");
    expect(block).toHaveTextContent("Customer signature");
    expect(block).toHaveTextContent("Date");
    expect(screen.getAllByTestId("preview-signature-field")).toHaveLength(2);
    /* ⚠ AND THE PLAIN LINE IS GONE, not drawn above it — an APPENDED block
       prints both, which is DEF-NOT-4464 one shape along.
       ⚠ **COUNTED IN THE TEXT, NOT ASKED OF `queryByText`, AND THAT CORRECTION
       IS THE POINT.** This case first read `expect(queryByText(SIGNED))
       .toBeNull()`, and when the append version was built to prove the case RED
       it PASSED — because Testing Library normalises whitespace, and the
       author's line holds a run of ten spaces, so that query could never match
       whether the line was drawn or not. A check that cannot fail is worse than
       no check; it was found by law 7's own procedure and only by that. */
    const shown = container.textContent ?? "";
    expect(shown.split("(signed electronically)").length - 1).toBe(1);
    expect(shown.split("Customer signature").length - 1).toBe(1);
  });

  /* ⚠ **THE CASE THAT WAS DEAD UI, AND IT IS THE ONE THAT MATTERS MOST.**
     None of the four contract classes has a published version — BR-NOT-002
     makes a contract effective-dated and that date is a human's choice — so
     none of them ever reaches the RENDERED path. What a clerk actually sees is
     the platform's OFFERED wording, which still carries its `{tokens}`. A
     renderer that matched only the substituted sample therefore drew a
     signature block on exactly zero of the templates it was written for, while
     every test above passed, because each tested the path it was written for.
     Found by sweeping every row in a browser and by nothing else (law 2). */
  it("draws the block on the OFFERED wording too, where the tokens are unresolved", () => {
    const { container } = render(
      <ContractSurface
        body={"Service agreement\n\nCustomer signature: {customer_signature}          Date: {date}"}
        data={aDetail({
          group: "contracts",
          merge_field_rows: [
            {
              token: "customer_signature",
              insert: "{customer_signature}",
              sample_value: "(signed electronically)",
              sample_unavailable: null,
              derived_spelling: false,
            },
          ],
        })}
      />,
    );
    expect(screen.getByTestId("preview-signature")).toBeTruthy();
    expect(screen.getAllByTestId("preview-signature-field")).toHaveLength(2);
    expect(container.textContent ?? "").toContain("Customer signature");
    // and the raw line is not ALSO printed as prose
    expect((container.textContent ?? "").split("Customer signature").length - 1).toBe(1);
  });

  it("leaves a contract with no signature token exactly as its author typed it", () => {
    render(
      <ContractSurface
        body={`Deposit agreement\n\n${SIGNED}`}
        data={aDetail({ group: "contracts", merge_field_rows: [] })}
      />,
    );
    expect(screen.queryByTestId("preview-signature")).toBeNull();
  });
});

describe("the in-app shape", () => {
  // RED PROOF: deleting the audience line leaves a banner that renders
  // perfectly and fails this — DEF-NOT-4476, where the only signal that no
  // customer reads this template was a MISSING letterhead.
  it("says who reads it, in one sentence (DEF-NOT-4476, B14 rule 32)", () => {
    render(<InAppSurface preview={aPreview({ body: "Run finished." })} />);
    const line = screen.getByTestId("preview-audience");
    expect(line.textContent ?? "").not.toEqual("");
    // One sentence. A second would be over rule 32's budget.
    expect((line.textContent ?? "").split(".").filter((s) => s.trim() !== "")).toHaveLength(1);
    // And it carries no rule id or internal code (B14 rule 31 / DEF-335).
    expect(line.textContent ?? "").not.toMatch(/\b(?:BR|OQ|DEF|US|EP)-/);
  });

  it("has no letterhead, and the absence is the ruling", () => {
    render(<InAppSurface preview={aPreview({ body: "Run finished." })} />);
    expect(screen.queryByTestId("preview-letterhead")).toBeNull();
  });

  it("draws the banner over a sketch that is decoration, not a second document", () => {
    render(<InAppSurface preview={aPreview({ body: "Run finished." })} />);
    const sketch = screen.getByTestId("preview-app-sketch");
    expect(sketch).toContainElement(screen.getByTestId("preview-bell-panel"));
    for (const bar of sketch.querySelectorAll("[aria-hidden='true']")) {
      expect(bar.textContent ?? "").toEqual("");
    }
  });
});
