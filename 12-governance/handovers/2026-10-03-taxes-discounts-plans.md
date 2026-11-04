# Handover — 2026-10-03 coordinator chat (taxes, discounts, plans)

Written when the PO moved to a new chat (credit ran out). Read this, then the files it names. The repo is the truth; this note only points.

## Where things stand
| Work | State | Record |
|---|---|---|
| Taxes & fees redesign `CR-165-BRC10` | **DONE `2.481.2`** — all 10 tasks, web walk 79/79, bill label prints on the bill (PO "Okay") | CR-165 §16–§17, `08-qa/taxes-fees-2026-10-03/walk-report.md` |
| Discounts redesign `CR-166-BRC10` | **DONE `2.481.11`** — all 10 tasks; web walk 215 checks, 209 pass (steps 1–11, real issued bills); with the PO: Garden usage allowance (recommended hide the type) and fee waivers (recommended keep refusing) | CR-166 §16–§17, `08-qa/discounts-2026-10-03/walk-report.md`, decision log "THE DISCOUNTS REDESIGN IS CLOSED" |
| Plans redesign `CR-167-BRC10` | **CLOSED at 2.490.5** (walk 195/195; §18–§19) — *read "IN PROGRESS — round 2" until the close* | `12-governance/change-requests/CR-167-BRC10-plans-redesign.md`, `05-prototype/plans-2026-10-03/README.md` |
| App frame in 11 languages | DONE `2.481.4` (DEF-SHL-9320) | decision log 2026-10-03 |
| Size names, not codes (PO report on live 2.455.0) | DONE `2.481.5` (DEF-RAT-9321, 9322) — reaches the live site on next deploy | CHANGELOG 2.481.5 |

## Discount web walk — what to do next
1. `git log --oneline | grep -i "walk"` and look for `08-qa/discounts-2026-10-03/walk-report.md`. If the lane's checkpoint landed, resume from the phase it names. If not, re-run the walk from the start per `web-walk.md`, using the taxes walk as the pattern (`10-scripts/cr165_taxwalk.mjs`, `cr165_taxwalk_world.py`).
2. Open defects the walk must fix: **DEF-RAT-9318** (a charge-waiver discount can never be saved from the New form — high), **DEF-RAT-9319** (discount list's 12 columns overflow at 1440; Type wraps one character per line in ja/ko). Close **DEF-RAT-9289** if D11–D13 save through the New form screen.
3. Known and expected (not new): "Granted this month"/"This month" blank (DEF-2430, DEF-BIL-5341); Duplicate disabled (DEF-RAT-9310); plan add/remove from the discount page disabled (DEF-478); second approval not built (DEF-RAT-9303); no CSV on Accounts/Audit (DEF-1005).
4. Then task 10: close CR-166 the way CR-165 §17 did.

## Open, not scheduled (suggested follow-up round after the close)
Discount Duplicate, plan add/remove from the discount page, "granted this month". Small: DEF-RAT-9315 (unused EffectiveStep), DEF-BIL-9317 (2% tax shows $0.02 in Billing's Rate column), DEF-RAT-9323 (charge-code price header names the wrong classes), DEF-MET-9324 (routes wizard Service column blank), DEF-RAT-9277 ("Set exemptions" link has nowhere to go). Long-standing red tests: ConfirmDialogTier census (BulkRunPage, 8b7aee258), wizardRailCensus (b71588e74), runbooks blocks.test `$8.2900`.

## Proposed, awaiting the PO
- A native-quality language review page by page (Meter Reads first: 使用法/前へ wrong, 読み取り left, meter numbers wrapping) — ~10–12 lanes, 2–3 at a time. Not started.
- Plans redesign: the PO's **go**. "Move units to another plan" was ruled *"not now"*.

## Do not re-ask
OQ-CUS-12785 (single-family owner-occupier). CAP/SENIOR = A (one of the two). Bill label prints = yes.

## Working rules this chat used (all already in CLAUDE.md / the decision log)
Lanes in their own `git worktree`; own PostgreSQL DB per lane at 127.0.0.1:55433 (venv /tmp/venv_a5c), own ports, never a broad pkill; start lanes only when load < 5; push via `10-scripts/push_paths.sh`; on each report: fetch, verify, ff, remove worktree, plain-English table, send a checked screenshot. Build screens from IMAGES (B14 rule 42). Desktop only.

## UPDATE — the discount walk's checkpoint landed (`d74d243c6`, build 2.481.6)
Steps 1–6 walked (118 of 120 checks pass) plus the list-width fix; **steps 7 (Edit), 8 (one version per date + Dec/Jan bills), 9 (limits on ISSUED runs), 10 (Retire), 11 (Utility B + all 11 languages) NOT walked.** Resume from `08-qa/discounts-2026-10-03/walk-report.md` (scripts `10-scripts/cr166_discwalk.mjs`, `cr166_discwalk_world.py`).
- Fixed in 2.481.6 but NOT yet closed in the register: DEF-RAT-9318, 9319, 9325, 9326 — run `close_defect.py` against `d74d243c6`. Also close DEF-RAT-9289 (D11–D13 stored correctly through the screen in step 1).
- **Open, not pushed: DEF-RAT-9327** — an approved charge waiver on named codes stops the WHOLE bill for every enrolled account ("rating refused to price this bill"). A guard at approval in 🔒 `discount_services` was started and withdrawn; nothing on the branch. Fix it first.
- **Put to the PO 2026-10-03, answer pending:** a usage allowance (Garden, image 10) can be created but never goes live — signed BR-RAT-962 keeps it unpriceable (billing it as money would take $2.00 off where the ruled arithmetic says $14.40). Options: (a) build the "free units before pricing" step — a money change, re-sign; (b) stop offering the usage-allowance type on the New form until then. Coordinator recommended (b). Check the decision log for the answer before acting.
- CR-166 section for task 9 and its decision-log row not yet written (content is in the walk report). Golden suite before: 25 passed + 1 xfailed — re-run after the 9327 fix.

## UPDATE — the discounts redesign is CLOSED (`CR-166-BRC10` §17, 2.481.11)
Walk complete (steps 1–11, 215 checks, 209 pass); every defect it found is fixed or filed. Still open
against discounts, none a blocker: the PO's two questions (Garden; may a waiver take a fee off),
`DEF-2430`/`DEF-BIL-5341` (granted this month, yearly caps — re-walk CAP-$300 on a bigger bill:
the $50 floor holds CAP at $10/month on $60), `DEF-RAT-9310` Duplicate, `DEF-478` plan add/remove,
`DEF-RAT-9303` second approval, `DEF-1005` CSV, `DEF-BIL-9346` bill Document tab wording.
The three "long-standing" front-end reds above now have rows: ConfirmDialog census `DEF-SHL-9347`
(BulkRunPage), rail census `DEF-RAT-9348` (it is the TAX edit form, `b71588e74`), runbooks `$8.2900`
`DEF-RBS-9349` (the test is stale since the 2026-10-02 unit-price ruling).

## UPDATE — the plans redesign is CLOSED (`CR-167-BRC10` §18–§19, 2.490.5)
Full web walk done (lane PLAN-WALK): nine phases, **195 checks, 195 pass**, on PostgreSQL 16 with the API
running as a NOSUPERUSER NOBYPASSRLS role (a superuser bypasses RLS and leaks the other utility's codes
into the form — walk as an app role). Real issued December and January bills: Ruth $94.35 → $98.38 after
the water schedule's v2; billing gets one plan version per date. Fixed in the walk: `DEF-RAT-9510`
(draft v1 through the version door), `9514` (a draft edited only on a priced step never saved), `9515`
(one banner line per upcoming change), `9516` (a plan not yet started read as its newest version),
`9517` (a corrected upcoming schedule version vanished), `9518` (English left in other languages).
Open: `DEF-RAT-9519` (low — a Residential plan lists a commercial-only tax and counts it in *combined*;
recommended mark it, leave it out of *combined*). Move units to another plan: not now. Report:
`08-qa/plans-2026-10-03/walk-report.md`; scripts `10-scripts/cr167_planwalk.mjs`,
`cr167_planwalk_world.py`.
