#!/usr/bin/env python3
"""Run veraPDF PDF/UA-1 over a fake-data sample of EVERY customer PDF type.

Group H (F-06), decision log 2026-10-23 *"Portal accessibility, Group H (bill
PDF, F-06)"*: veraPDF PDF/UA-1 must report 0 failed rules on a sample of every
in-scope type x utility layout x language.

WHAT IT SAMPLES (from `06-backend/tests/a11y_pdf_samples.py`, the same samples
the pytest suite reads):
  * the bill, in each of the five platform layouts (`documents.LAYOUT_SPECS`),
    for two utility set-ups (West Des Moines-like and Ann Arbor-like), in
    English and Spanish. Final bills, one-time bills and statements are the
    same document through the same writer, so they are covered by these.
  * the service agreement, as sent and as stamped, in English and Spanish.

`--writer old` renders through the pre-Group-H writers (the hand-written
Base-14 bill writer and `page_print`), which is the BEFORE figure; `--writer
new` (the default) renders through `core.tagged_pdf`, which is what a customer
receives from now on.

veraPDF IS NOT IN THE REPO. Install it once (Java 11+), e.g. from Maven
Central — `org.verapdf.apps:greenfield-apps:1.28.2` and its dependencies —
and point `--verapdf-classpath` (or `VERAPDF_CLASSPATH`) at the jar folder,
or `--verapdf` at a `verapdf` launcher script. Without either it still writes
the PDFs and says plainly that nothing was validated.

    python3 10-scripts/a11y/verapdf_customer_pdfs.py --out /tmp/h --writer new \
        --verapdf-classpath '/opt/verapdf/lib/*'

Exit status: 0 when every sample passes, 1 when any fails, 2 when nothing could
be validated.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "06-backend"


def _django() -> None:
    sys.path.insert(0, str(BACKEND))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.test")
    import django

    django.setup()


def samples(writer: str):
    """Yield `(name, type, layout, language, bytes)` for every sample."""
    from apps.billing import documents
    from apps.customers import agreement_pdf

    from tests import a11y_pdf_samples as s

    for utility in s.UTILITIES:
        for language in s.LANGUAGES:
            for spec in documents.LAYOUT_SPECS:
                document, spec = s.bill_document(utility, language, spec.key)
                if writer == "old":
                    data = documents._pdf(document, spec).data
                else:
                    data = documents.LAYOUTS_BY_KEY[spec.key].tagged_pdf(document).data
                yield (f"bill-{utility}-{spec.key}-{language}", "bill", spec.key, language, data)
    for language in s.LANGUAGES:
        for stamped in (False, True):
            facts, body, stamp, lang = s.agreement_inputs(language, stamped=stamped)
            if writer == "old":
                data = agreement_pdf.render_untagged(facts, body, stamp=stamp)
            else:
                data = agreement_pdf.render(facts, body, stamp=stamp, language=lang)
            kind = "agreement-stamped" if stamped else "agreement"
            yield (f"{kind}-{language}", kind, "agreement", language, data)


def validate(paths: list[Path], launcher: list[str]) -> dict[Path, tuple[str, int, int]]:
    """`{path: (PASS|FAIL, failed_rules, failed_checks)}` from veraPDF's MRR XML."""
    result: dict[Path, tuple[str, int, int]] = {}
    for path in paths:
        run = subprocess.run(
            [*launcher, "--flavour", "ua1", "--format", "mrr", str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
        xml = run.stdout
        summary = re.search(
            r'<validationReport[^>]*isCompliant="(true|false)".*?<details passedRules="(\d+)" '
            r'failedRules="(\d+)" passedChecks="(\d+)" failedChecks="(\d+)"',
            xml,
            re.S,
        )
        if not summary:
            result[path] = ("ERROR", -1, -1)
            continue
        verdict = "PASS" if summary.group(1) == "true" else "FAIL"
        result[path] = (verdict, int(summary.group(3)), int(summary.group(5)))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--out", required=True, help="folder for the sample PDFs")
    parser.add_argument("--writer", choices=("old", "new"), default="new")
    parser.add_argument("--verapdf", help="a verapdf launcher script")
    parser.add_argument(
        "--verapdf-classpath",
        default=os.environ.get("VERAPDF_CLASSPATH"),
        help="classpath of the veraPDF greenfield jars, e.g. '/opt/verapdf/lib/*'",
    )
    args = parser.parse_args()
    _django()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    written: list[tuple[str, str, str, str, Path]] = []
    for name, kind, layout, language, data in samples(args.writer):
        path = out / f"{args.writer}-{name}.pdf"
        path.write_bytes(data)
        written.append((name, kind, layout, language, path))
    print(f"wrote {len(written)} sample PDFs to {out} (writer: {args.writer})")

    launcher: list[str] | None = None
    if args.verapdf:
        launcher = [args.verapdf]
    elif args.verapdf_classpath and shutil.which("java"):
        launcher = ["java", "-cp", args.verapdf_classpath, "org.verapdf.apps.GreenfieldCliWrapper"]
    if launcher is None:
        print("veraPDF NOT RUN: no --verapdf or --verapdf-classpath given; 0 samples validated.")
        return 2
    verdicts = validate([row[-1] for row in written], launcher)
    failures = 0
    print(f"{'sample':58} {'verdict':7} {'rules':>5} {'checks':>6}")
    for name, _kind, _layout, _language, path in written:
        verdict, rules, checks = verdicts[path]
        failures += verdict != "PASS"
        print(f"{name:58} {verdict:7} {rules:>5} {checks:>6}")
    print(f"{len(written) - failures} of {len(written)} samples pass PDF/UA-1; {failures} do not.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
