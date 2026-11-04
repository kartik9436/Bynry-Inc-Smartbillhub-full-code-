# T4-17 — Master-account link change (x = transfers route to master ACC-0009 → y = to ACC-9001; executed transfers stand)

---
id: T4-17
tier: 4
rules: [BR-BIL-013, BR-LED-001, BR-LED-011, BR-MET-046, BR-PAY-002]
stories: [US-BIL-011, US-LED-002, US-LED-010]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** x = Marina Bay units linked to master billing account ACC-0009 under the landlord-agreement flag (the OQ-069-closed prerequisite for BR-BIL-013's transfer-to-master settlement path); y = the landlord link re-pointed to ACC-9001 (property changed management). The boundary matters because the link is a ROUTING designation consumed at final-bill settlement time: future final bills must transfer to the NEW master, while every already-executed transfer is a balanced, audited, immutable transaction that stays exactly where it landed. Figures are the frozen WE-7B/LE-1 chain: final charges 289.40, deposit credit 153.50, transfer remainder **$135.90**.

**Fixture.** Tenant brazos-bend · Marina Bay premises, landlord link → **ACC-0009** · executed history: ACC-1055's final bill transferred **135.90** to ACC-0009 (LE-1) · link changed Aug 12 → **ACC-9001** · second tenancy ACC-1058 moves out Aug 20 with the same WE-7B shape (charges 289.40, deposit credit 153.50, remainder 135.90).

| # | Action | Upstream effect (what recomputes) | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | System Admin re-points the Marina Bay landlord-agreement link ACC-0009 → ACC-9001 | Master designation changes (the r10 #10 link); NOTHING recomputes — no balances move at link-change time | audit row with before/after master; the transfer settlement option remains available (link present); on an UNLINKED unit the option would be absent entirely | BR-BIL-013 (OQ-069 prereq) |
| 2 | Harness re-reads the executed LE-1 transfer after the change | — | ACC-0009 still carries the historical 135.90 (its AR position unchanged); the balance-transfer rows (credit final / debit master) are append-only and did NOT re-route | BR-PAY-002 posture · hard rule 4 |
| 3 | ACC-1058 moves out Aug 20; final bill issues; staff pick the transfer settlement path | Deposit credit 153.50 applies first; remainder **135.90** transfers as a balanced transaction to the CURRENT master = **ACC-9001**; AR total unchanged (AR just changes owner: CR final account / DR master) | ledger: AR ACC-1058 CR 135.90 / AR ACC-9001 DR 135.90, dimensions stamped (account, premises, unit, source); ACC-9001's next bill carries the transfer line; audited | BR-BIL-013 · BR-LED-001 |
| 4 | Harness checks reports | — | by-premises summary (LE-6 pattern): Marina Bay owed 0 at premises — owed now sits on ACC-9001, not ACC-0009; unit→premises chain integrity intact (units never moved); AR aging shows the 135.90 aging on the master, posting basis, labeled | BR-LED-011 · BR-MET-046 · BR-REP-001 |
| 5 | Negative probe: staff attempt a transfer to an arbitrary non-designated account | Refused — the transfer target must be THE designated master via the landlord-agreement link; exactly one settlement path per final bill | no rows written; error names the designation rule | BR-BIL-013 |
| 6 | **INVARIANCE** — what must NOT have changed | The LE-1 transfer to ACC-0009: byte-identical rows, never re-pointed, never reversed by the link change; both masters' issued bills unchanged; total tenant AR unmoved by any step except the new tenancy's own bill | balance-transfer transactions append-only; link-change touches ONE designation row + audit; trial balance ties out before and after | hard rule 4 · BR-LED-007 |
