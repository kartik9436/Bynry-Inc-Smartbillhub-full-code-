# SOC 2 / NIST / PII — Control Mapping (PO-directed sweep, 2026-08-08)

> Maps the ratified rule corpus to SOC 2 Trust Services Criteria + NIST CSF/800-63 + US-state privacy expectations. Status: **COVERED** (rule exists, cited) · **RECORDED TODAY** (standard control, no decision needed, written by this sweep) · **SC-#** (genuine choice → PO battery). Reference maths/examples: B6 capacity math · WE/PE/LE workbooks · GT-17..61.

## 1. Access control (SOC 2 CC6 · NIST PR.AC)
| Control | Status | Citation |
|---|---|---|
| Tenant isolation | COVERED | RLS FORCE + server-side GUC (NFR-10); zero-tolerance suite = release blocker |
| Least privilege / RBAC | COVERED | 3 platform roles, server-enforced, read-only matrix (BR-IDN-008/009/014) |
| Per-tenant identity, no cross-tenant SSO | COVERED | BR-IDN-029, B2 r11 |
| Password policy (NIST 800-63 aligned) | COVERED | BR-IDN-025 (no forced expiry, history block, lockout 5→15min) |
| Session management | COVERED | BR-IDN-026 (60m/12h/30d), server-side revocation |
| IP allowlisting w/ self-lockout guard | COVERED | BR-IDN-020 |
| MFA | **PO-ruled v2 stands (SC-1 CONFIRMED 2026-08-08)** — compensating controls §6 | COVERED |
| Periodic access reviews | COVERED (SC-2 CONFIRMED): quarterly access-review report v1 (users, roles, last sign-in, exportable per IS-11) | reports/identity packs |
| Last-admin protection | COVERED | BR-IDN-013 |

## 2. Data protection (CC6.1/6.7 · PR.DS)
| Control | Status | Citation |
|---|---|---|
| Encryption at rest | COVERED | OQ-016 closure: app-layer for high-sensitivity (EIN, TOTP, gov-ID tokenized), disk for rest (NFR-13) |
| Encryption in transit | RECORDED TODAY → **NFR-31**: TLS 1.2+ everywhere (app, DB, provider adapters); no plaintext listener anywhere | this doc |
| PII masking on display | COVERED | BR-CUS-045 (masked always; last-4 patterns) |
| PII inventory / data map | RECORDED TODAY | pii-inventory.md (full column register) |
| Payment data | COVERED by scope | no card storage v1 (capture-intent only, BR-PAY-015); rails W7 = PCI scope decision then |

## 3. Integrity & auditability (CC7 · PR.PT/DE.CM)
| Control | Status | Citation |
|---|---|---|
| Append-only financial records + balanced ledger | COVERED | NFR-15/17, hard rules 3–5 |
| Complete audit trail on money + CRUD | COVERED | hard rule 7, audit pack (wave), NFR-28 retention |
| Security-event logging | COVERED (SC-3 CONFIRMED): logged v1 (S61 auth class); alerting = ops config | BR-AUD-004 |
| Idempotency / no double-processing | COVERED | NFR-16 |
| Change management | COVERED | CODEOWNERS human-owned paths, migration-guard + trace-lint + security-scan CI, 11-change-management |
| Vulnerability management | COVERED: continuous dep-scanning CI + ANNUAL pen test + before major releases (SC-4 CONFIRMED) | security-scan.yml |

## 4. Availability & resilience (A1 · PR.IP/RC)
| Control | Status | Citation |
|---|---|---|
| Backups + PITR, RPO 1h / RTO 4h | COVERED (planning) | B6 table |
| Restore verification | COVERED (SC-5 CONFIRMED): QUARTERLY automated restore test | ops runbook |
| Capacity planning | COVERED | B6 capacity math (2.7B rows/3yr), NFR-24..30 |
| Incident response | COVERED (SC-6 CONFIRMED): state-law-driven notification w/ 72h INTERNAL assessment target | incident.md |

## 5. Privacy (P-series · US state privacy)
| Control | Status | Citation |
|---|---|---|
| Data residency US | COVERED | B6 |
| Retention schedule | COVERED | NFR-6..9, data-retention.md |
| Closed-account PII retention | COVERED (SC-7 CONFIRMED 2026-08-08): retained 7yr with the financial records, masked display | BR-CUS-065 |
| Customer data rights | COVERED (SC-8 CONFIRMED): documented staff process v1 (export via account ledger; deletion = anonymize non-financial PII after retention); self-serve v2 | this doc |
| Subprocessor register | RECORDED TODAY: ESP, Twilio (v1.1), print vendor, hosting, e-sign provider — register kept in audit-and-controls.md; contracts/DPAs = ops | — |
| No sale/secondary use of customer data | RECORDED TODAY → NFR-32: tenant customer data is used ONLY to operate the tenant's service | this doc |

## 6. Compensating controls while MFA is v2 (auditor note)
IP allowlist per tenant · lockout 5→15min · sessions 60m idle/12h absolute, server-revocable · admin-only user management + last-admin guard · per-tenant identity (no shared credentials across tenants) · full auth audit. Documented for SOC 2 scoping conversations; MFA lands v2 (PO ruling stands).

## SC battery — see decision log / PO chat for closure
ALL CLOSED 2026-08-08: SC-1..8, every item per recommendation (SC-7 confirmed in the final round). The SC battery is complete; this mapping carries no open items.
