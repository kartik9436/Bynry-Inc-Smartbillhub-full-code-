# End-to-end walk of everything delivered on 2026-10-07 — one build, one journey

**Build walked: v2.560.3** (shown in the sidebar on every photo; branch `claude/charming-pascal-k7i2lr` at `a2611eabd`, the tip when the walk started). The branch moved to 2.561.0 (`fef42e746`, the clerk-marks-ACH-returned lane) while the walk was running; that change was not walked here.

**Where:** a local copy of the product only — the web app built with an EMPTY API address and served at `127.0.0.1:5491`, its own API at `127.0.0.1:8491`, its own PostgreSQL 16 (port 55491, seeded with `seed_demo` + `load_sample_data` + `10-scripts/cr173_newworld_walk_seed.py`), its own Redis (port 6391) and the repo's fake SFTP server (`06-backend/tests/fake_sftp_server.py`, port 2291). Before signing in, every request the browser made went to `127.0.0.1:5491` (plus Google Fonts) — `00-signin-local-only.png`. The live site, the City of Ann Arbor, US Payments and the Census service were never contacted.

**Photos:** the session scratchpad's `po-shots/e2e-2026-10-07/` (the photo names below are relative to it); only this README is committed, at `08-qa/e2e-2026-10-07/README.md`.

**Signed in as:** Dana Whitfield, System Admin, Brazos Bend Utilities. Width 1440 throughout.

**The fake City.** The API was started through a small launcher (`scratchpad/lane-e2e/walk_api.py`) that adds three `.example` hosts to the product's own recorded-City switch — no product file was edited: `a2.gis.example` answers with the repo's own *2670 Sequoia Pkwy* recording (the building and unit A), `grid.gis.example` gives the same answer in Michigan State Plane feet, and `big.gis.example` is the recorded layer grown to 20 rows (7 pages). The refusing hosts (`key.`, `moved.`, `down.`, `token.gis.brazosbend.example`) and the 7-row `gis.example` are the product's own.

## Result

| Area | Checks | PASS | FAIL |
|---|---|---|---|
| A · GIS | 30 | 28 | 2 |
| B · New World receipt file | 13 | 13 | 0 |
| C · US Payments | 20 | 20 | 0 |
| D · Leave guard | 22 | 21 | 1 |
| **Total** | **85** | **82** | **3** |

The three FAILs are two defects, each reproduced at least twice and filed: **DEF-MET-10013** (A1a, A1d) and **DEF-CUS-10014** (D-A8).

## A · GIS

| Step | Expected | Seen | Result | Photo |
|---|---|---|---|---|
| A1a | Typing *2670 Sequoia* lists the building AND its unit A, told apart | Two rows, both *2670 Sequoia Pkwy · Parcel 09-00-00-000-001 · close match* — identical. The API answer does carry `unit: "A"` on the second; the screen does not show it | **FAIL** (DEF-MET-10013) | `A1-sequoia-candidates.png`, `A1-repro2-sequoia-candidates.png` |
| A1b | Each candidate shows its parcel | *Parcel 09-00-00-000-001* on both | PASS | `A1-sequoia-candidates.png` |
| A1c | *Use this* → the On-the-map panel with parcel and a pin | Parcel 09-00-00-000-001 · Point 42.300010, -83.790010 · Not checked yet | PASS | `A1-sequoia-picked-pin.png` |
| A1d | Picking the unit row keeps the unit | Street address reads *2670 Sequoia Pkwy*; unit A is gone, and the premises takes the UNIT's point (…010) | **FAIL** (DEF-MET-10013) | `A1-sequoia-picked-pin.png` |
| A2 key | Amber box, reason in words, no 500 | *The City's records are unreachable. The city rejected our key. Type the address to continue. Add the parcel number later.* | PASS | `A2-amber-key.png` |
| A2 moved | same, layer moved | *…The city's map layer has moved…* | PASS | `A2-amber-moved.png` |
| A2 down | same, service error | *…The city's service had an error…* | PASS | `A2-amber-down.png` |
| A2 token | 200 OK with an ArcGIS 498 body reads as a key refusal | *…The city rejected our key…* | PASS | `A2-amber-token.png` |
| A3 | Wrong grid (State Plane) refused, no candidates | *The city sent unusable map coordinates.* | PASS | `A3-wrong-grid-refused.png` |
| A4a | Edit premise: an Import reference another property holds is refused, naming it | *This parcel already belongs to 181 Willow Bend Dr, Silver Creek.* | PASS | `A4a-import-reference-taken.png` |
| A4b | Add premises: the City parcel already on another property is refused at Create, naming it (the pick itself is not refused, by design) | 409; *This parcel already belongs to 403 Silver Creek Rd, Silver Creek.* | PASS | `A4b-review.png`, `A4b-create-refused.png` (`A4b-city-parcel-taken-on-pick.png` shows the pick accepted) |
| A5a | Settings → Esri ArcGIS → Parcel check → Preview on the 7-row City: whole, no *Stopped* line | *City rows read 7 · Preview — nothing was written.* No *Stopped* line | PASS | `A5A6-parcel-check/gap3-preview-default-whole-1440.png` |
| A5b | Preview on a 20-row City (7 pages): reads 3, says so | *Stopped after 3 of 7 pages.* · City rows read 9 | PASS | `A5b-preview-20-rows-stopped-after-3-of-7.png` |
| A5c | Preview as a by-hand `?pages=1` call | *Stopped after 1 of 3 pages.* | PASS | `A5A6-parcel-check/gap3-preview-pages-1-stopped-1440.png` |
| A6a | Runbooks → Templates → add GIS reconciliation | 201, added | PASS | `A6a-runbook-templates.png`, `A6b-gis-reconciliation-added.png` |
| A6b | Run ▶ → Dry run, City pages 1 | *The city sent 3 rows over 1 page. Stopped after 1 of 3 pages.* | PASS | `A5A6-parcel-check/gap2-run-dialog-pages-1-1440.png`, `gap2-run-result-pages-1-1440.png` |
| A6c | Run ▶ → Dry run, box empty | *The city sent 7 rows over 3 pages.* | PASS | `A5A6-parcel-check/gap2-run-dialog-whole-1440.png`, `gap2-run-result-whole-1440.png` |
| A7a | No City GIS: property Overview has no Parcel / On the map / Checked against GIS | Only *Import reference R-114-0037-037* and *City limits* | PASS | `A7a-nogis-premises-overview.png` |
| A7b | No City GIS: Edit premise has no latitude/longitude | 0 boxes | PASS | `A7b-nogis-edit-premise.png` |
| A7c | Broken connection: fields drawn and one line | *The city connection is not working.* | PASS | `A7c-broken-premises-overview.png` |
| A7d | Working connection: fields back, no line | Parcel · On the map · Checked against GIS | PASS | `A7d-working-premises-overview.png` |
| A8a | Overview: *Import reference* for the import key, *Parcel* for the City's | both, separately | PASS | `A7d-working-premises-overview.png` |
| A8b | Edit premise box reads *Import reference* | *Import reference* | PASS | `A8b-edit-premise-import-reference.png` |
| A8c | Esri connection says *Parcel check*, not *Nightly parcel check* | *Parcel check* | PASS | `A8c-esri-connection-parcel-check.png` |
| A9a | Asset map tab: pins | *Showing 117 of 117 assets*, 117 markers — same as GIS Lane D's record | PASS | `A9-maps/e2e-asset-map-1440.png` |
| A9b | Asset pin popup | *W-5034 Meter · 169 Quarry Hill Ct · Unit 1 · Last read 4.000000 kgal · Open details →* (same text as Lane D) | PASS | `A9-maps/e2e-asset-map-popup-1440.png` |
| A9c | Asset click-through | opens `/assets/<id>` | PASS | `A9-maps/e2e-asset-click-through-1440.png` |
| A9d | Work order map: pins | 5 clusters, 0 unplaced — same as Lane D | PASS | `A9-maps/e2e-work-map-1440.png` |
| A9e | Work cluster popup and click-through | *3 JOBS AT THIS PLACE WO-0016, WO-0018, WO-0019* → opens `/work/orders/<id>` | PASS | `A9-maps/e2e-work-map-cluster-open-1440.png`, `e2e-work-cluster-click-through-1440.png` |
| A9f | Work map filter by area | Downtown: 5 clusters → 1 | PASS | `A9-maps/e2e-area-work-map-filtered-1440.png` |

## B · New World / Logos — Send to City folder and the receipt push

| Step | Expected | Seen | Result | Photo |
|---|---|---|---|---|
| B1 | Section *Send to City folder* on the connection | present, six items | PASS | `B1-send-to-city-folder-empty.png` |
| B2 | Save ✓ → password shown only masked, box emptied | *Saved: ••••real. Leave blank to keep it.* | PASS | `B2-saved-password-masked.png` |
| B3 | Test connection against the local fake SFTP server | *Signed in and wrote a file.* · *Server key saved: SHA256:GG8a…* | PASS | `B3-test-connection-ok.png` |
| B4 | Wrong password | *User name or password refused.* | PASS | `B4-test-wrong-password.png` |
| B5 | Runbooks → New World receipt push → Run ▶ → Dry run, day 2026-10-05 | *Dry run · 3 · Built and counted. Nothing was sent.* File name *Receipt_20261005.xml* | PASS | `B-1-dry-run-dialog.png`, `B-1-dry-run-result.png` |
| B6 | Run for real | *Sent · 3 · Receipt_20261005.xml is in the City folder.* | PASS | `B-2-live-run-dialog.png`, `B-2-live-run-result.png` |
| B6b | The file landed with the right name | the fake server's folder holds exactly `Receipt_20261005.xml` (the test file was deleted) | PASS | `B-landed-Receipt_20261005.xml` |
| B6c | One `<Receipts>` document | one XML declaration, one `<Receipts>`, three receipts | PASS | `B-landed-Receipt_20261005.xml` |
| B6d | No card fields | no element naming a card | PASS | `B-landed-Receipt_20261005.xml` |
| B6e | A US Payments (Payment agent) payment is NOT in it | the day held 3 online payments and 2 US Payments payments (PY-261005-0088 $150.00, PY-261005-0089 $100.00); the file holds only PY-261005-0085/0086/0087 ($42.18, $118.50, $63.07) | PASS | `B-landed-Receipt_20261005.xml`, `C8-payment-page-kiosk-4471.png` |
| B7 | A second real run for the same day is refused | *Already sent · That day's file went earlier.* — *Already sent for that day*; nothing re-sent | PASS | `B-3-live-again-run-result.png` |
| B8 | Run history row | Runbooks → Run history lists the three runs (Done; acted 0 · 1 · 0); the connection's Recent activity lists *Send receipt file 3 of 3* | PASS | `B8-runbook-run-history.png`, `B9-connection-run-history.png` |
| B9 | No answer ever carried the password | 52 answers read, none held it | PASS | — |

## C · US Payments

The three calls were made with curl against the local API only; the key is never written in the transcript.

| Step | Expected | Seen | Result | Photo |
|---|---|---|---|---|
| C1 | USPayments is a live card | *USPayments · Payments · They send · Not set up · 3* — no *coming soon* | PASS | `C1-connectors-grid-uspayments-live.png` |
| C2 | Its page: three APIs, all *They call us* | Payments, Account lookup, Returns | PASS | `C1-uspayments-connector-page.png`, `C2-uspayments-setup-page.png` |
| C3 | Switch-on refused until OTHER is mapped | 409; *Map OTHER first, then switch on.* | PASS | `C3-switch-on-refused-map-other-first.png` |
| C4a | Reference data → Payment methods → add *Other* (the utility had none) | added | PASS | `C4a-payment-method-other-added.png` |
| C4b | Map OTHER → Other | *OTHER → Other* | PASS | `C4b-mapping-before.png`, `C4b-mapping-other-mapped.png` |
| C5 | Save and test → switched on | 201 | PASS | `C5-switched-on.png` |
| C6 | Generate a key → shown | the key under *The key for them to use* | PASS | `C6-key-shown-once.png` |
| C6b | Shown once | after a reload it is gone; only ••••50d9 remains | PASS | `C6b-key-gone-after-reload.png` |
| C7a | Lookup AC-2026-00024 | 200, `accountValid: true, amountDue: 427.89` | PASS | `C-curl-transcript.txt` §1 |
| C7b | Pay $150.00 CASH at kiosk 4471 | 200 `received: true` | PASS | §2 |
| C7c | Lookup shows the new balance | 277.89 (427.89 − 150.00) | PASS | §3 |
| C7d | Pay $100.00 ACHCHECK | 200; lookup 177.89 | PASS | §4–5 |
| C7e | Return R01 → balance back | 200; lookup 277.89 | PASS | §6–7 |
| C7f | Duplicate payment and duplicate return | 409 `duplicate`, both | PASS | §8–9 |
| C7g | Wrong key; no key | 401, both | PASS | §10, §12 |
| C7h | Unknown account lookup | 200 `accountValid: false` | PASS | §11 |
| C8 | Payment page: *Payment agent · Kiosk · 4471* | Source *Payment agent* / *Kiosk · 4471*, Cash, Cleared, $150.00 | PASS | `C8-payment-page-kiosk-4471.png` |
| C9 | Reversal shows the bank code | Source *Payment agent* / *Bank code R01*, Reversed, −$100.00 | PASS | `C9-reversal-bank-code-R01.png` |
| C10 | The returned payment's history says so | *Returned by the bank · nsf* | PASS | `C10-ach-payment-returned.png` |
| C11 | The connector after the calls | 3 of 3 working, key ••••50d9 active, runs listed | PASS | `C11-connector-after-calls.png` |

## D · Leave guard

`10-scripts/leave_guard_walkthrough.mjs`, unchanged, on this build; its own photos are in `D-leave-guard/`.

| Step | Expected | Seen | Result | Photo |
|---|---|---|---|---|
| A0 | Move-in opened from SR-26-0001, untouched: no question | none | PASS | — |
| A1 | Two Continues: no popup on step changes | none, step 3 | PASS | `D-leave-guard/01-move-in-from-request-filled.png` |
| A2–A3 | Side nav while typed → *Save your work as a draft?* with Stay / Leave without saving / Save as draft | exactly that | PASS | `D-leave-guard/02-popup-save-as-draft-move-in-from-request.png` |
| A4 | Stay keeps the clerk on the wizard | stayed | PASS | — |
| A5–A6 | Save as draft → toast → on to Accounts | *Saved as draft. Find it on Move-ins.* | PASS | `D-leave-guard/03-toast-saved-as-draft.png` |
| A7 | Reopen shows the saved value | 11/03/2026 | PASS | `D-leave-guard/04-move-in-resumed-with-saved-value.png` |
| A8 | Change the date, wait 2.2 s, *Leave without saving*, reopen: the autosave kept it | the old date; no autosave was ever sent | **FAIL** (DEF-CUS-10014) | `D-leave-guard/05-move-in-autosaved-after-leave-without-saving.png`, `D-repro-A8-run1-*.png`, `D-repro-A8-run2-*.png` |
| B0 | Untouched Add property: no question | none | PASS | — |
| B1 | Add property step 2 typed → *Leave without saving?* / *Your work will not be saved.*, no draft offered | exactly that | PASS | `D-leave-guard/10-add-property-filled.png`, `11-popup-leave-without-saving-add-property.png` |
| B2 | Stay keeps the typing | kept | PASS | — |
| B3a–b | Reload → the browser's own prompt; dismissing keeps the typing | yes | PASS | — |
| B3 | Browser Back out of the wizard → popup | yes | PASS | — |
| B4–B5 | Second side-nav item → popup; Leave without saving leaves | yes, to Premises | PASS | — |
| C1 | New connection → the draft popup | yes | PASS | `D-leave-guard/20-new-connection-filled.png`, `21-popup-new-connection.png` |
| D1 | Park leaves with no popup | yes | PASS | `D-leave-guard/30-after-park-new-connection.png` |
| D2–D3 | Save draft & exit (request and standalone move-in) leave with no popup | yes | PASS | — |
| D4 | The last step's save (Complete) leaves with no popup | yes | PASS | `D-leave-guard/31-move-in-request-last-step.png` |

**What A8 is, measured:** the autosave takes its starting point 0.8 s after the form loads. On this stack the form finished loading about half a second before the walk typed, so the typed date became the starting point and nothing was ever sent (timer trace: starting point set at 2,544 ms, date typed at 3,057 ms, starting point taken at 3,349 ms, no write). With a 3-second pause before typing, the autosave sent `PUT …/move-in-form` and the date survived (`D-repro-A8-wait3s-*.png`). So a clerk who types in the first moment after Edit opens and then leaves without saving loses that change. Everything the PO asked for in D (the popup, Save as draft, the toast, the reopened value, no popup on Park / Complete / Save & exit) passes.

## Defects filed (reproduced at least twice before filing)

- **DEF-MET-10013** (medium) — the address search draws a building and its unit as two identical rows; picking the unit drops the unit and gives the premises the unit's point.
- **DEF-CUS-10014** (low) — a change made in the first 0.8 s after a request's move-in Edit loads is never autosaved.

## Seen, not counted as failures

- **Without a shared counter, every US Payments call with the right key is refused with 429.** The first run had no Redis; the product refuses rather than count in one process (`INTEGRATION_SHARED_COUNTER_REQUIRED`, CR-110-BRC04). That is the designed fail-closed behaviour, not a fault; the walk then gave the API its own Redis (`CACHE_URL`) as a deployment would have. Transcript kept: `C-curl-transcript-no-shared-counter-429.txt`.
- A US Payments payment's header reads *"taken by Nobody named"* (`C8`, `C9`, `C10`).
- The returned ACH payment's own status tile stays *Cleared* and still offers *Reverse it instead*; only its history says *Returned by the bank*, with the raw word *nsf* (`C10`). `reversal.py` keeps the original's status by design.
- The USPayments connector heads its page *Not tested yet* while all three APIs read *Working* (`C11`).
- The phone channel word is `IVR`; the walk sent `PHONE`, which recorded as *Other*, as the specification says it should.
- Sample data: the *multi-account cheque* block could not run during `load_sample_data` (`BlockCannotRun`, payments sample data) — logged by the seeder, did not stop it.
