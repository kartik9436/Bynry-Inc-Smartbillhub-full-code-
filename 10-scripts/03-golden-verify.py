#!/usr/bin/env python3
"""Golden-figure verification harness (finance-freeze sitting, 2026-08-08).

TWO ranges, two different kinds of check, plus a self-test. Read this before
trusting a green run.

PART 1 — workbook composites GT-17..GT-61 (+ GT-61 deposit interest).
    Independently RECOMPUTES every documented workbook figure (WE/PE/LE) from raw
    fixture inputs using ONLY the ratified rules (B4: half-up 2dp per line at
    finalization; BR-PAY-010 allocation; BR-CUS-043 remainder-on-final; etc.) and
    asserts equality with the values recorded in the workbooks. 33 checks.

PART 2 — legacy unit fixtures GT-1..GT-16 (added 2026-08-10, DEF-028).
    These are prose fixtures inside 04-docs/02-decisions/05-golden-tests.md, not
    workbook composites; there is no raw-input workbook to recompute them from.
    So this part parses the frozen figures OUT OF THAT DOCUMENT and checks them
    for INTERNAL ARITHMETIC CONSISTENCY: do the components B5 states actually
    produce the total B5 states? Until 2026-08-10 nothing had ever run that check
    on this range, which is exactly how DEF-028 (GT-10's total, off by $1.00
    against its own addends) survived a finance signature while this harness
    reported 33/33 PASS. DEF-028 is now closed by a PO/finance re-sign under
    HUMAN-GUIDE §6; Part 2 is the durable fix that stops the next one.
    A GT that does not state enough to check is reported NOT-CHECKABLE with the
    reason. It is NEVER reported as a pass — a verifier that counts unverifiable
    lines as green is worse than one that does not look (CLAUDE.md law 1).

PART 0 — self-test (CLAUDE.md law 7: prove a new guard goes RED).
    Because DEF-028 is now fixed in the document, a green Part 2 no longer proves
    Part 2 works. So every run first replays the defect: it takes the live B5
    text IN MEMORY, reverts GT-10's total to the pre-re-sign 116.01, and requires
    the checker to report GT-10 FAIL. Three more mutations exercise the other
    guard paths. If any fixture fails to go red, this script exits 1 — the guard
    cannot silently stop biting. Nothing is written to disk at any point.

THIS SCRIPT VERIFIES. IT NEVER EDITS. 04-docs/** is opened read-only and no
figure is ever "corrected" here: B4/B5 are ❄️ FROZEN and changing a signed figure
needs a finance re-sign via HUMAN-GUIDE §6, never an inline edit (and never an
implementer's edit). Discrepancies are REPORTED and routed, not resolved.

This verifies the DOCUMENTED expected values. It is QA scaffolding — it is not
the rating engine (human-owned 🔒) and must never be imported by it.

Run: python3 10-scripts/03-golden-verify.py
    exit 0  — every check passed, or the only failures are the exactly-specified
              known/logged defects in KNOWN_DEFECTS below (empty today; each
              entry, if any, is still printed loudly on every run).
    exit 1  — any workbook mismatch, any NEW Part 2 failure, any known failure
              whose numbers have CHANGED, any stale waiver, or any self-test
              fixture that failed to go red.
    --strict — ignore the waivers; exit 1 on any failure at all. Use this at a
              finance sitting, where "known defect" is the agenda item.
"""
import re
import sys
from decimal import Decimal as D, ROUND_HALF_UP
from pathlib import Path

def r2(x):
    return D(x).quantize(D("0.01"), ROUND_HALF_UP)

TAX = [D("0.0625"), D("0.01"), D("0.02"), D("0.002")]  # State/County/City/PUC
def tax_lines(base):
    return [r2(base * t) for t in TAX]

PASS, FAIL = [], []
def check(name, got, want):
    (PASS if str(got) == str(want) else FAIL).append(f"{name}: got {got}, want {want}")

# ═══════════════════════════════════════════════════════════════════════════
# PART 1 — workbook composites GT-17..GT-61. UNCHANGED (33 checks, 33 PASS).
# Do not alter what these verify; they are the figures finance signed on
# 2026-08-08 and every one is recomputed from raw inputs, not parsed.
# ═══════════════════════════════════════════════════════════════════════════

# ── CR-081 · SEWER IS A PERCENTAGE OF THE WATER **VOLUME** FROM 2026-09-08 ──
# ❄️ RE-SIGNED by the Product Owner as finance authority under HUMAN-GUIDE §6
# (decision log 2026-09-08, "THE PO RE-SIGNS SIX FROZEN SEWER FIGURES"),
# verbatim: *"C — factor 90%, rate $5.00 → $36.00, which is what a real sewer
# customer actually pays"*. Six sewer amounts move across five worked examples
# and every taxable subtotal, tax split and total on those five moves with them.
#
# ⚠ IT READ `r2(D("0.40") * sum(water))` — 40% of the water MONEY — IN FIVE
# PLACES UNTIL THAT DATE. The 40 was a PRICE RATIO; the 90 is a RETURN-TO-SEWER
# FACTOR, the share of metered water that physically reaches the sewer. The
# helper below is named for that so the two cannot be confused again.
#
# ⚠ **WE-6 (GT-22) IS DELIBERATELY NOT CONVERTED — SEE PART 4.** It carries a
# SEVENTH sewer figure that the re-sign did not cover, and a figure nobody
# signed is not moved here.
RETURN_TO_SEWER = D("0.90")          # CR-081 — the factor
SEWER_RATE = D("5.00")               # CR-081 — sewer's own rate per water's unit
def sewer_on(kgal):
    """90% of the metered water VOLUME, at sewer's own rate. UNROUNDED × price,
    finalized once — B4's per-line half-up 2dp, exactly as every other line."""
    return r2(RETURN_TO_SEWER * D(kgal) * SEWER_RATE)

# --- WE-1 reference bill (GT-17)
usage = [r2(D(q) * D(p)) for q, p in [("120", "0.22"), ("200", "0.14"), ("380", "0.09")]]
water = [r2(D("5") * D("4.00")), r2(D("3") * D("6.50"))]
sewer = sewer_on("8")                # 7.2 kgal x $5.00 = 36.00 (was 15.80)
taxable = sum(usage) + D("12.00") + sum(water) + D("8.00") + sewer + D("18.00") + D("40.00")
t = tax_lines(taxable)
current = taxable + sum(t) + D("5.00")
check("WE-1 taxable", taxable, "242.10"); check("WE-1 tax", sum(t), "22.87")
check("WE-1 current", current, "269.97"); check("WE-1 total", current + D("45.00"), "314.97")
# --- WE-2 exempt (GT-18). NOT a seventh signed figure: it is WE-1's own taxable
# subtotal with the tax lines removed, and that subtotal is explicitly re-signed.
check("WE-2 total", taxable + D("5.00") + D("45.00"), "292.10")
# --- WE-3 minimum bill (GT-19)
u3 = r2(D("0.4") * 4); adj = D("15.00") - u3 - D("8.00")
check("WE-3 adj", adj, "5.40"); check("WE-3 total", D("15.00") + sum(tax_lines(D("15.00"))), "16.42")
# --- WE-6 first bill (GT-22)
pro = lambda x: r2(D(x) * 20 / 31)
t1 = D("5") * 20 / 31
w6 = [r2(t1 * 4), r2((D("4.2") - t1) * D("6.50"))]
e6 = [r2(D(q) * D(p)) for q, p in [("70", "0.22"), ("120", "0.14"), ("210", "0.09")]]
tb6 = sum(e6) + pro("12.00") + sum(w6) + pro("8.00") + r2(D("0.40") * sum(w6)) + pro("18.00")
check("WE-6 taxable", tb6, "102.53")
check("WE-6 total", tb6 + sum(tax_lines(tb6)) + D("150") + D("25"), "287.23")
# --- WE-7 final-bill settlement (GT-23)
interest = r2(D("150") * D("0.02") * 14 / 12)
check("WE-7 interest", interest, "3.50")
check("WE-7 refund", D("150") + interest - D("142.30"), "11.20")
check("WE-7 due", D("289.40") - (D("150") + interest), "135.90")
# --- WE-9 correction (GT-25)
w9 = D("20.00") + r2(D("1") * D("6.50")); s9 = sewer_on("6")   # 5.4 x 5.00 = 27.00
tb9 = sum(usage) + D("12.00") + w9 + D("8.00") + s9 + D("18.00") + D("40.00")
new9 = tb9 + sum(tax_lines(tb9)) + D("5.00")
check("WE-9 rebill", new9, "245.90"); check("WE-9 credit", current - new9, "24.07")
# --- WE-10 back-bill across versions (GT-26)
p1 = D("26.50") + D("8.00") + sewer_on("6")      # Jan-Mar, tariff v3: 27.00
m2 = r2(D("5") * D("4.25")) + r2(D("1") * D("6.85"))
p2 = m2 + D("8.50") + sewer_on("6")              # Apr-Jun, tariff v4: 27.00
# ⚠ THE TWO HALVES ARE NOW THE SAME SEWER FIGURE AND THAT IS THE RULING, NOT A
# COPY-PASTE. On the DOLLAR basis a tariff change moved the sewer line with the
# water price (10.60 -> 11.24); on the VOLUME basis the same 6 kgal is the same
# 5.4 kgal of sewer, and only a change to SEWER's own rate can move it.
tb10 = 3 * p1 + 3 * p2
check("WE-10 total", tb10 + sum(tax_lines(tb10)), "410.77")
# --- WE-11 theft (GT-27)
a11 = [r2(D(q) * D(p)) for q, p in [("150", "0.22"), ("300", "0.14"), ("450", "0.09")]]
check("WE-11 total", sum(a11) + sum(tax_lines(sum(a11))) + D("500"), "626.42")
# --- WE-12 vacation hold (GT-28)
u12 = [r2(D(q) * D(p)) for q, p in [("60", "0.22"), ("95", "0.14"), ("160", "0.09")]]
tb12 = sum(u12) + D("12") + r2(D("3.1") * 4) + D("8") + sewer_on("3.1") + D("18")
check("WE-12 total", tb12 + sum(tax_lines(tb12)), "115.20")
# --- WE-16 capacity proration (GT-31)
check("WE-16", r2(D("40.00") * 10 / 31), "12.90")
# --- PE-2/3/4 allocation (GT-36/37/38)
check("PE-2 outstanding", D("21.90") + D("20.97") + D("5.00"), "47.87")
check("PE-3 jul-left", D("247.87") - (D("300") - D("142.30")), "90.17")
check("PE-4 credit", D("350") - D("292.87"), "57.13")
# --- PE-7 NSF (GT-41)
check("PE-7 balance", D("292.87") + D("30"), "322.87")
# --- PE-10 batches (GT-44)
check("PE-10 chk", D("292.87") + D("142.30") + D("36.22"), "471.39")
check("PE-10 csh", D("105.36") + D("16.42"), "121.78")
# --- PE-13 plan schedule (GT-47)
inst = r2((D("267.30") - D("50")) / 6)
check("PE-13 inst", inst, "36.22")
check("PE-13 final", D("267.30") - D("50") - 5 * inst, "36.20")
# --- LE-1 trial balance (GT-51): full three-account month
t7b = tax_lines(D("264.41"))
check("LE-1 WE-7B decomp", D("264.41") + sum(t7b), "289.40")
cash = D("150.00") + D("292.87")
ar = D("45.00") + D("247.87") + D("16.42") + D("289.40") - D("153.50") - D("292.87")
dep = D("150.00") + D("3.50") - D("153.50")
rev = D("226.90") + D("15.00") + D("264.41")
tax_l = D("20.97") + D("1.42") + sum(t7b)
dr = cash + ar + D("3.50"); cr = rev + tax_l + D("45.00") + dep
check("LE-1 AR", ar, "152.32"); check("LE-1 dep-liab", dep, "0.00")
check("LE-1 DR", dr, "598.69"); check("LE-1 CR", cr, "598.69")
check("LE-1 AR tie-out", D("135.90") + D("16.42"), str(ar))
# --- GT-61 deposit interest
check("GT-61", r2(D("150") * D("0.02") * 89 / 12), "22.25")

WORKBOOK_PASS, WORKBOOK_FAIL = list(PASS), list(FAIL)

# ═══════════════════════════════════════════════════════════════════════════
# PART 3 — THE DISCOUNT/TAX PAIR (added 2026-08-28, DEF-652).
#
# ⚠ READ THIS BEFORE ADDING ANYTHING HERE. Part 3 is NOT part of the ❄️ FROZEN
# B4/B5 set and must never be confused with it. Parts 1 and 2 verify figures
# FINANCE SIGNED on 2026-08-08; the figure below comes from a PRODUCT OWNER
# RULING of 2026-08-27 and is recomputed here from the B4 rounding rule the same
# way part 1 recomputes a workbook. It is counted, reported and gated
# SEPARATELY so that "33 PASS" keeps meaning exactly what it meant.
#
# WHY IT EXISTS AT ALL. `03-golden-verify.py` contained the word *discount* ZERO
# times until this block, and B4/B5 are silent on discounts too. So the two
# opposite readings of "does a discount reduce the tax base" BOTH passed every
# check this repo has, for months, while the product shipped one of them and the
# PO believed the other. A harness that cannot tell those apart is the reason
# DEF-652 survived — a $1.07 error per discounted bill per cycle, on the most
# ordinary bill a small utility issues.
#
# THE RULING (PO, 2026-08-27), verbatim:
#   "Does a discount come off before or after tax? Tax the full amount before
#    discount — The utility remits tax on the full service value; the discount
#    is the utility's cost, not the tax authority's. - what does the tax law in
#    the US say - lets go with it"
# confirming an earlier "this is correct - A $62.14 bill with a 25% senior
# discount of $15.54 — is the 6.85% tax charged on $62.14 ($4.26)".
#
# In the schema that is `taxes.discount_treatment = 'after'`; `before` is the
# other lawful answer and stays available PER TAX (BR-RAT-106). Both are
# recomputed below, because a check that only knew the ruled figure could not
# tell "the rule is applied" from "the column was deleted".
# ═══════════════════════════════════════════════════════════════════════════
RULING_PASS, RULING_FAIL = [], []

def ruling_check(name, got, want):
    (RULING_PASS if str(got) == str(want) else RULING_FAIL).append(
        f"{name}: got {got}, want {want}")

# The PO's own bill, from raw inputs. Nothing here is parsed out of a document.
_SVC_VALUE = D("62.14")              # the taxable tariff amount
_SENIOR = D("0.25")                  # a 25% senior discount
_RATE = D("0.0685")                  # Silver Creek's 6.85%
_REDUCTION = r2(_SVC_VALUE * _SENIOR)                    # 15.535  -> 15.54
_FULL_BASE = _SVC_VALUE                                  # treatment 'after'
_REDUCED_BASE = _SVC_VALUE - _REDUCTION                  # treatment 'before'

ruling_check("DEF-652 reduction (B4 half-up 2dp)", _REDUCTION, "15.54")
ruling_check("DEF-652 reduced base", _REDUCED_BASE, "46.60")
# THE RULED FIGURE — the tax the utility remits on the full service value.
ruling_check("DEF-652 tax, treatment 'after' (the ruling)", r2(_FULL_BASE * _RATE), "4.26")
# The other lawful answer, still expressible per tax (BR-RAT-106). This line is
# what makes the check able to FAIL rather than merely agree with itself.
ruling_check("DEF-652 tax, treatment 'before'", r2(_REDUCED_BASE * _RATE), "3.19")
# What the defect cost, per discounted bill per cycle.
ruling_check("DEF-652 the difference",
             r2(_FULL_BASE * _RATE) - r2(_REDUCED_BASE * _RATE), "1.07")
# The two treatments MUST differ. A column collapsed to a constant, or a reader
# that ignored it, would pass every line above except this one.
ruling_check("DEF-652 the treatments are not the same figure",
             r2(_FULL_BASE * _RATE) != r2(_REDUCED_BASE * _RATE), "True")

# ═══════════════════════════════════════════════════════════════════════════
# PART 4 — THE SEWER FIGURES CR-081 MOVED THAT THE RE-SIGN DID **NOT** COVER
# (added 2026-09-08 with CR-081).
#
# ⚠ READ THIS BEFORE "FIXING" ANYTHING IT REPORTS. Part 4 is NOT part of the
# ❄️ FROZEN set and it is not a defect either. It exists because a check that
# passes over a stale figure is worse than no check (CLAUDE.md law 7), and
# because a declared blind spot with NO NUMBER attached is indistinguishable
# from an empty one.
#
# WHAT HAPPENED. The PO re-signed SIX sewer amounts on 2026-09-08 across FIVE
# worked examples — WE-1, WE-4, WE-9, WE-10 (twice) and WE-12 — and Part 1
# above now recomputes every one of them on the volume basis. **The corpus
# holds a SEVENTH sewer amount that was not in front of them:** WE-6 (GT-22),
# the first-bill proration example, whose workbook line reads *"Sewer
# 40%x19.23=7.69"*. On the ruled basis it is 90% x 4.2 kgal x $5.00 = $18.90,
# which moves WE-6's taxable from $102.53 to $113.74 and its total from
# $287.23 to $299.49.
#
# **IT IS NOT MOVED, AND THAT IS THE POINT.** A signature covers only what was
# shown (HUMAN-GUIDE §6). Part 1 therefore still recomputes WE-6 the OLD way
# and still passes — truthfully, about a figure the engine will no longer
# produce. This part is what stops that pass from being silent: it asserts the
# GAP, so the day somebody quietly converts WE-6, or the day the factor or the
# rate moves again, this goes RED and names it.
#
# THE SAME APPLIES DOWNSTREAM AND IS ASSERTED THE SAME WAY. WE-1's total is an
# INPUT to five payments examples and to the ledger trial balance (PE-2/3/4/7/
# 10 and LE-1, i.e. GT-36/37/38/41/44/51), all ❄️ FROZEN, none re-signed. Part 1
# checks those from literals copied out of their own workbooks, so they tie out
# against each other and say nothing about WE-1. The delta is stated here.
#
# BOTH ARE ON THE PO's AGENDA AS **OQ-RAT-12347**. Nothing here resolves either.
# ═══════════════════════════════════════════════════════════════════════════
UNSIGNED_PASS, UNSIGNED_FAIL = [], []

def unsigned_check(name, got, want):
    (UNSIGNED_PASS if str(got) == str(want) else UNSIGNED_FAIL).append(
        f"{name}: got {got}, want {want}")

# WE-6 (GT-22) recomputed BOTH ways from its own raw inputs — 20/31 days of a
# 31-day cycle, water 4.2 kgal across a scaled tier-1 span of 5 x 20/31.
_w6_t1 = D("5") * 20 / 31
_w6 = [r2(_w6_t1 * 4), r2((D("4.2") - _w6_t1) * D("6.50"))]
_e6 = [r2(D(q) * D(p)) for q, p in [("70", "0.22"), ("120", "0.14"), ("210", "0.09")]]
_pro = lambda x: r2(D(x) * 20 / 31)
def _we6_total(sewer_line):
    base = sum(_e6) + _pro("12.00") + sum(_w6) + _pro("8.00") + sewer_line + _pro("18.00")
    return base, base + sum(tax_lines(base)) + D("150") + D("25")

_we6_signed_base, _we6_signed_total = _we6_total(r2(D("0.40") * sum(_w6)))
_we6_ruled_base, _we6_ruled_total = _we6_total(sewer_on("4.2"))

unsigned_check("WE-6/GT-22 sewer AS SIGNED (40% of water $)", r2(D("0.40") * sum(_w6)), "7.69")
unsigned_check("WE-6/GT-22 sewer ON THE RULED BASIS (90% of 4.2 kgal @ $5.00)",
               sewer_on("4.2"), "18.90")
unsigned_check("WE-6/GT-22 taxable as signed", _we6_signed_base, "102.53")
unsigned_check("WE-6/GT-22 taxable on the ruled basis", _we6_ruled_base, "113.74")
unsigned_check("WE-6/GT-22 total as signed", _we6_signed_total, "287.23")
unsigned_check("WE-6/GT-22 total on the ruled basis", _we6_ruled_total, "299.49")
unsigned_check("WE-6/GT-22 the two bases are NOT the same figure",
               _we6_signed_total != _we6_ruled_total, "True")
# What the un-re-signed downstream would move by, stated as one number each so a
# finance sitting can see the size of the question without re-deriving it.
unsigned_check("WE-1 total moved by (292.87 -> 314.97)", D("314.97") - D("292.87"), "22.10")
unsigned_check("WE-12 total moved by (105.36 -> 115.20)", D("115.20") - D("105.36"), "9.84")

# Figures Part 1 recomputed from raw inputs, re-used by Part 2 to tie the two
# ranges together (GT-15's proration ↔ WE-16/GT-31; GT-16's opening balance ↔
# PE-13/GT-47). These are computed above from inputs, never copied out of B5.
WE16_CAPACITY_PRORATION = r2(D("40.00") * 10 / 31)   # 12.90
PE13_OPENING_BALANCE = D("267.30")                    # the balance PE-13 amortises

# ═══════════════════════════════════════════════════════════════════════════
# PART 2 — GT-1..GT-16 self-consistency, parsed from B5.
# ═══════════════════════════════════════════════════════════════════════════

REPO_ROOT = Path(__file__).resolve().parent.parent
B5_PATH = REPO_ROOT / "04-docs" / "02-decisions" / "05-golden-tests.md"
GT_RANGE = range(1, 17)

def r4(x):
    return D(x).quantize(D("0.0001"), ROUND_HALF_UP)


def load_sections(text):
    """{gt_number: body_text} for every `## GT-n` heading."""
    out, cur, buf = {}, None, []
    for line in text.splitlines():
        if line.startswith("#"):
            if cur is not None:
                out[cur] = "\n".join(buf)
            m = re.match(r"^##\s+GT-(\d+)\b", line)
            cur, buf = (int(m.group(1)) if m else None), []
            continue
        if cur is not None:
            buf.append(line)
    if cur is not None:
        out[cur] = "\n".join(buf)
    return out


# ── generic scanner for equations B5 writes out literally ──────────────────
# This is the part with no per-GT knowledge: it finds every "<expression> =
# <expression>" B5 states and evaluates it. It is what catches a DEF-028-class
# error without being told where to look, in any GT that spells its sums out.
_NUM = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?%?|\d+(?:\.\d+)?%?"
_TOKEN = re.compile(
    rf"(?P<num>{_NUM})|(?P<ident>[A-Za-z][A-Za-z\-]*)|(?P<op>[+*/-])"
    r"|(?P<lp>\()|(?P<rp>\))|(?P<comma>,)|(?P<eq>=)|(?P<ws>\s+)|(?P<other>.)"
)

def _normalize(s):
    # Markdown/currency furniture out; unicode operators to ASCII. U+2013 EN DASH
    # is deliberately NOT mapped to minus — in B5 it is a range separator
    # ("31–60", "tiers 0–2"), and mapping it would invent subtractions.
    s = s.replace("**", " ").replace("`", " ").replace("$", " ")
    return s.replace("×", "*").replace("−", "-").replace("÷", "/")

def _tokenize(s):
    return [(m.lastgroup, m.group()) for m in _TOKEN.finditer(s) if m.lastgroup != "ws"]

def _value(tok):
    v = D(tok.rstrip("%").replace(",", ""))
    return v / 100 if tok.endswith("%") else v

def _places(tok):
    lit = tok.rstrip("%")
    return len(lit.split(".")[1]) if "." in lit else 0

class _Parser:
    """expr := term (('+'|'-') term)* · term := factor (('*'|'/') factor)*
    factor := ('max'|'min') '(' expr ',' expr ')' | '(' expr ')' | IDENT* NUM

    IDENT* before a NUM is a label ("usage 82.08", "base 18.50") — B5 writes its
    sums with the line names inline, and this reads them the way a person does.
    """
    def __init__(self, toks):
        self.t, self.i, self.last_num = toks, 0, None

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else (None, None)

    def expr(self):
        v = self.term()
        while self.peek()[0] == "op" and self.peek()[1] in "+-":
            op = self.t[self.i][1]; self.i += 1
            rhs = self.term()
            v = v + rhs if op == "+" else v - rhs
        return v

    def term(self):
        v = self.factor()
        while self.peek()[0] == "op" and self.peek()[1] in "*/":
            op = self.t[self.i][1]; self.i += 1
            rhs = self.factor()
            v = v * rhs if op == "*" else v / rhs
        return v

    def factor(self):
        kind, tok = self.peek()
        if kind == "ident" and tok.lower() in ("max", "min"):
            nxt = self.t[self.i + 1] if self.i + 1 < len(self.t) else (None, None)
            if nxt[0] == "lp":
                fn = max if tok.lower() == "max" else min
                self.i += 2
                a = self.expr()
                self._eat("comma")
                b = self.expr()
                self._eat("rp")
                return fn(a, b)
        if kind == "lp":
            self.i += 1
            v = self.expr()
            self._eat("rp")
            return v
        labels = 0
        while self.peek()[0] == "ident" and labels < 4:
            self.i += 1
            labels += 1
        kind, tok = self.peek()
        if kind != "num":
            raise ValueError("expected number")
        self.i += 1
        self.last_num = tok
        return _value(tok)

    def _eat(self, kind):
        if self.peek()[0] != kind:
            raise ValueError(f"expected {kind}")
        self.i += 1

def _parse_chain(toks):
    """Parse `expr (= expr)+`; return (segment values, final literal, tokens used)."""
    p = _Parser(toks)
    segs, finals = [], []
    segs.append(p.expr())
    finals.append(p.last_num)
    if p.peek()[0] != "eq":
        raise ValueError("no '='")
    while p.peek()[0] == "eq":
        p.i += 1
        p.last_num = None
        segs.append(p.expr())
        finals.append(p.last_num)
    return segs, finals[-1], p.i

def scan_equations(body):
    """Every `... = ...` B5 states in this section, evaluated.

    Returns [(text, segment_values, stated_decimal_places)]. A token run is a
    candidate only if it holds an '='; anything unparseable is skipped rather
    than guessed at, so a GT whose arithmetic is only prose falls through to a
    declared relation or to NOT-CHECKABLE — never to a free pass.
    """
    toks, runs, run = _tokenize(_normalize(body)), [], []
    for tk in toks:
        if tk[0] == "other":
            if run:
                runs.append(run)
            run = []
        else:
            run.append(tk)
    if run:
        runs.append(run)

    found, prev = [], None
    for r in runs:
        if not any(k == "eq" for k, _ in r):
            continue
        # "; +18.50 = 100.58" — B5 chains steps with the previous result implied.
        if r[0][0] == "op" and r[0][1] in "+-":
            if prev is None:
                continue
            r = [("num", str(prev))] + r
        for start in range(len(r)):
            if r[start][0] not in ("num", "lp", "ident"):
                continue
            try:
                segs, final_lit, used = _parse_chain(r[start:])
            except (ValueError, IndexError, ZeroDivisionError, ArithmeticError):
                continue
            if len(segs) < 2 or final_lit is None:
                continue
            if any(k in ("num", "op", "eq") for k, _ in r[start + used:]):
                continue
            found.append((" ".join(tok for _, tok in r[start:start + used]), segs,
                          _places(final_lit)))
            prev = segs[-1]
            break
    return found


# ── declared relations: what B5 states in prose, not as one equation ───────
# Every number still comes OUT of the document (`fig` below). Nothing is
# hard-coded as an expected value; the code encodes only the RELATION B5 claims.
# A figure the regex can no longer find is a FAIL, never a skip — B5 is FROZEN,
# so a figure that moved means the signed document changed.
class Section:
    def __init__(self, n, body):
        self.n, self.body, self.missing = n, body, []

    def fig(self, name, pattern, group=1):
        m = re.search(pattern, self.body)
        if not m:
            self.missing.append(name)
            return None
        return D(m.group(group).replace(",", ""))


def gt_specs(S):
    """{gt: (figures, [(label, relation)], blocker_or_None, [notes])}"""
    specs = {}

    # ── GT-1 ────────────────────────────────────────────────────────────────
    s = S[1]
    specs[1] = (dict(
        rate=s.fig("rate", r"\$(\d+(?:\.\d+)?)/kWh"),
        base=s.fig("base", r"base \$(\d+(?:\.\d+)?)"),
        qty=s.fig("usage qty", r"usage (\d[\d,]*\d|\d) kWh"),
        pct=s.fig("tax rate", r"tax (\d+(?:\.\d+)?)% on"),
        usage_amt=s.fig("usage charge", r"Assumed calc:[^=]*=\s*(\d+(?:\.\d+)?)"),
        taxable=s.fig("taxable subtotal", r";\s*\+[\d.]+\s*=\s*(\d+(?:\.\d+)?)"),
        tax_raw=s.fig("unrounded tax", r"tax (\d+(?:\.\d+)?) →"),
        tax=s.fig("rounded tax", r"tax [\d.]+ → (\d+(?:\.\d+)?)"),
        total=s.fig("total", r"\*\*total (\d+(?:\.\d+)?)\*\*"),
    ), [
        ("usage charge = rate x quantity", lambda f: (r2(f["rate"] * f["qty"]), f["usage_amt"])),
        ("taxable = usage + base", lambda f: (f["usage_amt"] + f["base"], f["taxable"])),
        ("tax at stated rate on taxable", lambda f: (r4(f["taxable"] * f["pct"] / 100), f["tax_raw"])),
        ("tax rounds half-up to 2dp", lambda f: (r2(f["tax_raw"]), f["tax"])),
        ("total = taxable + tax", lambda f: (f["taxable"] + f["tax"], f["total"])),
    ], None, [])

    # ── GT-2 ────────────────────────────────────────────────────────────────
    s = S[2]
    specs[2] = (dict(
        t1_hi=s.fig("tier-1 ceiling", r"tiers 0[–-](\d+) kgal"),
        t2_lo=s.fig("tier-2 floor", r"kgal @ \$[\d.]+, (\d+)[–-]\d+ @"),
        t2_hi=s.fig("tier-2 ceiling", r"kgal @ \$[\d.]+, \d+[–-](\d+) @"),
        usage=s.fig("usage", r"usage (\d+(?:\.\d+)?) kgal"),
        q1=s.fig("tier-1 quantity", r"Assumed: (\d+(?:\.\d+)?)×"),
        q2=s.fig("tier-2 quantity", r"×[\d.]+ \+ (\d+(?:\.\d+)?)×"),
    ), [
        ("tier-1 quantity fills tier 1 exactly", lambda f: (f["q1"], f["t1_hi"])),
        ("tier quantities sum to usage", lambda f: (f["q1"] + f["q2"], f["usage"])),
        ("tier-2 quantity fits the tier-2 span",
         lambda f: (f["q2"] <= f["t2_hi"] - f["t2_lo"], True)),
    ], "B5 states '+tax' with no tax rate, and states no bill total — the golden "
       "figure an engine would be asserted against is simply absent", [])

    # ── GT-3 ────────────────────────────────────────────────────────────────
    s = S[3]
    specs[3] = (dict(
        day=s.fig("move-in day", r"move-in day (\d+) of \d+"),
        days=s.fig("days in period", r"move-in day \d+ of (\d+)"),
        base=s.fig("base", r"base \$(\d+(?:\.\d+)?)"),
        num=s.fig("proration numerator", r"Base proration (\d+)/\d+"),
        den=s.fig("proration denominator", r"Base proration \d+/(\d+)"),
        prorated=s.fig("prorated base", r"\*\*(\d+(?:\.\d+)?)\*\*"),
    ), [
        ("served days = period - move-in day + 1",
         lambda f: (f["days"] - f["day"] + 1, f["num"])),
        ("proration denominator = days in period", lambda f: (f["den"], f["days"])),
        ("prorated base = base x served/period",
         lambda f: (r2(f["base"] * f["num"] / f["den"]), f["prorated"])),
    ], "B5 says so in its own words — 'example total pending usage figures'. No "
       "usage quantity, no tax and no bill total are stated; only the base-"
       "proration step is", [])

    # ── GT-4 ────────────────────────────────────────────────────────────────
    s = S[4]
    specs[4] = (dict(
        prior=s.fig("prior read", r"prior (\d[\d,]*\d|\d)"),
        cur=s.fig("current read", r"current (\d[\d,]*\d|\d)"),
        digits=s.fig("register digits", r"\((\d+)-digit meter"),
        span=s.fig("wrap span", r"wrapped at (\d[\d,]*\d|\d)"),
        mult=s.fig("multiplier", r"multiplier ×(\d+)"),
        expected=s.fig("expected consumption", r"\)\+\d+ = (\d[\d,]*\d|\d)"),
    ), [
        ("wrap span = 10 ^ register digits",
         lambda f: (D(10) ** int(f["digits"]), f["span"])),
        ("consumption = (span - prior) + current, x multiplier",
         lambda f: (((f["span"] - f["prior"]) + f["cur"]) * f["mult"], f["expected"])),
    ], "the consumption figure is a bare number with no unit anywhere in the GT "
       "(hard rule 3: always an explicit unit, never assume), so it cannot be "
       "asserted against an engine output", [])

    # ── GT-5 ────────────────────────────────────────────────────────────────
    s = S[5]
    specs[5] = (dict(
        raw=s.fig("raw register delta", r"\(current.prior\)=(\d[\d,]*\d|\d)"),
        mult=s.fig("multiplier", r"multiplier ×(\d+)"),
        adjusted=s.fig("adjusted consumption", r"→ (\d[\d,]*\d|\d) kWh"),
        t1_hi=s.fig("tier-1 ceiling", r"tiers 0[–-](\d+) @"),
        t1_rate=s.fig("tier-1 rate", r"tiers 0[–-]\d+ @(\d+(?:\.\d+)?)"),
        t2_rate=s.fig("tier-2 rate", r"\d+\+ @(\d+(?:\.\d+)?)"),
        q1=s.fig("tier-1 quantity", r"first: (\d[\d,]*\d|\d)×"),
        q2=s.fig("tier-2 quantity", r"×[\d.]+ \+ (\d[\d,]*\d|\d)×"),
        total=s.fig("total", r"= \*\*(\d+(?:\.\d+)?)\*\*"),
    ), [
        ("multiplier applied before tiers", lambda f: (f["raw"] * f["mult"], f["adjusted"])),
        ("tier quantities sum to adjusted consumption",
         lambda f: (f["q1"] + f["q2"], f["adjusted"])),
        ("tier-1 quantity fills tier 1 exactly", lambda f: (f["q1"], f["t1_hi"])),
        ("total = per-tier lines, rounded per line",
         lambda f: (r2(f["q1"] * f["t1_rate"]) + r2(f["q2"] * f["t2_rate"]), f["total"])),
    ], None, [])

    # ── GT-6 ────────────────────────────────────────────────────────────────
    s = S[6]
    specs[6] = (dict(
        invoice=s.fig("invoice", r"invoice \$(\d+(?:\.\d+)?)"),
        credit=s.fig("credit", r"credit \$(\d+(?:\.\d+)?)"),
        balance=s.fig("resulting balance", r"balance (\d+(?:\.\d+)?)"),
    ), [
        ("balance = invoice - credit note", lambda f: (f["invoice"] - f["credit"], f["balance"])),
    ], None, ["immutability of the original invoice is a structural claim, not an "
              "arithmetic one — asserted in 06-backend/tests/golden, not here"])

    # ── GT-7 ────────────────────────────────────────────────────────────────
    s = S[7]
    specs[7] = (dict(
        a=s.fig("BL-A balance", r"BL-A \$(\d+(?:\.\d+)?)"),
        b=s.fig("BL-B balance", r"BL-B \$(\d+(?:\.\d+)?)"),
        pay=s.fig("payment", r"payment \$(\d+(?:\.\d+)?)"),
        a_paid=s.fig("BL-A allocated", r"BL-A paid (\d+(?:\.\d+)?)"),
        b_paid=s.fig("BL-B allocated", r"BL-B paid (\d+(?:\.\d+)?)"),
        remaining=s.fig("remaining", r"remaining (\d+(?:\.\d+)?)"),
    ), [
        ("allocations sum to the payment", lambda f: (f["a_paid"] + f["b_paid"], f["pay"])),
        ("oldest-first exhausts BL-A before BL-B",
         lambda f: (min(f["pay"], f["a"]), f["a_paid"])),
        ("remaining = total balance - payment",
         lambda f: (f["a"] + f["b"] - f["pay"], f["remaining"])),
        ("remaining sits entirely on BL-B", lambda f: (f["b"] - f["b_paid"], f["remaining"])),
    ], None, [])

    # ── GT-8 ────────────────────────────────────────────────────────────────
    s = S[8]
    specs[8] = (dict(
        overdue=s.fig("overdue portion", r"overdue portion \$(\d+(?:\.\d+)?)"),
        floor=s.fig("fee floor", r"max\((\d+),"),
        rate=s.fig("fee rate", r"max\(\d+, (\d+(?:\.\d+)?)×"),
        formula_base=s.fig("formula base", r"max\(\d+, [\d.]+×(\d+(?:\.\d+)?)\)"),
        fee=s.fig("late fee", r"= (\d+(?:\.\d+)?)`"),
    ), [
        ("formula is applied to the overdue portion only",
         lambda f: (f["formula_base"], f["overdue"])),
        ("late fee = max(floor, rate x overdue portion)",
         lambda f: (max(f["floor"], r2(f["rate"] * f["overdue"])), f["fee"])),
    ], None, [])

    # ── GT-9 ────────────────────────────────────────────────────────────────
    s = S[9]
    specs[9] = (dict(
        est=s.fig("estimated consumption", r"avg = (\d[\d,]*\d|\d) kWh"),
        actual=s.fig("actual consumption", r"actual (\d[\d,]*\d|\d) →"),
        trueup=s.fig("true-up", r"true-up \+(\d[\d,]*\d|\d) kWh"),
    ), [
        ("true-up = actual - estimated", lambda f: (f["actual"] - f["est"], f["trueup"])),
    ], None, ["'actual 700' carries no unit of its own; the series it sits in is "
              "tagged kWh at both ends, so the subtraction is checked and the "
              "omission is REPORTED as a documentation nit rather than assumed away"])

    # ── GT-10 — the DEF-028 range ───────────────────────────────────────────
    s = S[10]
    specs[10] = (dict(
        usage=s.fig("usage", r"usage \$(\d+(?:\.\d+)?)"),
        base=s.fig("base", r"base \$(\d+(?:\.\d+)?)"),
        taxable=s.fig("taxable subtotal", r"= \$(\d+(?:\.\d+)?) taxable"),
        fee=s.fig("late fee", r"late fee \$(\d+(?:\.\d+)?) NOT taxable"),
        pct=s.fig("tax rate", r"tax (\d+(?:\.\d+)?)% ×"),
        taxbase=s.fig("tax base", r"tax [\d.]+% × (\d+(?:\.\d+)?) ="),
        tax=s.fig("tax", r"tax [\d.]+% × [\d.]+ = (\d+(?:\.\d+)?)"),
        total=s.fig("stated total", r"Total = [^=]*= \*\*(\d+(?:\.\d+)?)\*\*"),
    ), [
        ("taxable subtotal = usage + base", lambda f: (f["usage"] + f["base"], f["taxable"])),
        ("B4.2: the fee is NOT in the tax base", lambda f: (f["taxbase"], f["taxable"])),
        ("tax = rate x taxable subtotal",
         lambda f: (r2(f["taxable"] * f["pct"] / 100), f["tax"])),
        # ↓ THE DEF-028 CHECK. This is the assertion nothing had ever run.
        ("stated total = its own stated components",
         lambda f: (f["taxable"] + f["fee"] + f["tax"], f["total"])),
        ("cross-check vs GT-11 (same bill, tax-exempt) + this GT's own tax",
         lambda f: (f["gt11_total"] + f["tax"], f["total"])),
        ("cross-check vs GT-1 (same usage+base+tax) + GT-8's frozen fee",
         lambda f: (f["gt1_total"] + f["gt8_fee"], f["total"])),
    ], None, [])

    # ── GT-11 ───────────────────────────────────────────────────────────────
    s = S[11]
    specs[11] = (dict(
        tax=s.fig("tax", r"Tax = (\d+) regardless"),
        taxable=s.fig("taxable subtotal", r"Total = (\d+(?:\.\d+)?) \+"),
        fee=s.fig("late fee", r"Total = [\d.]+ \+ (\d+(?:\.\d+)?) ="),
        total=s.fig("total", r"= \*\*(\d+(?:\.\d+)?)\*\*"),
    ), [
        ("total = taxable + fee + zero tax",
         lambda f: (f["taxable"] + f["fee"] + f["tax"], f["total"])),
        ("'same as GT-10': taxable subtotal matches GT-10",
         lambda f: (f["taxable"], f["gt10_taxable"])),
        ("'same as GT-10': late fee matches GT-10", lambda f: (f["fee"], f["gt10_fee"])),
    ], None, [])

    # ── GT-12 ───────────────────────────────────────────────────────────────
    s = S[12]
    specs[12] = (dict(
        imports=s.fig("imports", r"Imports (\d[\d,]*\d|\d) kWh"),
        exports=s.fig("exports", r"exports (\d[\d,]*\d|\d)"),
        net=s.fig("net export", r"net −(\d[\d,]*\d|\d)"),
        bank=s.fig("bank credit", r"bank \+(\d[\d,]*\d|\d) kWh"),
        next_net=s.fig("next-cycle net", r"net \+(\d[\d,]*\d|\d) →"),
        draw=s.fig("bank draw", r"draw bank (\d[\d,]*\d|\d)"),
        billed=s.fig("billed consumption", r"bill (\d[\d,]*\d|\d) kWh"),
    ), [
        ("net export = exports - imports", lambda f: (f["exports"] - f["imports"], f["net"])),
        ("bank credit = net export", lambda f: (f["bank"], f["net"])),
        ("bank draw exhausts the banked credit exactly",
         lambda f: (f["draw"], f["bank"])),
        ("billed = next-cycle net - bank draw",
         lambda f: (f["next_net"] - f["draw"], f["billed"])),
    ], None, ["PROPOSED, blocked on OQ-001 — self-consistency is checkable and is "
              "checked here; ratification is a separate question and not this "
              "script's to answer",
              "'exports 964' and 'net −152' carry no unit of their own; the series "
              "is tagged kWh at 'Imports 812 kWh' and 'bank +152 kWh', so the "
              "arithmetic is checked and the omission is REPORTED, not assumed away"])

    # ── GT-13 ───────────────────────────────────────────────────────────────
    s = S[13]
    specs[13] = (dict(
        usage=s.fig("usage", r"Usage \$(\d+(?:\.\d+)?)"),
        base=s.fig("base", r"base \$(\d+(?:\.\d+)?)"),
        subtotal=s.fig("subtotal", r"= \$(\d+(?:\.\d+)?) <"),
        minimum=s.fig("minimum", r"minimum \$(\d+(?:\.\d+)?)"),
        adj=s.fig("adjustment line", r"adjustment line \$(\d+(?:\.\d+)?)"),
        taxbase=s.fig("tax base", r"tax on \$(\d+(?:\.\d+)?)"),
    ), [
        ("subtotal = usage + base", lambda f: (f["usage"] + f["base"], f["subtotal"])),
        ("the minimum bites (subtotal < minimum)",
         lambda f: (f["subtotal"] < f["minimum"], True)),
        ("adjustment = minimum - subtotal",
         lambda f: (f["minimum"] - f["subtotal"], f["adj"])),
        ("subtotal + adjustment = minimum",
         lambda f: (f["subtotal"] + f["adj"], f["minimum"])),
        ("tax base = the minimum, not the subtotal", lambda f: (f["taxbase"], f["minimum"])),
    ], None, [])

    # ── GT-14 ───────────────────────────────────────────────────────────────
    s = S[14]
    specs[14] = (dict(
        digits=s.fig("register digits", r"(\d+)-digit register"),
        prior=s.fig("prior read", r"prior (\d[\d,]*\d|\d)"),
        cur=s.fig("current read", r"current (\d[\d,]*\d|\d)"),
        mult=s.fig("multiplier", r"×(\d+) →"),
        span=s.fig("wrap span", r"\((\d[\d,]*\d|\d)−"),
        expected=s.fig("expected consumption", r"\)\+\d+ = (\d[\d,]*\d|\d)"),
        drop=s.fig("register drop", r"span check: (\d[\d,]*\d|\d) >"),
        pct=s.fig("span-check threshold", r"> (\d+)% of"),
        pct_span=s.fig("span-check span", r"% of (\d[\d,]*\d|\d)"),
    ), [
        ("wrap span = 10 ^ register digits",
         lambda f: (D(10) ** int(f["digits"]), f["span"])),
        ("the span check uses the same span", lambda f: (f["pct_span"], f["span"])),
        ("register drop = prior - current", lambda f: (f["prior"] - f["cur"], f["drop"])),
        ("drop exceeds the threshold share of span",
         lambda f: (f["drop"] > f["pct"] / 100 * f["span"], True)),
        ("consumption = (span - prior) + current, x multiplier",
         lambda f: (((f["span"] - f["prior"]) + f["cur"]) * f["mult"], f["expected"])),
    ], "the consumption figure is a bare number with no unit anywhere in the GT "
       "(hard rule 3: always an explicit unit, never assume) — the same gap as "
       "GT-4, which this GT supersedes", [])

    # ── GT-15 ───────────────────────────────────────────────────────────────
    s = S[15]

    def _gt15_unique(f):
        cands = {"solar line": f["solar_line"], "battery line": f["batt_line"],
                 "both lines": f["solar_line"] + f["batt_line"]}
        hits = [k for k, v in cands.items()
                if r2(v * f["pro_num"] / f["pro_den"]) == f["pro_amt"]]
        return (hits, ["solar line"])

    specs[15] = (dict(
        solar_q=s.fig("solar units", r"solar (\d+) units @"),
        solar_rate=s.fig("solar rate", r"solar \d+ units @ \$(\d+)"),
        batt_q=s.fig("battery units", r"battery (\d+) @"),
        batt_rate=s.fig("battery rate", r"battery \d+ @ \$(\d+)"),
        solar_line=s.fig("solar line", r"→ \$(\d+(?:\.\d+)?) \+"),
        batt_line=s.fig("battery line", r"→ \$[\d.]+ \+ \$(\d+(?:\.\d+)?) lines"),
        pro_num=s.fig("proration numerator", r"WE-16: (\d+)/\d+ days"),
        pro_den=s.fig("proration denominator", r"WE-16: \d+/(\d+) days"),
        pro_amt=s.fig("prorated capacity", r"days → \$(\d+(?:\.\d+)?)\)"),
    ), [
        ("solar line = units x rate",
         lambda f: (f["solar_q"] * f["solar_rate"], f["solar_line"])),
        ("battery line = units x rate",
         lambda f: (f["batt_q"] * f["batt_rate"], f["batt_line"])),
        ("exactly one stated line reproduces the prorated figure", _gt15_unique),
        ("prorated figure ties to WE-16/GT-31, recomputed in Part 1",
         lambda f: (f["pro_amt"], WE16_CAPACITY_PRORATION)),
    ], None, ["B5 does not say WHICH capacity line the 10/31 proration applies to; "
              "only the $40.00 solar line reproduces $12.90 (both lines together "
              "would give $20.65). REPORTED as an ambiguity, not resolved here"])

    # ── GT-16 ───────────────────────────────────────────────────────────────
    s = S[16]
    specs[16] = (dict(
        b_cur=s.fig("bucket Current", r"Current (\d+(?:\.\d+)?) /"),
        b1=s.fig("bucket 31-60", r"31[–-]60 (\d+(?:\.\d+)?) /"),
        b2=s.fig("bucket 61-90", r"61[–-]90 (\d+(?:\.\d+)?) /"),
        b3=s.fig("bucket 90+", r"90\+ (\d+(?:\.\d+)?) \(USD\)"),
        balance=s.fig("accounts.balance", r"balance` = \*\*(\d+(?:\.\d+)?)\*\*"),
        dr=s.fig("opening JE debit", r"DR AR (\d+(?:\.\d+)?) /"),
        cr=s.fig("opening JE credit", r"CR opening-balance clearing (\d+(?:\.\d+)?)"),
        a1=s.fig("aged 31-60", r"31[–-]60 ← (\d+(?:\.\d+)?)"),
        a2=s.fig("aged 61-90", r"61[–-]90 ← (\d+(?:\.\d+)?)"),
        a3=s.fig("aged 90+", r"90\+ ← (\d+(?:\.\d+)?)"),
    ), [
        ("balance = sum of the four opening buckets",
         lambda f: (f["b_cur"] + f["b1"] + f["b2"] + f["b3"], f["balance"])),
        ("opening JE is a balanced pair (DR = CR)", lambda f: (f["dr"], f["cr"])),
        ("opening JE posts the account balance", lambda f: (f["dr"], f["balance"])),
        ("forward aging conserves the total",
         lambda f: (f["a1"] + f["a2"] + f["a3"], f["balance"])),
        ("aging shifts Current -> 31-60", lambda f: (f["a1"], f["b_cur"])),
        ("aging shifts 31-60 -> 61-90", lambda f: (f["a2"], f["b1"])),
        ("aging merges 61-90 + 90+ -> 90+", lambda f: (f["a3"], f["b2"] + f["b3"])),
        ("balance ties to PE-13/GT-47, recomputed in Part 1",
         lambda f: (f["balance"], PE13_OPENING_BALANCE)),
    ], None, ["currency is explicit (USD) — checked",
              "NOT-CHECKABLE sub-item: the batch tie-out ($184,320.55 across 1,213 "
              "accounts) states no per-account fixture, so that sum cannot be "
              "recomputed; only the single-account opening JE is verified"])
    return specs


def run_part2(text):
    """Check GT-1..GT-16 for internal arithmetic consistency. Pure function of
    the B5 text, so the self-test can run it over a mutated copy in memory."""
    sections = load_sections(text)
    S = {n: Section(n, sections.get(n, "")) for n in GT_RANGE}
    absent = [n for n in GT_RANGE if n not in sections]
    specs = gt_specs(S)

    # Cross-GT figures. GT-10's total is corroborated by GT-1/GT-8/GT-11 — the
    # three independent cross-checks that identified DEF-028.
    cross = {
        10: {"gt11_total": specs[11][0]["total"], "gt1_total": specs[1][0]["total"],
             "gt8_fee": specs[8][0]["fee"]},
        11: {"gt10_taxable": specs[10][0]["taxable"], "gt10_fee": specs[10][0]["fee"]},
    }

    results = {}
    for n in GT_RANGE:
        figures, relations, blocker, notes = specs[n]
        figures = dict(figures)
        figures.update(cross.get(n, {}))
        checks = []

        for name in S[n].missing:
            checks.append((f"GT-{n} figure[{name}]", False,
                           "B5 no longer states this figure where the verifier reads it — "
                           "the FROZEN document changed; re-verify and re-sign (HUMAN-GUIDE §6)"))

        missing_names = sorted(k for k, v in figures.items() if v is None)
        for label, fn in relations:
            cid = f"GT-{n} rel[{label}]"
            if missing_names:
                checks.append((cid, None,
                               f"needs figure(s) not found in B5: {', '.join(missing_names)}"))
                continue
            try:
                got, want = fn(figures)
            except (ArithmeticError, TypeError, ValueError) as exc:
                checks.append((cid, None, f"not evaluable: {exc}"))
                continue
            checks.append((cid, got == want, f"computed {got}, B5 states {want}"))

        for i, (text_i, segs, places) in enumerate(scan_equations(S[n].body), 1):
            stated = segs[-1]
            bad = [v for v in segs[:-1]
                   if D(v).quantize(D(1).scaleb(-places), ROUND_HALF_UP) != stated]
            cid = f"GT-{n} eq[{i}]"
            if bad:
                checks.append((cid, False,
                               f'"{text_i}" — components give {bad[0]}, B5 states {stated} '
                               f"(off by {abs(D(bad[0]) - stated)})"))
            else:
                checks.append((cid, True, f'"{text_i}" -> {stated}'))

        failed = [c for c in checks if c[1] is False]
        verified = [c for c in checks if c[1] is True]
        unresolved = [c for c in checks if c[1] is None]
        if failed:
            status = "FAIL"
        elif blocker:
            status = "NOT-CHECKABLE"
        elif verified:
            status = "PASS"
        else:
            status = "NOT-CHECKABLE"
            blocker = ("B5 states no components-to-total arithmetic this verifier "
                       "can read for this GT")
        results[n] = dict(status=status, checks=checks, blocker=blocker, notes=notes,
                          verified=len(verified), failed=len(failed),
                          unresolved=len(unresolved))
    return results, absent


# ═══════════════════════════════════════════════════════════════════════════
# KNOWN DEFECTS — the ONLY failures allowed to exit 0. EMPTY TODAY.
#
# An entry here is not "ignore this". It is: this exact discrepancy, in this
# exact place, with these exact numbers, already has a row in
# 12-governance/10-defect-log.csv and is routed to a human ruling this lane has
# no authority to make. It exists so that the honest response to a signed-figure
# defect is "log it and keep the gate meaningful" rather than the thing that
# actually happens to a permanently-red gate: someone deletes the check.
#
# Three properties stop it from becoming the silencing that let DEF-028 through
# in the first place. All three are exercised on every run by SELF_TESTS below —
# this is a mechanism with no live entries, not a mechanism nobody has run.
#   1. NARROW   — keyed on (check id, exact message). Any drift in either
#                 number is a NEW failure and exits 1.
#   2. LOUD     — printed under a KNOWN-DEFECT banner and named on line 1, the
#                 line run_gates G4 surfaces. Never hidden.
#   3. EXPIRING — if a waived failure stops reproducing, that is a STALE WAIVER
#                 and exits 1. B5 is ❄️ FROZEN, so a silently-passing waived GT
#                 means someone edited a signed figure. The entry is removed
#                 when the defect row closes, not before.
#
# DEF-028 was the intended first entry. It was closed by a PO/finance re-sign
# under HUMAN-GUIDE §6 on 2026-08-10 before this lane landed, so it needs no
# waiver: GT-10 now passes on its merits, and SELF_TESTS keeps proving that the
# check which would have caught it still bites.
# ═══════════════════════════════════════════════════════════════════════════
KNOWN_DEFECTS = {}
DEFECT_ROUTE = {}


def classify(results, known, strict=False):
    """Split Part 2's failures into (new, waived, stale). Single source of the
    exit-code decision, so the self-test can exercise the exact same logic."""
    new_fails, waived = [], []
    for n in GT_RANGE:
        for cid, ok, detail in results[n]["checks"]:
            if ok is not False:
                continue
            if (cid, detail) in known and not strict:
                waived.append((known[(cid, detail)], cid, detail))
            else:
                new_fails.append((cid, detail))
    seen = {(cid, d) for n in GT_RANGE for cid, ok, d in results[n]["checks"] if ok is False}
    stale = [] if strict else [(did, k) for k, did in known.items() if k not in seen]
    return new_fails, waived, stale


# ═══════════════════════════════════════════════════════════════════════════
# PART 0 — SELF-TEST. CLAUDE.md law 7: prove a new guard goes RED before
# trusting it green.
#
# DEF-028 was fixed in B5 by a PO/finance re-sign on 2026-08-10, so Part 2 now
# passes GT-10 — which means a green Part 2 no longer demonstrates that Part 2
# works. These fixtures keep the demonstration alive permanently. Each mutates
# the LIVE B5 text IN MEMORY (nothing is written; 04-docs/** is never touched)
# and asserts an outcome. A fixture that fails to bite exits 1, so neither the
# checker nor the waiver discipline can rot into something that always passes.
#
# Group A — detection. Fixture A1 IS DEF-028, byte for byte as B5 read before
#           the re-sign; it must make GT-10 go red.
# Group B — waiver discipline. Proves NARROW and EXPIRING against a probe
#           registry, which is why KNOWN_DEFECTS can ship empty without being
#           unwired code (CLAUDE.md law 2).
# ═══════════════════════════════════════════════════════════════════════════
DEF028_TOTAL_LINE = "= **117.01** (fee added after tax)"
DEF028_PRE_RESIGN = "= **116.01** (fee added after tax)"
# The exact failure DEF-028 produced, in this verifier's own vocabulary.
DEF028_KEY = ("GT-10 rel[stated total = its own stated components]",
              "computed 117.01, B5 states 116.01")

DETECTION_FIXTURES = [
    ("A1", "DEF-028 replay — GT-10 total reverted to the pre-re-sign 116.01", 10,
     DEF028_TOTAL_LINE, DEF028_PRE_RESIGN,
     "the exact defect this range was extended for: a stated total that "
     "contradicts its own stated addends by 1.00"),
    ("A2", "GT-1 total tampered (108.88 -> 108.98)", 1,
     "**total 108.88**", "**total 108.98**",
     "a one-digit drift in a signed total must not pass"),
    ("A3", "GT-13 adjustment tampered (6.90 -> 6.80)", 13,
     "adjustment line $6.90", "adjustment line $6.80",
     "a prose-only relation with no written equation must still be checked"),
    ("A4", "GT-16 balance figure removed", 16,
     "`accounts.balance` = **267.30**", "`accounts.balance` = **(pending)**",
     "a figure that vanishes from a FROZEN document is a FAIL, never a silent skip"),
]


def run_self_tests(text):
    out = []

    def add(tag, name, ok, detail):
        out.append((tag, name, ok, detail))

    mutated = None
    for tag, name, gt, old, new, why in DETECTION_FIXTURES:
        if text.count(old) != 1:
            add(tag, name, False,
                f"fixture is stale: expected exactly one occurrence of {old!r} in B5, found "
                f"{text.count(old)} — the document moved under the fixture, so this proves nothing")
            continue
        res, _ = run_part2(text.replace(old, new))
        status = res[gt]["status"]
        first = next((d for _, ok, d in res[gt]["checks"] if ok is False), "no failing check")
        add(tag, name, status == "FAIL",
            f"GT-{gt} -> {status}" + (f"; first failure: {first}" if status == "FAIL"
                                      else f" (expected FAIL) — {why}"))
        if tag == "A1" and status == "FAIL":
            mutated = res

    # ── Group B — waiver discipline, against the DEF-028 replay ─────────────
    if mutated is None:
        add("B*", "waiver discipline", False,
            "cannot run: the DEF-028 replay (A1) did not produce a failure to waive")
        return out

    clean, _ = run_part2(text)

    n_new, n_waived, n_stale = classify(mutated, {DEF028_KEY: "DEF-PROBE"})
    add("B1", "a registered known defect is waived, not counted as a new failure",
        len(n_waived) >= 1 and DEF028_KEY not in n_new,
        f"{len(n_waived)} waived, {len(n_new)} unwaived (the equation-scanner hit on the same "
        f"defect stays unwaived, which is correct — each entry must be registered explicitly)")

    wrong = {(DEF028_KEY[0], "computed 117.01, B5 states 116.02"): "DEF-PROBE"}
    w_new, w_waived, w_stale = classify(mutated, wrong)
    add("B2", "NARROW: a waiver whose numbers drifted does NOT waive",
        len(w_waived) == 0 and len(w_stale) == 1,
        f"{len(w_waived)} waived (want 0), {len(w_stale)} stale (want 1) — a changed discrepancy "
        "is a new failure, never a covered one")

    s_new, s_waived, s_stale = classify(clean, {DEF028_KEY: "DEF-PROBE"})
    add("B3", "EXPIRING: a waiver that no longer reproduces is STALE and fails the gate",
        len(s_stale) == 1 and len(s_waived) == 0,
        f"{len(s_stale)} stale (want 1) — on today's re-signed B5 the DEF-028 waiver would "
        "correctly refuse to sit there silently")

    x_new, x_waived, x_stale = classify(mutated, {DEF028_KEY: "DEF-PROBE"}, strict=True)
    add("B4", "--strict ignores waivers entirely",
        len(x_waived) == 0 and DEF028_KEY in x_new,
        f"{len(x_waived)} waived (want 0); the defect is reported as a plain failure")
    return out

# ═══════════════════════════════════════════════════════════════════════════
# REPORT
# ═══════════════════════════════════════════════════════════════════════════
STRICT = "--strict" in sys.argv

results, absent, part2_errors, self_tests = None, [], [], []
if not B5_PATH.is_file():
    part2_errors.append(("B5 source", f"cannot read {B5_PATH}"))
else:
    b5_text = B5_PATH.read_text(encoding="utf-8")   # read-only, always
    results, absent = run_part2(b5_text)
    self_tests = run_self_tests(b5_text)

new_fails, waived, stale = [], [], []
counts = {"PASS": 0, "FAIL": 0, "NOT-CHECKABLE": 0}
if results:
    for n in GT_RANGE:
        counts[results[n]["status"]] += 1
    new_fails, waived, stale = classify(results, KNOWN_DEFECTS, STRICT)
new_fails += part2_errors
new_fails += [(f"GT-{n}", f"no `## GT-{n}` section in B5 — the FROZEN document changed")
              for n in absent]

blind = [(tag, name, detail) for tag, name, ok, detail in self_tests if not ok]

summary = f"golden-verify: {len(WORKBOOK_PASS)} PASS, {len(WORKBOOK_FAIL)} FAIL"
summary += (f"  |  ruling-derived (part 3, NOT frozen): {len(RULING_PASS)} PASS, "
            f"{len(RULING_FAIL)} FAIL")
summary += (f"  |  CR-081 not-yet-re-signed (part 4): {len(UNSIGNED_PASS)} PASS, "
            f"{len(UNSIGNED_FAIL)} FAIL")
if results:
    known = sorted({d for d, _, _ in waived})
    summary += (f"  |  GT-1..16 self-consistency: {counts['PASS']} PASS, {counts['FAIL']} FAIL"
                + (f" ({len(known)} known: {', '.join(known)}, waived)" if known else "")
                + f", {counts['NOT-CHECKABLE']} NOT-CHECKABLE")
    summary += f"  |  self-test: {len(self_tests) - len(blind)}/{len(self_tests)} guards bite"
if stale:
    summary += f"  |  STALE WAIVER: {', '.join(d for d, _ in stale)}"
print(summary)

print()
print("--- Part 1: workbook composites GT-17..GT-61 (recomputed from B4 rules) ---")
print(f"  {len(WORKBOOK_PASS)} PASS, {len(WORKBOOK_FAIL)} FAIL")
for f in WORKBOOK_FAIL:
    print("  FAIL", f)

print()
print("--- Part 3: the discount/tax pair (DEF-652) — RULING-DERIVED, NOT ❄️ FROZEN ---")
print(f"  {len(RULING_PASS)} PASS, {len(RULING_FAIL)} FAIL")
print("  Source: PO ruling 2026-08-27, not the 2026-08-08 finance freeze. Counted")
print("  separately so Part 1's 33 keeps meaning the 33 figures finance signed.")
for c in RULING_PASS:
    print("  PASS", c)
for f in RULING_FAIL:
    print("  FAIL", f)

print()
print("--- Part 4: sewer figures CR-081 moved that the 2026-09-08 re-sign did NOT cover ---")
print(f"  {len(UNSIGNED_PASS)} PASS, {len(UNSIGNED_FAIL)} FAIL   (OQ-RAT-12347 — with the PO)")
print("  These are NOT defects and NOT frozen figures to correct. Part 1 still")
print("  recomputes WE-6 the SIGNED way and still passes; this asserts the GAP so")
print("  that pass is not silent. A FAIL here means somebody moved one of them.")
for c in UNSIGNED_PASS:
    print("  PASS", c)
for f in UNSIGNED_FAIL:
    print("  FAIL", f)

if self_tests:
    print()
    print("--- Part 0: self-test (law 7 — prove the guard goes RED before trusting it green) ---")
    for tag, name, ok, detail in self_tests:
        print(f"  {'BITES' if ok else 'BLIND'} {tag}  {name}")
        print(f"           {detail}")
    if not blind:
        print("  All fixtures behaved. Part 2 is demonstrably checking, not merely passing,")
        print("  and the KNOWN_DEFECTS waiver discipline is exercised even while it is empty.")

if results:
    print()
    print("--- Part 2: GT-1..GT-16 self-consistency (parsed read-only from "
          f"{B5_PATH.relative_to(REPO_ROOT)}) ---")
    for n in GT_RANGE:
        r = results[n]
        print(f"  GT-{n:<3} {r['status']:<14} "
              f"{r['verified']} verified / {r['failed']} failed / {r['unresolved']} unresolved")
        if r["blocker"]:
            print(f"       NOT-CHECKABLE because: {r['blocker']}.")
            if r["verified"]:
                print(f"       ({r['verified']} stated step(s) checked and internally "
                      "consistent — REPORTED, but NOT counted as a pass)")
        for note in r["notes"]:
            print(f"       note: {note}")
        for cid, ok, detail in r["checks"]:
            if ok is False:
                mark = ("KNOWN-DEFECT" if (cid, detail) in KNOWN_DEFECTS and not STRICT
                        else "FAIL")
                print(f"    {mark} {cid}: {detail}")
            elif ok is None:
                print(f"    UNRESOLVED {cid}: {detail}")

if waived:
    print()
    print("--- KNOWN DEFECTS (reproduced by this run; already logged and routed) ---")
    for did in sorted({d for d, _, _ in waived}):
        print(f"  {did}: {DEFECT_ROUTE.get(did, 'see 12-governance/10-defect-log.csv')}")
        for d, cid, detail in waived:
            if d == did:
                print(f"    - {cid}: {detail}")
    print("  These do NOT fail the gate — they are logged and awaiting a human ruling.")
    print("  Run with --strict to fail on them too.")

if stale:
    print()
    print("--- STALE WAIVER (this DOES fail the gate) ---")
    for did, (cid, detail) in stale:
        print(f"  FAIL {did} no longer reproduces at {cid}.")
        print(f"       expected: {detail}")
        print("       B5 is ❄️ FROZEN. Either a signed figure was edited without a finance")
        print("       re-sign (HUMAN-GUIDE §6), or the defect closed and this waiver must be")
        print("       removed together with its row in 12-governance/10-defect-log.csv.")

if blind:
    print()
    print("--- SELF-TEST BLIND (this DOES fail the gate) ---")
    for tag, name, detail in blind:
        print(f"  FAIL self-test fixture {tag} did not behave: {name}")
        print(f"       {detail}")
    print("       A guard that cannot be shown to fail is not a guard (CLAUDE.md law 7).")
    print("       If B5 was legitimately re-signed, the fixture's search string moved with it:")
    print("       refresh DETECTION_FIXTURES to the new wording as part of that re-sign, so the")
    print("       guard keeps proving itself. Do NOT delete the fixture to clear this.")

if new_fails:
    print()
    print("--- FAILURES (not known, not waived) ---")
    for cid, detail in new_fails:
        print(f"  FAIL {cid}: {detail}")
    print("       B5 is ❄️ FROZEN and finance-signed. This script REPORTS; it never edits a")
    print("       figure. Route a real discrepancy to a finance re-sign (HUMAN-GUIDE §6) and")
    print("       add a row to 12-governance/10-defect-log.csv.")

raise SystemExit(
    1
    if (WORKBOOK_FAIL or RULING_FAIL or UNSIGNED_FAIL or new_fails or stale or blind)
    else 0
)
