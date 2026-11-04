// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  **B14 rule 43**, PO 2026-09-20: *"make them coponents - dont write
//          stand alone code , engineer it"*.
// Rules:   hard-won law 2 (built is not wired — a component nothing renders is
//          dead UI; and its MIRROR, a row of facts with nothing to press over
//          a live endpoint) · law 7 (every case here was shown RED first, in
//          `vitest`, which is the harness that will run it) · B14 rule 31 ·
//          rule 33 · `DEF-CUS-5872`
// ───────────────────────────────────────────────────────
//
// ⚠ **EVERY CASE READS RENDERED OUTPUT, NEVER A PROP.** No gate in this repo
// looks at rendered output (hard-won law 6), and a component can be imported,
// handed every prop, compile clean and put nothing in front of a clerk — that
// was four of one day's nine defects.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

// Node's own modules, reached the way `src/styles/routeBUtilities.test.ts`
// does — the string-split import keeps Vite from pre-bundling them and keeps
// `tsc` from looking for `@types/node`, which this project does not carry.
const nodeFs = (await import(/* @vite-ignore */ ["node", "fs"].join(":"))) as {
  readFileSync(p: string, enc: string): string;
};
const nodePath = (await import(/* @vite-ignore */ ["node", "path"].join(":"))) as {
  join(...p: string[]): string;
  dirname(p: string): string;
};
const nodeUrl = (await import(/* @vite-ignore */ ["node", "url"].join(":"))) as {
  fileURLToPath(url: URL | string): string;
};
const HERE = nodePath.dirname(nodeUrl.fileURLToPath(import.meta.url));
const SRC = nodePath.join(HERE, "..", "..");

import i18n from "@/i18n";

import { DocumentCapture } from "./DocumentCapture";
import { DocumentTable } from "./DocumentTable";
import {
  DOCUMENT_ACCEPT,
  emptyDocumentCapture,
  filterDocumentRows,
  formatDocumentSize,
} from "./documentCapture";
import type { DocumentCaptureValue, DocumentRow } from "./documentCapture";
import { DOCUMENT_LINK_NOT_BROWSABLE, openStoredDocument } from "./openStoredDocument";

afterEach(cleanup);

const t = (key: string, options?: Record<string, unknown>): string =>
  i18n.t(key, options as never) as unknown as string;

function row(over: Partial<DocumentRow> & Pick<DocumentRow, "id" | "doc_type">): DocumentRow {
  return {
    what_it_proves: null,
  document_number: null,
    name: null,
    uploaded_at: null,
    uploaded_by_name: null,
    required: false,
    size_bytes: null,
    original_size_bytes: null,
    file_present: false,
    verification_state: "not_checked",
    reject_reason: null,
    ...over,
  };
}

/** A row exactly as p078 draws one: a real file, a size, a person, a date. */
const WITH_FILE = row({
  id: "d1",
  doc_type: "proof_of_identity",
  name: "driving-licence.pdf",
  size_bytes: 1_258_291,
  uploaded_at: "2026-05-04T18:00:00Z",
  uploaded_by_name: "S. Ortiz",
  file_present: true,
  verification_state: "verified",
  what_it_proves: "Who they are",
});

/** `DEF-CUS-5872`'s shape: a NAME, a `verified` state and NO FILE. */
const PLACEHOLDER = row({
  id: "d2",
  doc_type: "tenancy_agreement_or_deed",
  name: "tenancy.pdf",
  uploaded_at: "2026-05-04T18:00:00Z",
  uploaded_by_name: "S. Ortiz",
  file_present: false,
  verification_state: "verified",
});

function mount(over?: {
  rows?: readonly DocumentRow[];
  value?: DocumentCaptureValue;
  onSubmit?: (withFile: boolean) => void;
  onOpen?: (r: DocumentRow) => void;
  onChange?: (v: DocumentCaptureValue) => void;
  openError?: string | null;
}) {
  return render(
    <DocumentCapture
      rows={over?.rows ?? [WITH_FILE, PLACEHOLDER]}
      value={over?.value ?? emptyDocumentCapture("proof_of_identity")}
      onChange={over?.onChange ?? (() => {})}
      onSubmit={over?.onSubmit ?? (() => {})}
      docTypes={[
        { value: "proof_of_identity", label: "Proof of identity" },
        { value: "tenancy_agreement_or_deed", label: "Tenancy agreement or deed" },
        { value: "other", label: "Anything else" },
      ]}
      requiredOf={(r) => (r.doc_type === "other" ? null : r.required)}
      t={t}
      locale="en"
      timeZone="America/Chicago"
      dateFormat="MM/DD/YYYY"
      onOpen={over?.onOpen}
      openError={over?.openError ?? null}
    />,
  );
}

describe("B14 rule 43 · the document capture is one addressable block", () => {
  /**
   * ⚠ **AMENDED 2026-09-22, AND IT HAD BEEN RED FOR AN HOUR BEFORE ANYBODY
   * READ IT (hard-won law 7 habit 1).** Commit `74511fa68` acted on two of the
   * PO's findings and did not come back to this file:
   *
   *   · **item 10** — `All · Required · Missing · Rejected` left the CAPTURE
   *     screen. They are the reviewer's filters, and nothing on a capture
   *     screen can be Missing or Rejected. They stay on the detail page.
   *   · **item 5** — *"Every attachment lands Not checked."* left the product.
   *     ⚠ This note then called it *"a claim about a virus scan this product
   *     does not run"* — FALSE until 2026-09-23: the scan ran in middleware on
   *     every upload, and only the sentence had gone. The PO asked again and
   *     the scan itself was deleted (`DEF-SHL-6347`); see the last block below.
   *
   * The assertions are moved to what the ruling says, not deleted: a test that
   * stops asking is how the NEXT removal goes unnoticed.
   */
  it("draws the whole drawn block — table, the form, both buttons, and NO reviewer chips", () => {
    mount();
    expect(document.querySelector('[data-table="capture-documents"]')).not.toBeNull();
    // PO 2026-09-22 item 10 — the reviewer's filters are not on capture.
    expect(document.querySelectorAll("[data-doc-filter]")).toHaveLength(0);
    expect(screen.getByLabelText(/Document type/i)).toBeInTheDocument();
    expect(document.querySelector("[data-doc-attach]")).not.toBeNull();
    expect(document.querySelector("[data-doc-add]")).not.toBeNull();
    // PO 2026-09-22 item 5 — the scan sentence is gone from the product.
    expect(document.querySelector("[data-doc-note]")).toBeNull();
  });

  it("prints name and size on a file, and an em dash on a row that has none", () => {
    mount();
    const cells = [...document.querySelectorAll("[data-doc-file]")].map((c) => c.textContent);
    expect(cells[0]).toBe("driving-licence.pdf · 1.2 MB");
    // ⚠ `DEF-CUS-5872` — the placeholder HAS a name and no file, and printing
    // the name beside nothing is the claim this component must never make.
    expect(cells[1]).toBe("—");
  });

  /**
   * ⚠ **AMENDED 2026-09-22 — PO ruling, verbatim: *"once you remove the virus
   * check - you will ahveonly two cases verified or rejected in case of
   * rejected show the reason in short to user why it is rejected."***
   *
   * The row this asserts on is `DEF-CUS-5872`'s: a `storage_ref` that resolves
   * to nothing, with `verified` in its state column. **That half is the point
   * and it has not moved** — the cell must not read `Verified` over a file
   * nobody can open. What moved is what it reads INSTEAD: the capture table's
   * FILE column one place left already prints `—`, so this cell says nothing
   * rather than saying the same absence twice.
   */
  it("says NOTHING over a row whose state says `verified` and whose file is not there", () => {
    mount();
    const states = [...document.querySelectorAll("[data-doc-state]")].map((c) => c.textContent);
    expect(states[0]).toBe("Verified");
    expect(states[1]).toBe("");
    // The verdict is still COMPUTED, and it is not `verified` — a screen that
    // merely printed nothing while believing the row was verified would pass
    // the line above and be the same defect (law 7: what makes it pass wrongly).
    expect(
      document.querySelectorAll('[data-doc-state] [data-doc-verdict="nothing_attached"]'),
    ).toHaveLength(1);
  });

  it("never renders a database id — B14 rule 31", () => {
    mount();
    const table = document.querySelector('[data-table="capture-documents"]');
    expect(table?.textContent).not.toContain("d1");
    expect(table?.textContent).not.toContain("d2");
  });

  /**
   * ⚠ **HALVED 2026-09-22 (PO item 10) AND THE SURVIVING HALF IS THE ONE THAT
   * MATTERED.** The chip that narrowed to none cannot be pressed on capture any
   * more, so the second half of this case asserts against a control that does
   * not exist. The FIRST half — *you have none of these* — is still a claim
   * this component makes and is still asserted. `DocumentFilterChips` keeps its
   * own tests; the filter-empty state is not deleted from the product, only
   * from this screen.
   */
  it("says `you have none of these` when there are no rows at all", () => {
    mount({ rows: [] });
    expect(document.querySelector("[data-doc-empty]")).not.toBeNull();
    // No chips on capture, so no chip can have narrowed anything to nothing.
    expect(document.querySelector("[data-doc-filter-empty]")).toBeNull();
    expect(document.querySelectorAll("[data-doc-filter]")).toHaveLength(0);
  });

  it("hands the host `true` for Attach and `false` for Add — one act, with and without bytes", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    mount({ onSubmit });
    await user.click(document.querySelector("[data-doc-attach]") as HTMLElement);
    await user.click(document.querySelector("[data-doc-add]") as HTMLElement);
    expect(onSubmit.mock.calls.map((c) => c[0])).toEqual([true, false]);
  });

  it("filters on `file_present`, never on a name — `DEF-CUS-5872`", () => {
    const kept = filterDocumentRows([WITH_FILE, PLACEHOLDER], "missing", () => false);
    expect(kept.map((r) => r.id)).toEqual(["d2"]);
  });

  it("puts `BR-SHL-031`'s allowlist on the picker", () => {
    mount();
    expect(document.querySelector("#capture-doc-file")).toBeNull();
    expect(
      (document.querySelector('input[type="file"]') as HTMLInputElement).accept,
    ).toBe(DOCUMENT_ACCEPT);
  });
});

// ══════════════════════════════════════════════════════════════════════════
// LAW 2's MIRROR — A ROW OF FACTS WITH NOTHING TO PRESS
// ══════════════════════════════════════════════════════════════════════════
describe("a document with a file can be opened", () => {
  it("draws `Open the file` over a file and an em dash over a row with none", () => {
    mount({ onOpen: () => {} });
    const actions = [...document.querySelectorAll("[data-doc-actions]")].map((c) => c.textContent);
    expect(actions[0]).toBe("Open the file");
    // ⚠ NOT a disabled control: there is no file, so no act is being withheld.
    expect(actions[1]).toBe("—");
  });

  it("draws no actions column at all when a host gives it nothing to do", () => {
    mount();
    expect(document.querySelector("[data-doc-actions]")).toBeNull();
  });

  it("hands the host the ROW, so the host owns its own route", async () => {
    const user = userEvent.setup();
    const onOpen = vi.fn();
    mount({ onOpen });
    await user.click(document.querySelector("[data-doc-open]") as HTMLElement);
    expect(onOpen).toHaveBeenCalledWith(expect.objectContaining({ id: "d1" }));
  });

  it("prints a refusal the host hands back rather than going quiet", () => {
    mount({ onOpen: () => {}, openError: "That link has expired." });
    expect(document.querySelector("[data-doc-open-error]")?.textContent).toBe(
      "That link has expired.",
    );
  });
});

describe("openStoredDocument · the link, and the one a browser cannot follow", () => {
  const client = (url: string) =>
    ({
      get: async () => ({ status: 200, data: { url, expires_in_seconds: 14400 }, etag: null, notModified: false }),
    }) as never;

  it("opens an https link and says how long it lives", async () => {
    const opened: string[] = [];
    const link = await openStoredDocument("/service-requests/r1/documents/d1/download", {
      client: client("https://store.example/x?sig=1"),
      open: (u) => opened.push(u),
    });
    expect(opened).toEqual(["https://store.example/x?sig=1"]);
    expect(link.expires_in_seconds).toBe(14400);
  });

  it("REFUSES a `file://` link by name instead of opening nothing", async () => {
    // ⚠ The dev storage backend mints these. `window.open` on one is blocked
    // silently — a control that looks alive and does nothing, which is the
    // exact shape this folder exists to stop building.
    const opened: string[] = [];
    await expect(
      openStoredDocument("/service-requests/r1/documents/d1/download", {
        client: client("file:///var/lib/docs/abc"),
        open: (u) => opened.push(u),
      }),
    ).rejects.toThrow(DOCUMENT_LINK_NOT_BROWSABLE);
    expect(opened).toEqual([]);
  });
});

// ══════════════════════════════════════════════════════════════════════════
// THE DRIFT GUARD — TWO SPELLINGS OF ONE FORMATTER, HELD TOGETHER
// ══════════════════════════════════════════════════════════════════════════
// `formatBytes` lives in `features/customers/AccountDocumentsTab.tsx` and its
// own comment says why there must only ever be one: *"a second `formatBytes`
// is two answers to `1.2 MB`"*. Folding it in is that file's owner's move, not
// this lane's, so until then the two are held together here — the same guard
// `applicantCapture.dom.test.tsx` uses for exactly this situation. **When the
// tab's owner folds it in, delete this with the duplicate, not before.**
describe("the size formatter has one answer, in both places it is spelt", () => {
  it("agrees with `AccountDocumentsTab.formatBytes` on every scale", async () => {
    const { formatBytes } = await import("@/features/customers/AccountDocumentsTab");
    // ⚠ **THE FIRST FIXTURE HERE COULD NOT FAIL, AND THE LAW 7 PROOF IS WHAT
    // FOUND IT.** It held 0, 1, 1023, 1024, 4096, 1_048_575, 1_048_576,
    // 1_258_291 and 10_485_760 — and NOT ONE of them distinguishes
    // `Math.round` from `Math.ceil` in the KB branch, so a real drift in the
    // rounding passed green. `1_100` (1.07 KB) and `2_100` (2.05 KB) are here
    // precisely because they do. The question is not *what makes this fail*,
    // it is *what would make it pass wrongly*.
    for (const bytes of [
      0, 1, 1023, 1024, 1_100, 2_100, 4096, 1_048_575, 1_048_576, 1_258_291, 3_200_000,
      10_485_760,
    ]) {
      expect(formatDocumentSize(bytes, "en")).toBe(formatBytes(bytes, "en"));
      expect(formatDocumentSize(bytes, "de")).toBe(formatBytes(bytes, "de"));
    }
  });
});

// ══════════════════════════════════════════════════════════════════════════
// RULE 43 CLAUSE 1 — ADDRESSABILITY, MEASURED RATHER THAN ASSERTED
// ══════════════════════════════════════════════════════════════════════════
describe("the block is addressable, and the page it came out of no longer holds it", () => {
  const page = () =>
    nodeFs.readFileSync(
      nodePath.join(SRC, "features", "customers", "ServiceRequestCapturePage.tsx"),
      "utf8",
    );

  it("is rendered by the page it was extracted from — hard-won law 2", () => {
    // ⚠ A component nothing renders is dead UI.
    //
    // ⚠ **THIS ASSERTION WAS `toContain("<DocumentCapture")` AND COULD NOT
    // FAIL, AND THE LAW 7 PROOF IS WHAT FOUND IT.** Renaming the element to
    // `<DocumentCaptureXX` — the mutation that proves a host stopped rendering
    // it — left the substring intact and the check passed green over a page
    // that no longer used the component at all. The element name is matched to
    // its own boundary now. *What would make this pass wrongly* is the
    // question; *what makes it fail* was never the hard half.
    expect(page()).toContain('from "@/components/documents"');
    // ⊕ **LANE CF-1 (2026-10-18) — THE REQUEST'S STEP 1 NOW DRAWS MOVE-IN'S
    // DOCUMENTS TABLE** (`MoveInDocumentsTable`, through `CaptureCustomerForm`;
    // drawing set `customer-forms-2026-10-18`, image 03), so the capture page
    // no longer renders this element. The kit's own law-2 proof moves to a
    // host that still draws it — the New Connection detail's Documents tab —
    // and the boundary-matched assertion is kept exactly as it was.
    const host = nodeFs.readFileSync(
      nodePath.join(SRC, "features", "work", "buildRecord", "BuildDocumentsTab.tsx"),
      "utf8",
    );
    expect(host).toMatch(/<DocumentCapture[\s/>]/);
    expect(page()).toContain("<CaptureCustomerForm");
  });

  // ⚠ **THE RENDERED PROOF IS NEXT DOOR AND IS NOW THIS COMPONENT'S.**
  // `ServiceRequestCapturePage.test.tsx` asserts `[data-doc-row]` elements on
  // a mounted step 4 (96 cases, all green after the extraction). The inline
  // table that used to emit those attributes is GONE, so the only thing that
  // can still satisfy them is `DocumentTable`. A source check says the host
  // imports it; that suite says a clerk sees it.

  it("is GONE from that page — the extraction, not a second copy", () => {
    const source = page();
    // The three things only the inline block had. If any comes back, somebody
    // has re-inlined the block rule 43 was ruled about.
    expect(source).not.toContain('<table className="data-table" data-table="capture-documents">');
    expect(source).not.toContain("capture.attachingOne");
    expect(source).not.toContain("capture.everyAttachmentLands");
  });

  // ══════════════════════════════════════════════════════════════════════
  // THE ADOPTION RECORD — A HOLD WITH A TEST THAT FIRES WHEN IT EXPIRES
  // ══════════════════════════════════════════════════════════════════════
  // CLAUDE.md law 2: *"WHEN YOU WRITE A HOLD, WRITE THE TEST THAT FIRES WHEN
  // THE HOLD EXPIRES, in the same commit"*. Three more surfaces draw documents
  // and none uses this kit yet; two of them are another lane's files today.
  // **This records who does, so the day one more adopts it the suite goes RED
  // and NAMES the file** — and whoever wired it updates this list and the
  // handover note in the same commit, instead of the question *has the second
  // host arrived* belonging to nobody. That is the mechanism that cost the
  // customer portal six working doors.
  it("names every host that draws this kit — and goes red when one more does", () => {
    const hosts = [
      "features/customers/ServiceRequestCapturePage.tsx",
      "features/customers/AccountDocumentsTab.tsx",
      "features/customers/ServiceRequestDetailPage.tsx",
      "features/customers/moveInRequestBlocks.tsx",
      "features/customers/TransferWizard.tsx",
      "features/work/buildRecord/BuildDocumentsTab.tsx",
    ];
    const uses = hosts.filter((f) =>
      nodeFs.readFileSync(nodePath.join(SRC, f), "utf8").includes('"@/components/documents"'),
    );
    // ⚠ **TWO TODAY, AND THE SECOND ARRIVED 2026-09-22.** The request
    // DETAIL's Documents tab now draws `DocumentStateCell` from this kit — the
    // PO's rows 2 and 3 were built here for capture and that tab was not
    // touched, so the clerk who ATTACHES a document and the clerk who REVIEWS
    // it read different words about one row. It does NOT draw `DocumentTable`
    // (it has Verify and Reject actions this kit's table does not offer); what
    // it shares is the VERDICT, which is the thing the two had disagreed on.
    // The other three are named in the lane's handover. Add a file here the
    // moment you wire it — this case going red is the census working.
    //
    // ⚠ **THREE FROM 2026-09-23 — `moveInRequestBlocks.tsx` (`DEF-SHL-6347`).**
    // The move-in's Documents table printed its own `Not checked` for every
    // row nobody had judged, which is the third state the PO removed with the
    // virus check. It takes `DocumentStateCell` now, and nothing else.
    //
    // ⚠ **FOUR FROM 2026-09-24 — `TransferWizard.tsx`, AND THIS CASE WAS RED
    // FOR FIVE DAYS BEFORE ANYBODY READ IT (`DEF-CUS-7852`).** The transfer
    // wizard wired the kit in `ab729d4c0` and the census was not updated in
    // the same commit, which is exactly the act this list exists to force. The
    // census WORKED — it went red and it named the file; what failed is
    // hard-won law 7's *"a guard is a claim only while somebody reads its
    // output"*. Found by a lane running the suite for something else.
    //
    // ⚠ **SIX FROM 2026-10-02, AND THIS CASE HAD BEEN RED SINCE 2.454.2
    // (`DEF-CUS-9205`).** `AccountDocumentsTab.tsx` took `openDocumentContent`
    // from this kit in `4bb519fe2` (`DEF-CUS-9147`) and the census was not
    // updated; found by lane NC-B running this file for its own change
    // (`CR-163-BRC10`), dated with `git log -S`, and confirmed red on the tip
    // before that lane's first edit. `BuildDocumentsTab.tsx` — the New
    // Connection detail — has drawn `DocumentCapture` since `DEF-CUS-7618` and
    // was never on the candidate list at all, which is law 7's *reporting
    // zero over a scope it silently excludes*; it is added to both.
    // ⚠ **FIVE FROM 2026-10-13 — `moveInRequestBlocks.tsx` LEAVES
    // (`DEF-GOV-10106`).** Its `RequestDocuments` block, the one that drew
    // `DocumentStateCell`, was rendered by no screen after the move-in's
    // Customer step went to `MoveInDocumentsTable` (`0e9b22d99`) and is
    // deleted. The file stays on the candidate list so a return is counted.
    // ⚠ **FOUR FROM 2026-10-18 — `TransferWizard.tsx` LEAVES (`DEF-CUS-10255`,
    // lane CF-2).** The buyer step's documents are Move-in's
    // `MoveInDocumentsTable` (image `07-transfer.png`), so the wizard no longer
    // draws this kit. It stays on the candidate list so a return is counted.
    expect(uses).toEqual([
      "features/customers/ServiceRequestCapturePage.tsx",
      "features/customers/AccountDocumentsTab.tsx",
      "features/customers/ServiceRequestDetailPage.tsx",
      "features/work/buildRecord/BuildDocumentsTab.tsx",
    ]);
  });

  it("renders its table on its own, with no host, no router and no query client", () => {
    // Rule 43 clause 1: if a sibling screen needing this would have to copy it,
    // it is standalone code however well written. This IS the test of that.
    render(
      <DocumentTable
        rows={[WITH_FILE]}
        t={t}
        locale="en"
        timeZone="America/Chicago"
        dateFormat="MM/DD/YYYY"
        requiredOf={() => null}
      />,
    );
    expect(document.querySelector('[data-doc-row="proof_of_identity"]')).not.toBeNull();
  });
});

// ══════════════════════════════════════════════════════════════════════════
// NO VIRUS SCAN — PO 2026-09-22 AND 2026-09-23 (`DEF-SHL-6347`)
// ══════════════════════════════════════════════════════════════════════════
// PO, verbatim, 2026-09-23: *"please remove virus scan chek user don't wan't
// it. we have ask remove it before why you did not remove it?"* — and on
// 2026-09-22: *"once you remove the virus check - you will ahveonly two cases
// verified or rejected in case of rejected show the reason in short to user
// why it is rejected."*
//
// ⚠ **THE FIRST INSTRUCTION WAS READ AS A SENTENCE AND THE SCANNER STAYED.**
// On the deployed build step 4 then refused every file with *"The virus
// scanner is unreachable. Try again shortly."* These cases read the RENDERED
// state column and the CATALOGUES, so neither the word nor the refusal can
// come back without one of them going red. The server half — no scanner on
// any upload — is `06-backend/tests/test_br_shl_253_malware_scan.py`.
describe("no virus scan — two verdicts, and no scan words anywhere", () => {
  const LOCALES = nodePath.join(SRC, "i18n", "locales");
  const LANGS = [
    "de", "en", "es", "es-MX", "fr-FR", "hi", "id-ID", "it-IT", "ja-JP", "ko-KR", "pt-BR",
  ];
  const catalogue = (lang: string): Record<string, string> =>
    JSON.parse(nodeFs.readFileSync(nodePath.join(LOCALES, `${lang}.json`), "utf8")) as Record<
      string,
      string
    >;

  it("prints Verified, Rejected with its reason, or NOTHING — never a third word", () => {
    const attachedUnjudged = row({
      id: "u1",
      doc_type: "proof_of_identity",
      name: "licence.pdf",
      size_bytes: 2048,
      file_present: true,
      verification_state: "not_checked",
    });
    const refused = row({
      id: "r1",
      doc_type: "tenancy_agreement_or_deed",
      name: "lease.pdf",
      size_bytes: 4096,
      file_present: true,
      verification_state: "rejected",
      reject_reason: "Unreadable photo",
    });
    mount({ rows: [attachedUnjudged, WITH_FILE, refused] });
    const states = [...document.querySelectorAll("[data-doc-state]")].map((c) => c.textContent);
    expect(states[0]).toBe("");
    expect(states[1]).toBe(t("customers.serviceRequest.capture.state.verified"));
    expect(states[2]).toBe(t("customers.serviceRequest.capture.state.rejected") + "Unreadable photo");
    const table = document.querySelector('[data-table="capture-documents"]')?.textContent ?? "";
    expect(table).not.toMatch(/not (yet )?checked|virus|malware|scann/i);
  });

  it("no catalogue carries a scanner refusal or the old third state", () => {
    const retired = [
      "upload.refusal.infected",
      "upload.refusal.scanner_stale",
      "upload.refusal.scanner_unavailable",
      "upload.refusal.too_large_to_scan",
      "customers.serviceRequest.capture.everyAttachmentLands",
      "customers.serviceRequest.capture.state.not_checked",
      "customers.serviceRequest.documents.state.not_checked",
    ];
    for (const lang of LANGS) {
      const keys = Object.keys(catalogue(lang));
      expect(keys.filter((k) => retired.includes(k) || k.startsWith("upload.refusal.")), lang)
        .toEqual([]);
    }
    const english = catalogue("en");
    expect(
      Object.keys(english).filter((k) => /virus|malware/i.test(english[k])),
      "an English string names a virus scan",
    ).toEqual([]);
  });
});
