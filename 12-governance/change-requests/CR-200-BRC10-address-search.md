# CR-200-BRC10 · Address search: portal suggestions, apartment choice, one word-by-word staff search

**Raised:** 2026-10-29 by the Product Owner, in chat (screenshots: Premises list "heml", Units list "hosk", portal Start service).

**Requester's words, verbatim:** *"in premise lit view search bar inline search is working ; In unit list view search tab inline search is working ; in consumer portal in search street field - inline address search is not working; … in case of multifamily homes ; property adress is on premis and on unit sub address are different ; how you will going to hanlde"*, then answers *"Question 1 …-A · Question 2 …-A · Question 3 …-A"*, *"Question 1: should "Ask us for something" also suggest addresses?-A"*, the code plan *"this is ok"*, and *"start"*.

**Ruling record:** decision log 2026-10-29 *"Address search: portal suggestions, apartment choice, staff multi-word search"* and its four same-day follow-ups (rows confirmed, code plan approved, Ask us A).

## 1 · Classification
MAINTENANCE (defects — the portal's Start service ignores the apartment and judges occupancy for the whole building; the staff searches cannot combine words) plus new capability (public address suggestions). Not the fast path: a public read of the utility's address list (privacy), and occupancy judgement on the new-connection money path (connection fee vs move-in).

## 2 · What moves, what stands
**Stands:** hard rule 8 / `BR-MET-1161` (address on premises only; a unit refines by LABEL); `US-CWP-012` TC-2 (an unknown address is *a person will look at it*, never a refusal); `BR-CWP-021` (availability never names the occupier — suggestions carry street + town + ZIP only, apartments carry labels only, never occupancy); `BR-CUS-070` (Ask us still requires an address, and an unmatched one is accepted). **Changes:** occupancy (move-in vs new connection) is judged for the picked UNIT; `find_premises_by_parts`'s *"only one exact row … Offering the nearest matches … is not built here"* is superseded by the suggestion read.

## 3 · Tasks (28) and lanes
P1–P4 · S1–S9 · F1–F6 · T1–T6 · R1–R3, as put to the PO on 2026-10-29. Lanes: **A Staff search** (S1–S6, T1, T2) · **B Portal suggestions + apartment** (S7–S9, F1–F5, T3, T4) · **C Proof** (F6, T5, T6, R1–R3, by the coordinator after A and B).

## 5 · APIs (each lane adds its own)

### 5b · Lane B (portal) — built 2026-10-29

| Method · path | Who | What |
|---|---|---|
| `GET /api/{tenant}/portal/public/premises/suggestions?q=` | guest (no session), `PublicOnboardingThrottle` 60/min per address + `PortalTenantThrottle`, `portal_admission` | **New.** From the 4th character, at most 5 `{street, city, state, postal_code}` — no id, name, unit or occupancy. Under 4 characters `{"suggestions": []}`. Word by word over street, town and ZIP (`metering.address_match.address_suggestions`) |
| `GET …/portal/public/premises/availability` | unchanged guards | **+ `unit=`** (a label). Answer **+ `units`** (labels, only when the premises has more than one live non-common-area unit) **+ `unit`** (label meant, or null). `job` is `null` at such a building until a unit is named. ⚠ **AMENDED 2026-10-30 (PO ruling A, *"A, move-in"*; `DEF-CWP-10690`, lane C):** `job` was judged by the unit's OCCUPANCY (Apt B empty → `new_connection`), which contradicted the 2026-09-23 / 2026-10-11 rulings the Approve window keeps. It is now `move_in` for every matched premises and picked apartment, **occupied or empty** (`31 Palm Ct`, an empty house, too); occupancy is not read; the fees are the plan's move-in fees for a home (`rating_seam.move_in_fees` → `rating.move_in_fees.plan_move_in_charges`, sized by `metering_seam.connection_sizes`), so a one-time code the plan carries for another class is no longer quoted |
| `POST …/portal/public/requests` (*Ask us for something*) | unchanged guards | **+ optional `street`, `city`, `postal_code`, `unit`** — a picked suggestion's parts; re-matched server-side, request linked to premises (+ unit). A typed address is stored as typed |
| `POST …/portal/public/applications/{token}/submit` | unchanged | Request now linked to the draft's matched premises and the apartment picked by label (`applications.place_for`) |

Internal, no route: `customers.service_request_service.create_from_portal(resolved_place={premises_id, unit_id})` (server-only keyword, runs `_resolution_from_pick`; a guest's `picked_premises_id` is still refused) · `metering.address_match`: `address_suggestions`, `units_to_choose`, `unit_matching_label`, `unit_key` · ~~`portal.seams.customers_seam.unit_is_occupied`~~ (deleted 2026-10-30 with `premises_is_occupied`, ruling A) · `customers_seam.home_account_type_code` · `metering_seam.connection_sizes` · `rating_seam.move_in_fees` · `portal.applications.place_for` / `place_from_parts`.

## 5a · Lane A (staff search) — notes

- **No new API and no changed request/response shape.** The five reads keep their URLs and payloads; only what `q` matches changed: `GET /premises?q=`, `GET /units?q=`, `GET /premises/picker?q=`, the Move-in unit search (`GET /move-ins/units?q=`) and `GET /search?q=` (premises + units groups).
- **The matcher:** `core.search.search_words` (split on spaces and commas) and `core.search.matches_every_word(term, fields, also=…)` — every word must match one field (`icontains`), words ANDed; one word is exactly `matches_any`. `core.search.rank_word` gives the top bar's prefix band its word (the FIRST — decision log 2026-10-29). `matches_any` and `prefix_then_recency` are unchanged, so the other thirteen top-bar groups are untouched.
- **Metering owns the field lists** (`apps/metering/selectors.py`): `PREMISES_WORD_FIELDS` = street, town, ZIP, premises number, name, plus a unit inside (`premises_with_unit_word`, a lazy `pk IN (SELECT premises_id …)` subquery); `UNIT_WORD_FIELDS` = label, unit number + the building's street, town, ZIP, number, name (walked, hard rule 8).
- **Per search, before → after** (measured "before" is §6a):
  1. Premises list: street/no./owner/town/ref/parcel, whole phrase → the same six + ZIP, name, unit label/no., word by word.
  2. Units list: label/no./premises no./street (+ meter no.) → + town, ZIP, premises name, word by word; the meter number stays a whole-phrase alternative.
  3. Move-in unit picker: label/no./premises no./name/street/town → + ZIP, word by word; the caller's account/customer/meter legs stay whole-phrase alternatives (`apps/customers/move_in_units.py` unchanged).
  4. Premises picker: street/no./town → + ZIP, name, unit label/no., word by word; still never the owner.
  5. Top bar: premises no./name/street → + town, ZIP, unit label/no.; units label/no. → + the building's street, town, ZIP, no., name (`DEF-MET-10679`); word by word, ranked on the first word.
- **Not changed, on purpose:** `metering.selectors.unit_ids_matching` and `unit_id_query`/`premises_id_query` (they serve the assets, customers and ledger searches, none of the five); `apps/metering/address_match.py` and the portal (lane B).
- **Proof:** `06-backend/tests/test_cr200_staff_word_search.py` — red first on tip `91cd9c795` (23 failed / 11 passed: every multi-word case in all five places, and the top bar's units by street), green after. Exactly one SQL statement asserted for the Premises list, Premises picker, Move-in units and both top-bar groups; the Units list keeps its existing meter-number id lookup (one extra query, as before) and its multi-word page is asserted. 34/34 on SQLite and 34/34 on a throwaway PostgreSQL 16 cluster; neighbours on PostgreSQL (Premises picker, Move-in all units, metering list paging): 50 more passed. Reds not ours: `test_us_shl_003_search.py` (23) fails inside its own fixture (`Account.account_type` NULL — `AccountType.objects.first()` finds none) before any search runs; `test_us_shl_003_search_isolation.py` (14) errors in its fixture on a superuser cluster (`AccountType.get(code='residential')` sees both tenants).
- **Frontend:** no change. The placeholders already name address, city and premises number (`metering.premises.searchPlaceholder`, `metering.units.searchPlaceholder`); nothing on screen claimed a whole-phrase match.

## 6a · P2 — what each staff search matches TODAY (measured 2026-10-29, lane A, before any change)

Every one of the five matches the WHOLE typed phrase, as one `icontains`, against one field at a time — so a phrase whose words sit in two different fields ("12 Oak 2B": street + unit label) matches nothing anywhere.

| # | Search | Code (tip `11369acb1`) | Fields matched today (whole phrase, `icontains`, any one) | Min chars |
|---|---|---|---|---|
| 1 | **Premises list** (S14, `GET /premises?q=`) | `06-backend/apps/metering/selectors.py:607-618` (`premises_list`) | `address_line` · `premise_no` · `owner_manager` · `city` · `external_ref` · `gis_parcel_id` | 2 |
| 2 | **Units list** (S15, `GET /units?q=`) | `06-backend/apps/metering/selectors.py:2509-2517` (`units_queryset`; NOT `unit_ids_matching` at :2338, which serves the assets and customers searches, not this list) | unit `label` · `unit_no` · `premises.premise_no` · `premises.address_line` · **or** the unit holds a current meter whose `asset_no` contains the phrase (`assets.selectors.unit_ids_for_asset_search`, an id list) | 2 |
| 3 | **Move-in unit picker** (`move_in_unit_queryset`) | `06-backend/apps/metering/selectors.py:2353-2382`; caller `apps/customers/move_in_units.py:256-277` adds account no., customer/contact name and meter number legs on the whole phrase | unit `label` · `unit_no` · `premises.premise_no` · `premises.name` · `premises.address_line` · `premises.city` | none (empty = every live unit) |
| 4 | **Premises picker** (`GET /premises/picker?q=`) | `06-backend/apps/metering/api.py:665` → `06-backend/apps/metering/address_picker.py:100-104` (`search`) | `address_line` · `premise_no` · `city` (owner deliberately NOT matched) | 2 |
| 5 | **Top search bar** (`GET /search?q=`, premises + units groups) | `06-backend/core/search.py:195` (`matches_any`) · `06-backend/apps/metering/search_sources.py:44,47,68-101` | premises: `premise_no` · `name` · `address_line`; units: `unit_no` · `label` ONLY — a unit is never found by its building's street ("12 Oak" returns the premises, never Apt 2B). Ranked by `prefix_then_recency` on `premise_no` / `unit_no` with the whole phrase | 2 (kernel) |

None matches the ZIP (`premises.postal_code`). Every field above is kept after the change (nothing lost); see §5a for what was added.

## 7 · Version
Assigned at release by the coordinator.
