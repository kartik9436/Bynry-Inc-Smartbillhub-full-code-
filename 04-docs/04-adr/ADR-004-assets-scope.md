# ADR-004 — Assets = meter-to-cash assets only
- **Status:** Accepted (Product Owner, 2026-08-08) · **Deciders:** Product Owner
## Context
v4 adds an Assets module (meters/sub-meters/behind-the-meter). Risk of scope-creep into enterprise asset management.
## Decision
An asset exists here only if it can be assigned to a Unit and can affect a bill: revenue-metering chain + customer-premise BTM devices. Grid/network infrastructure, fleet, tools are OUT. Metering module owns the tables (B2 r4); assets is a docs folder + frontend feature.
## Consequences
No work orders/EAM features beyond the repair/retire lifecycle shown in design; transformer/generator only when customer-premise.
