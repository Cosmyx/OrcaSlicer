"""Cosmyx GUI goldens, command line (wiki/cosmyx/gui-goldens.md).

    cli.py resolve   --run RUN.json --artifacts-list LIST.jsonl --changed FILES.txt --mode M --stability S
                     --event E [--github-output FILE]
    cli.py run       --os OS --artifacts DIR --subject DIR --out DIR [--passes N]
    cli.py compare   --os OS --goldens DIR --actual DIR --subject DIR --out DIR [--second DIR]
                     [--gcode FILE] [--step-summary FILE] [--report-only]
    cli.py update    --goldens DIR --actual DIR --report REPORT.json
    cli.py stability --os OS --first DIR --second DIR --subject DIR
    cli.py fetch     --run-id ID [--repo OWNER/NAME] [--goldens-root DIR]
    cli.py review    [--goldens-root DIR] --out DIR
    cli.py local     --run-id ID [--repo OWNER/NAME] [--passes N]

The CI runs it with `python -I`, so this file puts scripts/cosmyx on sys.path
itself; artifact_checks (T13 slice checks, T16a Mesa download) is imported
from there at run time, from the trusted checkout of the workflow.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gui_goldens import GUI_DIR, OSES, REPO_ROOT, GoldenError  # noqa: E402
from gui_goldens import compare as compare_mod  # noqa: E402
from gui_goldens import launch, masks, protocol, report, seed  # noqa: E402
from gui_goldens import png as png_mod  # noqa: E402

GOLDENS_DIR = GUI_DIR / "goldens"
STEP_TIMEOUT_S = 40   # the driver's own step timeout is 30 s
PASS_TIMEOUT_S = 40 * 60
DRIFT_KEYS = ("GL_RENDERER", "GL_VERSION", "display", "scale", "platform")
STABILITY_PATHS = ("tests/cosmyx/gui/", "scripts/cosmyx/gui_goldens/", "src/slic3r/GUI/Cosmyx/Golden",
                   "src/slic3r/GUI/Cosmyx/logic/Golden")
MIN_G1_MOVES = 100


def boolean(text: str) -> bool:
    return str(text).strip().lower() in ("1", "true", "yes")


# ---------------------------------------------------------------------------
# one pass


class Pass:
    """Answers the driver's events until it is done: captures, stores, acks."""

    def __init__(self, driver_dir: Path, images: Path, capturer, webview_mask: bool,
                 alive: Callable[[], bool] = lambda: True, clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep, step_timeout: float = STEP_TIMEOUT_S,
                 pass_timeout: float = PASS_TIMEOUT_S):
        self.driver_dir, self.images, self.capturer = driver_dir, images, capturer
        self.webview_mask, self.alive, self.clock, self.sleep = webview_mask, alive, clock, sleep
        self.step_timeout, self.pass_timeout = step_timeout, pass_timeout
        self.hello: dict | None = None
        self.fails: list[dict] = []
        self.done: dict | None = None
        # Surface ids already written in this pass: a second event with the same id would overwrite the
        # first file and lose that state silently (decision 0179).
        self.stored: set[str] = set()

    def handle(self, event: dict) -> None:
        kind = event["event"]
        if kind == "hello":
            self.hello = event
            self.capturer.park_pointer()
        elif kind == "capture":
            try:
                self.claim(protocol.image_file_name(event["id"]))
                self.store(event)
            except GoldenError as error:
                self.fails.append({"id": event["id"], "reason": f"capture failed: {error}"})
            protocol.ack(self.driver_dir, event["seq"])
        elif kind == "text":
            try:
                name = self.claim(protocol.text_file_name(event["id"]))
            except GoldenError as error:
                self.fails.append({"id": event["id"], "reason": f"text failed: {error}"})
                return
            self.images.mkdir(parents=True, exist_ok=True)
            (self.images / name).write_text(event["content"], encoding="utf-8", newline="\n")
        elif kind == "fail":
            self.fails.append({"id": event["id"], "reason": event["reason"]})
        elif kind == "done":
            self.done = event

    def claim(self, name: str) -> str:
        """The file name, once per pass; GoldenError when an earlier event already wrote it."""
        if name in self.stored:
            raise GoldenError(f"duplicate surface: {name} was already written in this pass")
        self.stored.add(name)
        return name

    def store(self, event: dict) -> None:
        kind = event["kind"]
        if kind == "menu":
            try:
                image = self.capturer.popup()
            finally:
                self.capturer.escape()
        elif kind == "menubar":
            try:
                image = self.capturer.menubar(event.get("menu", ""))
            finally:
                self.capturer.escape()
        else:
            image = self.capturer.rect(event["rect_px"], event["scale"])
            rects = list(event["masks"]) + (list(event["webviews"]) if self.webview_mask else [])
            image = masks.apply(image, rects)
        png_mod.write(self.images / protocol.image_file_name(event["id"]), image)

    def run(self) -> None:
        reader = protocol.EventReader(self.driver_dir)
        start = last = self.clock()
        while self.done is None:
            events = reader.poll()
            for event in events:
                self.handle(event)
            now = self.clock()
            if events:
                last = now
                continue
            if not self.alive():
                self.fails.append({"id": "harness", "reason": "the application exited before the done event"})
                return
            if now - last > self.step_timeout:
                self.fails.append({"id": "harness", "reason": f"no event from the driver for {self.step_timeout:.0f} s"})
                return
            if now - start > self.pass_timeout:
                self.fails.append({"id": "harness", "reason": f"the pass took more than {self.pass_timeout / 60:.0f} min"})
                return
            self.sleep(0.05)
        if self.hello is None:
            self.fails.append({"id": "harness", "reason": "the driver sent no hello event"})

    def environment(self, os_name: str) -> dict:
        hello = dict(self.hello or {})
        hello.pop("seq", None)
        hello.pop("event", None)
        hello.pop("version", None)
        hello["platform"] = f"{platform.system()} {platform.release()} {platform.machine()}"
        hello["os"] = os_name
        return hello


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def run_pass(os_name: str, app: launch.App, subject: Path, out: Path, tolerance: compare_mod.Tolerance) -> list[dict]:
    from gui_goldens.capture import Capturer  # noqa: PLC0415 (per-OS backend)

    driver_dir, datadir, images = out / "driver", out / "data", out / "images"
    for folder in (driver_dir, images):
        folder.mkdir(parents=True, exist_ok=True)
        for child in folder.iterdir():
            if child.is_file():
                child.unlink()
    seed.seed(datadir, subject / "version.inc")
    script = subject / "tests" / "cosmyx" / "gui" / "script.json"
    process = launch.start(app, datadir, driver_dir, script, os_name, out / "app.log")
    one = Pass(driver_dir, images, Capturer(os_name, app.process), tolerance.webview_mask,
               alive=lambda: process.poll() is None)
    try:
        one.run()
    finally:
        launch.stop(process)
    write_json(images / "environment.json", one.environment(os_name))
    gcode = driver_dir / "gcode" / "plate_1.gcode"
    if gcode.is_file():
        shutil.copy2(gcode, out / "plate_1.gcode")
    write_json(out / "fails.json", one.fails)
    return one.fails


def cmd_run(args) -> int:
    subject, out = Path(args.subject), Path(args.out)
    tolerance = compare_mod.load_tolerance(subject / "tests" / "cosmyx" / "gui" / "tolerance.json", args.os)
    displays = launch.start_display_for(args.os, os.environ)
    try:
        app = launch.prepare(args.os, Path(args.artifacts), out / "app")
        for index in range(1, args.passes + 1):
            fails = run_pass(args.os, app, subject, out / f"pass-{index}", tolerance)
            print(f"pass {index}: {len(fails)} driver or harness failure(s)")
    finally:
        for process in displays:
            process.kill()
    return 0


# ---------------------------------------------------------------------------
# comparison


def gcode_results(gcode: Path | None, version_inc: Path) -> list[compare_mod.Result]:
    """The UI slice must produce real G-code: the T13 checks (slice.py)."""
    if gcode is None:
        return []
    if not gcode.is_file():
        return [compare_mod.Result("90-slice-gcode", "fail", "the UI slice wrote no G-code")]
    try:
        from artifact_checks import slice as slice_mod  # noqa: PLC0415 (T13, runtime import)
    except ImportError:
        return [compare_mod.Result("90-slice-gcode", "fail", "artifact_checks.slice (T13) is not available")]
    identity = slice_mod.header_identity(version_inc.read_text(encoding="utf-8"))
    if identity is None:
        return [compare_mod.Result("90-slice-gcode", "fail", "version.inc has no app name or version")]
    problems = slice_mod.gcode_problems(gcode.read_text(encoding="utf-8", errors="replace"), identity[0], identity[1],
                                        MIN_G1_MOVES)
    return [compare_mod.Result("90-slice-gcode", "fail" if problems else "pass", "; ".join(problems[:5]))]


def drift(golden_dir: Path, actual_dir: Path) -> list[str]:
    try:
        before = json.loads((golden_dir / "environment.json").read_text(encoding="utf-8"))
        after = json.loads((actual_dir / "environment.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [f"{key}: {before.get(key)!r} -> {after.get(key)!r}" for key in DRIFT_KEYS if before.get(key) != after.get(key)]


def stability_results(first: Path, second: Path, tolerance: compare_mod.Tolerance) -> list[compare_mod.Result]:
    results = compare_mod.compare_dirs(first, second, compare_mod.halved(tolerance))
    for result in results:
        if result.status in ("missing", "gone"):
            result.status, result.reason = "fail", "produced by one pass only"
    return results


def cmd_compare(args) -> int:
    subject = Path(args.subject)
    tolerance = compare_mod.load_tolerance(subject / "tests" / "cosmyx" / "gui" / "tolerance.json", args.os)
    goldens, actual = Path(args.goldens), Path(args.actual)
    results = compare_mod.compare_dirs(goldens, actual, tolerance)
    results += gcode_results(Path(args.gcode) if args.gcode else None, subject / "version.inc")
    fails_file = actual.parent / "fails.json"
    fails = json.loads(fails_file.read_text(encoding="utf-8")) if fails_file.is_file() else []
    stability = stability_results(actual, Path(args.second), tolerance) if args.second else None
    notes = []
    if not compare_mod.golden_names(goldens):
        notes.append(f"no goldens committed for {args.os} yet: run `just goldens-gui-fetch <run id>` on this run")
    ok = report.write(Path(args.out), args.os, results, fails, stability, drift(goldens, actual), notes)
    text = (Path(args.out) / "report.md").read_text(encoding="utf-8")
    if args.step_summary:
        with open(args.step_summary, "a", encoding="utf-8", newline="\n") as summary:
            summary.write(text)
    print(text)
    return 0 if ok or args.report_only else 1


def cmd_stability(args) -> int:
    tolerance = compare_mod.load_tolerance(Path(args.subject) / "tests" / "cosmyx" / "gui" / "tolerance.json", args.os)
    results = stability_results(Path(args.first), Path(args.second), tolerance)
    for result in results:
        if result.status != "pass":
            print(f"{result.name}: {result.reason}")
    stable = compare_mod.passed(results)
    print("stable" if stable else "UNSTABLE")
    return 0 if stable else 1


def update(goldens: Path, actual: Path, data: dict) -> list[str]:
    """Rewrites the goldens that failed, adds the new ones, removes the gone
    ones; a golden that passed is never touched (decision 0172)."""
    changed = []
    goldens.mkdir(parents=True, exist_ok=True)
    for result in data.get("results", []):
        name, status = result["name"], result["status"]
        if not name.endswith(compare_mod.GOLDEN_SUFFIXES) or status == "pass":
            continue
        if status == "gone":
            (goldens / name).unlink(missing_ok=True)
        elif (actual / name).is_file():
            shutil.copy2(actual / name, goldens / name)
        changed.append(name)
    if (actual / "environment.json").is_file():
        shutil.copy2(actual / "environment.json", goldens / "environment.json")
    return changed


def cmd_update(args) -> int:
    changed = update(Path(args.goldens), Path(args.actual), report.read(Path(args.report)))
    print(f"{len(changed)} golden(s) updated")
    for name in changed:
        print(f"  {name}")
    return 0


def empty(folder: Path) -> None:
    """Empties a folder in place: a folder deleted and recreated at once can
    linger on an SMB share."""
    folder.mkdir(parents=True, exist_ok=True)
    for child in folder.iterdir():
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()


def cmd_fetch(args) -> int:
    gh = shutil.which("gh")
    if gh is None:
        print("gh (GitHub CLI) is needed to download the goldens of a run", file=sys.stderr)
        return 1
    root = Path(args.goldens_root)
    download = root.parent / ".fetch"
    empty(download)
    subprocess.run([gh, "run", "download", str(args.run_id), "--repo", args.repo, "--pattern", "cosmyx-gui-goldens-*",
                    "--dir", str(download)], check=True)
    total = 0
    for os_name in OSES:
        folder = download / f"cosmyx-gui-goldens-{os_name}"
        if not (folder / "report" / "report.json").is_file():
            continue
        changed = update(root / os_name, folder / "images", report.read(folder / "report" / "report.json"))
        total += len(changed)
        print(f"{os_name}: {len(changed)} golden(s) updated")
    empty(download)
    print(f"{total} golden(s) updated; review them with `just goldens-gui-review` before committing")
    return 0


def changed_goldens(root: Path) -> list[tuple[str, str]]:
    rel = root.resolve().relative_to(REPO_ROOT)
    done = subprocess.run(["git", "-C", str(REPO_ROOT), "status", "--porcelain", "--untracked-files=all", "--", str(rel)],
                          capture_output=True, text=True, check=True)
    entries = []
    for line in done.stdout.splitlines():
        state, path = line[:2].strip(), line[3:].strip().strip('"')
        if path.endswith(compare_mod.GOLDEN_SUFFIXES):
            entries.append((state, path))
    return sorted(entries, key=lambda item: item[1])


def cmd_review(args) -> int:
    """Before/after page of every golden changed in the working tree."""
    root, out = Path(args.goldens_root), Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for state, path in changed_goldens(root):
        name = path.replace("/", "_")
        before = out / f"before_{name}"
        shown = subprocess.run(["git", "-C", str(REPO_ROOT), "show", f"HEAD:{path}"], capture_output=True, check=False)
        has_before = shown.returncode == 0
        if has_before:
            before.write_bytes(shown.stdout)
        after = REPO_ROOT / path
        cell = lambda file, ok: (f'<img src="{html.escape(file.as_uri())}">' if path.endswith(".png") else
                                 f"<pre>{html.escape(file.read_text(encoding='utf-8'))}</pre>") if ok else "<i>none</i>"
        rows.append(f"<tr><td>{html.escape(path)}<br>{html.escape(state)}</td><td>{cell(before, has_before)}</td>"
                    f"<td>{cell(after, after.is_file())}</td></tr>")
    page = ("<!doctype html><meta charset=utf-8><title>GUI goldens review</title>"
            "<style>body{background:#222;color:#eee;font:14px sans-serif}img{max-width:640px}td{vertical-align:top}</style>"
            "<table><tr><th>Golden</th><th>Before (HEAD)</th><th>After</th></tr>" + "".join(rows) + "</table>\n")
    (out / "index.html").write_text(page, encoding="utf-8", newline="\n")
    print(f"{len(rows)} changed golden(s): {out / 'index.html'}")
    return 0


# ---------------------------------------------------------------------------
# resolve (workflow plan)


def default_classify():
    from artifact_checks import inventory  # noqa: PLC0415 (T13, runtime import)
    expectations = inventory.load_expectations()
    return lambda name: inventory.classify(name, expectations)


def pick_artifacts(names: list[str], classify) -> dict[str, str]:
    """The artifact each OS pass runs: the x64 portable build (not MSVC),
    the universal DMG (else arm64), the x86_64 AppImage."""
    found = {}
    preference = {"windows": [("windows-portable", "x64", False)],
                  "macos": [("mac-universal", "", False), ("mac-arm64", "", False)],
                  "linux": [("linux-appimage", "x86_64", False)]}
    classified = [a for a in (classify(n) for n in names) if a is not None]
    for os_name, wanted in preference.items():
        for family, arch, msvc in wanted:
            match = sorted(a.name for a in classified if a.family == family and (not arch or a.arch == arch) and
                           bool(getattr(a, "msvc", False)) == msvc)
            if match:
                found[os_name] = match[0]
                break
    return found


def resolve(run: dict, artifacts: list[dict], changed: list[str], mode: str, stability: str, event: str,
            classify) -> dict:
    head = (run.get("head_repository") or {}).get("full_name")
    exec_ok = head is not None and head == (run.get("repository") or {}).get("full_name")
    branch = run.get("head_branch") or ""
    conclusion = run.get("conclusion") or ""
    live = [a["name"] for a in artifacts if not a.get("expired")]
    picked = pick_artifacts(live, classify)
    reason = ""
    if conclusion != "success":
        reason = f"the build concluded {conclusion or 'without a result'}"
    elif not exec_ok:
        reason = "fork build: its binaries are never run (decision 0141)"
    elif set(picked) != set(OSES):
        reason = "no artifact to run for " + ", ".join(sorted(set(OSES) - set(picked)))
    touches = any(path.startswith(STABILITY_PATHS) for path in changed)
    two = stability == "on" or (stability == "auto" and (mode == "update" or event == "schedule" or touches))
    matrix = [{"os": os_name, "artifact": picked[os_name],
               "runner": {"linux": "ubuntu-24.04", "macos": "macos-15", "windows": "windows-2025"}[os_name]}
              for os_name in OSES if os_name in picked] if exec_ok and conclusion == "success" else []
    return {"head_sha": run.get("head_sha", ""), "head_branch": branch, "head_repo": head or "",
            "run_ok": "true" if not reason else "false", "reason": reason,
            "report_only": "true" if branch == "MIXED" else "false",
            "passes": "2" if two else "1", "mode": mode, "matrix": json.dumps(matrix)}


def read_artifact_list(path: Path) -> list[dict]:
    items = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            items += value["artifacts"] if isinstance(value, dict) and "artifacts" in value else [value]
    return items


def cmd_resolve(args) -> int:
    run = json.loads(Path(args.run).read_text(encoding="utf-8"))
    changed = Path(args.changed).read_text(encoding="utf-8").split() if args.changed and Path(args.changed).is_file() else []
    outputs = resolve(run, read_artifact_list(Path(args.artifacts_list)), changed, args.mode, args.stability, args.event,
                      default_classify())
    for key, value in outputs.items():
        print(f"{key}={value}")
    if args.github_output:
        with open(args.github_output, "a", encoding="utf-8", newline="\n") as out:
            for key, value in outputs.items():
                out.write(f"{key}={value}\n")
    return 0


# ---------------------------------------------------------------------------
# local


def docker_image_tag(dockerfile: Path) -> str:
    import hashlib  # noqa: PLC0415
    return "cosmyx-gui-goldens:" + hashlib.sha256(dockerfile.read_bytes()).hexdigest()[:12]


def cmd_local(args) -> int:
    """Linux pass of a CI build on this machine, in the pinned image (Docker
    runs the same linux/amd64 image as CI; it is emulated on arm64 hosts, so
    CI stays the reference)."""
    gh, docker = shutil.which("gh"), shutil.which("docker")
    if gh is None or docker is None:
        print("gh (GitHub CLI) and docker are needed", file=sys.stderr)
        return 1
    work = REPO_ROOT / "build" / "cosmyx-gui-goldens" / str(args.run_id)
    listing = subprocess.run([gh, "api", "--paginate", f"repos/{args.repo}/actions/runs/{args.run_id}/artifacts?per_page=100",
                              "--jq", ".artifacts[]"], capture_output=True, text=True, check=True).stdout
    names = [json.loads(line)["name"] for line in listing.splitlines() if line.strip()]
    picked = pick_artifacts(names, default_classify()).get("linux")
    if picked is None:
        print(f"run {args.run_id} has no Linux AppImage artifact", file=sys.stderr)
        return 1
    artifacts = work / "artifacts" / picked
    if not artifacts.is_dir() or not any(artifacts.iterdir()):
        subprocess.run([gh, "run", "download", str(args.run_id), "--repo", args.repo, "--name", picked, "--dir",
                        str(artifacts)], check=True)
    dockerfile = GUI_DIR / "docker" / "Dockerfile"
    tag = docker_image_tag(dockerfile)
    subprocess.run([docker, "build", "--platform", "linux/amd64", "-t", tag, str(dockerfile.parent)], check=True)
    rel = lambda path: path.relative_to(REPO_ROOT).as_posix()
    out = work / "out"
    subprocess.run([docker, "run", "--rm", "--platform", "linux/amd64", "-v", f"{REPO_ROOT}:/work", "-w", "/work", tag,
                    "python3", "-I", "scripts/cosmyx/gui_goldens/cli.py", "run", "--os", "linux", "--artifacts",
                    rel(artifacts), "--subject", ".", "--out", rel(out), "--passes", str(args.passes)], check=True)
    compare_args = ["--os", "linux", "--goldens", str(GOLDENS_DIR / "linux"), "--actual", str(out / "pass-1" / "images"),
                    "--gcode", str(out / "pass-1" / "plate_1.gcode"), "--out", str(out / "report")]
    if args.passes == 2:
        compare_args += ["--second", str(out / "pass-2" / "images")]
    return main(["compare"] + compare_args)


# ---------------------------------------------------------------------------


def parser() -> argparse.ArgumentParser:
    main = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = main.add_subparsers(dest="command", required=True)

    p = sub.add_parser("resolve")
    p.add_argument("--run", required=True)
    p.add_argument("--artifacts-list", required=True)
    p.add_argument("--changed", default="")
    p.add_argument("--mode", choices=("compare", "update"), default="compare")
    p.add_argument("--stability", choices=("auto", "on", "off"), default="auto")
    p.add_argument("--event", default="workflow_run")
    p.add_argument("--github-output", default="")
    p.set_defaults(func=cmd_resolve)

    p = sub.add_parser("run")
    p.add_argument("--os", required=True, choices=OSES)
    p.add_argument("--artifacts", required=True)
    p.add_argument("--subject", default=str(REPO_ROOT))
    p.add_argument("--out", required=True)
    p.add_argument("--passes", type=int, default=1, choices=(1, 2))
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("compare")
    p.add_argument("--os", required=True, choices=OSES)
    p.add_argument("--goldens", required=True)
    p.add_argument("--actual", required=True)
    p.add_argument("--subject", default=str(REPO_ROOT))
    p.add_argument("--out", required=True)
    p.add_argument("--second", default="")
    p.add_argument("--gcode", default="")
    p.add_argument("--step-summary", default="")
    p.add_argument("--report-only", action="store_true")
    p.set_defaults(func=cmd_compare)

    p = sub.add_parser("update")
    p.add_argument("--goldens", required=True)
    p.add_argument("--actual", required=True)
    p.add_argument("--report", required=True)
    p.set_defaults(func=cmd_update)

    p = sub.add_parser("stability")
    p.add_argument("--os", required=True, choices=OSES)
    p.add_argument("--first", required=True)
    p.add_argument("--second", required=True)
    p.add_argument("--subject", default=str(REPO_ROOT))
    p.set_defaults(func=cmd_stability)

    p = sub.add_parser("fetch")
    p.add_argument("--run-id", required=True)
    p.add_argument("--repo", default=os.environ.get("COSMYX_REPO", "Cosmyx/OrcaSlicer"))
    p.add_argument("--goldens-root", default=str(GOLDENS_DIR))
    p.set_defaults(func=cmd_fetch)

    p = sub.add_parser("local")
    p.add_argument("--run-id", required=True)
    p.add_argument("--repo", default=os.environ.get("COSMYX_REPO", "Cosmyx/OrcaSlicer"))
    p.add_argument("--passes", type=int, default=1, choices=(1, 2))
    p.set_defaults(func=cmd_local)

    p = sub.add_parser("review")
    p.add_argument("--goldens-root", default=str(GOLDENS_DIR))
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_review)
    return main


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        return args.func(args)
    except GoldenError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
