"""Merge the records of every job into JUnit XML and a Markdown summary.

The run fails when a record fails, when an OS job broke before writing its
records, and in strict mode when a check was skipped for a reason other than
design (a missing tool, a task not merged yet).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

from .records import Record, read_jsonl

MAX_LISTED = 200


def failing(record: Record, strict: bool) -> bool:
    return record.status == "fail" or (strict and record.status == "skip" and not record.by_design)


def job_records(job_results: dict[str, str], records: list[Record]) -> list[Record]:
    """A fail record for every OS job that broke without leaving records."""
    seen = {r.os for r in records}
    extra = []
    for os_name, result in sorted(job_results.items()):
        if result in ("failure", "cancelled") and os_name not in seen:
            extra.append(Record(os_name, f"{os_name} job", "", "required", "fail",
                                f"the {os_name} job ended with {result} before writing its records"))
    return extra


def load_all(folder: Path) -> list[Record]:
    records = []
    for path in sorted(folder.rglob("report-*.jsonl")):
        records += read_jsonl(path)
    return records


def junit(records: list[Record], strict: bool) -> str:
    suites: dict[tuple[str, str], list[Record]] = defaultdict(list)
    for record in records:
        suites[(record.os, record.check)].append(record)
    root = ET.Element("testsuites", name="cosmyx-artifact-checks")
    total = fails = skips = 0
    for (os_name, check), items in sorted(suites.items()):
        suite = ET.SubElement(root, "testsuite", name=f"{os_name}.{check}")
        suite_fails = suite_skips = 0
        for record in items:
            name = f"{record.artifact}: {record.path}" if record.path else record.artifact
            case = ET.SubElement(suite, "testcase", classname=f"{os_name}.{check}", name=name)
            if failing(record, strict):
                ET.SubElement(case, "failure", message=record.reason or record.status)
                suite_fails += 1
            elif record.status == "skip":
                ET.SubElement(case, "skipped", message=record.reason)
                suite_skips += 1
            elif record.status == "warn":
                ET.SubElement(case, "system-out").text = f"warning: {record.reason}"
        suite.set("tests", str(len(items)))
        suite.set("failures", str(suite_fails))
        suite.set("skipped", str(suite_skips))
        total += len(items)
        fails += suite_fails
        skips += suite_skips
    root.set("tests", str(total))
    root.set("failures", str(fails))
    root.set("skipped", str(skips))
    ET.indent(root)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode") + "\n"


def _line(record: Record) -> str:
    where = f"{record.artifact}" + (f" `{record.path}`" if record.path else "")
    return f"- **{record.os}/{record.check}** {where}: {record.reason}"


def markdown(records: list[Record], mode: str, strict: bool, run_url: str = "") -> str:
    lines = ["# Cosmyx artifact checks", ""]
    lines.append(f"Windows signing mode: **{mode}**; strict: **{'yes' if strict else 'no'}**."
                 + (f" Build run: {run_url}" if run_url else ""))
    lines += ["", "| OS | Check | Pass | Fail | Warn | Skip |", "|----|-------|------|------|------|------|"]
    counts: dict[tuple[str, str], Counter] = defaultdict(Counter)
    for record in records:
        counts[(record.os, record.check)]["fail" if failing(record, strict) else record.status] += 1
    for (os_name, check), counter in sorted(counts.items()):
        lines.append(f"| {os_name} | {check} | {counter['pass']} | {counter['fail']} | {counter['warn']} | {counter['skip']} |")
    fails = [r for r in records if failing(r, strict)]
    warns = [r for r in records if r.status == "warn"]
    for title, items in (("Failures", fails), ("Warnings", warns)):
        if items:
            lines += ["", f"## {title} ({len(items)})", ""]
            lines += [_line(r) for r in items[:MAX_LISTED]]
            if len(items) > MAX_LISTED:
                lines.append(f"- ... and {len(items) - MAX_LISTED} more (see junit.xml)")
    if not records:
        lines += ["", "No records: nothing was checked."]
    lines += ["", "**Result: " + ("failed" if fails else "passed") + "**", ""]
    return "\n".join(lines)


def write(records: list[Record], out: Path, mode: str, strict: bool, run_url: str = "") -> bool:
    """Write junit.xml and report.md; True when the run passes."""
    out.mkdir(parents=True, exist_ok=True)
    (out / "junit.xml").write_text(junit(records, strict), encoding="utf-8", newline="\n")
    (out / "report.md").write_text(markdown(records, mode, strict, run_url), encoding="utf-8", newline="\n")
    return not any(failing(r, strict) for r in records)
