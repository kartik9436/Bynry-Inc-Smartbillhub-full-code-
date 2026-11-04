# Portal request to active account — the 21-walk (2026-10-02)

Driven by `10-scripts/cwpwalk_portal_walk21.mjs` in a real browser against a real
PostgreSQL 16; read back by `10-scripts/cwpwalk_readback.py`. Screenshots are
beside this file, named `<walk>-<step>.png`. `readback.json` holds every stored
fact the table below was built from.

## W1–W12 — apply online, clerk processes, account goes ACTIVE

| Walk | Premises | Applicant | Services | New / linked | Regular / master | Class | Submitted | Docs saved | Docs viewed | Correction updated | Approved as | ACTIVE | Portal sees it | Saved / updated / viewed (database) | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| W1 | on file, one unit: 14 Alder Run | person — Lena M. Ortiz | water | new C-00059 | regular | residential | yes | 2 of 2 | yes | yes (applicant_name) | move_in | yes AC-2026-00061 | yes | request SR-26-0009 approved; 2/2 files stored; agreements water; equipment water:W-58; audit service_request.updated: Lena Ortiz → Lena M. Ortiz; 4 open(s) audited | portal login w1.login@example.test (active) |
| W2 | on file, one unit: 16 Alder Run | person — Marcus Bell | water, sewer, trash, solar, battery, fire | linked C-00053 | regular | commercial | yes | 2 of 2 | yes | yes (requested_start) | move_in | yes AC-2026-00062 | yes | request SR-26-0010 approved; 2/2 files stored; agreements water,sewer,trash,solar,battery,fire; equipment water:W-58, trash:CART-96, solar:SOL-P4, battery:BAT-10, fire:FL-4; audit service_request.updated: 2026-10-23 → 2026-10-30; 4 open(s) audited | portal login marcus.bell@example.test (active) |
| W3 | on file, one unit: 18 Alder Run | business — Alder Bakery LLC | sewer | new C-00060 | master | institutional | yes | 2 of 2 | yes | yes (applicant_name) | move_in | yes AC-2026-00063 | yes | request SR-26-0011 approved; 2/2 files stored; agreements sewer; audit service_request.updated: Alder Bakry LLC → Alder Bakery LLC; 4 open(s) audited | portal login w3.login@example.test (active) |
| W4 | on file, one unit: 20 Alder Run | business — Alder Freight Co | water, sewer, trash, solar, battery, fire | linked C-00054 | regular | industrial | yes | 2 of 2 | yes | yes (requested_start) | move_in | yes AC-2026-00064 | yes | request SR-26-0012 approved; 2/2 files stored; agreements water,sewer,trash,solar,battery,fire; equipment water:W-58, trash:CART-96, solar:SOL-P4, battery:BAT-10, fire:FL-4; audit service_request.updated: 2026-10-23 → 2026-10-30; 4 open(s) audited | portal login ap@alderfreight.test (active) |
| W5 | on file, with units: 400 Heron Court Unit 2 | person — Nadia Rahman | trash | linked C-00055 | regular | municipal | yes | 2 of 2 | yes | yes (applicant_name) | move_in | yes AC-2026-00065 | yes | request SR-26-0013 approved; 2/2 files stored; agreements trash; equipment trash:CART-96; audit service_request.updated: Nadia Rahmen → Nadia Rahman; 4 open(s) audited | portal login nadia.rahman@example.test (active) |
| W6 | on file, with units: 402 Heron Court Unit 2 | person — Owen Price | water, sewer, trash, solar, battery, fire | new C-00061 | regular | agricultural | yes | 2 of 2 | yes | yes (requested_start) | move_in | yes AC-2026-00066 | yes | request SR-26-0014 approved; 2/2 files stored; agreements water,sewer,trash,solar,battery,fire; equipment water:W-58, trash:CART-96, solar:SOL-P4, battery:BAT-10, fire:FL-4; audit service_request.updated: 2026-10-23 → 2026-10-30; 4 open(s) audited | portal login w6.login@example.test (active) |
| W7 | on file, with units: 404 Heron Court Unit 3 | business — Heron Fire Supply Inc | fire | new C-00062 | regular | builder_developer | yes | 2 of 2 | yes | yes (applicant_name) | move_in | yes AC-2026-00067 | yes | request SR-26-0015 approved; 2/2 files stored; agreements fire; equipment fire:FL-4; audit service_request.updated: Heron Fire Suply Inc → Heron Fire Supply Inc; 4 open(s) audited | portal login w7.login@example.test (active) |
| W8 | on file, with units: 406 Heron Court Unit 1 | business — Heron Court Partners LLC | water, sewer, trash, solar, battery, fire | linked C-00056 | master | commercial | yes | 2 of 2 | yes | yes (requested_start) | move_in | yes AC-2026-00068 | yes | request SR-26-0016 approved; 2/2 files stored; agreements water,sewer,trash,solar,battery,fire; audit service_request.updated: 2026-10-23 → 2026-10-30; 4 open(s) audited | portal login ops@heroncourt.test (active) |
| W9 | not in the system: 77 Juniper Bend | person — Priya Nair | solar | new C-00063 | regular | residential | yes | 2 of 2 | yes | yes (applicant_name) | new_connection | yes AC-2026-00070 | yes | request SR-26-0017 approved; 2/2 files stored; agreements solar; equipment solar:SOL-P1; audit service_request.updated: Priya Naer → Priya Nair; 4 open(s) audited; build owner AC-2026-00069 (master) on C-00063 | portal login w9.login@example.test (active) |
| W10 | not in the system: 79 Juniper Bend | person — Tomas Vega | water, sewer, trash, solar, battery, fire | linked C-00057 | regular | municipal | yes | 2 of 2 | yes | yes (requested_start) | new_connection | yes AC-2026-00072 | yes | request SR-26-0018 approved; 2/2 files stored; agreements water,sewer,trash,solar,battery,fire; equipment water:—, trash:CART-35, solar:SOL-P1, battery:BAT-10; audit service_request.updated: 2026-10-23 → 2026-10-30; 4 open(s) audited; build owner AC-2026-00071 (master) on C-00057 | portal login tomas.vega@example.test (active) |
| W11 | not in the system: 81 Juniper Bend | business — Kestrel Energy Co-op | battery | linked C-00058 | master | agricultural | yes | 2 of 2 | yes | yes (applicant_name) | new_connection | yes AC-2026-00073 | yes | request SR-26-0019 approved; 2/2 files stored; agreements —; audit service_request.updated: Kestrel Energy Coop → Kestrel Energy Co-op; 4 open(s) audited | portal login office@kestrel.test (active) |
| W12 | not in the system: 83 Juniper Bend | business — Juniper Foods Co | water, sewer, trash, solar, battery, fire | new C-00064 | regular | industrial | yes | 2 of 2 | yes | yes (requested_start) | new_connection | yes AC-2026-00075 | yes | request SR-26-0020 approved; 2/2 files stored; agreements water,sewer,trash,solar,battery,fire; equipment water:—, trash:CART-35, solar:SOL-P1, battery:BAT-10; audit service_request.updated: 2026-10-23 → 2026-10-30; 4 open(s) audited; build owner AC-2026-00074 (master) on C-00064 | portal login w12.login@example.test (active) |

## W13–W21 — the refusals and the edges

| Walk | What was tried | Result | Detail |
|---|---|---|---|
| W13 | paperless box arrives unticked | pass | unticked |
| W13 | sent | pass | 200 SR-26-0021 |
| W13 | clerk opens w13-lease.pdf | pass | 200 application/pdf 224B |
| W13 | clerk opens w13-photo-id.png | pass | 200 image/png 70B |
| W13 | the legacy government class is not offered on a new request | pass | residential, commercial, industrial, agricultural, institutional, municipal, builder_developer |
| W13 | request declined and says so | pass |  |
| W13 | customer's Track page shows the refusal | pass | WHERE IT STANDS Reference SR-26-0021 Reported 10/02/2026 00:00 Now REFUSED The status and the dates. No account details, no names, no balances — a reference is  |
| W13 | a refused request offers no Add a document | pass | not offered |
| W14 | paperless box arrives unticked | pass | unticked |
| W14 | sent | pass | 200 SR-26-0022 |
| W14 | clerk opens w14-lease.pdf | pass | 200 application/pdf 224B |
| W14 | clerk opens w14-photo-id.png | pass | 200 image/png 70B |
| W14 | clerk asks for more | pass |  |
| W14 | customer's Track page says more is needed | pass | WHERE IT STANDS Reference SR-26-0022 Reported 10/02/2026 00:00 Now MORE INFO NEEDED The status and the dates. No account details, no names, no balances — a refe |
| W14 | customer's Track page offers Add a document | pass |  |
| W14 | customer sends a second document from the portal | pass | w14-second-id.png |
| W14 | the sent application's upload door refuses a second file | pass | 409 |
| W14 | clerk sees a second document from the customer | pass | 3 file(s) on the request |
| W14 | clerk opens w14-second-id.png | pass | 200 image/png |
| W14 | the request shows the customer replied | pass | Customer replied |
| W15 | a start date under three working days is refused | pass | typed 2026-10-05; draft holds '' |
| W16 | an application with no address step cannot be sent | pass | 404 errors.not-found step= |
| W16 | the screen does not offer to carry on without an address | pass | Continue held |
| W17 | a closed tab keeps the draft | pass | Kofi / Mensah / kofi.mensah@example.test · Picked up where you left off |
| W18 | another utility cannot see the request — request detail | pass | status 404, reference not shown |
| W18 | another utility cannot see the request — request list search | pass | status 200, reference not shown |
| W18 | another utility cannot see the request — screen | pass | page opened, reference not shown |
| W18 | another utility cannot see the request — guest draft by token | pass | status 404, reference not shown |
| W19 | a file that is not PDF, JPG or PNG is refused by name | pass | notes.png: use PDF, JPG, PNG. |
| W19 | nothing was stored for the refused file | pass | 0 row(s) |
| W20 | a file over 10 MB is refused by name | pass | scan-11mb.pdf is over 10 MB. |
| W20 | nothing was stored for the refused file | pass | 0 row(s) |
| W21 | another utility cannot list the documents | pass | status 404 |
| W21 | another utility cannot open the documents | pass | status 404 |

## What the walk found

**Fixed during the walk** (each filed first, red test first, re-walked green):
`DEF-CUS-9041` the clerk could not pick the property on a portal request ·
`DEF-CWP-4930` an address we do not hold could not be applied for ·
`DEF-CUS-9042` the request page dropped the unit · `DEF-CUS-9043` no way to link
a customer on file from Approve · `DEF-CUS-9044` the move-in started blank ·
`DEF-CWP-9045` a business's Tax ID never reached its new customer ·
`DEF-CWP-9046` the date of birth typed online was dropped ·
`DEF-CUS-9047` New Connect's owner class ignored the clerk's pick ·
`DEF-CWP-9051` a save's answer wiped an attached file off the screen ·
`DEF-CUS-9052` the move-in held a linked or Tax-ID business on step 1 ·
`DEF-CUS-9053` a master account opened with no contact, so its portal login could
not be set up · `DEF-CUS-9074` New Connect asked again for what the request
holds · `DEF-CUS-9078` one applicant got two customer numbers ·
`DEF-CWP-9049` after *Ask for more* the customer could not send a second
document — Track now offers *Add a document* (W14) · `DEF-CWP-9079` the
paperless box arrived ticked — it now arrives unticked (W1–W14) ·
`DEF-CUS-9048` (fixed by the coordinator on the PO's ruling of 2026-10-02, not by
this lane) the billing clerk could not read New Connect's size and equipment
lists — W9–W12 re-walked and now offered them.

**Still failing, filed, not fixed:**
* `DEF-CUS-9050` — New Connect's occupancy choice *Open an account* does nothing
  (the walk opens the occupant's account through Move-in instead). Left
  unbuilt: nothing says WHO the per-unit account is for — the wizard names no
  occupant — and `BR-MET-116` (PO 2026-08-25) says every unit is vacant at
  confirm. `DEF-CUS-9082`: the other two non-default choices are read by
  nothing either.

**Open, with the coordinator for the PO:** `OQ-1361` — sizing a fire line from
New Connect (on the re-walk W10 and W12 store sized trash, solar and battery
equipment, but fire gets no fire line and the water meter no size class) · W11: the owner's master account on a new single-unit build opens
ACTIVE with no service on it, because the battery sits on Unit 1, which has no
occupant account.

**Walk artefact, not a defect:** every walk comes from one address, and the
guest door allows sixty requests a minute per address (BR-CWP-022); W17 waits a
minute so it measures the draft and not the throttle.

## Superseded in part, 2026-10-02 — a master account only on two or more homes

The PO ruled the same day (`BR-CUS-1114`): no master account on a single-family home or a
single-unit premises. Five results above opened one there, and are kept as the record of
what the product did that morning, not as what it should do: **W3** (`AC-2026-00063`, 18 Alder
Run — one home; the walk added a Laundry common area to make the form appear), **W11**
(`AC-2026-00073`, the applicant's master on a one-unit new build, holding no service), and the
build owners' masters of **W9, W10 and W12** (`AC-2026-00069`, `-00071`, `-00074`). They are
counted and left unchanged. `10-scripts/cwpwalk_portal_walk21.mjs` now walks W3 and W11 as
regular accounts, checks the owner's master door is closed on W3's single home, and checks
every one-unit build raises no owner master.
