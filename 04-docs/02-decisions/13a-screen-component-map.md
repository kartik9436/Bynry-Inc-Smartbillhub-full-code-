# 13a — Screen → Component → API Map (W0 checkpoint artifact, generated 2026-08-09)
> Companion to B13 component registry. Endpoint cells cite A11 verbatim; `GAP → A11 audit` marks missing coverage feeding the W0 A11 conformance audit. PO checkpoint: most screens must resolve to shared components + configuration.

**Conventions.** One row per A1 canonical screen ID; S97–S102 and S103–S106 stay collapsed exactly as A1 lists them. AppShell (EP-SHL-01, US-SHL-001…005) hosts every authenticated screen and is not repeated per row. DataTable rows imply IS-2..5 capability (server pagination/sort/filter/column chooser) plus IS-6 row/bulk actions; conformance details live in each epic's capability-matrix row, never here. Stories = US-IDs whose `screens:` frontmatter claims the S-ID (compressed ranges); annotations in parentheses are findings, not prose.

## Public & onboarding — tenancy · identity (S1–S6, S110–S114)
| S-ID | Screen | Shared components | Screen-specific | A11 endpoints | Stories |
|---|---|---|---|---|---|
| S1 | Pricing / packages | — | pricing plan cards | GAP → A11 audit | US-SHL-005 (sign-out target only) |
| S2 | Welcome gateway | — | first-time / sign-in fork | GAP → A11 audit | US-SHL-005 · US-IDN-001 |
| S3 | Sign-in | StateFrame · Toast | sign-in form | GAP → A11 audit | US-IDN-001 · US-IDN-002 |
| S4 | Setup wizard Step 1 (superseded by S110) | WizardFrame | — | GAP → A11 audit | unclaimed — superseded by S110–S114 (A1 rev 2026-08-08) |
| S5 | Setup wizard Step 2 (superseded by S111) | WizardFrame | — | GAP → A11 audit | unclaimed — superseded by S110–S114 |
| S6 | Setup wizard Step 3 (superseded by S114) | WizardFrame | — | POST /tenants | unclaimed — superseded by S110–S114 |
| S110 | Onboarding 1 · Your utility | WizardFrame | subdomain availability check · state type-ahead | GAP → A11 audit | unclaimed — flag (wizard UI = W8 onboarding epics per EP-TEN-03 Out; fields mapped in US-TEN-001) |
| S111 | Onboarding 2 · How you bill | WizardFrame | — | GAP → A11 audit | US-TEN-002 |
| S112 | Onboarding 3 · Plan & setup | WizardFrame · MoneyCell | plan cards · running cost line | GAP → A11 audit | unclaimed — flag (W8) |
| S113 | Onboarding 4 · Review | WizardFrame · MoneyCell | default-value markers · due-today panel | GAP → A11 audit | **US-TEN-021 (authored 2026-08-16, DEF-137 — was "unclaimed — flag (W8)" and had been since 2026-08-09)** |
| S114 | Onboarding 5 · Create login | WizardFrame · Toast | — | POST /tenants (A11 cites it on S6) | US-TEN-001 · US-TEN-003 · US-TEN-004 · US-SHL-009 |

## Platform shell & dashboard — platform-shell · reports · tenancy (S7, S48, S62)
| S-ID | Screen | Shared components | Screen-specific | A11 endpoints | Stories |
|---|---|---|---|---|---|
| S7 | Dashboard | PageHeader · KPIStrip · Chart · StateFrame | activity feed · quick actions | GET /dashboard/summary | **US-REP-019 (the SCREEN — built 2026-08-16, DEF-129)** · US-SHL-001 (chrome) · US-REP-016 · US-REP-017 (the W5 figure set) |
| S48 | User menu + self-service modals | FormModal · Toast | upward menu popover · 2FA QR enrollment | GAP → A11 audit | US-SHL-005 · US-IDN-003 · US-IDN-008 · US-IDN-009 |
| S62 | Post-signup checklist | StateFrame | dismissible gap checklist | GAP → A11 audit | US-TEN-003 (frontmatter claims S114 — retag to S62) |

## Settings — tenancy · identity · notifications · integrations (S8, S63–S66, S69–S71)
| S-ID | Screen | Shared components | Screen-specific | A11 endpoints | Stories |
|---|---|---|---|---|---|
| S8 | Settings (10 tabs) | DetailTabs · DataTable · FilterBar · FormModal · ConfirmDialog · StatusPill · Toast · StateFrame | regional live preview · roles matrix · integration connect cards · fiscal calendar | GET /integrations · POST /integrations/{key}/connect · POST /integrations/{key}/test · DELETE /integrations/{key} — Integrations tab only; other 9 tabs GAP → A11 audit | US-TEN-005–012 · US-IDN-002/004–007/010 · US-MET-006 · US-BIL-017/021 · US-NOT-001–008/013–015 · US-AUD-004 · US-INT-001–012 · US-SHL-001/013/014 |
| S63 | Holiday calendar | DataTable · FormModal · ConfirmDialog · DateCell · Toast | — | GAP → A11 audit | unclaimed — flag (US-TEN-013..017 allocated, unauthored — EP-TEN-07 scope addendum) |
| S64 | Read validation & estimation rules | FormModal · UnitCell · Toast | — | GAP → A11 audit | unclaimed — flag (same US-TEN-013..017 allocation; config consumed by US-MET-011/012/014) |
| S65 | Account types & sub-types | DataTable · FormModal · ConfirmDialog · StatusPill · Toast | — | GAP → A11 audit | unclaimed — flag (US-TEN-013..017 allocation) |
| S66 | Billing defaults | FormModal · MoneyCell · Toast | — | GAP → A11 audit | US-BIL-009 · US-BIL-018 · US-BIL-020 |
| S69 | Budget billing rules | FormModal · Toast | — | GAP → A11 audit | unclaimed — flag (US-TEN-013..017 allocation) |
| S70 | Collections & notices rules | FormModal · Toast | — | GAP → A11 audit | unclaimed — flag (US-TEN-013..017 allocation; cadence consumed by US-NOT-/US-REP- stories) |
| S71 | Finance controls | FormModal · MoneyCell · Toast | — | GAP → A11 audit | unclaimed — flag (US-TEN-013..017 allocation) |

## Plans & Rates — rating (S9–S13)
| S-ID | Screen | Shared components | Screen-specific | A11 endpoints | Stories |
|---|---|---|---|---|---|
| S9 | Plans & Rates (4 tabs) | DetailTabs · DataTable · FilterBar · StatusPill · MoneyCell · StateFrame | — | GAP → A11 audit | US-RAT-001/003/004/008–011 |
| S10 | New Plan wizard | WizardFrame · Toast | — | GAP → A11 audit | US-SHL-010 · US-RAT-002 · US-RAT-003 |
| S11 | New Rate wizard | WizardFrame · MoneyCell · UnitCell · Toast | rate tier/TOU editor | GAP → A11 audit | US-RAT-005–007/010 |
| S12 | New Charge Code form | FormModal · Toast | — | GAP → A11 audit | US-SHL-009 · US-RAT-008 |
| S13 | New Tax/Fee form | FormModal · Toast | — | GAP → A11 audit | US-SHL-009 · US-RAT-009 |

## Premises & Units — metering (S14–S16)
| S-ID | Screen | Shared components | Screen-specific | A11 endpoints | Stories |
|---|---|---|---|---|---|
| S14 | Premises list | DataTable · FilterBar · StatusPill · StateFrame | — | GAP → A11 audit | US-MET-001 · US-SHL-003 |
| S15 | Units list | DataTable · FilterBar · StatusPill | — | GAP → A11 audit | US-MET-002 |
| S16 | Add Premises & Unit form | FormModal · Toast | single-or-bulk rows · meter/plan assignment | GAP → A11 audit | US-SHL-009 · US-MET-003 · US-MET-004 |

## Accounts — customers (S17–S24, S68)
| S-ID | Screen | Shared components | Screen-specific | A11 endpoints | Stories |
|---|---|---|---|---|---|
| S17 | Accounts list | DataTable · FilterBar · StatusPill · MoneyCell · StateFrame | — | GET /accounts | US-CUS-001/002/019–023 · US-SHL-001/003/006/007/011/013/014 |
| S18 | New Account wizard | WizardFrame · Toast | premises+unit picker | GAP → A11 audit | US-SHL-010 · US-CUS-003/006/007 |
| S19 | Move-In wizard (four steps, `CR-171-BRC10`; its answer *Move-in completed*, image 48) | WizardFrame · PageHeader · Panel · CheckList · StatusPill · Toast | `moveInWizard/` — one file per step (`StepUnit` · `StepCustomer` · `StepBilling` · `StepReview`) reading ONE `MoveInWizardContext`, each step's own state in its `useStep<X>Own()`; `MoveInCompleted` (the ✓ list is the server's `what_happened`) — P2.15–P2.17, 2026-10-05 | POST /accounts/{id}/move-in · POST /units/{id}/move-in (CR-171 §9.FLOW, §9.MONEY — not in A11) | US-CUS-004/006/007 |
| S20 | Move-Out wizard | WizardFrame · MoneyCell · Toast | final-bill preview | GAP → A11 audit | US-CUS-005/007 · US-BIL-011 |
| S21 | Account detail | EntityHeader · DetailTabs · AuditTab · DataTable · StatusPill · MoneyCell · DateCell · DownloadButton · StateFrame | — | GET /accounts/{id} | US-CUS-006/008–015 · US-RAT-014 · US-PAY-007/009/016/018/019 · US-AUD-005 · US-SHL-002/003 |
| S22 | Account action modals (7) | FormModal · ConfirmDialog · MoneyCell · Toast | — | POST /accounts/{id}/payments — other 6 modals GAP → A11 audit | US-CUS-012–015 · US-PAY-001/002/006 · US-NOT-009 · US-SHL-009/012 |
| S23 | Change Plan wizard | WizardFrame · MoneyCell · Toast | proration preview | GAP → A11 audit | US-SHL-010 · US-CUS-016 · US-CUS-017 |
| S24 | Payment Plan wizard | WizardFrame · MoneyCell · Toast | installment schedule editor | GAP → A11 audit | US-CUS-018 · US-PAY-017 · US-NOT-012 |
| S68 | Account onboarding import wizard | ImportStager · WizardFrame · Toast | value-mapping step | GAP → A11 audit | US-CUS-019–023 |

## Meter Reads — metering (S25–S29)
| S-ID | Screen | Shared components | Screen-specific | A11 endpoints | Stories |
|---|---|---|---|---|---|
| S25 | Reads list | DataTable · FilterBar · StatusPill · UnitCell · DateCell · StateFrame | — | GET /reads | US-MET-011/012/014–016/018–020 · US-AST-012 · US-SHL-006/011 |
| S26 | Routes tab | DataTable | — | GAP → A11 audit | US-MET-005 |
| S27 | Cycles tab | DataTable · DateCell | — | GAP → A11 audit | US-MET-005 · US-MET-018 |
| S28 | Read upload wizard | ImportStager · WizardFrame · UnitCell · Toast | completeness bar | POST /reads/import | US-MET-007–010/014/017 · US-AST-011 · US-SHL-010/011 |
| S29 | Read detail drawer | UnitCell · DateCell · StateFrame | read-chain + flag-explanation drawer | GAP → A11 audit | US-MET-010/013/015/016 · US-AST-012 · US-AUD-006 |

## Billing (S30–S31.3)
| S-ID | Screen | Shared components | Screen-specific | A11 endpoints | Stories |
|---|---|---|---|---|---|
| S30 | Bills list | DataTable · FilterBar · StatusPill · MoneyCell · DateCell · DownloadButton · StateFrame | pending-billing queue chip | GAP → A11 audit (A11 notes name "Bills" for pagination; no endpoint row) | US-BIL-001/005–008/010–020/022–027 · US-PAY-016 · US-NOT-001/002/013/014 · US-SHL-001/003/006/007/008/013 |
| S31 | Run Bills wizard | WizardFrame · StateFrame · Toast | — | POST /billing/runs | US-BIL-001/004–006/010/012–014/023 · US-SHL-002/010/012 |
| S31.2 | Run Bills Step 2 — findings (6 sub-tabs) | DetailTabs · DataTable · UnitCell · MoneyCell | — | GET /billing/runs/{id}/findings | US-BIL-002 · US-MET-014/015 · US-RAT-012–014 |
| S31.3 | Run Bills Step 3 — exception cases | DataTable · ConfirmDialog · Toast | per-case fix tables | GAP → A11 audit | US-BIL-003 · US-SHL-008 |

## Payments (S32–S35)
| S-ID | Screen | Shared components | Screen-specific | A11 endpoints | Stories |
|---|---|---|---|---|---|
| S32 | Payments summary | KPIStrip · Chart · MoneyCell · StatusPill · StateFrame | autopay-scheduled panel · returned-mail chip | GAP → A11 audit | US-PAY-005/013/014/016/024 · US-REP-017 · US-REP-018 |
| S33 | Record payments ledger | DataTable · FilterBar · MoneyCell · DateCell · StatusPill · Toast | — | GET /payments | US-PAY-001–004/006–011/018/024/025 · US-NOT-011 · US-SHL-003/006/007/008/011/014 |
| S34 | Outstandings | DataTable · FilterBar · MoneyCell · StatusPill | — | GET /ar/outstanding | US-PAY-012–015/017–019 · US-NOT-009/010 · US-SHL-006/007/008/014 |
| S35 | Payment modals (12) | FormModal · ConfirmDialog · MoneyCell · Toast | — | GAP → A11 audit | US-PAY-001–003/008–010/012/015/016/025 · US-NOT-001/009–011/014 · US-INT-008 · US-SHL-012 |

## Finance — payments · ledger (S36–S43, S56–S58)
| S-ID | Screen | Shared components | Screen-specific | A11 endpoints | Stories |
|---|---|---|---|---|---|
| S36 | Revenue & AR | KPIStrip · Chart · DataTable · MoneyCell · StateFrame | aging buckets · tie-out panel | GAP → A11 audit (named a read-model candidate; no endpoint row) | US-LED-001/002/004/007/015 · US-SHL-001/011/013/014 |
| S37 | Deposits & Bank | DataTable · FilterBar · MoneyCell · StatusPill | — | GET /finance/deposits | US-PAY-020–023 |
| S38 | Bank import wizard | WizardFrame · ImportStager · DataTable · MoneyCell · Toast | — | POST /finance/bank-imports | US-PAY-021/022 · US-INT-008 · US-SHL-010–012 |
| S39 | Batch detail | EntityHeader · DataTable · MoneyCell · AuditTab | batch-vs-bank compare | GET /finance/deposits/{id} | US-PAY-023 · US-SHL-002 |
| S40 | Finance reconcile modal | FormModal · MoneyCell · Toast | — | GAP → A11 audit | US-PAY-022 |
| S41 | Taxes & Remittance | DataTable · MoneyCell · DownloadButton | dual-basis remittance view | GET /finance/taxes | US-BIL-008 · US-LED-014 |
| S42 | Export to accounting | DataTable · StatusPill · DownloadButton | — | POST /finance/exports | US-LED-015 · US-LED-016 · US-INT-009 |
| S43 | QuickBooks sync modal | FormModal · StatusPill · Toast | — | GAP → A11 audit | US-LED-016 · US-NOT-015 · US-INT-009 |
| S56 | General ledger tab | DataTable · FilterBar · MoneyCell · DownloadButton | account-mapping panel | GAP → A11 audit | US-LED-001–003/005/006/008/011–013 · US-BIL-009 |
| S57 | Manual journal entry modal | FormModal · MoneyCell · Toast | balanced debit/credit line editor | GAP → A11 audit | US-LED-011–013 |
| S58 | Record refund modal | FormModal · MoneyCell · Toast | — | GAP → A11 audit | US-PAY-011 |

## Reports (S44–S47, S59–S60)
| S-ID | Screen | Shared components | Screen-specific | A11 endpoints | Stories |
|---|---|---|---|---|---|
| S44 | Reports library | StateFrame | report card grid | GET /reports/{key} | US-REP-001 · US-REP-012 · US-AUD-009 |
| S45 | Scheduled & history | DataTable · SchedulePicker · StatusPill · DateCell | — | GAP → A11 audit | US-REP-004/012–015 · US-NOT-015 |
| S46 | Report viewer | FilterBar · KPIStrip · DataTable · MoneyCell · UnitCell · DownloadButton | — | GET /reports/{key} | US-REP-002/003/005–009/011 |
| S47 | Report builder | FilterBar · DataTable | dataset/column picker | GAP → A11 audit | US-REP-010–012 |
| S59 | Report — Account ledger | FilterBar · DataTable · MoneyCell · DateCell · DownloadButton | — | GET /reports/{key} (A11 cites it on S44/46) | US-LED-009 |
| S60 | Report — By-premises summary | FilterBar · DataTable · MoneyCell · DownloadButton | — | GET /reports/{key} (A11 cites it on S44/46) | US-LED-010 |

## Assets (S49–S55)
| S-ID | Screen | Shared components | Screen-specific | A11 endpoints | Stories |
|---|---|---|---|---|---|
| S49 | Assets list (3 tabs) | DetailTabs · DataTable · FilterBar · StatusPill · StateFrame | — | GAP → A11 audit | US-AST-001–003/007–010 · US-SHL-001 |
| S50 | Asset detail (5 tabs) | EntityHeader · DetailTabs · AuditTab · DataTable · UnitCell · StateFrame | — | GAP → A11 audit | US-AST-004–009/011/012 · US-AUD-005 |
| S51 | Add asset modal | FormModal · Toast | — | GAP → A11 audit | US-AST-002 |
| S52 | Asset bulk import | ImportStager · Toast | — | GAP → A11 audit | US-AST-010 |
| S53 | Log repair/maintenance modal | FormModal · Toast | — | GAP → A11 audit | US-AST-007 |
| S54 | Retire asset modal | FormModal · ConfirmDialog · Toast | — | GAP → A11 audit | US-AST-008 |
| S55 | Reassign asset modal | FormModal · UnitCell · Toast | — | GAP → A11 audit | US-AST-009 |

## Audit (S61)
| S-ID | Screen | Shared components | Screen-specific | A11 endpoints | Stories |
|---|---|---|---|---|---|
| S61 | Audit log viewer | DataTable · FilterBar · DateCell · DownloadButton · StateFrame | before/after JSON-diff drawer | GAP → A11 audit | US-AUD-001–009 |

## Templates & designers — notifications · billing (S67, S91–S106)
| S-ID | Screen | Shared components | Screen-specific | A11 endpoints | Stories |
|---|---|---|---|---|---|
| S67 | Contract template designers | DocumentViewer · FormModal · Toast | designer canvas · variable palette | GAP → A11 audit | US-NOT-006 · US-NOT-012 |
| S91 | Template designer · Bill residential | DocumentViewer · FormModal · Toast | designer canvas · variable palette | GAP → A11 audit | US-BIL-021 |
| S92 | Template designer · Bill commercial | DocumentViewer · FormModal · Toast | designer canvas · variable palette | GAP → A11 audit | US-BIL-021 |
| S93 | Template designer · Statement | DocumentViewer · FormModal · Toast | designer canvas · variable palette | GAP → A11 audit | US-BIL-021 |
| S94 | Template designer · Disconnect notice | DocumentViewer · FormModal · Toast | designer canvas · variable palette · 3-tier regulatory footer | GAP → A11 audit | US-NOT-007 · US-NOT-009 |
| S95 | Template designer · Dunning | DocumentViewer · FormModal · Toast | designer canvas · variable palette · 3-stage banners | GAP → A11 audit | US-NOT-007 · US-NOT-010 |
| S96 | Template designer · Receipt | DocumentViewer · FormModal · Toast | designer canvas · variable palette | GAP → A11 audit | US-NOT-007 · US-NOT-011 |
| S97–S102 | Email designers (6) | FormModal · Toast | designer canvas · variable palette · send-test | GAP → A11 audit | US-NOT-008 |
| S103–S106 | SMS designers (4) | FormModal · Toast | designer canvas · variable palette · segment counter | GAP → A11 audit | US-NOT-008 |

## Billing plan (subscription to Bynry) — tenancy · B10 (S107–S109)
| S-ID | Screen | Shared components | Screen-specific | A11 endpoints | Stories |
|---|---|---|---|---|---|
| S107 | Billing plan · Plan tab | StatusPill · MoneyCell · DateCell | entitlement counters · payment-method card | GAP → A11 audit | unclaimed — flag (W8 per EP-TEN-03/05 Out-scope, B10) |
| S108 | Billing plan · Invoices tab | KPIStrip · DataTable · FilterBar · MoneyCell · StatusPill · DownloadButton | as-at-issue plan/method rendering | GAP → A11 audit | unclaimed — flag (W8, B10; named a DataTable consumer in EP-SHL-02 header only) |
| S109 | Manage payment method modal | FormModal · Toast | card/ACH capture form | GAP → A11 audit | unclaimed — flag (W8, B10) |

## Coverage summary
- **89 rows mapped, covering all 97 canonical A1 screen IDs** (S1–S48 incl. S31.2/S31.3 = 50 · S49–S60 = 12 · S61–S71 = 11 · S91–S114 = 24; S97–S102 and S103–S106 stay collapsed exactly as A1 lists them).
- **47 rows resolve to shared components only · 42 rows (50 screens) carry a screen-specific part.** Every authenticated screen includes at least one shared component; only public marketing S1/S2 have none. No screen is bespoke end-to-end — the PO thesis holds, and most "specific" cells are a single panel/preview on top of shared parts.
- **B13 candidate (biggest lever):** the pair "designer canvas · variable palette" repeats across all 9 designer rows (17 screens: S67, S91–S106). Promoting it to a shared **TemplateDesigner** component would flip those rows to configuration-only → 56/89 rows (64/97 screens) shared-only.
- **A11 endpoint coverage: 22 screens carry at least one verbatim A11 endpoint; 2 of those are partial** (S8 — Integrations tab only; S22 — record-payment modal only). **67 rows (75 screens) are `GAP → A11 audit`.** A11 extracted only 17 endpoint rows + the integrations addendum; whole modules have zero endpoint coverage: Plans & Rates (S9–S13), Premises/Units (S14–S16), Assets (S49–S55), Audit (S61), Settings reference-data cards (S63–S71), Templates (S67, S91–S106), Billing plan (S107–S109), plus first-class lists Bills S30, Payments summary S32, Revenue & AR S36, General ledger S56–S58. Also feeding the audit: `GET /search?q=` is flagged inside US-SHL-003/BR-SHL-005 as a PROPOSED addition not present in A11.
- **19 screens unclaimed by any story** (no `screens:` frontmatter claim in any epic), and **this list is now MACHINE-CHECKED**: `10-scripts/gates/g25_screen_coverage.py` re-measures it against A1 on every run and refuses any screen that is neither claimed nor registered in `10-scripts/gates/screen_story_coverage.txt` with a dated reason. The gate was added 2026-08-16 after hard-won law 8 was broken a THIRD time (DEF-006 S1 · DEF-129 S7 · DEF-137 S113) and this hand-maintained line had carried the finding for a week with nothing acting on it. **S113 came off the list in that commit** — it is now US-TEN-021. The current 19: S4, S5 (superseded by S110–S114 — retire or retag in A1; **S6 is claimed now**); S63, S64, S65, S69, S70, S71 (stories US-TEN-013..017 allocated in EP-TEN-07's scope addendum but not yet authored); S107, S108, S109 (wave 8, B10); S110, S112 (onboarding wizard UI deferred to W8 per EP-TEN-03 Out-scope); S98, S99, S100, S101, S104, S105 (inside A1's RANGED designer rows S97–S102 and S103–S106, which the notifications template stories cite by range rather than by id). **Plus 1 claim mismatch:** S62's functionality is authored as US-TEN-003 (post-signup checklist) but its frontmatter claims S114 — retag to S62.
- **Reserved/unassigned S-IDs:** S72–S90 (19 IDs) remain reserved for design — no rows. S49–S62 are ratified canonical (OQ-014 CLOSED per EP-AST-03); S63–S71 assigned by A1 addenda 2026-08-08.
