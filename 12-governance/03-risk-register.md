# Risk Register
| ID | Risk | Likelihood | Impact | Owner | Mitigation | Trend |
|---|---|---|---|---|---|---|
| R-001 | Billing math built on unconfirmed rules (A17 #1/#3, B4 placeholders) → silent money errors | High if unmanaged | Critical | PM | Engine stays stubbed until finance signs B4/B5; golden tests xfail-gated | flat |
| R-002 | Tenant-isolation defect ships | Low | Critical | Eng Lead | RLS FORCE + isolation suite as release gate + CODEOWNERS | flat |
| R-003 | Spec/prototype drift as design iterates | Medium | Medium | PM | 04-docs/CHANGELOG re-export procedure; weekly drift check | improving |
| R-004 | Single-maintainer bus factor on 🔒 files | Medium | High | Eng Lead | decisions documented in ADRs; profiles in 04-docs/roles | flat |
| R-005 | Hosting decision delayed blocks first deploy | Medium | Medium | PM | decision logged as due; 09-infra/README lists requirements | flat |
| R-006 | Subscription (Bynry) invoices leak into customer billing surfaces | Low | High | Eng Lead | B10 separation: platform tables, no FKs, separate number series; trace/CI assert | flat |
