# Module — assets (product name: Assets)

Registry + lifecycle for meter-to-cash assets ONLY (ADR-004): meters, sub-meters, net meters, and customer-premise behind-the-meter devices that can affect a bill (PV, battery, EV charger, backflow, comms endpoint). Grid/network infrastructure is out of scope — this is not an EAM.
**Tables:** owned by metering (B2 r4 `assets` table) — this module is a docs + frontend feature surface. **Screens:** S49–S55 (provisional, OQ-014) + net-meter read channels.
**Lifecycle (A5 v4):** Inventory/Spare → Installed/Active → Needs repair → In repair → Active | Retired (terminal). Assets referenced by issued bills are audit-locked — retire, never hard-delete.
**Epics:** EP-AST-01…05 (waves 1–2).
