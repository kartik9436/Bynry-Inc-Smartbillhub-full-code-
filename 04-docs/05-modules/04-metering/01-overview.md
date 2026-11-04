# Module — metering (product name: **Meter Reads**)

Physical world: premises→units→service points→meters (incl. sub-meters), read ingestion + validation + estimation.

**Owns (B2):** premises, units, service_points, meters, meter_reads, routes, cycles, read_schedules
**Screens:** S14–S16 Premises/Units · S25–S29 Reads
**Boundary rule (B1):** no other module writes this module's tables; cross-module reads via service functions only.

**v4 update:** owns the `assets` table (generalized from meters, B2 r4); the Assets UI surface is documented in 04-docs/05-modules/05-assets/. Product name for this module in all user-facing docs: **Meter Reads**.

---

## CR-023 · THE PREMISES PAGE IS ONE PAGE WITH THREE TABS (2026-08-21)

**PO ask, verbatim:** *"Premises - Here are the screenshots from new UI from R10;
I want you to do exact UI. It has 3 tabs - Premises, Units and Imports."*

Until now `/premises` and `/premises/units` were **two routes with two page
heads**. r10 draws **one page**: one `h1` reading **Premises** on all three tabs,
one roll-up sentence, one tab strip, and head actions that CHANGE with the tab.

| Route | Screen | What it mounts |
|---|---|---|
| `/premises` | S14 · `PRM-01` | `PremisesTabsPage` with the Premises tab open |
| `/premises/units` | S15 · `PRM-01U` | the same shell, Units tab open |
| `/premises/imports` | `PRM-04` (**no A1 id** — reported) | the same shell, Imports tab open |
| `/premises/:id` | `PRM-02` | premise detail — **six tabs**, four KPI tiles |
| `/premises/units/:id` | `PRM-03` | unit detail — **six tabs**, four KPI tiles |

⚠ **`/premises/units` STILL RESOLVES AND MUST.** The tab is the ROUTE rather than
a `?tab=` parameter precisely so that every existing deep link, bookmark and
`?f.premises_id=`-scoped URL keeps working byte for byte (B15 TC-24).

### What is on those screens that the product cannot yet support

Seven capabilities are asserted by r10's two detail views (B15 §2A.3). **Six are
stated as absences on screen, each citing the row that will close it** — never
filled with a plausible figure:

| r10 says | State | Cites |
|---|---|---|
| `Inside city limits — no ×1.5 multiplier` | **`premises.inside_city_limits` exists and NO endpoint serves it** | `DEF-507` |
| Common areas · master account · `JULY COMMON BILL $69.60` | what a common area IS is undecided | `OQ-314` |
| `UNALLOCATED USAGE 3.1%` | nothing computes it; three readings give three numbers | `OQ-327` (minted here) |
| `Sewer (85% of water)` | sewer-on-water is not in the rating packet | `OQ-315` · `DEF-492` |
| `Eligibility check · Passes — …` | nothing evaluates an eligibility rule | `DEF-404` |
| Vacancy rows on the occupancy timeline | vacant billing is CONFIRMED (`BR-MET-094`); who pays is not | `OQ-316` · `OQ-314` |
| Closing read · final bill per occupant | computed at close, readable by no route | `DEF-509` |

**The seventh is FILLED:** `Residential Standard · v2` — a plan's version — is
real since Wave G closed `DEF-410` on the same day B15 was written, so the Plan
tab reads `GET /plans/{id}` and prints the server's own version number.

⚠ **B15 §2A.3 NAMES THE JURISDICTION LINE AS THE ONE FILLABLE TODAY AND IT IS
NOT.** The column landed for the rating engine and no read surface landed with
it. That is `DEF-507`, and it is the reason the count above is six and not five.
