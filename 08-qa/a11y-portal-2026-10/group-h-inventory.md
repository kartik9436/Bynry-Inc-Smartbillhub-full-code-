# Customer portal accessibility — Group H (F-06, the bill PDF): inventory, baseline and after

Lane **A11Y-H**, 2026-10-23. Ruling built: decision log 2026-10-23 *"Portal accessibility, Group H (bill PDF, F-06)"*. Our own judgments: the entry below it, *"Group H (F-06, `DEF-BIL-10546`): build judgments"*. Defect: `DEF-BIL-10546`.

**What QA found:** bill BL-2609-000651 fails veraPDF PDF/UA-1 on 7 rules and 360 checks. It has no structure tree (256 content items unmarked), no `/Lang`, no `DisplayDocTitle`, and its fonts are not embedded.

**Root cause:** `06-backend/apps/billing/documents.py` wrote the PDF by hand, with the standard library and the Base-14 fonts. That was an engineering choice of 2026-08-11 ("no PDF library"), never a PO ruling. The writer cannot produce a structure tree, a language, a title preference or an embedded font. `apps/billing/page_print.py` is the same engine, and the agreement borrowed it.

## Every place that makes a PDF, before changing anything

| # | What | Code | Who receives it | Writer before | Writer after |
|---|---|---|---|---|---|
| 1 | **Bill** (cycle bill), kept at issue | `billing/issue.py` → `documents.render_invoice` → `frozen_bill.freeze_at_issue` | **Customer**: post, bill link, portal *Download* | hand-written, Base-14 | **tagged (WeasyPrint)** |
| 2 | **Final bill** (move-out), the same document | `billing/final_bill.py`, `final_bill_email.py` (drafted render attached to the move-out email) | **Customer** | hand-written | **tagged** (a draft render) |
| 3 | **Statement / balance-forward bill**: the bill format, not a separate writer | `documents.render_invoice` | **Customer** | hand-written | **tagged** |
| 4 | **One-time, fee and corrected bills**: the same document through the same issue | `one_time_send.py`, `fee_bill.py`, `cut_bill.py`, `corrections.py` → `issue_invoice` | **Customer** | hand-written | **tagged** |
| 5 | **Service agreement**, as sent (email attachment) and as stamped on acceptance | `customers/agreement_pdf.py` via `agreements._pdf` | **Customer** | `page_print`, Base-14 | **tagged**, `/Lang` = the agreement's published language |
| 6 | Re-render of a bill **issued before v2.88.0** (it has no kept original) | `documents_api.invoice_document_pdf` fallback, `print_set`, `partner_api` | staff/print, marked *re-rendered* | hand-written | **unchanged, on purpose**: ruled *"New bills only. The old ones stay as issued"* |
| 7 | Layout chooser preview | `billing/layout_preview_api.py` | staff (it shows what customers will get) | hand-written | **tagged** |
| 8 | Work order print, technician day pack | `work/print_docs.py` via `page_print` | **staff only** | `page_print` | **unchanged** (out of scope, ruling item 4) |
| 9 | Reports | none; reports export CSV/XLSX | staff | — | — |

**Not PDFs at all today:**
- Payment reminders, disconnection notices, receipts and letters. `notifications/frozen_documents.py` freezes the print channel as `text/plain`, and the print vendor receives text. There is no inaccessible PDF to fix; what does not exist is the PDF. Filed as `DEF-NOT-10556`; making them PDFs is `CR-049` task 6.
- The portal's *payment-plan agreement* download is served under the name `payment-plan-agreement.pdf` with the content type of whatever the notifications freeze kept for the plan. Per the table above, that is a text or email artefact, not a PDF. **Found by reading the code, not reproduced in a browser.** Worth a tester's look.

## Samples (fake data only)

`06-backend/tests/a11y_pdf_samples.py` builds every sample. The suite and the veraPDF script read the same file.
- **Bills:** each of the 5 platform layouts (`documents.LAYOUT_SPECS`: standard, compact, amount-due-first, no-stub, pre-printed letterhead) × 2 utility set-ups × 2 customers = **20**.
  - *West Des Moines-like*: water and electric, no logo.
  - *Ann Arbor-like*: water, sewer and storm water, a stamped logo, a payment-plan line, BL-2609-000651.
- **Agreements:** sent and stamped × English and Spanish = **4**.
- **Language.** A bill has no language of its own today: every label is English. So the "Spanish" bill is a Spanish-speaking customer's bill: their name (José Muñoz Peña), their address (Calle Ñandú) and the utility's Spanish message, under English labels. That is exactly what such a customer receives. The Spanish agreement is genuinely Spanish.

## veraPDF PDF/UA-1 results

veraPDF 1.28.2 (greenfield), `--flavour ua1`, run by `10-scripts/a11y/verapdf_customer_pdfs.py`.

| Sample | Before: failed rules / failed checks | After: failed rules / failed checks |
|---|---|---|
| Bill, West Des Moines-like, standard (en / es) | 7 / 528 | **0 / 0** |
| … compact | 7 / 477 | **0 / 0** |
| … amount due first | 7 / 531 | **0 / 0** |
| … no stub | 7 / 321 | **0 / 0** |
| … letterhead | 7 / 522 | **0 / 0** |
| Bill, Ann Arbor-like, standard (en / es) | 7 / 571 | **0 / 0** |
| … compact | 7 / 504 | **0 / 0** |
| … amount due first | 7 / 574 | **0 / 0** |
| … no stub | 7 / 359 | **0 / 0** |
| … letterhead | 7 / 564 | **0 / 0** |
| Agreement (en / es) | 7 / 27 | **0 / 0** |
| Agreement, stamped (en / es) | 7 / 32 | **0 / 0** |
| **Total** | **0 of 24 pass** | **24 of 24 pass** |

English and Spanish gave identical figures in every row. The 7 rules that failed before, on every sample: 6.2-1, 7.1-3, 7.1-8, 7.1-10, 7.1-11, 7.2-34 and 7.21.4.1-1. Those are the marked-content, structure-tree, language, title and font-embedding rules, which matches QA's report on BL-2609-000651.

**A real issued bill** went through the shipped one-time Send, was kept at issue, and was then downloaded over HTTP from the bill link and from the staff document route (BL-2607-000001, test database). Both downloads were byte-identical to the kept file, and both pass with **0 failed rules**. The portal serves the same kept bytes; `test_us_cwp_034` proves that byte for byte. No browser and no screen reader were run in this lane.

Also passing PDF/UA-1 with 0 failed rules: agreements whose body is Hindi, Japanese or Korean. Their text prints as `?`, exactly as the old writer printed it (`DEF-BIL-10555`).

## Parity: the new page says what the old page said

`tests/test_def_bil_f06_tagged_pdf.py`, for all 20 bill samples and all 4 agreements:
- the money figures are the same, in the same order;
- the same words appear, as often (case folded);
- the sections come in the same order;
- the remittance stub is present (or absent for the no-stub layout), carries the scan line, and is the last section;
- agreements read word for word the same.

Worked figure, Ann Arbor-like bill, both writers: Previous balance 45.00 USD · Payments & credits −45.00 · Current charges 105.17 · Payment plan, not yet due −20.00 · **Total due 105.17** · stub Amount due 105.17.

## How the tester checks it

- **veraPDF:** `verapdf --flavour ua1 <bill>.pdf` should end in `PASS`. Or: `python3 10-scripts/a11y/verapdf_customer_pdfs.py --out /tmp/h --verapdf-classpath '<veraPDF lib>/*'`.
- **Acrobat:** *Accessibility → Full Check*. It should report the document as tagged, the language set (English for a bill), the title shown, the fonts embedded (`SBH-Liberation-Sans`, two subsets), the tables with header cells, and reading order as described below. Acrobat's "Color contrast" item is always manual.
- **What a screen reader should read, in this order:** the window title *"Utility bill BL-…"*, not a file name. The logo as *"<utility name> logo"*. The utility name and address. The heading *"UTILITY BILL"* (level 1) and *"Bill BL-…"*. Each detail as label then value (*Account, AC-2026-00057*). Section headings at level 2 (*Amount due*, *Services this period*, *Charges this period*, *Usage history*, *Messages*, *Tear off and return with payment*). Each charge table with its caption (*Water*) and its column headers announced with each cell (*Amount, 12.50 USD*). The usage table with a month header on each figure, a dash for an unread month and *13** plus *"* estimated"* for an estimate. The remittance stub, with the scan line read as text and the bars skipped. The page footer (*Bill … Page 1 of 2*) is not read.

## Not changed, and why

- **Staff-only prints** (work orders, day packs) stay on `page_print`, per ruling item 4.
- **Bills already issued** keep their kept files. A re-render of a bill with no kept original stays on the old writer, per ruling item 3.
- **No second font.** Hindi, Japanese and Korean are no worse than before, and `DEF-BIL-10555` tracks the gap.
- **Colours.** The page-footer grey `#97918e` on white is 3.1:1, and the bill stylesheet's faint grey used for absent values is the same colour. QA's working rules require a confirmed colour change, so these are reported here and not changed.
- **A bill in Spanish** does not exist; the labels are English. That is a product question, not a tagging one.
