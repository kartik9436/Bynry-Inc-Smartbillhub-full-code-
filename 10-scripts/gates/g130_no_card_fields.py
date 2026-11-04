#!/usr/bin/env python3
"""G130 — the New World card attributes may appear, and may NEVER carry a value.

WHY THIS GATE EXISTS (CR-132-BRC07, 2026-09-22)
------------------------------------------------
Tyler's New World / Logos receipt format carries four card fields:

    ReceiptPaymentCreditCardNumber
    ReceiptPaymentCreditCardType
    ReceiptPaymentCreditCardExpirationDate
    ReceiptPaymentCreditCardValidationNumber

**Populating any one of them pulls cardholder data into a file and destroys the
PCI scoping that keeps card data out of this product entirely.** A card payment
leaves as `ReceiptPaymentType = 2` (Charge) with no card number.

⚠ **THE RULE CHANGED ON 2026-10-21 — FOR THE NAMES ONLY (`DEF-INT-10304`).**
From 2026-09-22 until then the PO's posture was *not built — NOT BUILT*, and
this gate failed if one of the four NAMES appeared as a quoted string, an XML
element or an identifier at all. On 2026-10-21 New World's confirmed template
turned out to list all four as attributes, and the PO ruled, verbatim:
*"Option A — Always write all four as `""`"* (decision log 2026-10-21,
*"New World / Logos receipt XML: attributes on a `<ROOT>` document; five
answers"*, answer 2). **The names now travel, always empty. Card DATA stays out
of the product.** So this gate changed from *"the names never appear"* to
*"the names may appear only with an empty value, and any code that could give
one of them a value fails"*.

⚠ **WHY A GATE AND NOT A COMMENT.** A rule that lives only in a docstring is a
note (hard-won law 1). The realistic way this breaks is a lane reading their
specification beside our emitter, seeing four attributes we write empty, and
helpfully "completing" them — passing every test, because nothing else in this
repository has an opinion about those four values.

WHAT IT CHECKS
--------------
**Python** (every `.py` in scope), by parsing — so prose in docstrings and
comments may name the fields, which is how a file explains the rule:

  1. **One home for the names.** A non-docstring string literal containing the
     prefix `ReceiptPaymentCreditCard` may appear ONLY as an element of the
     module-level tuple `CARD_ATTRIBUTES` in `apps/integrations/newworld.py`,
     and that tuple must be exactly the four names. Anywhere else —
     `node.set("ReceiptPaymentCreditCardNumber", x)`, a dict key, an f-string,
     a concatenation of the prefix — is a FAIL. That closes every write that
     names the field directly.
  2. **The one home can only be used to write `""`.** Every read of
     `CARD_ATTRIBUTES` must be either
       * the iterable of a `for` loop in whose body every write that uses the
         loop variable as the attribute name — `.set(name, …)`,
         `.setdefault`/`.update`, `setattr`, `x[name] = …`, `{name: …}`,
         `dict(name=…)` — writes the literal `""`; or
       * the right-hand side of an `in` / `not in` test (a READ).
     Anything else — `zip(CARD_ATTRIBUTES, values)`, `*CARD_ATTRIBUTES`,
     `dict.fromkeys(CARD_ATTRIBUTES, x)`, passing it to a function, aliasing
     it — is a FAIL, because each is a way a value could be paired with a name.
  3. **No identifier or keyword argument is named for one**, unless a keyword
     argument's value is the literal `""` (`ET.SubElement` turns keyword
     arguments into attributes).

**Every other file in scope** (fixtures, JSON, Markdown): the name as an XML
ELEMENT fails; the name as an attribute (`Name="…"`) or a JSON key
(`"Name": …`) fails unless its value is empty. Prose (backticks) is allowed.

The test whose job is to break the validator on purpose
(`tests/test_cr132_newworld_receipts.py`) is the NAME_HOLDER and is exempt: it
plants a value to prove the refusal, and that IS the check.

⚠ **WHAT WOULD MAKE THIS PASS WRONGLY** (law 7, habit 2), and how each is
closed:

  * **the scope shrinking under it.** The scope is a DIRECTORY SWEEP of
    `06-backend/apps/integrations/` and the detail line prints how many files
    were read on every run — a blind spot with no number is indistinguishable
    from an empty one.
  * **the file list coming back empty.** A sweep of nothing would pass, so the
    gate FAILS when it reads no files.
  * **the home moving or being renamed.** If `CARD_ATTRIBUTES` vanished, rule 1
    would turn every surviving literal into a FAIL; and if no literal survived,
    the builder writes no card attribute, which `newworld.validate` refuses.
    The gate also FAILS outright if the home is missing or not exactly the four.
  * **a value arriving through a path this AST walk does not model** (a name
    built at runtime from data, `getattr` games). Rule 1 removes the only
    source of the names in code; a name built from data rather than a literal
    would also have to defeat `newworld.validate`, which refuses any file whose
    card attribute is not empty before it is sent or served. Two independent
    layers, deliberately.

PROVED RED BEFORE IT WAS TRUSTED GREEN, THROUGH `run_gates` AND NOT THROUGH
`python3 g130_no_card_fields.py` — hard-won law 7's second half
(`DEF-GOV-3733`). The 2026-10-21 red proofs: a planted `node.set(name,
self.check_number)` inside the loop, a planted `zip(CARD_ATTRIBUTES, …)`, and a
fixture attribute `ReceiptPaymentCreditCardNumber="4111"` — each FAIL naming
the file and line. ⚠ **A FOURTH PLANT FOUND A HOLE AND IT IS WHY PYTHON FILES
ARE ALWAYS PARSED:** `node.set("ReceiptPaymentCredit" "CardNumber", p.card)`
PASSED the first draft, because a raw-text pre-filter skipped any file whose
bytes did not spell the prefix. Removed, and compositions (`+`, f-strings of
literals, `"".join([...])`) are folded and checked too; the same plant and a
`"ReceiptPayment" + "Credit" + "CardType"` plant now both FAIL.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

#: The four field names, and the prefix they share.
CARD_FIELDS = (
    "ReceiptPaymentCreditCardNumber",
    "ReceiptPaymentCreditCardType",
    "ReceiptPaymentCreditCardExpirationDate",
    "ReceiptPaymentCreditCardValidationNumber",
)
CARD_PREFIX = "ReceiptPaymentCreditCard"

#: The one home of the names in code.
HOME_FILE = "06-backend/apps/integrations/newworld.py"
HOME_NAME = "CARD_ATTRIBUTES"

#: Where a card value could reach a partner's file from.
SCOPES = (
    "06-backend/apps/integrations",
    "06-backend/tests/test_cr132_newworld_receipts.py",
)

SUFFIXES = {".py", ".xml", ".json", ".md", ""}

#: The one file allowed to plant a card VALUE: the test that proves
#: `newworld.validate` refuses one. Naming it here rather than widening a
#: pattern is the discipline `tests/test_be_default_authentication.py` applies.
NAME_HOLDER = "06-backend/tests/test_cr132_newworld_receipts.py"

#: Calls that write a key/value pair when the key is their first argument.
_WRITE_METHODS = {"set", "setdefault", "update", "__setitem__", "put"}

#: Non-Python files: an element, an attribute, a JSON key.
_ELEMENT = re.compile(r"<\s*/?\s*(ReceiptPaymentCreditCard\w*)")
_ATTRIBUTE = re.compile(r"""(ReceiptPaymentCreditCard\w*)\s*=\s*(["'])(.*?)\2""")
_JSON_KEY = re.compile(r'"(ReceiptPaymentCreditCard\w*)"\s*:\s*("(?:[^"\\]|\\.)*"|[^\s,}\]]+)')


def _files() -> list[Path]:
    found: list[Path] = []
    for scope in SCOPES:
        target = ROOT / scope
        if target.is_file():
            found.append(target)
            continue
        if not target.is_dir():
            continue
        for path in sorted(target.rglob("*")):
            if path.is_file() and path.suffix in SUFFIXES and "__pycache__" not in path.parts:
                found.append(path)
    return found


def _is_empty_literal(node: ast.AST | None) -> bool:
    return isinstance(node, ast.Constant) and node.value == ""


def _docstring_ids(tree: ast.AST) -> set[int]:
    """`id()` of every string constant that is a bare expression statement —
    a docstring or a stray string — which is prose, not data."""
    out: set[int] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            out.add(id(node.value))
    return out


def _fold(node: ast.AST | None) -> str | None:
    """The string a composition of literals evaluates to, or `None`."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _fold(node.left), _fold(node.right)
        return None if left is None or right is None else left + right
    if isinstance(node, ast.JoinedStr):
        parts = [_fold(one) for one in node.values]
        return None if any(one is None for one in parts) else "".join(parts)  # type: ignore[arg-type]
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "join"
        and len(node.args) == 1
        and isinstance(node.args[0], (ast.List, ast.Tuple))
    ):
        glue = _fold(node.func.value)
        parts = [_fold(one) for one in node.args[0].elts]
        if glue is None or any(one is None for one in parts):
            return None
        return glue.join(parts)  # type: ignore[arg-type]
    return None


def _parents(tree: ast.AST) -> dict[int, ast.AST]:
    parent: dict[int, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parent[id(child)] = node
    return parent


def _home_tuple(tree: ast.Module) -> ast.Tuple | None:
    for stmt in tree.body:
        targets: list[ast.AST] = []
        value = None
        if isinstance(stmt, ast.Assign):
            targets, value = stmt.targets, stmt.value
        elif isinstance(stmt, ast.AnnAssign):
            targets, value = [stmt.target], stmt.value
        for target in targets:
            if isinstance(target, ast.Name) and target.id == HOME_NAME and isinstance(value, ast.Tuple):
                return value
    return None


def _refers_to_home(node: ast.AST) -> bool:
    return (isinstance(node, ast.Name) and node.id == HOME_NAME) or (
        isinstance(node, ast.Attribute) and node.attr == HOME_NAME
    )


def _uses(node: ast.AST, var: str) -> bool:
    return any(isinstance(one, ast.Name) and one.id == var for one in ast.walk(node))


def _loop_writes_only_empty(loop: ast.For) -> str | None:
    """`None` when every write keyed by the loop variable writes `""`; else why not."""
    if not isinstance(loop.target, ast.Name):
        return "the loop target is not a plain name"
    var = loop.target.id
    for node in ast.walk(ast.Module(body=loop.body, type_ignores=[])):
        if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign, ast.NamedExpr)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name) and target.id == var:
                    return f"the loop variable {var} is reassigned"
                if isinstance(target, ast.Subscript) and _uses(target.slice, var):
                    value = getattr(node, "value", None)
                    if isinstance(node, ast.AugAssign) or not _is_empty_literal(value):
                        return f"a subscript keyed by {var} is given a non-empty value"
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if key is not None and _uses(key, var) and not _is_empty_literal(value):
                    return f"a dict keyed by {var} holds a non-empty value"
        if isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            if name in _WRITE_METHODS or name == "setattr":
                args = list(node.args)
                if name == "setattr":
                    args = args[1:]
                if args and _uses(args[0], var):
                    if name != "set" and name != "setattr":
                        return f".{name}() keyed by {var}"
                    if len(args) < 2 or not _is_empty_literal(args[1]):
                        return f".{name}({var}, …) with a value other than the literal \"\""
            for keyword in node.keywords:
                if keyword.arg is None and _uses(keyword.value, var):
                    return f"**-expansion involving {var}"
    return None


def _check_python(relative: str, text: str, hits: list[str]) -> tuple[bool, str | None]:
    """Appends hits; returns `(home_found, home_problem)` for the home file."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return False, None
    prose = _docstring_ids(tree)
    parent = _parents(tree)
    is_home = relative == HOME_FILE
    home = _home_tuple(tree) if is_home else None
    home_ids: set[int] = set()
    home_problem = None
    if is_home:
        if home is None:
            home_problem = f"{HOME_FILE} has no module-level tuple {HOME_NAME}"
        else:
            values = [one.value for one in home.elts if isinstance(one, ast.Constant)]
            if tuple(values) != CARD_FIELDS or len(values) != len(home.elts):
                home_problem = f"{HOME_NAME} is not exactly the four card names"
            home_ids = {id(one) for one in home.elts}

    for node in ast.walk(tree):
        line = getattr(node, "lineno", 0)
        # 1 — one home for the names
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if CARD_PREFIX in node.value and id(node) not in prose and id(node) not in home_ids:
                hits.append(f"{relative}:{line} — the name written outside {HOME_NAME}")
        # 1b — …or COMPOSED: `"ReceiptPayment" + "CreditCardNumber"`, an
        # f-string of literals, `"".join([...])`.
        folded = _fold(node)
        if folded is not None and CARD_PREFIX in folded and not (
            isinstance(node, ast.Constant)
        ):
            up = parent.get(id(node))
            if _fold(up) is None:  # report the outermost composition once
                hits.append(f"{relative}:{line} — the name composed outside {HOME_NAME}")
        # 3 — identifiers and keyword arguments
        if isinstance(node, ast.Name) and node.id.startswith(CARD_PREFIX):
            hits.append(f"{relative}:{line} — identifier {node.id}")
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name.startswith(CARD_PREFIX):
            hits.append(f"{relative}:{line} — definition {node.name}")
        if isinstance(node, ast.keyword) and (node.arg or "").startswith(CARD_PREFIX):
            if not _is_empty_literal(node.value):
                hits.append(f"{relative}:{line} — keyword {node.arg} with a value")
        # 2 — the home can only be used to write ""
        if _refers_to_home(node) and isinstance(getattr(node, "ctx", None), ast.Load):
            up = parent.get(id(node))
            if isinstance(up, ast.For) and up.iter is node:
                why = _loop_writes_only_empty(up)
                if why:
                    hits.append(f"{relative}:{line} — loop over {HOME_NAME}: {why}")
            elif (
                isinstance(up, ast.Compare)
                and node in up.comparators
                and all(isinstance(op, (ast.In, ast.NotIn)) for op in up.ops)
            ):
                pass
            elif isinstance(up, ast.Attribute):
                hits.append(f"{relative}:{line} — {HOME_NAME}.{up.attr} (only a loop or an `in` test may read it)")
            else:
                hits.append(
                    f"{relative}:{line} — {HOME_NAME} used as {type(up).__name__} "
                    "(only a loop writing \"\" or an `in` test may read it)"
                )
    return home is not None, home_problem


def _check_text(relative: str, text: str, hits: list[str]) -> None:
    for number, line in enumerate(text.splitlines(), start=1):
        for match in _ELEMENT.finditer(line):
            hits.append(f"{relative}:{number} — element <{match.group(1)}>")
        for match in _ATTRIBUTE.finditer(line):
            if match.group(3) != "":
                hits.append(f"{relative}:{number} — {match.group(1)} carries a value")
        for match in _JSON_KEY.finditer(line):
            if match.group(2) != '""':
                hits.append(f"{relative}:{number} — {match.group(1)} carries a value")


def check() -> tuple[list[str], int]:
    """`(hits, files_read)`."""
    hits: list[str] = []
    files = _files()
    home_seen = False
    for path in files:
        relative = path.relative_to(ROOT).as_posix()
        if relative == NAME_HOLDER:
            # The test that plants a value to prove the validator refuses it.
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if relative == HOME_FILE:
            found, problem = _check_python(relative, text, hits)
            home_seen = found
            if problem:
                hits.append(problem)
            continue
        if path.suffix == ".py":
            # ⚠ NO RAW-TEXT SHORTCUT FOR PYTHON. `"ReceiptPaymentCredit"
            # "CardNumber"` never spells the prefix in the file's bytes and
            # IS the name once parsed — a pre-filter on the text let exactly
            # that through on 2026-10-21, found by the red proof.
            _check_python(relative, text, hits)
        elif CARD_PREFIX in text:
            _check_text(relative, text, hits)
    if files and not home_seen and not any(HOME_FILE in one for one in hits):
        hits.append(f"{HOME_FILE}: no {HOME_NAME} found — the one home of the names moved")
    return hits, len(files)


def run():
    """Runner contract: ('PASS'|'FAIL'|'SKIP', detail).

    ⚠ THE DETAIL PRINTS THE FILE COUNT ON A PASS TOO. A green line that does
    not say how much it read cannot be told apart from a green line that read
    nothing (law 7).
    """
    hits, files = check()
    if not files:
        return "FAIL", (
            "read 0 files — the scope is wrong or the integrations directory moved. "
            "A sweep of nothing passes cleanly, so this is a FAIL by construction."
        )
    if hits:
        return "FAIL", (
            f"{len(hits)} New World card attribute problem(s) in {files} file(s): {hits[0]} — "
            "the four card attributes are written present and ALWAYS \"\" (PO 2026-10-21, "
            "option A); a value would pull cardholder data into a partner file and destroy "
            "this product's PCI scoping."
        )
    return "PASS", (
        f"no New World card attribute can carry a value; {files} file(s) read "
        f"(names only in {HOME_NAME}, written as \"\"; prose naming them is allowed)"
    )


def main() -> int:
    status, detail = run()
    print(f"G130 {status}: {detail}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
