"""Report of a goldens run: report.md (step summary, pull request) and
report.json (read back by update and fetch)."""

from __future__ import annotations

import json
from pathlib import Path

from .compare import Result

ICON = {"pass": "pass", "fail": "FAIL", "missing": "NEW", "gone": "GONE"}


def write(out: Path, os_name: str, results: list[Result], fails: list[dict], stability: list[Result] | None,
          drift: list[str], notes: list[str]) -> bool:
    ok = bool(results) and all(r.status == "pass" for r in results) and not fails and \
        (stability is None or all(r.status == "pass" for r in stability))
    out.mkdir(parents=True, exist_ok=True)
    data = {"os": os_name, "ok": ok,
            "results": [r.__dict__ for r in results],
            "fails": fails,
            "stability": None if stability is None else [r.__dict__ for r in stability],
            "drift": drift, "notes": notes}
    (out / "report.json").write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    lines = [f"## GUI goldens: {os_name}: {'pass' if ok else 'FAIL'}", ""]
    counts: dict[str, int] = {}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1
    lines.append(", ".join(f"{ICON[k]} {v}" for k, v in sorted(counts.items())) or "no surfaces compared")
    lines.append("")
    for note in notes:
        lines.append(f"- {note}")
    for fail in fails:
        lines.append(f"- driver: `{fail.get('id')}`: {fail.get('reason')}")
    bad = [r for r in results if r.status != "pass"]
    if bad:
        lines += ["", "| Surface | State | Why |", "|---|---|---|"]
        lines += [f"| `{r.name}` | {ICON[r.status]} | {r.reason} |" for r in bad]
    if stability is not None:
        unstable = [r for r in stability if r.status != "pass"]
        lines += ["", f"Stability (two passes): {'stable' if not unstable else f'{len(unstable)} unstable'}"]
        lines += [f"- `{r.name}`: {r.reason}" for r in unstable]
    if drift:
        lines += ["", "Environment drift (reported only):"] + [f"- {d}" for d in drift]
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return ok


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
