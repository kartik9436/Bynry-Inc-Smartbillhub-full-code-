# ── Trace ──────────────────────────────────────────────
# Journey:  J72 § E11 — the bulk bill run beside its D1 drawings (wave 2, 2026-10-01)
# Defect:   DEF-BIL-8700 — the unit shown twice on every Check row, Fix account
#           and the Not in this run lists
# Drawing:  05-prototype/bulk-bill-run-2026-09-30/14 ("1487 Hill Dr · Unit A"),
#           22 ("Sara Cohen · 1589 Pine Ct · Unit A")
# ───────────────────────────────────────────────────────
"""`display_for` names the street as `address` and the unit as `unit_label`.

customers' premise cell is `(unit label, "street · unit label")` — the unit
column's word first, the premise column's line second. `display_for` unpacked
it as `(address, unit_label)`, so the screen got `address="Unit 105"` and
`unit_label="2200 Riverside Dr · Unit 105"` and printed the unit twice. Every
DOM fixture served the pair with the meaning its names say, so only the live
seed showed it.
"""

from __future__ import annotations

from apps.billing import check_store, gather


class _Account:
    def __init__(self, pk: str) -> None:
        self.pk = pk


class _QS:
    def filter(self, **_: object) -> list[_Account]:
        return [_Account("a1"), _Account("a2")]


def _fake_resolve(module: str, attribute: str, kind: str = "selectors"):
    if attribute == "primary_contact_names_for":
        return lambda ids: {"a1": "Grace Okafor", "a2": "Owner Co"}
    if attribute == "account_queryset":
        return lambda: _QS()
    if attribute == "premise_cells_for":
        # Exactly customers' shape: a unit account, and an owner's account with no unit.
        return lambda accounts: {
            "a1": ("Unit 105", "2200 Riverside Dr · Unit 105"),
            "a2": (None, "2200 Riverside Dr"),
        }
    return None


def test_display_for_serves_the_street_and_the_unit_once_each(monkeypatch):
    monkeypatch.setattr(gather, "_resolve", _fake_resolve)
    shown = check_store.display_for(["a1", "a2"])
    assert shown["a1"] == {
        "customer_name": "Grace Okafor",
        "address": "2200 Riverside Dr",
        "unit_label": "Unit 105",
    }
    assert shown["a2"] == {"customer_name": "Owner Co", "address": "2200 Riverside Dr", "unit_label": None}
