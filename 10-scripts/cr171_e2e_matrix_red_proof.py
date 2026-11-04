"""CR-171-BRC10 P4 matrix — lane MVI-E2E-3 red proofs (law 7): break ONE expectation in memory, run the readback against the
case's committed database, print the check that goes red; then run it unbroken and print it green.

    red_proof.py <case> <move_no> <proof-name>
"""
import copy
import importlib.util
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "06-backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sjf = load("sjf", REPO / "08-qa/01-e2e/stack/seed_journey_fixture.py")
sjf.django_setup()
rb = load("rb", REPO / "10-scripts/cr171_e2e_matrix_readback.py")
world = load("cr171_e2e_matrix_world", REPO / "10-scripts/cr171_e2e_matrix_world.py")

case, move, proof = sys.argv[1], sys.argv[2], sys.argv[3]


def run(kind, **kw):
    if kind == "main":
        return rb.readback(world, case, move)["checks"]
    if kind == "cancel":
        return rb.after_cancel(world, case, move)["checks"]
    if kind == "date":
        return rb.after_date(world, case, move, kw.get("was", ""))["checks"]
    if kind == "requests":
        return rb.requests_readback(world)["checks"]


# proof name -> (readback kind, mutation of EXPECT[case] or of world, the check's name fragment, kwargs)
def mutate(e):
    if proof == "m6-deposit":
        e["fees"] = [("deposit", "DEPOSIT", "450.0000"), ("fee", "CONN", "25.0000")]
        return "main", "the fee lines are the plan's deposit", {}
    if proof == "m6-city-tax":
        e["taxes_present"] = e["taxes_present"] + ["City of Cedar Ford utility tax"]
        e["taxes_absent"] = []
        return "main", "City of Cedar Ford utility tax", {}
    if proof == "m6-inverter":
        e["devices"] = {"PV-M6": "W-M6"}
        return "main", "PV-M6 still stands under", {}
    if proof == "m7-exemption":
        e["taxes_present"] = e["taxes_present"] + ["City of Cedar Ford utility tax"]
        e["taxes_absent"] = ["TX State Utility Tax"]
        return "main", "City of Cedar Ford utility tax", {}
    if proof == "m7-po":
        e["po_number"] = "PO-2026-119"
        return "main", "the account carries PO", {}
    if proof == "m7-trash":
        e["trash"] = {"count": 3, "amount": "60.00"}
        return "main", "trash is priced for", {}
    if proof == "p24-unit-vacant":
        return "cancel", "the unit holds no open account", {}
    if proof == "p24-reads-kept":
        e["opening_reads"] = {}
        return "cancel", "opening reads are KEPT", {}
    if proof == "p25-new-date":
        e["change_date"] = {"to": "2026-10-16"}
        return "date", "the account now opens on", {}
    if proof == "p25-proration":
        return "date", "prorated base charges move", {"was": os.environ.get("NOW_BASE", "")}
    if proof == "p26-decline":
        return "requests", "is Declined", {}
    if proof == "p26-job":
        return "requests", "ONE move-in job, done by Complete", {}
    raise SystemExit(f"unknown proof {proof}")


rb.EXPECT.setdefault(case, {})  # P26 reads the world's requests, not an EXPECT row
original = copy.deepcopy(rb.EXPECT[case])
kind, fragment, kw = mutate(rb.EXPECT[case])
P26_WANT = {"p26-decline": ("is Declined (refused)", "more_info"), "p26-job": ("ONE move-in job", ["pending"]),
            "p24-unit-vacant": ("the unit holds no open account", 1)}
rb_eq = rb.Checks.eq
if proof in P26_WANT:
    frag, wrong = P26_WANT[proof]

    def eq(self, module, name, actual, expected):
        rb_eq(self, module, name, actual, wrong if frag in name else expected)
    rb.Checks.eq = eq
broken = [r for r in run(kind, **kw) if fragment in r["name"]]
print(f"BROKEN ({proof}):")
for r in broken:
    print(f"  {'PASS' if r['pass'] else 'FAIL'}  {r['name']} — {r['detail']}")
rb.EXPECT[case] = original
rb.Checks.eq = rb_eq
restored = [r for r in run(kind, **({"was": os.environ.get("WAS_BASE", "")} if proof == "p25-proration" else {}))
            if fragment in r["name"]]
print("RESTORED:")
for r in restored:
    print(f"  {'PASS' if r['pass'] else 'FAIL'}  {r['name']}{'' if r['pass'] else ' — ' + r['detail']}")
