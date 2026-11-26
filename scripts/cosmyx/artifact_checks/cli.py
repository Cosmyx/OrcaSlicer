"""Cosmyx artifact checks, command line (wiki/cosmyx/artifact-checks.md).

    cli.py resolve  --run RUN.json --artifacts-list LIST.jsonl --out DIR [--github-output FILE]
    cli.py windows|macos|linux --tools T --subject S --artifacts A --mode M --strict B --exec-ok B --out DIR
    cli.py content  --os OS --tools T --subject S --artifacts A --head-sha SHA --out DIR
    cli.py report   --in DIR --out DIR --mode M --strict B [--job OS=RESULT ...] [--step-summary FILE]
    cli.py download --run-id ID --repo OWNER/NAME --names JSON --dest DIR
    cli.py local    --run-id ID [--repo OWNER/NAME]

The CI runs it with `python -I`, so this file puts its parent folder on
sys.path itself. OS jobs exit 0 once their records are written: the report
job decides.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from artifact_checks import allowlist as allowlist_mod  # noqa: E402
from artifact_checks import content, inventory, linux, macos, policy_windows, report, signing_policy  # noqa: E402
from artifact_checks import smoke_native  # noqa: E402
from artifact_checks.records import Record, build_manifest, sha256sums, write_jsonl  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
SIGN_VARIABLES = ("COSMYX_SIGN_ALL_REFS", "COSMYX_SIGN_SUBJECT", "COSMYX_SIGN_EKU")
RUNNERS = {"windows": "windows-latest", "macos": "macos-15", "linux": "ubuntu-24.04"}
SUBJECT_PATHS = ("version.inc", "src/slic3r/GUI/Cosmyx/logic/CosmyxVersion.hpp", "localization/cosmyx",
                 "resources/cosmyx")
HOST_OS = {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux" if sys.platform.startswith("linux") else "")


def boolean(text: str) -> bool:
    return str(text).strip().lower() in ("1", "true", "yes")


def read_artifact_list(path: Path) -> list[dict]:
    """Artifacts from `gh api --paginate ... --jq '.artifacts[]'` (one object per
    line) or from raw API pages (objects with an "artifacts" list)."""
    items = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            items += value["artifacts"] if isinstance(value, dict) and "artifacts" in value else [value]
    return items


# ---------------------------------------------------------------------------
# resolve


def resolve(run: dict, artifacts: list[dict], variables: dict, secrets: dict, strict: bool,
            expectations: dict) -> tuple[dict, list[Record]]:
    """The plan of a check run (its outputs) and the records known up front."""
    conclusion = run.get("conclusion")
    found = inventory.inventory(artifacts, expectations)
    outputs = {
        "skip": "true" if conclusion in ("cancelled", "skipped", None, "") else "false",
        "head_sha": run.get("head_sha", ""),
        "head_branch": run.get("head_branch") or "",
        "head_repo": (run.get("head_repository") or {}).get("full_name", ""),
        "event": run.get("event", ""),
        "conclusion": conclusion or "",
        "mode": signing_policy.mode_for_run(run, variables, secrets),
        "mac_mode": signing_policy.mac_mode_for_run(run, variables, secrets),
        "exec_ok": "true" if signing_policy.exec_ok(run) else "false",
        "strict": "true" if strict else "false",
        "run_url": run.get("html_url", ""),
    }
    tags = [a.tag for items in found.values() for a in items if a.tag]
    outputs["tag"] = tags[0] if tags else outputs["head_sha"][:12]
    matrix = []
    for os_name, items in found.items():
        live = [a.name for a in items if not a.expired]
        outputs[f"{os_name}_names"] = json.dumps(live)
        if live:
            matrix.append({"os": os_name, "runner": RUNNERS[os_name], "names": live})
    outputs["matrix"] = json.dumps(matrix)
    outputs["checked_oses"] = " ".join(entry["os"] for entry in matrix)
    records = inventory.required_records(run, found, expectations)
    for items in found.values():
        for artifact in items:
            if artifact.expired:
                records.append(Record(artifact.os, artifact.name, "", "required", "skip",
                                      "artifact expired (90-day retention), not checked"))
    return outputs, records


def cmd_resolve(args) -> int:
    run = json.loads(Path(args.run).read_text(encoding="utf-8"))
    artifacts = read_artifact_list(Path(args.artifacts_list))
    variables = {name: os.environ.get(name, "") for name in SIGN_VARIABLES}
    secrets = signing_policy.secrets_from_env(os.environ)
    outputs, records = resolve(run, artifacts, variables, secrets, boolean(args.strict), inventory.load_expectations())
    missing = signing_policy.missing_secrets(secrets)
    if outputs["mode"] == signing_policy.NOT_CONFIGURED and len(missing) < len(signing_policy.SIGNING_SECRETS):
        print(f"::warning::Windows signing secrets partly set; missing: {', '.join(missing)}")
    mac_missing = signing_policy.missing_secrets(secrets, signing_policy.MAC_SIGNING_SECRETS)
    if outputs["mac_mode"] == signing_policy.NOT_CONFIGURED and len(mac_missing) < len(signing_policy.MAC_SIGNING_SECRETS):
        print(f"::warning::macOS signing secrets partly set; missing: {', '.join(mac_missing)}")
    write_jsonl(Path(args.out) / "report-resolve.jsonl", records)
    for key, value in outputs.items():
        print(f"{key}={value}")
    if args.github_output:
        with open(args.github_output, "a", encoding="utf-8", newline="\n") as out:
            for key, value in outputs.items():
                out.write(f"{key}={value}\n")
    return 0


# ---------------------------------------------------------------------------
# OS jobs


def downloaded(artifacts_dir: Path, os_name: str, expectations: dict) -> list[inventory.Artifact]:
    found = []
    if artifacts_dir.is_dir():
        for folder in sorted(p for p in artifacts_dir.iterdir() if p.is_dir()):
            artifact = inventory.classify(folder.name, expectations)
            if artifact and artifact.os == os_name and artifact.kind != "ignored":
                found.append(artifact)
    return found


def write_outputs(out: Path, os_name: str, records: list[Record], artifacts_dir: Path,
                  artifacts: list[inventory.Artifact], manifests: dict) -> None:
    write_jsonl(out / f"report-{os_name}.jsonl", records)
    files = []
    for artifact in artifacts:
        folder = artifacts_dir / artifact.name
        files += [(f"{artifact.name}/{p.name}", p) for p in sorted(folder.iterdir()) if p.is_file()]
    (out / "SHA256SUMS").write_text(sha256sums(files), encoding="utf-8", newline="\n")
    (out / "manifest.json").write_text(json.dumps(manifests, indent=1, sort_keys=True) + "\n", encoding="utf-8",
                                       newline="\n")


def load_allowlist(os_name: str) -> tuple[allowlist_mod.Allowlist, list[Record]]:
    try:
        return allowlist_mod.load(today=dt.date.today()), []
    except allowlist_mod.AllowlistError as error:
        check = "signature" if os_name == "windows" else "arch"
        return allowlist_mod.Allowlist(), [Record(os_name, "allowlist", "data/allowlist.json", check, "fail", str(error))]


def tree_hook(os_name: str, tools: Path, subject: Path):
    def hook(artifact: inventory.Artifact, tree: Path) -> list[Record]:
        return content.tree_records(os_name, artifact.name, tree, tools, subject)
    return hook


def cmd_windows(args, run=subprocess.run) -> int:
    expectations = inventory.load_expectations()
    artifacts_dir, out, work = Path(args.artifacts), Path(args.out), Path(args.work or Path(args.out) / "work")
    artifacts = downloaded(artifacts_dir, "windows", expectations)
    allow, records = load_allowlist("windows")
    if args.mode == signing_policy.NOT_CONFIGURED and os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::notice::{signing_policy.NOTICE}")
    collected = policy_windows.collect(artifacts_dir, artifacts, work, expectations, dict(os.environ), run,
                                       install=not args.no_install)
    records += collected.records
    facts = policy_windows.collect_facts(collected.items, work, run)
    identity = policy_windows.Identity(os.environ.get("COSMYX_SIGN_SUBJECT", "").strip(),
                                       os.environ.get("COSMYX_SIGN_EKU", "").strip())
    records += policy_windows.evaluate(collected.items, facts, args.mode, identity, allow,
                                       expectations["windows"]["own_names"], boolean(args.strict))
    manifests = {}
    hook = tree_hook("windows", Path(args.tools), Path(args.subject))
    for name, tree in collected.trees:
        artifact = next(a for a in artifacts if a.name == name)
        manifests[name] = build_manifest(tree)
        records += hook(artifact, tree)
        records += smoke_native.windows_records(artifact, tree, Path(args.subject), work, expectations,
                                                boolean(args.exec_ok), run=run)
    write_outputs(out, "windows", records, artifacts_dir, artifacts, manifests)
    return 0


def cmd_macos(args, run=subprocess.run) -> int:
    expectations = inventory.load_expectations()
    artifacts_dir, out, work = Path(args.artifacts), Path(args.out), Path(args.work or Path(args.out) / "work")
    artifacts = downloaded(artifacts_dir, "macos", expectations)
    allow, records = load_allowlist("macos")
    manifests: dict = {}
    if args.mode == signing_policy.NOT_CONFIGURED and os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::notice::{signing_policy.MAC_NOTICE}")
    # The macOS leg gets the macOS mode (decision 0156) and the TEAM_ID secret,
    # masked by GitHub, as COSMYX_MAC_TEAM_ID.
    records += macos.check(artifacts_dir, artifacts, work, allow, run, tree_hook("macos", Path(args.tools), Path(args.subject)),
                           manifests, enforce_stale=args.mode == signing_policy.ENFORCE, mode=args.mode,
                           team=os.environ.get("COSMYX_MAC_TEAM_ID", "").strip(), strict=boolean(args.strict),
                           exec_ok=boolean(args.exec_ok), subject=Path(args.subject), expectations=expectations)
    write_outputs(out, "macos", records, artifacts_dir, artifacts, manifests)
    return 0


def cmd_linux(args, run=subprocess.run) -> int:
    expectations = inventory.load_expectations()
    artifacts_dir, out, work = Path(args.artifacts), Path(args.out), Path(args.work or Path(args.out) / "work")
    artifacts = downloaded(artifacts_dir, "linux", expectations)
    manifests: dict = {}
    records = linux.check(artifacts_dir, artifacts, work, Path(args.subject), expectations, boolean(args.exec_ok), run,
                          tree_hook("linux", Path(args.tools), Path(args.subject)), manifests,
                          xvfb=shutil.which("xvfb-run") is not None)
    write_outputs(out, "linux", records, artifacts_dir, artifacts, manifests)
    return 0


def cmd_content(args) -> int:
    expectations = inventory.load_expectations()
    artifacts = downloaded(Path(args.artifacts), args.os, expectations)
    version = content.display_version(Path(args.tools), Path(args.subject))
    records = inventory.names_records([a.name for a in artifacts], version, args.head_sha, expectations, args.os)
    write_jsonl(Path(args.out) / f"report-content-{args.os}.jsonl", records)
    return 0


def cmd_report(args) -> int:
    records = report.load_all(Path(args.input))
    jobs = dict(item.split("=", 1) for item in args.job or [])
    records += report.job_records(jobs, records)
    ok = report.write(records, Path(args.out), args.mode, boolean(args.strict), args.run_url or "",
                      args.mac_mode)
    text = (Path(args.out) / "report.md").read_text(encoding="utf-8")
    if args.step_summary:
        with open(args.step_summary, "a", encoding="utf-8", newline="\n") as summary:
            summary.write(text)
    print(text)
    return 0 if ok else 1


# ---------------------------------------------------------------------------
# local


def gh(args: list[str], gh_path: str) -> str:
    return subprocess.run([gh_path] + args, check=True, capture_output=True, text=True).stdout


def download(run_id: str, repo: str, names: list[str], dest: Path, gh_path: str) -> None:
    """Download each artifact into dest/<name> (one call per artifact, so the
    layout never depends on how many there are). Already downloaded ones are kept."""
    for name in names:
        target = dest / name
        if target.is_dir() and any(target.iterdir()):
            continue
        print(f"downloading {name}")
        subprocess.run([gh_path, "run", "download", str(run_id), "--repo", repo, "--name", name, "--dir", str(target)],
                       check=True)


def cmd_download(args) -> int:
    gh_path = args.gh or shutil.which("gh") or ""
    if not gh_path:
        print("gh (GitHub CLI) is needed to download artifacts", file=sys.stderr)
        return 1
    download(args.run_id, args.repo, json.loads(args.names), Path(args.dest), gh_path)
    return 0


def export_subject(sha: str, target: Path) -> bool:
    """Write the data files of the built commit, read from the local git history."""
    def git(*command: str, text: bool = True):
        return subprocess.run(["git", "-C", str(REPO_ROOT), *command], capture_output=True, text=text, check=False)

    if git("cat-file", "-e", f"{sha}^{{commit}}").returncode != 0:
        print(f"commit {sha} is not in the local history: run `git fetch origin {sha}` first", file=sys.stderr)
        return False
    # -z gives the raw names: without it git C-quotes non-ASCII names (core.quotePath).
    raw = git("ls-tree", "-r", "-z", "--name-only", sha, "--", *SUBJECT_PATHS, text=False).stdout
    listing = [entry.decode("utf-8", "surrogateescape") for entry in raw.split(b"\0") if entry]
    for name in listing:
        blob = git("show", f"{sha}:{name}", text=False).stdout
        path = target.joinpath(*name.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(blob)
    return True


def cmd_local(args) -> int:
    gh_path = args.gh or shutil.which("gh") or ""
    if not gh_path:
        print("gh (GitHub CLI) is needed for a local check", file=sys.stderr)
        return 1
    if not HOST_OS:
        print(f"unsupported host platform {sys.platform}", file=sys.stderr)
        return 1
    dest = Path(args.dest or REPO_ROOT / "build" / "cosmyx" / "artifacts" / args.run_id)
    dest.mkdir(parents=True, exist_ok=True)
    run = json.loads(gh(["api", f"repos/{args.repo}/actions/runs/{args.run_id}"], gh_path))
    listing = gh(["api", "--paginate", f"repos/{args.repo}/actions/runs/{args.run_id}/artifacts?per_page=100",
                  "--jq", ".artifacts[]"], gh_path)
    artifacts = [json.loads(line) for line in listing.splitlines() if line.strip()]
    variables = {name: os.environ.get(name, "") for name in SIGN_VARIABLES}
    # A local run cannot see the repository secrets: COSMYX_HAS_<SECRET>=true
    # in the environment stands for them, and COSMYX_MAC_TEAM_ID for TEAM_ID
    # (wiki/cosmyx/artifact-checks.md).
    secrets = signing_policy.secrets_from_env(os.environ)
    expectations = inventory.load_expectations()
    outputs, records = resolve(run, artifacts, variables, secrets, args.strict, expectations)
    out = dest / "out"
    write_jsonl(out / "report-resolve.jsonl", records)
    if run.get("status") != "completed":
        print(f"run {args.run_id} is {run.get('status')}: wait until it has finished", file=sys.stderr)
        return 1
    for os_name in ("windows", "macos", "linux"):
        if os_name != HOST_OS and json.loads(outputs[f"{os_name}_names"]):
            print(f"skip: {os_name} artifacts are checked on {os_name} only (this host is {HOST_OS})")
    names = json.loads(outputs[f"{HOST_OS}_names"])
    artifacts_dir = dest / "artifacts"
    download(args.run_id, args.repo, names, artifacts_dir, gh_path)
    subject = dest / "subject"
    if not export_subject(outputs["head_sha"], subject):
        return 1
    host_mode = outputs["mac_mode"] if HOST_OS == "macos" else outputs["mode"]
    common = argparse.Namespace(tools=str(REPO_ROOT), subject=str(subject), artifacts=str(artifacts_dir),
                                mode=host_mode, strict=outputs["strict"], exec_ok=outputs["exec_ok"],
                                out=str(out), work=str(dest / "work"), no_install=True, os=HOST_OS,
                                head_sha=outputs["head_sha"])
    {"windows": cmd_windows, "macos": cmd_macos, "linux": cmd_linux}[HOST_OS](common)
    cmd_content(common)
    result = cmd_report(argparse.Namespace(input=str(out), out=str(out), mode=outputs["mode"],
                                           mac_mode=outputs["mac_mode"], strict=outputs["strict"],
                                           job=[], run_url=outputs["run_url"], step_summary=""))
    print(f"report: {out / 'report.md'}")
    return result


# ---------------------------------------------------------------------------


def parser() -> argparse.ArgumentParser:
    main = argparse.ArgumentParser(description="Cosmyx artifact checks")
    sub = main.add_subparsers(dest="command", required=True)
    p = sub.add_parser("resolve", help="read a build run and plan the checks")
    p.add_argument("--run", required=True)
    p.add_argument("--artifacts-list", required=True)
    p.add_argument("--strict", default="false")
    p.add_argument("--out", required=True)
    p.add_argument("--github-output", default="")
    for name in ("windows", "macos", "linux"):
        p = sub.add_parser(name, help=f"check the {name} artifacts")
        for option in ("--tools", "--subject", "--artifacts", "--out"):
            p.add_argument(option, required=True)
        p.add_argument("--mode", default=signing_policy.REPORT,
                       choices=(signing_policy.ENFORCE, signing_policy.NOT_CONFIGURED, signing_policy.REPORT))
        p.add_argument("--strict", default="false")
        p.add_argument("--exec-ok", default="false")
        p.add_argument("--work", default="")
        p.add_argument("--no-install", action="store_true", help="never run the Windows installer")
    p = sub.add_parser("content", help="check the artifact names")
    for option in ("--os", "--tools", "--subject", "--artifacts", "--head-sha", "--out"):
        p.add_argument(option, required=True)
    p = sub.add_parser("report", help="merge the records into junit.xml and report.md")
    p.add_argument("--in", dest="input", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--mode", default=signing_policy.REPORT)
    p.add_argument("--mac-mode", default="")
    p.add_argument("--strict", default="false")
    p.add_argument("--job", action="append", help="OS=RESULT of an OS job")
    p.add_argument("--run-url", default="")
    p.add_argument("--step-summary", default="")
    p = sub.add_parser("download", help="download artifacts of a run, one folder each")
    p.add_argument("--run-id", required=True)
    p.add_argument("--repo", required=True)
    p.add_argument("--names", required=True, help="JSON list of artifact names")
    p.add_argument("--dest", required=True)
    p.add_argument("--gh", default="")
    p = sub.add_parser("local", help="download a run's artifacts for this OS and check them here")
    p.add_argument("--run-id", required=True)
    p.add_argument("--repo", default=os.environ.get("COSMYX_REPO", "Cosmyx/OrcaSlicer"))
    p.add_argument("--dest", default="")
    p.add_argument("--gh", default="")
    p.add_argument("--strict", action="store_true")
    return main


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    handlers = {"resolve": cmd_resolve, "windows": cmd_windows, "macos": cmd_macos, "linux": cmd_linux,
                "content": cmd_content, "report": cmd_report, "download": cmd_download, "local": cmd_local}
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
