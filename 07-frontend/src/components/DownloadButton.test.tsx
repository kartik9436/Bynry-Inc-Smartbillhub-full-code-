// ── Trace ──────────────────────────────────────────────
// Story:    US-SHL-008 (EP-SHL-02 §Stories)  Screens: every export-declaring list/report (S17, S30, S44, …)
// Rules:    BR-SHL-016 · BR-SHL-029 · IS-11 (CSV always, PDF where formatted, no XLSX)
// ───────────────────────────────────────────────────────
// TC tests for FE-14 DownloadButton: the IS-11 control surface. Export
// EXECUTION (streaming, caps, audit) is BE-21's — honest todos below.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import "@/i18n"; // initializes the i18next singleton with the five catalogs

import { DownloadButton } from "./DownloadButton";
import { DownloadIcon } from "./icons";

const noop = () => undefined;

describe("US-SHL-008 — DownloadButton (FE-14): the one IS-11 download control", () => {
  it("IS-11: CSV always — the default control is a single 'Download CSV' button (no menu when nothing else is offered)", () => {
    const html = renderToStaticMarkup(<DownloadButton onDownload={noop} />);
    expect(html).toContain("Download CSV");
    expect(html).not.toContain('data-download="menu"');
    expect(html).not.toContain("Download PDF");
  });

  it("IS-11: where the screen declares a formatted layout, the menu offers CSV AND PDF — CSV never disappears", () => {
    const html = renderToStaticMarkup(<DownloadButton onDownload={noop} pdf />);
    expect(html).toContain('data-download="menu"');
    expect(html).toContain("Download CSV");
    expect(html).toContain("Download PDF");
  });

  it("IS-11: no XLSX in v1 — the control cannot even be asked for one", () => {
    const single = renderToStaticMarkup(<DownloadButton onDownload={noop} />);
    const menu = renderToStaticMarkup(<DownloadButton onDownload={noop} pdf />);
    expect(single.toLowerCase()).not.toContain("xlsx");
    expect(menu.toLowerCase()).not.toContain("xlsx");
    expect(menu.toLowerCase()).not.toContain("excel");
  });

  it("US-SHL-014-adjacent: a gated control renders disabled (reason copy is the consuming screen's)", () => {
    const html = renderToStaticMarkup(<DownloadButton onDownload={noop} pdf disabled />);
    expect(html).toContain("disabled");
    expect(html).not.toContain('data-download="menu"'); // no dead popover behind a disabled control
  });

  it("US-SHL-008 (IS-9 hook, both sides): the control slots into DataTable's downloadSlot — proven from the table side at US-SHL-008 (IS-9 hook) in DataTable.test.tsx", () => {
    // This side only proves the control renders standalone with the .btn kit.
    const html = renderToStaticMarkup(<DownloadButton onDownload={noop} />);
    expect(html).toContain('data-variant="secondary"');
  });

  it.todo(
    "US-SHL-008 TC-5: export honors current filters + visible columns and streams server-side under RLS — BE-21 + FI-01 wiring",
  );
  it.todo(
    "US-SHL-008 TC-6/TC-7: the 50,000-row cap refuses with plain-language copy and a money-table export writes audit_log (BR-SHL-016/029) — server scope",
  );
  it.todo(
    "US-SHL-008 TC-8 (isolation): an export can never contain another tenant's rows — backend isolation suite",
  );
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-SHL-008@17df6a0 (story+rules snapshot hash)
// generated: 2026-08-09 by story-coder v1
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: trace_lint✔ run_gates✔ (10 PASS · 0 FAIL · 2 SKIP) tsc✔ eslint✔ vitest 94/94✔ (12 todo this packet — browser/server/consumer scope)
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────

// ── CR-045 A.3 ──────────────────────────────────────────────────────────────
describe("CR-045 A.3 — the download control is a ↓ glyph, in BOTH variants", () => {
  // ⚠ **WHY THE TESTS ABOVE STAY GREEN AND STILL DO NOT COVER THIS.** They
  // assert `html` CONTAINS "Download CSV" — and it still does, as the
  // `aria-label` and the `title`. Every one of them passes on a button with a
  // text label and on a button with a glyph, which is the whole reason a
  // separate claim is needed: the sentence did not go away, it changed ROLE.
  //
  // What this cannot claim is the ~95px the glyph gives back to the toolbar.
  // jsdom computes no layout and no gate in this repo reads rendered output
  // (hard-won law 6). The width refund is the ARGUMENT; the structure is what
  // a test can hold.
  it("the CSV-only variant renders the glyph and no visible word", () => {
    const html = renderToStaticMarkup(<DownloadButton onDownload={noop} />);
    expect(html).toContain("<svg");
    // The sentence survives as the accessible name and the tooltip …
    expect(html).toContain('aria-label="Download CSV"');
    expect(html).toContain('title="Download CSV"');
    // … and NOT as a text node between the tags.
    expect(html).not.toContain(">Download CSV<");
  });

  it("the CSV/PDF variant changes only its TRIGGER — the two menu items keep their words", () => {
    const html = renderToStaticMarkup(<DownloadButton onDownload={noop} pdf />);
    const summary = html.slice(html.indexOf("<summary"), html.indexOf("</summary>"));
    expect(summary).toContain("<svg");
    expect(summary).toContain('aria-label="Download CSV"');
    expect(summary).not.toContain(">Download");
    // A menu item is a CHOICE and a choice needs a name.
    expect(html).toContain(">Download CSV<");
    expect(html).toContain(">Download PDF<");
  });

  it("both variants occupy the SAME square, so a toolbar's width does not depend on whether its screen offers a PDF", () => {
    const single = renderToStaticMarkup(<DownloadButton onDownload={noop} />);
    const menu = renderToStaticMarkup(<DownloadButton onDownload={noop} pdf />);
    for (const html of [single, menu]) {
      expect(html).toContain("h-9 w-9");
    }
  });

  it("B14 rule 15: the glyph rendered here IS the shared vocabulary's, not a local copy", () => {
    // ⚠ **ASSERTED BY COMPARING THE PIXELS, NOT BY READING THE SOURCE.** The
    // first draft read `DownloadButton.tsx` off disk and grepped it for the
    // import — which proves the import EXISTS and not that it is what renders,
    // and needed `node:fs` in a browser-ish suite besides (tsc refused it).
    //
    // Byte-comparing the two markups is the stronger claim: an inline copy that
    // drifted from the vocabulary by one path would fail here, and that drift —
    // the same pencil four times, byte for byte, until it wasn't — is DEF-348,
    // which is why `icons.tsx` exists at all.
    const glyph = renderToStaticMarkup(<DownloadIcon />);
    for (const variant of [
      renderToStaticMarkup(<DownloadButton onDownload={noop} />),
      renderToStaticMarkup(<DownloadButton onDownload={noop} pdf />),
    ]) {
      expect(variant).toContain(glyph);
    }
  });
});
