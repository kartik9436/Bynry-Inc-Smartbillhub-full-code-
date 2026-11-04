# CR-157-BRC10 — Rate schedules: two clerks saving at once get a named refusal, billing reads exactly one record for every date, and the screens are rebuilt from 71 images

**Raised:** 2026-10-01, by the Product Owner — a GO on a 52-task plan put to them the same
hour, and the redesign artifact named as the reference. Both are rows in
`12-governance/02-decision-log.md` dated 2026-10-01 whose last column reads
*"rate-schedule redesign"* (*"GO ON THE RATE SCHEDULE BUILD — 52 TASKS"* and *"THE RATE
SCHEDULE REDESIGN ARTIFACT IS THE REFERENCE"*); those rows are the specification and are
quoted, not paraphrased, below.
**Branch:** `claude/upbeat-dirac-olttw0` (`BRC10`, already claimed for this branch by
`CR-156-BRC10` in `12-governance/14-id-reservations.md`). Number from
`10-scripts/allocate.py cr` against the remote (`157`), re-verified at push time.
**Classification:** a **CHANGE** (`13-change-process.md` §1) for the screens and the
three-step wizard; the concurrent-save hole that wave A closes is a **DEFECT** of the agreed
behaviour (`BR-RAT-037` already says windows never overlap and a clash is a named refusal)
and is filed on its own row before it is fixed — see §5.
**Waves:** **0** — the 71 images (DONE the same hour, `05-prototype/rate-schedules-2026-10-01/`)
· **A** — areas 1–3 (tables, saving without deadlock, billing reads one record) and their
backend tests — this file's §6 is wave A's record · **B** — API reads and the screens built
from the images (B14 rules 37, 42, 44) · **C** — end-to-end, web walk, records.

---

## 0 · What arrived, in the requester's words

> *"based on this start the tasks"* — quoting the plan in full (decision log 2026-10-01,
> *"GO ON THE RATE SCHEDULE BUILD — 52 TASKS IN WAVES 0 / A / B / C, SCREENS FROM 71
> IMAGES"*).

> *"https://claude.ai/artifact/Vi5Nj88KnsWu5y4XvKe7oV - we are using this artifcats for rate
> schedule"* (decision log 2026-10-01, *"THE RATE SCHEDULE REDESIGN ARTIFACT IS THE
> REFERENCE FOR RATE SCHEDULES"*).

The plan as ruled, from the decision-log row: overlap of versions and a second draft are
already refused by the database (`ex_tariff_versions_no_overlap`, `rating/0047`;
`uq_tariff_versions_one_draft`); billing already asks one function
(`selectors.in_force_version`) that returns one row; **the GAP is concurrent saves — no row
lock, so a clash fails at commit with a raw error.** Tasks: tables 2 · saving and no
deadlock 5 · billing one record 4 · API reads 6 · frontend 12 · backend tests 8 ·
end-to-end 8 · web walk 2 · records 5 = **52** (+3 if the minimum is A).

## 1 · Classified

* Screens (List · View details: Overview / Rates / Plans / Audit · Add · Edit with *Change
  the rate* / *Fix an error*), the three-step wizard (Details · Pricing · Review) — **CHANGE**.
* Two saves at the same moment answering a raw database error instead of
  `rating.schedules.window_overlap` — **DEFECT** (the agreed behaviour is the named refusal;
  `BR-RAT-037`, `_guard_window`). Filed before the fix (§5).

## 2 · What signed statement moves

* **Nothing in B4/B5 ❄️.** No figure moves; `tests/golden` must stay 23 passed, 1 xfailed.
* The five-step RAT-03 wizard becomes three steps (the artifact ruling above) — wave B.
* **Still OPEN, not answered by this:** the minimum (A per size billed / B per version / C
  none). `DEF-RAT-8737` stays held and wave A does not touch it.

## 3 · Impact (ten surfaces)

Code: `apps/rating/services.py` (the save paths), `apps/rating/selectors.py` (the one
lookup), a new repo gate · Data: none (no migration in wave A; no row rewritten) · Screens:
wave B · API: wave A changes no contract shape (§6) · Business rules: `BR-RAT-037` (made
true under concurrency), `BR-RAT-114` (asserted, already built) · Tests: §6 · Open
questions: the minimum (A/B/C) stays open · Demo fixture: untouched · Lanes building now:
charge-code wave A (`CR-156-BRC10`) owns the base-charge price lookup — this CR reads it and
edits none of its code · Docs: this file, the decision log, the review ledger.

## 4 · Already built and now wrong

Nothing shipped is wrong in the single-clerk case. Under two simultaneous saves the second
clerk saw a server error and the first clerk's save was intact; nothing half-written was
ever committed (the constraint refused the whole transaction). Wave A turns that into the
named refusal.

## 5 · Size, confirmation, defects

52 tasks, confirmed by the PO's GO. Defect rows filed before fixing are listed in §6.

## 6 · Wave A record

**Defect filed before the fix:** `DEF-RAT-8750` (pushed alone, `449dc556e`).

### 6.1 · Area 1 — the tables (no new table, no migration)

`rating/0047`'s `ex_tariff_versions_no_overlap` (EXCLUDE USING gist, `WHERE effective_from IS NOT NULL
AND superseded_by_version_id IS NULL`, `DEFERRABLE INITIALLY DEFERRED`) and `uq_tariff_versions_one_draft`
already cover all three cases, and wave A proves it **through the services** on PostgreSQL rather than with
planted rows (`test_def_rat_8000_no_overlap_pg.py` already did that half):

* **drafts** — excluded by design (no window); a draft parked beside a live version is allowed;
* **corrections** — the superseded original is excluded; the correction restates its window;
* **new versions** — the previous window is closed the day before.

`test_cr157_pg__v1_v2_v3_and_a_correction__exactly_one_row_prices_every_day`: v1 01/01, v2 04/01, v3 07/01,
then v2 corrected → for **every one of the 365 days of 2026** exactly one row could price it,
`in_force_version` returns that row, the constraint holds when forced, the original v2 is kept with
`superseded_by` set and its stated end (06/30) unmoved, and a February catch-up bill run in May reads **v1**.

Base-charge dates are charge-code wave A's (`CR-156-BRC10`, `selectors.base_code_price_rows`) — read, not
edited, by this lane; `G141` holds that one lookup.

### 6.2 · Area 2 — saving without a deadlock

**Locked, and where.** New `services._lock_schedule(tariff_id)`: `SELECT … FOR UPDATE` on the `tariffs`
row, then on every `tariff_versions` row of it in id order. It replaces the plain read at the top of all
seven schedule save paths — `update_rate_schedule` (and the `_save_schedule_draft` it calls),
`discard_rate_schedule_draft`, `activate_rate_schedule`, `correct_rate_schedule_version`,
`create_rate_schedule_version`, `duplicate_rate_schedule` (the source), `archive_rate_schedule` — and
`apply_rate_change_batch` locks ALL its schedules up front, ascending id, before writing any.
`create_rate_schedule` takes no lock because its schedule row does not exist until it inserts it. The
operator's `rat_resolve_schedule_overlap` now locks the schedule row before its one UPDATE. **One order
everywhere — schedule, then its versions; several schedules in ascending id — so no two writers can each
hold what the other wants.** Billing never takes these locks; readers do not wait on row locks.

**The refusal a clerk sees.** The existing `rating.schedules.window_overlap` — *"Versions may not overlap.
This one starts {date} but the current version already starts {date}."* Under the lock the second save
waits, then reads the first's version, and `_guard_window` refuses it by name before writing. Behind that,
`_check_windows_now` runs `SET CONSTRAINTS ex_tariff_versions_no_overlap IMMEDIATE` inside a savepoint at
the end of activate / correct / new version / bulk, turns SQLSTATE `23P01` into the same named refusal, and
sets the constraint back to DEFERRED (the correction still needs its write order).

**Proof on PostgreSQL 16 (`tests/test_cr157_rate_schedule_saves_pg.py`, 9 passed, 66s).** Clerk A's save is
held open for one second after it writes; clerk B starts only once A has written:

| race | A | B |
|---|---|---|
| two new versions, same date | saved | **refused: `rating.schedules.window_overlap`** (1.22s, no deadlock) |
| CONTROL — the same race on the old code (plain reads, no immediate check) | saved | **raw `IntegrityError` (`ExclusionViolation`)** |
| a correction and a rate change at once | saved | saved (1.37s) — one row per date afterwards |
| two activations of one saved draft | saved | **refused: `rating.schedules.already_activated`**; the activated version survives |
| two draft autosaves | saved | saved — the later one's content, exactly one draft |

After the refused save: v1 + exactly one June version, v1 ends 05/31, **one** `rate_change_log` row — nothing
half-written. A planted second live row (a writer that skipped the lock) surfaces as the named refusal and
the whole save rolls back.

**Time of use.** `services.tou_register_for_window`: a window named *On-peak / Mid-peak / Off-peak* (case,
space and hyphen ignored) DERIVES its register `tou_on / tou_mid / tou_off`, so the screen sends the name and
no register; a register that contradicts the name is refused with the new key
`rating.tou.window_register_mismatch` (*"{{window}} must use its own register."*, eleven catalogues). A
window the utility names itself (*Punta*, *Peak*) keeps `BR-RAT-067` unchanged: its register is required.
Two cases of `test_us_rat_006_tc9_window_register.py` were amended to exercise that rule on tenant-named
windows, stated in each case.

**Seasonal — confirmed, nothing changed.** `rate_seasons` stores `start_month/start_day/end_month/end_day`;
a season sent as a full date is refused as an unknown field, so the screen sends month and day and a
picker's year never reaches storage. *Summer 05/01–09/30* prices July 2026 and July 2031 alike; *Winter
10/01–04/30* wraps the year.

**Structure on step 1 — confirmed, no contract change.** `POST /rate-schedules` with `name · service ·
model · uom` and no dates saves the schedule with a dateless DRAFT version carrying the model.

### 6.3 · Area 3 — billing gets exactly one record

**The audit, found against listed.** All ten listed billing files (`backbill`, `corrections`,
`counted_service_line`, `fee_bill`, `gather`, `midperiod`, `pipeline`, `rating_seam`, `resolution_switch`,
`runs`) and the portal/runbooks seams were read: **zero** direct `TariffVersion` queries in billing, portal
or runbooks. Every date-based price read goes through `rating.selectors.pricing_inputs` →
`in_force_version` (`gather._tariff_config_for`, `backbill._version_id_at`, `midperiod` via `backbill`);
`corrections`, `counted_service_line`, `fee_bill`, `pipeline`, `runs` price through `rating_seam.price_bill`
on what `gather` resolved; `resolution_switch` prices a version **named by id** by R2 through
`pricing_inputs_for_version_id`. Found beyond the list: `billing/reporting.py`, `bulk_corrections.py` and
`billing/selectors.py` join the version STAMPED on an issued line (what priced that bill), which is not a
resolution. **One second reader exists, inside rating:** `resolution_catalogue.schedule_version_facts` (R2 of
the ruled chain) lists live versions and asks `in_force_on` with the same predicate; under `rating/0047` at
most one matches and it refuses rather than chooses — listed in `G142`, not changed.

**Gate `G142` one-tariff-version-lookup** (number from `allocate.py gate`): fails any
`TariffVersion.objects`, `tariffversion_set.<manager>()`, `get_model(…, "TariffVersion")` or raw SQL on
`tariff_versions` outside `rating/selectors.py`, `rating/models.py` and the save-path functions of
`rating/services.py`, except eleven listed (file, function) readers each with its reason; a listed reader
that stops querying FAILS too, so the list only shrinks. **Proved RED through `run_gates.GATES`** on a copy
of `apps/` with one planted line in `billing/gather.py`:

    PLANTED: FAIL — 1 direct tariff_versions read(s) outside rating.selectors and the save paths:
             apps/billing/gather.py:4077 in _planted_g142_red(): TariffVersion.objects …
    TREE   : PASS — read 861 file(s); skipped 2 owner file(s) and 487 test/migration file(s);
             18 hit(s) on 11/11 listed reader(s)

**A bill period crossing a version change is split by days — already built (`BR-RAT-114`,
`billing/midperiod.py`) and now asserted with versions written the way a clerk writes them.**
`test_cr157_split__…`: $2.00/kgal from 01/01/2025, the change to $2.20 filed through
`create_rate_schedule_version` from 06/16/2026 (the save stamps the old end 06/15 itself); June's 10 kgal
splits 15 days / 15 days → **5 × $2.00 + 5 × $2.20 = $10.00 + $11.00 = $21.00**, one bill, two usage lines
each stamped with its own version. Each part's base is prorated by `midperiod` over the period's own day count
(B4.3, `cycle_days` held to the caller's); no frozen figure moved.

### 6.4 · Contract changes for wave B

* **None to any route or response shape.** New on the write side only: a TOU window may omit `channel` when
  its `label` is On-peak / Mid-peak / Off-peak; a contradicting `channel` is a validation error,
  `rating.tou.window_register_mismatch` on `structure.windows[i].channel`.
* A concurrent clash answers the same `BIZ-WINDOW` refusal, `rating.schedules.window_overlap`, a single clerk
  already gets — the screen needs nothing new.
* Base-charge rows for the Rates tab: `selectors.base_code_price_rows(service_code, on_date)` (CR-156 §7).

### 6.5 · Reds I did not cause, dated

On the tip `aa80e888f` with this lane's `services.py` swapped back to the tip's own, **16** cases of
`test_us_rat_schedules.py` / `test_us_rat_plans.py` and **5** of `test_us_rat_006_tc9_window_register.py`
fail identically, 19 of them with `rating.schedules.no_base_charge_code` at activation. They were also red
on `9910f15a8` (CR-156-BRC10 wave A) before this lane rebased. Not caused here; reported to the coordinator.

**Not done here, on purpose:** the minimum (A/B/C is unanswered — `DEF-RAT-8737` held); API reads and
screens (wave B).

### 6.6 · Wave B record — areas 4 and 5 (2026-10-01)

**Screens, each built from its image** (`05-prototype/rate-schedules-2026-10-01/images`), photographed in
Chromium at 1440 beside the image in `08-qa/screens/rate-schedules-waveB-2026-10-01/`:

| Screen | Images | Shipped |
|---|---|---|
| List — 11 columns, service chips, In force + Scheduled, icon actions | 01–07 | 2.432.0 |
| View details — Overview · Rates · Plans · Audit, tiles above the tabs | 08–39 | 2.432.0, 2.433.3, 2.433.4 |
| Add / Edit — Details · Pricing · Review; Change the rate / Fix an error | 40–71 | 2.434.0 |

**API reads:** `GET /rate-schedules/{id}/rates` (base rows in size order: price, version, from/to, the
size's own minimum, units per size) and `GET /rate-schedules/{id}/plans` (paged in SQL); list cards carry
class name, base code and *n of m* sizes priced. `apps/rating/schedule_reads.py`, no `TariffVersion`
query (G142).

**Minimum, PO 2026-10-01 option A:** the step-3 version minimum is removed and never sent; the review
and View show the per-size minimum only (*No minimum* when blank). Plan details' single figure reads the
per-size minimum when every size states the same one (`DEF-RAT-8759`, rating half; the Meter Reads unit
panel is outside this lane and the row stays open for it).

**Proof:** `e2e/CR-157-rate-schedules-wave-b.spec.ts` — 4 passed, 94 assertions: the four View tabs; one
schedule of each of the seven methods added and read back by model; *Change the rate* from the 1st of
next month (a new version; the old one ends the day before); *Fix an error* (same dates, a reason, the
wrong version kept). The lane's own calls are in the decision log, *"Rate schedules wave B — the lane's
own calls"*.

**Defects:** `DEF-RAT-8748` fixed (2.434.0). `DEF-RAT-8810` filed (old five-step bodies left unmounted).

## 7 · Version

**2.430.0** (wave A) — `allocate.py version --bump change`, re-verified at push.

**2.432.0, 2.433.3, 2.433.4, 2.434.0** (wave B) — each allocated with `allocate.py` and verified at push.

## 8 · Close and rollback

Wave A rollback: revert its commit. No migration and no data was written, so a revert restores the old
read-then-write behaviour exactly (and with it the raw error under two simultaneous saves). Close is stated
before wave C ships.

Wave B rollback: revert its four commits. They add two read endpoints and change screens only; no
migration, no stored data.
