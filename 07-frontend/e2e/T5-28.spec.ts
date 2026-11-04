// ── Trace ──────────────────────────────────────────────
// Journey:  T5-28 — upload guards. It was "Malware upload rejection (scan
//           before acceptance, nothing stored)" until 2026-09-23, when the PO
//           removed the virus scan for the second time — *"please remove virus
//           scan chek user don't wan't it"* (`DEF-SHL-6347`; BR-SHL-253 and
//           the scan clauses of BR-SHL-031 / NFR-34 SUPERSEDED). Steps 1 and 4
//           are turned round to assert there is NO scan; 2, 3 and 5 stand.
//           `08-qa/01-e2e/journeys/T5-28-malware-upload-rejection.md` is the
//           spec; this file walks its six-row step table in order.
// Story:    US-CUS-011 (the account Documents tab — the upload surface this
//           journey exercises) · US-IDN-001 (sign in)
//           Screens: S3 · S21 Account detail → Documents
// Rules:    BR-SHL-031 (every upload passes type allowlist → size cap BEFORE
//           acceptance; its malware-scan clause SUPERSEDED 2026-09-22/23) ·
//           NFR-34 (the cap is tenant config; its scan clause SUPERSEDED) ·
//           NFR-35 (write-once 7yr for the legal/e-signed class)
// Money:    NONE. No step renders a figure; `moneyTriple` is not called.
// Tests:    this file. The EICAR string is the industry-standard harmless test
//           signature — it is assembled at run time from its documented parts
//           so this source file does not itself carry a pattern every scanner
//           on the box would quarantine.
// ───────────────────────────────────────────────────────
import { expect, test } from "@playwright/test";
import type { APIRequestContext } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";
import { journey } from "./support/journey";

// The EICAR anti-malware test file, assembled rather than written whole.
const EICAR = ["X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-", "ANTIVIRUS-TEST-FILE!$H+H*"].join("");
const OVERSIZE_BYTES = 14 * 1024 * 1024; // the journey's 14MB against a 10MB cap

function api(path: string): string {
  return `/api/${tenant()}${path}`;
}

async function anyAccountId(request: APIRequestContext): Promise<string> {
  const response = await request.get(api("/accounts?per=1"));
  expect(response.status()).toBe(200);
  const rows = ((await response.json()) as { results: { id: string }[] }).results;
  expect(rows.length, "the fixture has no account to upload against").toBeGreaterThan(0);
  return rows[0].id;
}

async function documentCount(request: APIRequestContext, accountId: string): Promise<number> {
  const response = await request.get(api(`/accounts/${accountId}/documents`));
  expect(
    response.status(),
    `GET /accounts/{id}/documents answered ${response.status()} — with no documents ` +
      "resource, 'nothing stored' cannot be asserted at all",
  ).toBe(200);
  return ((await response.json()) as { count: number }).count;
}

journey("T5-28", "Upload guards — type and size refused, and NO malware scan", () => {
  // NOT serial: each row builds its own precondition, so the run reports which
  // of the journey's six hold rather than stopping at the first that does not.
  skipUnlessAppServer(test);

  // ⚠ **`doc_type` IS SENT ON EVERY UPLOAD IN THIS FILE (2026-09-23).** The
  // account door has refused a file with no type (`customers.document.
  // type_unknown`, 422) since `CR-094` wave I, so without it every step below
  // was refused for a reason none of them names.
  //
  // ⚠ **TURNED ROUND 2026-09-23 (`DEF-SHL-6347`), NOT DELETED.** This step
  // asserted the scan REFUSED the EICAR file. The PO removed the scan twice
  // (2026-09-22 and 2026-09-23), and the deployed build meanwhile refused every
  // upload with "The virus scanner is unreachable". The EICAR string is still
  // the right input: it is the one file any content scan would refuse, so its
  // ACCEPTANCE is the proof that none is standing in front of the store.
  test("step 1 — the EICAR-bearing PDF is ACCEPTED: there is no malware scan", async ({
    page,
  }) => {
    await signIn(page);
    const accountId = await anyAccountId(page.request);
    const before = await documentCount(page.request, accountId);

    const response = await page.request.post(api(`/accounts/${accountId}/documents`), {
      multipart: {
        doc_type: "kyc",
        file: {
          name: "exemption-cert.pdf",
          mimeType: "application/pdf",
          buffer: Buffer.from(`%PDF-1.4\n% ${EICAR}\n%%EOF\n`, "ascii"),
        },
      },
    });
    const body = await response.text();
    expect(
      [200, 201],
      `the upload answered ${response.status()} — no scan may refuse it (PO 2026-09-23): ${body.slice(0, 300)}`,
    ).toContain(response.status());
    expect(body, "no refusal may name a scanner").not.toMatch(/virus|malware|scanner/i);
    expect(await documentCount(page.request, accountId)).toBe(before + 1);
  });

  test("step 2 — a disallowed type is refused before any storage work", async ({ page }) => {
    await signIn(page);
    const accountId = await anyAccountId(page.request);
    const response = await page.request.post(api(`/accounts/${accountId}/documents`), {
      multipart: {
        doc_type: "kyc",
        file: {
          name: "invoice.pdf.exe",
          mimeType: "application/octet-stream",
          buffer: Buffer.from("MZ", "ascii"),
        },
      },
    });
    expect(response.status()).toBeGreaterThanOrEqual(400);
    expect(
      await response.text(),
      "the refusal must NAME the allowed types (PDF/PNG/JPG/CSV + tenant config)",
    ).toMatch(/pdf|allowed|type/i);
  });

  test("step 3 — a 14MB file is refused by the tenant-config size cap, with the cap shown", async ({
    page,
  }) => {
    await signIn(page);
    const accountId = await anyAccountId(page.request);
    const response = await page.request.post(api(`/accounts/${accountId}/documents`), {
      multipart: {
        doc_type: "kyc",
        file: {
          name: "site-survey.pdf",
          mimeType: "application/pdf",
          buffer: Buffer.alloc(OVERSIZE_BYTES, 0x20),
        },
      },
    });
    expect(response.status()).toBeGreaterThanOrEqual(400);
    expect(await response.text(), "the refusal must carry the cap value").toMatch(/10|size|cap|MB/i);
  });

  // ⚠ **TURNED ROUND 2026-09-23 (`DEF-SHL-6347`).** This probe posted the
  // EICAR file to `/documents` and passed on any status ≥ 400 — which it always
  // got, because no such route exists: a check that could not fail. What it
  // asks now is the thing the PO ruled: no upload is ever refused on account of
  // a scanner, whether or not one is running.
  test("step 4 — no upload is ever refused on account of a scanner", async ({ page }) => {
    await signIn(page);
    const accountId = await anyAccountId(page.request);
    const response = await page.request.post(api(`/accounts/${accountId}/documents`), {
      multipart: {
        doc_type: "kyc",
        file: {
          name: "meter-photo.png",
          mimeType: "image/png",
          buffer: Buffer.from("89504e470d0a1a0a0000000d49484452", "hex"),
        },
      },
    });
    const body = await response.text();
    expect(response.status(), body.slice(0, 300)).not.toBe(503);
    expect(body).not.toMatch(/upload\.refusal\.(infected|scanner_|too_large_to_scan)/);
  });

  test("step 5 — contrast: a clean PDF is accepted, stored and audited", async ({ page }) => {
    await signIn(page);
    const accountId = await anyAccountId(page.request);
    const before = await documentCount(page.request, accountId);

    const response = await page.request.post(api(`/accounts/${accountId}/documents`), {
      multipart: {
        doc_type: "kyc",
        file: {
          name: "exemption-cert-clean.pdf",
          mimeType: "application/pdf",
          buffer: Buffer.from("%PDF-1.4\n% T5-28 clean fixture\n%%EOF\n", "ascii"),
        },
      },
    });
    expect(
      [200, 201],
      `the clean upload answered ${response.status()}: ${(await response.text()).slice(0, 300)}`,
    ).toContain(response.status());
    expect(await documentCount(page.request, accountId)).toBe(before + 1);
  });

  test("step 6 — RECOVERY: the clerk's upload surface exists on S21 Documents", async ({ page }) => {
    await signIn(page);
    const accountId = await anyAccountId(page.request);
    await page.goto(`/${tenant()}/accounts/${accountId}?tab=documents`);
    await expect(page.locator("main")).toBeVisible();
    await expect(
      page.locator("main"),
      "US-CUS-011's Documents tab must offer the staff-mediated upload this journey is " +
        "about; it currently renders the 'arrives with' panel instead",
    ).not.toContainText(/arrives with|not built|coming/i);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: T5-28 journey activation (batch B lane, 2026-08-15)
// generated: 2026-08-15 by the E2E journey-activation lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: run against the live stack on E2E_BACKEND_PORT=8040 / E2E_WEB_PORT=8120
// exceptions: (1) the EICAR signature is assembled from two halves at run time
//   so this source file does not itself carry the pattern; since 2026-09-23 it
//   is asserted ACCEPTED, not refused (DEF-SHL-6347) · (2) NFR-35's
//   write-once 7yr class is NOT asserted — no retention surface exists to read
//   it from, and asserting it against nothing would be a claim, not a check
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
