# ── Trace ──────────────────────────────────────────────
# Change:   CR-190-BRC10 lane AGREEMENT — the agreement as a PDF (PO
#           2026-10-22, answer 1: *"email it as a PDF attachment"*) and the
#           stamped copy (*"a PDF copy stamped 'Accepted on … by …' stored on
#           the account"*)
# Rules:    B14 rule 43 (the product's ONE PDF writer, `apps/billing/
#           page_print.py`, reused — never a second writer) · B14 rule 31 (no
#           database id on paper) · B1 (billing reached by NAME, read only)
# Tests:    06-backend/tests/test_cr190_agreements.py ·
#           06-backend/tests/test_def_bil_f06_tagged_pdf.py (DEF-BIL-10546)
# Impacts:  apps/customers/agreements.py (the only caller)
# Defect:   DEF-BIL-10546 (portal accessibility F-06) — the agreement is a
#           customer PDF, so from 2026-10-23 it is a TAGGED PDF/UA-1 file
#           written by `core.tagged_pdf` from the HTML below (decision log
#           "Portal accessibility, Group H", item 4: *"Everything a customer
#           receives … agreements"*).
# ───────────────────────────────────────────────────────
"""The agreement on paper: the text exactly as published, and its stamp.

The body is `agreement_requests.rendered_body` — rendered ONCE, at issue, from
the pinned version — so the PDF attached to the email, the text on the
acceptance page and the stamped copy are the same words by construction.

The stamped copy is the SAME pages with one block added after the text: the
acceptance line, the date the customer entered and when it was submitted. It is
rendered at accept time and stored; it is never re-rendered.

Words printed here are English, like every printed document in the product
(`apps/work/print_docs.py`'s posture, the bill's own) — the agreement's TEXT is
the utility's own wording in the language it published.

THE TAGGED PAGE (`DEF-BIL-10546`, 2026-10-23). `render` writes the agreement
as HTML (`html`) and hands it to `core.tagged_pdf`, the product's one tagged-PDF
renderer: a structure tree, `/Lang`, the agreement's name as the displayed
title, Liberation Sans embedded. The document's language is the language the
AGREEMENT was published in (`agreement_requests.template_language`), because
the body is nearly every word on the page; the few English words around it
(Version, Account, Accepted on) are marked `lang="en"` where they differ.
`render_untagged` is the previous `page_print` page, kept ONLY so the parity
test can prove the tagged page says the same words in the same order. Nothing
sends it.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any


def _pp() -> Any:
    """`apps.billing.page_print` by name — read only, renders bytes, writes no
    table (the `work.seams.billing_seam.page_engine` precedent)."""
    return import_module("apps.billing.page_print")


def _line(text: str, *, bold: bool = False, muted: bool = False, size: float | None = None):
    pp = _pp()
    size = size or pp.SIZE_BODY
    lines = pp.wrap(text, pp.PAGE_RIGHT - pp.PAGE_MARGIN, bold=bold, size=size) or [""]
    return [
        pp.PageRow(
            pp.LEAD_BODY,
            (
                pp.PageCell(
                    line,
                    pp.PAGE_MARGIN,
                    pp.FONT_BOLD if bold else pp.FONT_REGULAR,
                    size,
                    pp.MUTED if muted else pp.INK,
                ),
            ),
        )
        for line in lines
    ]


def _gap() -> list[Any]:
    pp = _pp()
    return [pp.PageRow(pp.LEAD_GAP)]


def _rows(facts: dict[str, Any], body: str, stamp: dict[str, Any] | None) -> list[Any]:
    pp = _pp()
    rows: list[Any] = []
    if facts.get("utility_name"):
        rows += _line(str(facts["utility_name"]), bold=True, size=pp.SIZE_TITLE)
    rows += _line(str(facts["agreement_name"]), bold=True, size=pp.SIZE_SECTION)
    version = f"Version {facts['version']}"
    if facts.get("effective_from"):
        version += f" · effective {facts['effective_from']}"
    rows += _line(version, muted=True, size=pp.SIZE_SMALL)
    rows += _line(f"Account {facts['account_no']} · {facts['customer_name']}", muted=True,
                  size=pp.SIZE_SMALL)
    rows += _gap()
    for paragraph in str(body or "").replace("\r\n", "\n").split("\n"):
        rows += _line(paragraph) if paragraph.strip() else _gap()
    if stamp is not None:
        rows += _gap() + _gap()
        rows.append(pp.PageRow(pp.LEAD_BODY, (), (pp.PageRule(dy=4.0),)))
        rows += _line(f"Accepted on {stamp['accepted_date']} by {stamp['accepted_name']}", bold=True)
        rows += _line(
            f"Submitted online {stamp['accepted_at']} · ticked 'I have read and agree'",
            muted=True,
            size=pp.SIZE_SMALL,
        )
    return rows


def render_untagged(
    facts: dict[str, Any], body: str, *, stamp: dict[str, Any] | None = None
) -> bytes:
    """The PRE-2026-10-23 page (`page_print`, Base-14, untagged). Parity only."""
    pp = _pp()
    printed = pp.render([_rows(facts, body, stamp)], footer=str(facts["agreement_name"]))
    return printed.data


#: The agreement's own stylesheet, on the bill's palette and scale
#: (`documents.DOCUMENT_STYLESHEET`'s values) so the two papers look related.
AGREEMENT_STYLESHEET = """
@page{size:letter;margin:0.78in 0.78in 0.9in}
body{margin:0;color:#201e1d;font-size:9pt;line-height:1.45}
.utility{margin:0 0 4pt;font-size:15pt;font-weight:700}
h1{margin:0 0 4pt;font-size:12pt;font-weight:700}
.meta{margin:0;font-size:8pt;color:#6b6664}
.body{margin-top:12pt}
.body p{margin:0 0 3pt}
.body .gap{height:9pt}
.stamp{margin-top:20pt;border-top:0.7pt solid #d8d5d3;padding-top:6pt}
.stamp p{margin:0 0 2pt}
.stamp .accepted{font-weight:700}
"""


def html(
    facts: dict[str, Any],
    body: str,
    *,
    stamp: dict[str, Any] | None = None,
    language: str | None = None,
) -> str:
    """The agreement as HTML — the input to the tagged page. Every value escaped."""
    import html as _html

    def esc(value: Any) -> str:
        return _html.escape(str(value), quote=True)

    lang = (language or "en").strip() or "en"
    # English chrome inside a non-English agreement says which language it is.
    en = "" if lang.split("-")[0].lower() == "en" else ' lang="en"'
    name = str(facts["agreement_name"])
    parts = [
        f'<!doctype html><html lang="{esc(lang)}"><head><meta charset="utf-8">'
        f"<title>{esc(name)}</title><style>{AGREEMENT_STYLESHEET}</style></head><body><article>"
    ]
    if facts.get("utility_name"):
        parts.append(f'<p class="utility">{esc(facts["utility_name"])}</p>')
    parts.append(f"<h1>{esc(name)}</h1>")
    version = f"Version {facts['version']}"
    if facts.get("effective_from"):
        version += f" · effective {facts['effective_from']}"
    parts.append(f'<p class="meta"{en}>{esc(version)}</p>')
    parts.append(
        f'<p class="meta"><span{en}>Account</span> {esc(facts["account_no"])} · '
        f'{esc(facts["customer_name"])}</p>'
    )
    parts.append('<div class="body">')
    for paragraph in str(body or "").replace("\r\n", "\n").split("\n"):
        if paragraph.strip():
            parts.append(f"<p>{esc(paragraph)}</p>")
        else:
            parts.append('<div class="gap" aria-hidden="true"></div>')
    parts.append("</div>")
    if stamp is not None:
        parts.append(
            f'<section class="stamp"><p class="accepted"><span{en}>Accepted on</span> '
            f'{esc(stamp["accepted_date"])} <span{en}>by</span> {esc(stamp["accepted_name"])}</p>'
            f'<p class="meta"{en}>Submitted online {esc(stamp["accepted_at"])} · ticked '
            "&#39;I have read and agree&#39;</p></section>"
        )
    parts.append("</article></body></html>")
    return "".join(parts)


def render(
    facts: dict[str, Any],
    body: str,
    *,
    stamp: dict[str, Any] | None = None,
    language: str | None = None,
) -> bytes:
    """The PDF bytes — a tagged PDF/UA-1 file (`DEF-BIL-10546`). `facts` =
    `{utility_name, agreement_name, version, effective_from, account_no,
    customer_name}`; `stamp` = `{accepted_date, accepted_name, accepted_at}`
    for the accepted copy; `language` is the agreement's published language."""
    from core import tagged_pdf

    printed = tagged_pdf.render(
        html(facts, body, stamp=stamp, language=language),
        footer=str(facts["agreement_name"]),
    )
    return printed.data


__all__ = ["html", "render", "render_untagged"]
