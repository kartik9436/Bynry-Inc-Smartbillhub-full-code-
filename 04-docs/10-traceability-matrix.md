# Requirements Traceability Matrix (v2)

One row per story; grows with each epic pack. CSV mirror in `12-governance/07-metrics/traceability.csv`. Validated by `10-scripts/02-trace_lint.py` (CI). Code-refs column fills from PR merges (PR template names the US-ID).

| US-ID | Module | Epic | Wave | Screens | BR-IDs | OQ blocks | TCs | GTs | Code refs | UAT | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| US-TEN-001 | tenancy | EP-TEN-03 | W0 | S114 | BR-TEN-001,003,010,011,013,014,016 | — (OQ-034 vocab only) | 5 | — | — | — | draft |
| US-TEN-002 | tenancy | EP-TEN-03 | W0 | S111 | BR-TEN-012,013,016 | — | 6 | — | — | — | draft |
| US-TEN-003 | tenancy | EP-TEN-03 | W0 | S114 (+checklist, OQ-034) | BR-TEN-015,016 | — (OQ-034 vocab only) | 5 | — | — | — | draft |
| US-TEN-004 | tenancy | EP-TEN-03 | W0 | S114 | BR-TEN-001,010,011,016 | — | 5 | — | — | — | draft |
| US-TEN-005 | tenancy | EP-TEN-05 | W0 | S8 | BR-TEN-016,017,018,019,024 | — | 7 | — | — | — | draft |
| US-TEN-006 | tenancy | EP-TEN-05 | W0 | S8 | BR-TEN-016,020,021,022,023,024 | OQ-033 (ledger enforcement only) | 7 | — | — | — | draft |
| US-TEN-007 | tenancy | EP-TEN-06 | W0 | S8 | BR-TEN-016,025,026 | — | 5 | — | — | — | draft |
| US-TEN-008 | tenancy | EP-TEN-06 | W0 | S8 | BR-TEN-016,024,027 | — | 6 | — | — | — | draft |
| US-TEN-009 | tenancy | EP-TEN-07 | W0 | S8 | BR-TEN-029,033 | — | 6 | — | — | — | draft |
| US-TEN-010 | tenancy | EP-TEN-07 | W0 | S8 | BR-TEN-016,028,030,031,032 | OQ-031, OQ-032 (4 enum-backed lists) | 7 | — | — | — | draft |
| US-TEN-011 | tenancy | EP-TEN-07 | W0 | S8 | BR-TEN-016,029,034 | — | 6 | — | — | — | draft |
| US-TEN-012 | tenancy | EP-TEN-08 | W0 | S8 | BR-TEN-016,024,033,035 | — | 8 | — | — | — | draft |
| US-TEN-021 | tenancy | EP-TEN-03 | W8 | S113 | BR-TEN-014,010,045 + BR-SHL-010,023,044 | OQ-224 (the first-charge DATE only — Due today, the amount and the trial end all ship) | 7 | — | — | — | ready |
| US-IDN-001 | identity | EP-IDN-01 | W0 | S2, S3 | BR-IDN-001,BR-IDN-002,BR-IDN-003,BR-IDN-004 | — | see §3 | — | — | — | draft |
| US-IDN-002 | identity | EP-IDN-01 | W0 | S3 | BR-IDN-002,BR-IDN-005,BR-IDN-016 | OQ-025, OQ-028 | see §3 | — | — | — | blocked |
| US-IDN-003 | identity | EP-IDN-01 | W0 | S48 | BR-IDN-006,BR-IDN-007 | — | see §3 | — | — | — | draft |
| US-IDN-004 | identity | EP-IDN-02 | W0 | S8 | BR-IDN-008,BR-IDN-009,BR-IDN-010 | — | see §3 | — | — | — | draft |
| US-IDN-005 | identity | EP-IDN-02 | W0 | S8 | BR-IDN-005,BR-IDN-008,BR-IDN-009,BR-IDN-010,BR-IDN-011 | OQ-025, OQ-028 | see §3 | — | — | — | blocked |
| US-IDN-006 | identity | EP-IDN-02 | W0 | S8 | BR-IDN-008,BR-IDN-009,BR-IDN-012,BR-IDN-013 | — | see §3 | — | — | — | draft |
| US-IDN-007 | identity | EP-IDN-02 | W0 | S8 | BR-IDN-008,BR-IDN-009,BR-IDN-012,BR-IDN-013,BR-IDN-014 | — | see §3 | — | — | — | draft |
| US-IDN-008 | identity | EP-IDN-03 | W0 | S48 | BR-IDN-015,BR-IDN-016,BR-IDN-017 | — | see §3 | — | — | — | draft |
| US-IDN-009 | identity | EP-IDN-03 | W0 | S48 | BR-IDN-004,BR-IDN-015,BR-IDN-018 | — | see §3 | — | — | — | draft |
| US-IDN-010 | identity | EP-IDN-04 | W0 | S8 | BR-IDN-004,BR-IDN-006,BR-IDN-016,BR-IDN-019,BR-IDN-020 | OQ-025, OQ-026 | see §3 | — | — | — | blocked |
| US-SHL-001 | platform-shell | EP-SHL-01 | W0 | shell-chrome, S7, S8, S17, S30, S36, S49 | BR-SHL-001,BR-SHL-002,BR-SHL-003 | — | see §3 | — | — | — | draft |
| US-SHL-002 | platform-shell | EP-SHL-01 | W0 | shell-chrome, S21, S31, S39 | BR-SHL-004 | — | see §3 | — | — | — | draft |
| US-SHL-003 | platform-shell | EP-SHL-01 | W0 | shell-chrome, S14, S17, S21, S30, S33 | BR-SHL-005,BR-SHL-006 | — | see §3 | — | — | — | draft |
| US-SHL-004 | platform-shell | EP-SHL-01 | W0 | shell-chrome | BR-SHL-007 | — | see §3 | — | — | — | draft |
| US-SHL-005 | platform-shell | EP-SHL-01 | W0 | shell-chrome, S48, S1, S2 | BR-SHL-008,BR-SHL-009 | — | see §3 | — | — | — | draft |
| US-SHL-006 | platform-shell | EP-SHL-02 | W0 | S17, S25, S30, S33, S34 | BR-SHL-010,BR-SHL-011,BR-SHL-012 | — | see §3 | — | — | — | draft |
| US-SHL-007 | platform-shell | EP-SHL-02 | W0 | S17, S30, S33, S34 | BR-SHL-011,BR-SHL-013 | — | see §3 | — | — | — | draft |
| US-SHL-008 | platform-shell | EP-SHL-02 | W0 | S33, S34, S30, S31.3 | BR-SHL-014,BR-SHL-015,BR-SHL-016 | — | see §3 | — | — | — | draft |
| US-SHL-009 | platform-shell | EP-SHL-03 | W0 | S12, S13, S16, S22, S114 | BR-SHL-017 | — | see §3 | — | — | — | draft |
| US-SHL-010 | platform-shell | EP-SHL-03 | W0 | S10, S18, S23, S28, S31, S38 | BR-SHL-018,BR-SHL-019 | — | see §3 | — | — | — | draft |
| US-SHL-011 | platform-shell | EP-SHL-04 | W0 | S17, S25, S28, S33, S36, S38 | BR-SHL-020 | — | see §3 | — | — | — | draft |
| US-SHL-012 | platform-shell | EP-SHL-04 | W0 | S22, S31, S35, S38 | BR-SHL-021,BR-SHL-022 | — | see §3 | — | — | — | draft |
| US-SHL-013 | platform-shell | EP-SHL-05 | W0 | S8, S17, S30, S36 | BR-SHL-023,BR-SHL-024 | — | see §3 | — | — | — | draft |
| US-SHL-014 | platform-shell | EP-SHL-06 | W0 | S8, S17, S33, S34, S36 | BR-SHL-003,BR-SHL-025 | — | see §3 | — | — | — | draft |
| US-MET-001 | metering | EP-MET-01 | W1 | S14 | BR-MET-001,BR-MET-003 | — | see §3 | — | — | — | draft |
| US-MET-002 | metering | EP-MET-01 | W1 | S15 | BR-MET-002,BR-MET-003 | — | see §3 | — | — | — | draft |
| US-MET-003 | metering | EP-MET-01 | W1 | S16 | BR-MET-001,BR-MET-002,BR-MET-003,BR-MET-006,BR-MET-007 | — | see §3 | — | — | — | draft |
| US-MET-004 | metering | EP-MET-01 | W1 | S16 | BR-MET-002,BR-MET-004,BR-MET-005,BR-MET-006,BR-MET-007 | — (OQ-039 pattern grammar only) | see §3 | — | — | — | draft |
| US-MET-005 | metering | EP-MET-02 | W1 | S26, S27 | BR-MET-010,BR-MET-011 | — | see §3 | — | — | — | draft |
| US-MET-006 | metering | EP-MET-02 | W1 | S8 (Routes & Cycles) | BR-MET-008,BR-MET-009,BR-MET-010 | — (OQ-041 capacity only) | see §3 | — | — | — | draft |
| US-MET-007 | metering | EP-MET-03 | W2 | S28 | BR-MET-012,BR-MET-013,BR-MET-014,BR-MET-032,BR-MET-059 | — (OQ-040 CLOSED — no mapping memory) | see §3 | — | — | — | draft |
| US-MET-008 | metering | EP-MET-03 | W2 | S28 | BR-MET-012,BR-MET-015,BR-MET-019,BR-MET-049,BR-MET-052 | — (OQ-002, OQ-009 CLOSED — referenced only) | see §3 | — | — | — | draft |
| US-MET-009 | metering | EP-MET-03 | W2 | S28 | BR-MET-016,BR-MET-017,BR-MET-052,BR-MET-053 | — | see §3 | — | — | — | draft |
| US-MET-010 | metering | EP-MET-03 | W2 | S28, S29 | BR-MET-015,BR-MET-017,BR-MET-018,BR-MET-019,BR-MET-053,BR-MET-055 | — (OQ-042, OQ-044 CLOSED — key mechanics Eng-Lead 🔒) | see §3 | — | — | — | draft |
| US-MET-011 | metering | EP-MET-04 | W2 | S25 | BR-MET-020,BR-MET-021,BR-MET-022,BR-MET-025,BR-MET-049,BR-MET-052 | — (OQ-002 CLOSED — engine config-driven) | see §3 | — | — | — | draft |
| US-MET-012 | metering | EP-MET-04 | W2 | S25 | BR-MET-021,BR-MET-023,BR-MET-049,BR-MET-055,BR-MET-060 | — | see §3 | — | — | — | draft |
| US-MET-013 | metering | EP-MET-04 | W2 | S29 | BR-MET-022,BR-MET-023,BR-MET-024,BR-MET-053,BR-MET-056 | — (OQ-043 CLOSED — v1 record+flag+hold) | see §3 | — | — | — | draft |
| US-MET-014 | metering | EP-MET-05 | W3 | S25, S28, S31.2 | BR-MET-026,BR-MET-027,BR-MET-028,BR-MET-058 | — (OQ-003 CLOSED — defaults tenant-configurable) | see §3 | GT-9 | — | — | draft |
| US-MET-015 | metering | EP-MET-05 | W3 | S25, S29, S31.2 | BR-MET-028,BR-MET-029,BR-MET-030,BR-MET-058 | — (OQ-003 CLOSED — defaults tenant-configurable) | see §3 | GT-9 | — | — | draft |
| US-MET-016 | metering | EP-MET-04 | W3 | S25, S29 | BR-MET-053,BR-MET-054 | — | see §3 | — | — | — | draft |
| US-MET-017 | metering | EP-MET-03 | W2 | S28 | BR-MET-049,BR-MET-052,BR-MET-059 | — | see §3 | — | — | — | draft |
| US-MET-018 | metering | EP-MET-03 | W2 | S25, S27 | BR-MET-049,BR-MET-057 | — | see §3 | — | — | — | draft |
| US-MET-019 | metering | EP-MET-04 | W2 | S25 | BR-MET-056,BR-MET-060 | — | see §3 | — | — | — | draft |
| US-MET-020 | metering | EP-MET-03 | W3 | S25 (archive search) | BR-MET-055 | — | see §3 | — | — | — | draft |
| US-AST-001 | assets | EP-AST-01 | W1 | S49 | BR-AST-001,004,005,006,007 | — (OQ-046 seeded defaults only) | 7 | — | — | — | draft |
| US-AST-002 | assets | EP-AST-01 | W1 | S49, S51 | BR-AST-003,008,009,010,011 | — (OQ-045 auto-number default only) | 8 | — | — | — | draft |
| US-AST-003 | assets | EP-AST-01 | W1 | S49 | BR-AST-002,012,013 | — | 7 | — | — | — | draft |
| US-AST-004 | assets | EP-AST-02 | W1 | S50 | BR-AST-007,014,015 | — (OQ-046 seeded defaults only) | 7 | — | — | — | draft |
| US-AST-005 | assets | EP-AST-02 | W1 | S50 | BR-AST-003,016 | — | 6 | — | — | — | draft |
| US-AST-006 | assets | EP-AST-02 | W1 | S50 | BR-AST-017,018,019 | — | 6 | — | — | — | draft |
| US-AST-007 | assets | EP-AST-03 | W1 | S53, S49, S50 | BR-AST-018,020 | — | 7 | — | — | — | draft |
| US-AST-008 | assets | EP-AST-03 | W1 | S54, S49, S50 | BR-AST-002,013,020,021 | — | 7 | — | — | — | draft |
| US-AST-009 | assets | EP-AST-03 | W1 | S55, S49, S50 | BR-AST-017,020,022 | — | 7 | — | — | — | draft |
| US-AST-010 | assets | EP-AST-04 | W1 | S52, S49 | BR-AST-008,009,023 | — (OQ-045 blank-# handling only) | 8 | — | — | — | draft |
| US-AST-011 | assets | EP-AST-05 | W2 | S28, S50 | BR-AST-010,024 | — (OQ-001 blocks EP-RAT-06, not this) | 7 | — | — | — | draft |
| US-AST-012 | assets | EP-AST-05 | W2 | S50, S25, S29 | BR-AST-016,024,025 | — (OQ-001 blocks EP-RAT-06, not this) | 5 | — | — | — | draft |
| US-RAT-001 | rating | EP-RAT-01 | W1 | S9 | BR-RAT-012,024,025,027,030 | — | 7 | — | — | — | draft |
| US-RAT-002 | rating | EP-RAT-01 | W1 | S10 | BR-RAT-012,020,023,024,025,026,027,030,039 | — (OQ-055 discounts/eligibility blocks only) | 8 | — | — | — | draft |
| US-RAT-003 | rating | EP-RAT-01 | W1 | S9, S10 | BR-RAT-017,025,030,037 | — | 7 | — | — | — | draft |
| US-RAT-004 | rating | EP-RAT-02 | W1 | S9 | BR-RAT-019,024,025,031 | — | 6 | — | — | — | draft |
| US-RAT-005 | rating | EP-RAT-02 | W1 | S11 | BR-RAT-013,026,031,032,038 | — | 8 | GT-2 | — | — | draft |
| US-RAT-006 | rating | EP-RAT-02 | W1 | S11 | BR-RAT-021,024,031,033 | — | 8 | — | — | — | draft |
| US-RAT-007 | rating | EP-RAT-02 | W1 | S11 | BR-RAT-014,015,018,019,022,031,034 | — (demand measurement PROPOSED per B4 addendum — capture buildable) | 9 | GT-15 | — | — | draft |
| US-RAT-008 | rating | EP-RAT-03 | W1 | S9, S12 | BR-RAT-005,025,035 | — (OQ-053 Formula option only) | 9 | — | — | — | draft |
| US-RAT-009 | rating | EP-RAT-03 | W1 | S9, S13 | BR-RAT-005,006,025,036 | — (OQ-054 threshold-limited per-unit only) | 8 | GT-10 | — | — | draft |
| US-RAT-010 | rating | EP-RAT-04 | W1 | S9, S11 | BR-RAT-007,017,025,037 | — | 8 | — | — | — | draft |
| US-RAT-011 | rating | EP-RAT-04 | W1 | S9 | BR-RAT-017,025,037,040 | — | 8 | — | — | — | draft |
| US-RAT-012 | rating | EP-RAT-05 | W3 | S31.2 | BR-RAT-001,002,003,004,011,015,021,026,038 | — (🔒 engine.py HUMAN-OWNED — Eng Lead implements) | 10 | GT-1, GT-2, GT-5 | — | — | draft |
| US-RAT-013 | rating | EP-RAT-05 | W3 | S31.2 | BR-RAT-003,005,006,016,028,036 | — (🔒 engine.py HUMAN-OWNED — Eng Lead implements) | 9 | GT-10, GT-11, GT-13 | — | — | draft |
| US-RAT-014 | rating | EP-RAT-06 | W3 | S21, S31.2 | BR-RAT-003,004,018,019,022,029 | — (net-metering credits v1.1 by closed OQ-001) | 8 | GT-15 | — | — | draft |
| US-CUS-001 | customers | EP-CUS-01 | W2 | S17 | BR-CUS-015,016,017,053,055 | — (OQ-064 class seed — billing W3 only) | 7 | — | — | — | draft |
| US-CUS-002 | customers | EP-CUS-01 | W2 | S17 | BR-CUS-015,016,053,054 | — | 7 | — | — | — | draft |
| US-CUS-003 | customers | EP-CUS-02 | W2 | S18 | BR-CUS-010,012,014,017,018,019,020,021,022,023,028,045,054,058,059,060 | — | 8 | GT-3 | — | — | draft |
| US-CUS-004 | customers | EP-CUS-02 | W2 | S19 | BR-CUS-010,014,019,020,021,022,023,024,054,056 + BR-MET-044 | — | 7 | GT-3 | — | — | draft |
| US-CUS-005 | customers | EP-CUS-02 | W2 | S20 | BR-CUS-014,025,030,031,056,057 + BR-MET-036,BR-MET-044,BR-BIL-004 | — | 8 | GT-3 | — | — | draft |
| US-CUS-006 | customers | EP-CUS-02 | W2 | S18, S19, S21 | BR-CUS-011,012,013,014,029,055,058 | — | 7 | — | — | — | draft |
| US-CUS-007 | customers | EP-CUS-02 | W2 | S18, S19, S20 | BR-RAT-020,023 + BR-CUS-023,024,025,054,057 | — | 8 | — | — | — | draft |
| US-CUS-008 | customers | EP-CUS-03 | W2 | S21 | BR-CUS-016,033,034,054,055,058 | — (OQ-064 class seed — action gating beyond Closed only) | 6 | — | — | — | draft |
| US-CUS-009 | customers | EP-CUS-03 | W2 | S21 | BR-CUS-028,034,045,054,057,058 | — | 7 | — | — | — | draft |
| US-CUS-010 | customers | EP-CUS-03 | W2 | S21 | BR-CUS-034 + BR-BIL-004,BR-PAY-002 | — | 6 | — | — | — | draft |
| US-CUS-011 | customers | EP-CUS-03 | W2 | S21 | BR-CUS-034,035,036 + BR-MET-017 | — | 8 | — | — | — | draft |
| US-CUS-012 | customers | EP-CUS-04 | W4 | S22, S21 | BR-CUS-037,059 + BR-PAY-001,BR-PAY-010,BR-PAY-002 | — | 7 | GT-7 | — | — | draft |
| US-CUS-013 | customers | EP-CUS-04 | W4 | S22, S21 | BR-CUS-037,038 + BR-BIL-004,BR-BIL-009 | — | 7 | GT-6 | — | — | draft |
| US-CUS-014 | customers | EP-CUS-04 | W4 | S22, S21 | BR-CUS-037,040 | — | 6 | — | — | — | draft |
| US-CUS-015 | customers | EP-CUS-04 | W4 | S22, S21 | BR-CUS-035,037,039 + BR-BIL-007 | — | 7 | — | — | — | draft |
| US-CUS-016 | customers | EP-CUS-05 | W8 | S23 | BR-CUS-041,042 + BR-RAT-030,BR-RAT-043 | — | 7 | GT-3 | — | — | draft |
| US-CUS-017 | customers | EP-CUS-05 | W8 | S23 | BR-CUS-011,013,014,029,042 | — | 7 | — | — | — | draft |
| US-CUS-018 | customers | EP-CUS-06 | W4 | S24 | BR-CUS-037,043,044 (default clause SUPERSEDED 2026-08-11), BR-BIL-073 | OQ-139 (partial-payment order) · (OQ-059 CLOSED — auto-charge = W7 execution per BR-CUS-059) | 11 | GT-47 | apps/customers/payment_plan.py, payment_plan_service.py, seams.py | — | built (backend wizard; the plan ROWS are payments-owned and unbuilt — the handoff refuses) |
| US-CUS-019 | customers | EP-CUS-07 | W2 | S17 (entry; wizard ID OQ-063) | BR-CUS-017,046,047,051,054,059,060 + BR-TEN-035 | — (OQ-063 wizard screen ID only) | 8 | — | — | — | draft |
| US-CUS-020 | customers | EP-CUS-07 | W2 | S17 (entry; wizard ID OQ-063) | BR-CUS-051,052,055 | — (OQ-064 class seed — mapping unaffected) | 6 | — | — | — | draft |
| US-CUS-021 | customers | EP-CUS-07 | W2 | S17 (entry; wizard ID OQ-063) | BR-CUS-048,051 | — (OQ-065 credit-balance rows only) | 6 | GT-16 | — | — | draft |
| US-CUS-022 | customers | EP-CUS-07 | W2 | S17 (service contract; results on S56 in W5) | BR-CUS-048,049 | — | 6 | GT-16 | — | — | draft |
| US-CUS-023 | customers | EP-CUS-07 | W2 | S17 (entry; wizard ID OQ-063) | BR-CUS-025,050,057 | — | 6 | — | — | — | draft |
| US-BIL-001 | billing | EP-BIL-01 | W3 | S30, S31 | BR-BIL-005,021,024 | — | 6 | — | — | — | draft |
| US-BIL-002 | billing | EP-BIL-01 | W3 | S31.2 | BR-BIL-001,002,008,028,029 | — | 7 | GT-8 | — | — | draft |
| US-BIL-003 | billing | EP-BIL-01 | W3 | S31.3 | BR-BIL-003,006,007,015 | — | 8 | GT-9 | — | — | draft |
| US-BIL-004 | billing | EP-BIL-01 | W3 | S31 | BR-BIL-004,023,029 | — | 7 | — | — | — | draft |
| US-BIL-005 | billing | EP-BIL-01 | W3 | S31, S30 | BR-BIL-004,010,011,016,022,024,026 | — | 7 | — | — | — | draft |
| US-BIL-006 | billing | EP-BIL-01 | W3 | S30, S31 | BR-BIL-005,015 | — | 7 | — | — | — | draft |
| US-BIL-007 | billing | EP-BIL-02 | W3 | S30 | BR-BIL-004,010,011 | — | 7 | — | — | — | draft |
| US-BIL-008 | billing | EP-BIL-02 | W3 | S30, S41 | BR-BIL-021 + B4.2 (tax base/exemption) | — | 7 | GT-10, GT-11 | — | — | draft |
| US-BIL-009 | billing | EP-BIL-02 | W3 | S56, S66 | BR-BIL-010,011,013 | — | 7 | — | — | — | draft |
| US-BIL-010 | billing | EP-BIL-03 | W3 | S31, S30 | BR-BIL-012 | — | 7 | GT-3 | — | — | draft |
| US-BIL-011 | billing | EP-BIL-03 | W3 | S20, S30 | BR-BIL-013 | — (OQ-069, OQ-070 CLOSED — referenced only) | 7 | — | — | — | draft |
| US-BIL-012 | billing | EP-BIL-03 | W3 | S30, S31 | BR-BIL-020,023 | — | 6 | — | — | — | draft |
| US-BIL-013 | billing | EP-BIL-03 | W5 | S30, S31 | BR-BIL-018 | — (OQ-071 CLOSED — cap + theft exemption) | 7 | — | — | — | draft |
| US-BIL-014 | billing | EP-BIL-03 | W5 | S30, S31 | BR-BIL-007,018,019 | — | 7 | — | — | — | draft |
| US-BIL-015 | billing | EP-BIL-04 | W5 | S30 | BR-BIL-004,014 | — | 7 | GT-6 | — | — | draft |
| US-BIL-016 | billing | EP-BIL-04 | W5 | S30 | BR-BIL-014 | — | 7 | — | — | — | draft |
| US-BIL-017 | billing | EP-BIL-04 | W5 | S30, S8 | BR-BIL-009,014 | — (OQ-072 CLOSED — Admin-all v1, threshold v2) | 6 | — | — | — | draft |
| US-BIL-018 | billing | EP-BIL-05 | W4 | S30, S66 | BR-BIL-017,021 | — | 6 | GT-24 | apps/billing/budget.py, budget_service.py, migrations/0012+0013 | — | built (backend; S30 tab unbuilt) |
| US-BIL-019 | billing | EP-BIL-05 | W4 | S30 | BR-BIL-017,072 | OQ-164 (FINAL bill only) · OQ-142 (settle-up GL) | 10 | GT-24 | apps/billing/budget.py, budget_service.record_bill, stages/assemble_document.py, selectors.amount_due_for | — | built (backend; S30 tab unbuilt) |
| US-BIL-020 | billing | EP-BIL-05 | W4 | S30, S66 | BR-BIL-017 (drop-off clause SUPERSEDED 2026-08-11) | — (OQ-068 CLOSED — ±30% override; OQ-141 CLOSED — no drop-off) | 8 | — | apps/billing/budget_service.relevel/override_level/remove_from_budget | — | built (backend; S30 tab unbuilt) |
| US-BIL-021 | billing | EP-BIL-06 | W3 | S8, S91, S92, S93 | BR-BIL-025,026,027 | — | 6 | — | — | — | draft |
| US-BIL-022 | billing | EP-BIL-06 | W3 | S30 | BR-BIL-026,027 | — | 6 | — | — | — | draft |
| US-BIL-023 | billing | EP-BIL-06 | W3 | S31, S30 | BR-BIL-016 | — (OQ-073, OQ-074 CLOSED — email dispatch deferred → W6) | 7 | — | — | — | draft |
| US-BIL-024 | billing | EP-BIL-06 | W3 | S30 | BR-BIL-016 | — | 6 | — | — | — | draft |
| US-BIL-025 | billing | EP-BIL-07 | W3 | S30 | BR-BIL-004,022 | — | 7 | — | — | — | draft |
| US-BIL-026 | billing | EP-BIL-07 | W3 | S30 | BR-BIL-004,010,026 | — | 6 | — | — | — | draft |
| US-BIL-027 | billing | EP-BIL-07 | W5 | S30 | BR-BIL-004,009 | — (OQ-012 CLOSED — void windows referenced) | 6 | — | — | — | draft |
| US-BIL-028 | billing | EP-BIL-02 | W2 | S30, S31 | BR-BIL-030 + BR-TEN-048,050 | OQ-125 (4 of 6 data types stubbed) · OQ-118 (3 of 8 entities reached) | 10 | — | apps/billing/custom_snapshot.py, apps/billing/migrations/0009_w2_custom_snapshot.py | — | draft |
| US-PAY-001 | payments | EP-PAY-01 | W4 | S22, S35, S33 | BR-PAY-002,021,022,026,028 | — | 7 | — | — | — | draft |
| US-PAY-002 | payments | EP-PAY-01 | W4 | S22, S35, S33 | BR-PAY-010,012 + BR-BIL-012 | — | 6 | — | — | — | draft |
| US-PAY-003 | payments | EP-PAY-01 | W4 | S35, S33 | BR-PAY-003,021,023,028 | — (lockbox date interplay = pack report P-3, candidate) | 7 | — | — | — | draft |
| US-PAY-004 | payments | EP-PAY-01 | W4 | S33 | BR-PAY-002,021,027 | — | 7 | — | — | — | draft |
| US-PAY-005 | payments | EP-PAY-01 | W4 | S32 | BR-PAY-015,018,027 | — (DSO formula = pack report P-1, candidate) | 6 | — | — | — | draft |
| US-PAY-006 | payments | EP-PAY-02 | W4 | S22, S33 | BR-PAY-001,010,021 | — (OQ-010 CLOSED — order referenced) | 8 | GT-7 | — | — | draft |
| US-PAY-007 | payments | EP-PAY-02 | W4 | S33, S21 | BR-PAY-010,012 + BR-CUS-061 | — | 6 | — | — | — | draft |
| US-PAY-008 | payments | EP-PAY-02 | W4 | S35, S33 | BR-PAY-002,030,031 | — | 7 | — | — | — | draft |
| US-PAY-009 | payments | EP-PAY-03 | W4 | S35, S33, S21 | BR-PAY-002,013,021 + BR-BIL-007 | — | 7 | — | — | — | draft |
| US-PAY-010 | payments | EP-PAY-03 | W4 | S35, S33 | BR-PAY-002,011,030 | — (OQ-012 CLOSED — windows referenced) | 8 | — | — | — | draft |
| US-PAY-011 | payments | EP-PAY-03 | W5 | S58, S33 | BR-PAY-002,014,024 | — | 7 | — | — | — | draft |
| US-PAY-012 | payments | EP-PAY-03 | W4 | S34, S35 | BR-PAY-002,020 | — (agency/deposit-flag checkboxes = pack report P-4/P-5, candidates) | 7 | — | — | — | draft |
| US-PAY-013 | payments | EP-PAY-04 | W4 | S34, S32 | BR-PAY-015,018,021,029 | — (days-late base = pack report P-2, candidate) | 7 | — | — | — | draft |
| US-PAY-014 | payments | EP-PAY-04 | W4 | S34, S32 | BR-PAY-017,021 + BR-NOT-005 | — | 8 | — | — | — | draft |
| US-PAY-015 | payments | EP-PAY-04 | W4 | S35, S34 | BR-PAY-017,029 + BR-NOT-005,BR-CUS-039 | — | 7 | — | — | — | draft |
| US-PAY-016 | payments | EP-PAY-04 | W4 | S35, S30, S32, S21 | BR-PAY-018 + BR-NOT-005 | — | 6 | — | — | — | draft |
| US-PAY-017 | payments | EP-PAY-05 | W4 | S24, S34 | BR-PAY-012 + BR-CUS-043,BR-CUS-044 | — | 8 | — | — | — | draft |
| US-PAY-018 | payments | EP-PAY-05 | W4 | S21, S34, S33 | BR-PAY-016,021 + BR-NOT-005 | — | 8 | — | — | — | draft |
| US-PAY-019 | payments | EP-PAY-05 | W4 | S21, S34 | BR-PAY-016,017 + BR-CUS-043 | — | 7 | — | — | — | draft |
| US-PAY-020 | payments | EP-PAY-06 | W5 | S37 | BR-PAY-004,021,025 | — | 6 | — | — | — | draft |
| US-PAY-021 | payments | EP-PAY-06 | W5 | S38, S37 | BR-PAY-004,019,021 | — (Plaid connect out of v1 = pack report P-6) | 7 | — | — | — | draft |
| US-PAY-022 | payments | EP-PAY-06 | W5 | S40, S38, S37 | BR-PAY-004,013,019 | — (force-match supersession = pack report P-8, candidate) | 7 | — | — | — | draft |
| US-PAY-023 | payments | EP-PAY-06 | W5 | S39, S37 | BR-PAY-002,004,019 | — | 6 | — | — | — | draft |
| US-PAY-024 | payments | EP-PAY-07 | W4 | S32, S33 | BR-PAY-015,021 + BR-CUS-059 | — | 7 | — | — | — | draft |
| US-PAY-025 | payments | EP-PAY-07 | W4 | S35, S33 | BR-PAY-021,024 + BR-NOT-005 | — | 6 | — | — | — | draft |
| US-LED-001 | ledger | EP-LED-01 | W5 | S56, S36 | BR-LED-001,008,015 + BR-BIL-011,BR-CUS-049 | — | 7 | GT-16 | — | — | draft |
| US-LED-002 | ledger | EP-LED-01 | W5 | S56, S36 | BR-LED-001,015 + BR-MET-046,BR-REP-002 | — | 6 | — | — | — | draft |
| US-LED-003 | ledger | EP-LED-01 | W5 | S56 | BR-LED-003,015 + BR-TEN-038,BR-BIL-014,BR-PAY-013 | — | 7 | GT-6 | — | — | draft |
| US-LED-004 | ledger | EP-LED-01 | W5 | S36 | BR-LED-007,015 + BR-REP-001,BR-REP-002 | — | 6 | — | — | — | draft |
| US-LED-005 | ledger | EP-LED-02 | W5 | S56 | BR-LED-014,015 | — (COA seed content = r13 #7 — finance at GT freeze) | 6 | — | — | — | draft |
| US-LED-006 | ledger | EP-LED-02 | W5 | S56 | BR-LED-004,014,015 + BR-BIL-010 | — | 7 | — | — | — | draft |
| US-LED-007 | ledger | EP-LED-03 | W5 | S36 | BR-LED-007,016,015 + BR-REP-001,009,011,014 | — | 6 | — | — | — | draft |
| US-LED-008 | ledger | EP-LED-03 | W5 | S56 | BR-LED-009,015 + BR-TEN-022,BR-MET-046,BR-REP-018 | — | 6 | — | — | — | draft |
| US-LED-009 | ledger | EP-LED-03 | W5 | S59 | BR-LED-010,015 + BR-REP-008,BR-REP-018,BR-CUS-048 | — | 7 | — | — | — | draft |
| US-LED-010 | ledger | EP-LED-03 | W5 | S60 | BR-LED-011,015 + BR-MET-046,BR-REP-009,BR-REP-018 | — | 6 | — | — | — | draft |
| US-LED-011 | ledger | EP-LED-04 | W5 | S57, S56 | BR-LED-001,003,015 | — | 7 | — | — | — | draft |
| US-LED-012 | ledger | EP-LED-04 | W5 | S57, S56 | BR-LED-003,005,015 + BR-TEN-022,BR-TEN-038 | — | 7 | — | — | — | draft |
| US-LED-013 | ledger | EP-LED-04 | W5 | S56, S57 | BR-LED-003,012,015 | — | 7 | — | — | — | draft |
| US-LED-014 | ledger | EP-LED-05 | W5 | S41 | BR-LED-002,007,013,015 + BR-REP-003 | — (filing confirmation/receipt columns = pack report L-4, candidate) | 8 | — | — | — | draft |
| US-LED-015 | ledger | EP-LED-05 | W5 | S42, S36 | BR-LED-006,015 + BR-TEN-022,023,038 | — (checklist hard-block question = pack report L-3) | 7 | — | — | — | draft |
| US-LED-016 | ledger | EP-LED-05 | W5 | S42, S43 | BR-LED-004,014,015 + BR-REP-005 | — (S43 weekly/email/lock-after-send prototype-only = pack report L-1/L-2/L-3; live ERP connections = L-5 seam) | 7 | — | — | — | draft |
| US-NOT-001 | notifications | EP-NOT-01 | W3 | S8, S30, S35 | BR-NOT-005 + BR-BIL-016 | — | 6 | — | — | — | draft |
| US-NOT-002 | notifications | EP-NOT-01 | W3 | S8, S30 | BR-NOT-005 + BR-BIL-016 | — | 7 | — | — | — | draft |
| US-NOT-003 | notifications | EP-NOT-01 | W3 | S8 | BR-NOT-005 + BR-BIL-016,BR-PAY-017 | — (OQ-073, OQ-074 CLOSED — email dispatch W6 · SMS v1.1) | 7 | — | — | — | draft |
| US-NOT-004 | notifications | EP-NOT-01 | W3 | S8 | BR-NOT-005 + BR-TEN-041 | — | 7 | — | — | — | draft |
| US-NOT-005 | notifications | EP-NOT-02 | W3 | S8 | BR-BIL-026 + BR-TEN-017 | — | 7 | — | — | — | draft |
| US-NOT-006 | notifications | EP-NOT-02 | W3 | S8, S67 | BR-NOT-002 + BR-BIL-025,026,027 | — | 7 | — | — | — | draft |
| US-NOT-007 | notifications | EP-NOT-02 | W3 | S8, S94, S95, S96 | BR-CUS-039 + BR-REP-016,BR-BIL-027 | — | 7 | — | — | — | draft |
| US-NOT-008 | notifications | EP-NOT-02 | W3 | S8, S97–S102, S103–S106 | BR-BIL-026 + BR-CUS-039 | — | 8 | — | — | — | draft |
| US-NOT-009 | notifications | EP-NOT-03 | W4 | S94, S22, S34, S35 | BR-CUS-039 + BR-PAY-017,BR-NOT-005 | — | 7 | — | — | — | draft |
| US-NOT-010 | notifications | EP-NOT-03 | W4 | S95, S34, S35 | BR-PAY-035,BR-PAY-017 + BR-REP-016,BR-NOT-005 | — (firm-tone body precision = pack report N-2, candidate) | 7 | — | — | — | draft |
| US-NOT-011 | notifications | EP-NOT-03 | W4 | S96, S33, S35 | BR-PAY-024,BR-PAY-016 + BR-NOT-005 | — (plan-notice body = pack report N-1, candidate) | 7 | — | — | — | draft |
| US-NOT-012 | notifications | EP-NOT-03 | W4 | S67, S24 | BR-NOT-001,002,003,004 + BR-CUS-044 | — | 7 | — | — | — | draft |
| US-NOT-013 | notifications | EP-NOT-04 | W4 | S8, S30 | BR-NOT-005 + BR-TEN-041 | — | 6 | — | — | — | draft |
| US-NOT-014 | notifications | EP-NOT-04 | W4 | S8, S30, S35 | BR-PAY-018 + BR-NOT-005 | — | 7 | — | — | — | draft |
| US-NOT-015 | notifications | EP-NOT-04 | W5 | S8, S45, S43 | BR-REP-007,BR-REP-017 + BR-LED-020,BR-NOT-005 | — | 7 | — | — | — | draft |
| US-REP-001 | reports | EP-REP-01 | W5 | S44 | BR-REP-002,006,007 | — (generic-viewer column sets = pack report R-2, candidates) | 6 | — | — | — | draft |
| US-REP-002 | reports | EP-REP-01 | W5 | S46 | BR-REP-001,002,006 + BR-CUS-055 | — | 7 | — | — | — | draft |
| US-REP-003 | reports | EP-REP-01 | W5 | S46 | BR-REP-001,018 + BR-SHL-016 | — | 7 | — | — | — | draft |
| US-REP-004 | reports | EP-REP-01 | W5 | S45 | BR-REP-002,017,018 | — (report_runs schema anchor = pack report R-1, candidate) | 6 | — | — | — | draft |
| US-REP-005 | reports | EP-REP-02 | W5 | S46 | BR-REP-001,008,011 + BR-CUS-048,BR-PAY-032 | — | 7 | GT-16 | — | — | draft |
| US-REP-006 | reports | EP-REP-02 | W5 | S46 | BR-REP-001,006 + BR-BIL-018,019 | — | 7 | — | — | — | draft |
| US-REP-007 | reports | EP-REP-02 | W5 | S46 | BR-REP-001,013,014 + BR-PAY-012,015,021 | — | 7 | — | — | — | draft |
| US-REP-008 | reports | EP-REP-02 | W5 | S46 | BR-REP-006,012 + BR-MET-020,021,049,BR-CUS-055 | — | 7 | — | — | — | draft |
| US-REP-009 | reports | EP-REP-02 | W5 | S46 | BR-REP-001,007 + BR-BIL-014,016,017,BR-PAY-018,020,BR-NOT-005 | — | 8 | — | — | — | draft |
| US-REP-010 | reports | EP-REP-03 | W5 | S47 | BR-REP-006,007 + BR-PAY-021 | — | 6 | — | — | — | draft |
| US-REP-011 | reports | EP-REP-03 | W5 | S47, S46 | BR-REP-001,006 + BR-CUS-016,BR-PAY-021 | — | 7 | — | — | — | draft |
| US-REP-012 | reports | EP-REP-03 | W5 | S47, S44, S45 | BR-REP-002,018 + BR-SHL-016 | — (saved-definition visibility = pack report R-3, candidate) | 6 | — | — | — | draft |
| US-REP-013 | reports | EP-REP-04 | W5 | S45 | BR-REP-017,018 | — (external recipients = pack report R-6, candidate — W6 concern) | 6 | — | — | — | draft |
| US-REP-014 | reports | EP-REP-04 | W5 | S45 | BR-REP-001,002,018 | — | 7 | — | — | — | draft |
| US-REP-015 | reports | EP-REP-04 | W5 | S45 | BR-REP-007,017 + BR-NOT-005 | — | 6 | — | — | — | draft |
| US-REP-016 | reports | EP-REP-05 | W5 | S7 | BR-REP-001,002,009,010,011,012 | — (forecast line = pack report R-9, candidate) | 7 | — | — | — | draft |
| US-REP-017 | reports | EP-REP-05 | W5 | S7, S32 | BR-REP-015 + BR-BIL-014,015,BR-PAY-018,BR-LED-007,BR-NOT-005 | — | 7 | — | — | — | draft |
| US-REP-018 | reports | EP-REP-05 | W5 | S32 | BR-REP-001,010,011,014,016 + BR-PAY-017 | — | 6 | — | — | — | draft |
| US-REP-019 | reports | EP-REP-05 | W5 | S7 | BR-REP-001,002,012,024 + BR-SHL-001,011,012,020,023,044,BR-TEN-022 | OQ-220, OQ-221, OQ-222 (greeting wording · cycle countdown · To-do counts — all non-blocking) | 10 | — | 06-backend/apps/reports/dashboard.py, 07-frontend/src/features/reports/DashboardPage.tsx | — | ready |
| US-AUD-001 | audit | EP-AUD-01 | W0 | S61 | BR-AUD-002,007,012,015 | — (closed-tenant/SC-7 disposition OPEN — cited only) | 7 | — | — | — | draft |
| US-AUD-002 | audit | EP-AUD-01 | W0 | S61 | BR-AUD-003,004,005,006 | — (event-code extensibility + Source anchoring = pack report AUD-D1/D2, candidates) | 8 | — | — | — | draft |
| US-AUD-003 | audit | EP-AUD-01 | W0 | S61 | BR-AUD-001,008,011 + BR-TEN-038 | — (write-guarantee mechanics Eng-Lead 🔒) | 8 | — | — | — | draft |
| US-AUD-004 | audit | EP-AUD-02 | W1 | S61, S8 | BR-AUD-002,007,009,013 | — (Source column render = AUD-D2, candidate) | 8 | — | — | — | draft |
| US-AUD-005 | audit | EP-AUD-02 | W1 | S61, S21, S50 | BR-AUD-006,009,010 | — | 8 | — | — | — | draft |
| US-AUD-006 | audit | EP-AUD-02 | W1 | S61, S29 | BR-AUD-001,014,016 | — | 8 | — | — | — | draft |
| US-AUD-007 | audit | EP-AUD-03 | W5 | S61 | BR-AUD-002,012,015 | — (SC-7/closed-tenant config seam only) | 7 | — | — | — | draft |
| US-AUD-008 | audit | EP-AUD-03 | W5 | S61 | BR-AUD-002,007,013 | — | 7 | — | — | — | draft |
| US-AUD-009 | audit | EP-AUD-03 | W5 | S61, S44 | BR-AUD-007,014,017 | — (bespoke columns = reports R-2, candidate) | 8 | — | — | — | draft |
| US-INT-001 | integrations | EP-INT-01 | W4 | S8 | BR-INT-001,002,004 | — (Lob/DocPrint matrix placement = pack report I-1, candidate) | 7 | — | — | — | draft |
| US-INT-002 | integrations | EP-INT-01 | W4 | S8 | BR-INT-002,003,004,015 | — (connections schema anchor = pack report I-2, Eng batch) | 7 | — | — | — | draft |
| US-INT-003 | integrations | EP-INT-01 | W4 | S8 | BR-INT-016,003 + BR-NOT-005 | — | 7 | — | — | — | draft |
| US-INT-004 | integrations | EP-INT-01 | W4 | S8 | BR-INT-014,008,003 | — | 7 | — | — | — | draft |
| US-INT-005 | integrations | EP-INT-02 | W5 | S8 | BR-INT-005,007,003 | — (OQ-073 CLOSED — sending W6; test-email recipient = I-6, cosmetic) | 7 | — | — | — | draft |
| US-INT-006 | integrations | EP-INT-02 | W5 | S8 | BR-INT-006,004,003 | — (OQ-074 CLOSED — ESP as tenant integration) | 7 | — | — | — | draft |
| US-INT-007 | integrations | EP-INT-02 | W5 | S8 | BR-INT-008,006,007,015 + BR-NOT-005 | — | 7 | — | — | — | draft |
| US-INT-008 | integrations | EP-INT-03 | W4 | S8, S35, S38 | BR-INT-009,004,003 + BR-PAY-019,023 | — (SFTP pull execution = I-8, provision; registry anchor = payments P-10) | 8 | — | — | — | draft |
| US-INT-009 | integrations | EP-INT-03 | W5 | S8, S42, S43 | BR-INT-010,004 + BR-LED-004,014,020 | — | 7 | — | — | — | draft |
| US-INT-010 | integrations | EP-INT-03 | W5 | S8 | BR-INT-009,010,014,015 | — | 7 | — | — | — | draft |
| US-INT-011 | integrations | EP-INT-04 | W7 | S8 | BR-INT-001,011,003 | — (OQ-015 CLOSED — deferral is roadmap, not a question) | 6 | — | — | — | deferred |
| US-INT-012 | integrations | EP-INT-04 | v1.1/v2 | S8 | BR-INT-001,012,013,010,003 | — (waves per CL-1; NFR-27 gate at MDM enablement) | 7 | — | — | — | deferred |

## Addendum — CR-004 reference lists (2026-08-16): six new screens, NO new stories

The six lists landed in commit `4b02f48` are ordinary lists on the one
reference-data surface, so **CRUD is inherited, not re-specified**: CR-004 states
*"A new list inherits all three and does not need its own CRUD story."* No
US-ID is minted here. The three rows below RESTATE US-TEN-009/010/011 with their
CR-004 scope added — the parent rows above are unchanged and stay canonical for
everything that is not CR-004.

**Screens added by CR-004:** S75 areas · S76 utility service size classes
(`meter_size_classes` until BR-TEN-170 renamed it 2026-08-27) · S77 occupancy
statuses · S78 device types (BTM) · S79 certification types · S80 import mappings
(A1 addendum 2026-08-16). **Rules added:** BR-MET-066..070 (metering-owned) and
BR-LED-043 (import mappings). **The four Work cards carry NO US-ID, NO S-ID and
NO BR-ID** — they are declared placeholders and OQ-249 is OPEN.

| US-ID | Module | Epic | Wave | Screens | BR-IDs | OQ blocks | TCs | GTs | Code refs | UAT | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| US-TEN-009 (CR-004 scope) | tenancy | EP-TEN-07 | W0 | S8, S75, S76, S77, S78, S79, S80 | BR-TEN-029,031,033,036 + BR-MET-066,067,068,069,070 + BR-LED-043 | — (OQ-249 blocks the four Work cards only, which ship as placeholders) | 6 | — | 07-frontend/src/features/tenancy/referenceDataConfig.ts (six REFERENCE_CARDS rows), 06-backend/apps/tenancy/models.py (Area, MeterSizeClass, OccupancyStatus, DeviceType, CertificationType, ImportMapping), apps/tenancy/migrations/0010_area_certificationtype_devicetype_importmapping_and_more.py | — | built (cards render from the registry; browser click-through outstanding per CR-004's stated bar) |
| US-TEN-010 (CR-004 scope) | tenancy | EP-TEN-07 | W0 | S8, S75, S76, S77, S78, S79, S80 | BR-TEN-016,028,030,031,032,036 + BR-MET-066,067,068,069,070 + BR-LED-043 | — (OQ-031, OQ-032 are the 4 enum-backed lists, none of them these) | 7 | — | 06-backend/apps/tenancy/services.py (six HostedFlatLookupHandler registrations + SEED_LIST_OWNERS), apps/tenancy/fixtures/lookup_defaults.json (28 seeded entries; import_mappings deliberately empty) | — | built (backend handlers + seed; browser add/edit proof outstanding) |
| US-TEN-011 (CR-004 scope) | tenancy | EP-TEN-07 | W0 | S8, S75, S76, S77, S78, S79, S80 | BR-TEN-016,029,034,036 + BR-MET-066,067,068,069,070 + BR-LED-043 | — | 6 | — | 06-backend/apps/tenancy/services.py (shared deactivate/delete path; audit-lock unchanged), 06-backend/db/rls_tenancy_cr004_reference_lists.sql (HUMAN-REVIEW-PENDING) | — | built (shared path, no new code); browser deactivate/delete proof outstanding |
