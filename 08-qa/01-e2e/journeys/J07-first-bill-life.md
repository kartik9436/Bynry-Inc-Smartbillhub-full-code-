# J07 — First-bill life (move-in → prorated first bill with deposit + CONN → pay → month-2 normal)

---
id: J07
tier: 2
rules: [BR-CUS-021, BR-CUS-022, BR-CUS-023, BR-CUS-057, BR-BIL-012, BR-BIL-011, BR-BIL-010, BR-BIL-024, BR-BIL-016, BR-PAY-010, BR-PAY-012, BR-PAY-021, BR-PAY-024, BR-LED-007, BR-REP-001, BR-REP-012]
stories: [US-CUS-004, US-CUS-006, US-CUS-007, US-BIL-010, US-BIL-005, US-PAY-001, US-PAY-006, US-PAY-025, US-LED-001]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
# ABSORPTION MAP (T2 catalog closure): J23 tenant-isolation sweep → ABSORBED into T5-04 (parameterized over
# every tier incl. these T2 journeys); J24 localization → ABSORBED into T7-01..08 language rides. J07–J22
# complete the T2 tier; J23/J24 are intentionally not authored as files.
---

**Intent.** The account's first month of life, end-to-end: a Jul 12 move-in produces a FIRST bill that is unlike any other bill it will ever get — bases prorated 20/31, tier spans scaled, plus the two one-time lines (deposit → liability, CONN → fee) per BR-BIL-012 — and then month 2 proves the account has settled into a NORMAL cycle bill with no one-time residue. The frozen WE-6 figure $287.23 anchors the whole ride.

**Fixture.** Tenant brazos-bend · Residential Standard plan (WE-1 shape) · new account ACC-1201, unit 4B at 500 Main St · move-in **Jul 12, 2026** · deposit $150.00, election = add-to-first-bill · CONN $25.00 charge code · cycle due-days 21 · Jul 12–31 usage: TOU 70/120/210 kWh, water 4.2 kgal (= the WE-6 inputs).

| # | Date · action | Handoff contract (what this step leaves) | Downstream assertions (bill · ledger · reports · queue · audit) | Rule |
|---|---|---|---|---|
| 1 | **Jul 12** — Move-In wizard (S19): unit picked, plan snapshot saved, initial reads committed, deposit election add-to-first-bill, CONN attached | Account Active; `account_plan_assignments` snapshot row (BR-CUS-029); committed baseline reads per meter; deposit position $150.00 pending on first bill; unit occupancy derives Occupied | "New accounts" report counts the creation in period (BR-REP-012); audit rows for create/move-in; no invoice, no ledger row yet | BR-CUS-021/022/023 |
| 2 | **Aug 1** — cycle run bills Jul 12–31 (20/31 days): first bill BL-2608-1201 issues | **WE-6**: bases prorate elec 7.74 · water 5.16 · trash 11.61; tier-1 span scales to 3.225806 kgal → water 12.90+6.33; TOU 15.40+16.80+18.90; sewer 7.69; taxable 102.53 → tax 9.70; + **deposit 150.00 (non-taxable → deposit liability)** + **CONN 25.00 (fee, non-taxable)** → total **287.23**; due Aug 22 (issue+21, BR-BIL-024) | Invoice immutable, GL-stamped per line (BR-BIL-010); ONE balanced JE: DR AR 287.23 / CR revenue buckets + tax 9.70 + deposit-liability 150.00 + fee GL 25.00 (BR-BIL-011); delivery row queued per channel (BR-BIL-016); billed KPI = Aug, POSTING basis label (BR-REP-001); audit | BR-BIL-012 |
| 3 | **Aug 18** — payment $287.23 by check (posting Aug 18, clearing Aug 20 — both dates entered) | Payment on time by POSTING date (BR-PAY-021); allocation per BR-PAY-010 (usage+base → taxes → fees last); the deposit line is satisfied — $150.00 sits in deposit liability, never revenue (BR-PAY-012 deposit linkage); outstanding 0.00 | Ledger: DR cash / CR AR 287.23; deposit-liability tie-out = **150.00** exactly (BR-LED-007); interest accrual clock starts from receipt (BR-CUS-057); receipt auto-queued (BR-PAY-024); S32 today-total posting basis / method-mix clearing basis labels (BR-REP-010); audit | BR-PAY-010/021 |
| 4 | **Sep 1** — month-2 cycle run bills Aug 1–31 | A NORMAL bill: full-month bases, unscaled tier spans, NO deposit line, NO CONN line — amount **engine-computed** (00-e2e-design.md §5) | Bill anatomy per BR-BIL-011; no one-time GL buckets touched; aging shows account Current; delivery + audit rows | BR-BIL-012 (absence proof) |
| 5 | **INVARIANCE** — first bill BL-2608-1201 byte-identical on reprint; deposit-liability GL still 150.00 (untouched until final bill); plan snapshot unchanged; no UPDATE on any issued row | — | Reprints render the issued invoice verbatim (BR-CUS-040); append-only everywhere (hard rule 4); tie-outs hold (BR-LED-007) | BR-BIL-004 |
