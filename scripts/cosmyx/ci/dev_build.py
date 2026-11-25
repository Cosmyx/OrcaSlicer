"""Choose what a Cosmyx dev build compiles, and how it gets its macOS DMGs
(decision 0218).

    python scripts/cosmyx/ci/dev_build.py select [--output FILE]
    python scripts/cosmyx/ci/dev_build.py version [--output FILE]
    python scripts/cosmyx/ci/dev_build.py dmg-plan --arch ARCH --ver VER
        --product NAME --sha SHA --names-file FILE [--output FILE]
    python scripts/cosmyx/ci/dev_build.py seal-app --app APP

`select` reads the triggering event (GITHUB_EVENT_NAME, GITHUB_EVENT_PATH):

- `workflow_dispatch`: the boolean inputs `linux`, `windows`, `macos-arm64`
  and `macos-x86_64`.
- `pull_request`: the PR labels `build:linux`, `build:windows`,
  `build:macos-arm64` and `build:macos-x86_64`. Without any of them the build
  covers Linux, Windows and macOS arm64. A `labeled`/`unlabeled` event for a
  label outside `build:` builds nothing, so tagging a PR never restarts it.
  An unknown `build:` label fails, so a typo never falls back to the default.

It writes `build`, `linux`, `windows`, `macos` (true/false), `macos-archs`
(a JSON list) and `product` (the packages table's product name, CosmoSlice on
a base without it).

`version` writes `ver`, the name build_orca.yml gives the packages of this
checkout: the Cosmyx build tag of scripts/cosmyx/cosmyx_version.py when the
tree has it (its hook renames everything after it), else upstream's
`PR-<number>` on a pull request and `V<version>` otherwise. Run it on the same
checkout build_orca.yml makes, so git abbreviates the commit the same way.

`dmg-plan` picks, for one macOS arch, where its CosmoSlice DMG comes from,
given the names of the run's artifacts (one per line):

- `skip`: the build already uploaded `<product>_Mac_<arch>_<ver>`.
- `dmg`: only upstream's `OrcaSlicer_Mac_<arch>_<ver>` exists (a pull request
  build of a base whose product-name hook did not rename it): repack its app.
- `bundle`: the build packed `OrcaSlicer_Mac_bundle_<arch>_<sha>` (any base
  outside upstream's pull-request mode): build the DMG from that bundle.
- `skip` again when only a `<product>_Mac_<arch>_*` DMG under another version
  string exists.

`seal-app` makes the repacked app's signature verify before it goes into the
DMG (see `seal_command`); it fails when the bundle still does not verify.

Standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PACKAGES_TABLE = "cosmyx-src/branding/product-name/packages.json"
COSMYX_VERSION = "scripts/cosmyx/cosmyx_version.py"
DEFAULT_PRODUCT = "CosmoSlice"
UPSTREAM = "OrcaSlicer"

LABEL_PREFIX = "build:"
# Target -> PR label and dispatch input (they share the suffix).
TARGETS = ("linux", "windows", "macos-arm64", "macos-x86_64")
DEFAULT_TARGETS = ("linux", "windows", "macos-arm64")
DISPATCH_DEFAULTS = {"linux": True, "windows": True, "macos-arm64": True, "macos-x86_64": False}


class SelectError(Exception):
    pass


def as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in ("true", "false"):
        return value.strip().lower() == "true"
    raise SelectError(f"not a boolean: {value!r}")


def targets_from_labels(labels: list[str]) -> set[str]:
    wanted = set()
    for label in labels:
        if not label.startswith(LABEL_PREFIX):
            continue
        target = label[len(LABEL_PREFIX):]
        if target not in TARGETS:
            known = ", ".join(LABEL_PREFIX + t for t in TARGETS)
            raise SelectError(f"unknown label {label!r}; known build labels: {known}")
        wanted.add(target)
    return wanted or set(DEFAULT_TARGETS)


def targets_from_inputs(inputs: dict) -> set[str]:
    wanted = set()
    for target in TARGETS:
        value = inputs.get(target)
        if as_bool(DISPATCH_DEFAULTS[target] if value is None else value):
            wanted.add(target)
    if not wanted:
        raise SelectError("no OS selected: tick at least one checkbox")
    return wanted


def select(event_name: str, event: dict) -> dict:
    """The build selection for one event, as plain values."""
    if event_name == "workflow_dispatch":
        wanted = targets_from_inputs(event.get("inputs") or {})
    elif event_name == "pull_request":
        action = event.get("action")
        label = (event.get("label") or {}).get("name", "")
        if action in ("labeled", "unlabeled") and not label.startswith(LABEL_PREFIX):
            return {"build": False, "targets": [], "macos_archs": []}
        labels = [item.get("name", "") for item in (event.get("pull_request") or {}).get("labels", [])]
        wanted = targets_from_labels(labels)
    else:
        raise SelectError(f"unsupported event {event_name!r}")
    targets = [t for t in TARGETS if t in wanted]
    archs = [t.split("-", 1)[1] for t in targets if t.startswith("macos-")]
    return {"build": True, "targets": targets, "macos_archs": archs}


def version(event_name: str, event: dict, root: Path = REPO_ROOT) -> str:
    """The `ver` build_orca.yml names packages with on this checkout."""
    head = (event.get("pull_request") or {}).get("head", {}).get("sha", "") if event_name == "pull_request" else ""
    tool = root / COSMYX_VERSION
    if tool.is_file():
        # The same call as build_orca.yml's Cosmyx hook, with the commit its
        # "Get the version" step exports.
        env = dict(os.environ, git_commit_hash=head)
        result = subprocess.run(
            [sys.executable, str(tool), "--root", str(root), "build-tag"],
            cwd=root, env=env, capture_output=True, text=True, check=False,
        )
        if result.returncode != 0:
            raise SelectError(f"{COSMYX_VERSION}: {result.stderr.strip()}")
        return result.stdout.strip().splitlines()[-1]
    if event_name == "pull_request":
        return f"PR-{event['pull_request']['number']}"
    text = (root / "version.inc").read_bytes().decode("utf-8")
    match = re.search(r'set\(SoftFever_VERSION\s+"([^"]+)"', text)
    if not match:
        raise SelectError("version.inc: no SoftFever_VERSION")
    return f"V{match.group(1)}"


def product(root: Path = REPO_ROOT) -> str:
    """The product name of the packages table, or CosmoSlice on a base without it."""
    table = root / PACKAGES_TABLE
    if not table.is_file():
        return DEFAULT_PRODUCT
    return json.loads(table.read_bytes().decode("utf-8"))["product"]


def select_outputs(event_name: str, event: dict, root: Path = REPO_ROOT) -> dict[str, str]:
    chosen = select(event_name, event)
    targets = chosen["targets"]
    return {
        "build": str(chosen["build"]).lower(),
        "linux": str("linux" in targets).lower(),
        "windows": str("windows" in targets).lower(),
        "macos": str(bool(chosen["macos_archs"])).lower(),
        "macos-archs": json.dumps(chosen["macos_archs"]),
        "product": product(root),
    }


def dmg_plan(names: list[str], arch: str, ver: str, product_name: str, sha: str) -> dict[str, str]:
    present = {name.strip() for name in names if name.strip()}
    own = f"{product_name}_Mac_{arch}_{ver}"
    upstream_dmg = f"{UPSTREAM}_Mac_{arch}_{ver}"
    bundle = f"{UPSTREAM}_Mac_bundle_{arch}_{sha}"
    if own in present:
        return {"action": "skip", "source": own, "artifact": own}
    if upstream_dmg in present:
        return {"action": "dmg", "source": upstream_dmg, "artifact": own}
    if bundle in present:
        return {"action": "bundle", "source": bundle, "artifact": own}
    # The build named its DMG after another version string: it is still there.
    renamed = sorted(name for name in present if name.startswith(f"{product_name}_Mac_{arch}_"))
    if renamed:
        return {"action": "skip", "source": renamed[0], "artifact": renamed[0]}
    raise SelectError(f"macOS {arch}: none of {own}, {upstream_dmg} or {bundle} was uploaded")


def seal_command(app: Path) -> str:
    """Upstream's unsigned build leaves only the linker's ad-hoc signature on
    each Mach-O and never seals the bundle (no _CodeSignature), so
    `codesign --verify` fails with "code has no resources but signature
    indicates they must be present" and Gatekeeper calls the downloaded app
    damaged. Keep a signature that already verifies (a Developer ID one), fail
    on an identity signature that no longer verifies (never silently replace
    it), seal anything else ad hoc, then verify strictly."""
    return (
        f"set -e; app={shlex.quote(str(app))}; "
        'if codesign --verify --deep --strict "$app" 2>/dev/null; then echo "$app: signature kept"; '
        "elif codesign -dv \"$app\" 2>&1 | grep -q '^Authority='; then "
        'echo "::error::$app is signed with an identity but no longer verifies" >&2; exit 1; '
        'else codesign --force --deep --sign - "$app"; fi; '
        'codesign --verify --deep --strict --verbose=2 "$app"'
    )


def run_bash(command: str) -> None:
    subprocess.run(["bash", "-c", command], check=True)


def write_outputs(values: dict[str, str], output: str | None) -> None:
    lines = "".join(f"{key}={value}\n" for key, value in values.items())
    target = output or os.environ.get("GITHUB_OUTPUT")
    if target:
        with open(target, "a", encoding="utf-8", newline="\n") as handle:
            handle.write(lines)
    sys.stdout.write(lines)


def main(argv: list[str] | None = None, runner=run_bash) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("select", "version"):
        sub.add_parser(name).add_argument("--output")
    plan = sub.add_parser("dmg-plan")
    for name in ("--arch", "--ver", "--product", "--sha", "--names-file"):
        plan.add_argument(name, required=True)
    plan.add_argument("--output")
    sub.add_parser("seal-app").add_argument("--app", required=True)
    args = parser.parse_args(argv)
    if args.command == "seal-app":
        try:
            runner(seal_command(Path(args.app)))
        except subprocess.CalledProcessError as error:
            print(f"::error::{args.app} does not verify after sealing (exit {error.returncode})", file=sys.stderr)
            return 1
        return 0
    try:
        if args.command in ("select", "version"):
            event_name = os.environ.get("GITHUB_EVENT_NAME", "")
            event_path = os.environ.get("GITHUB_EVENT_PATH")
            event = json.loads(Path(event_path).read_bytes().decode("utf-8")) if event_path else {}
            if args.command == "select":
                write_outputs(select_outputs(event_name, event), args.output)
            else:
                write_outputs({"ver": version(event_name, event)}, args.output)
        else:
            names = Path(args.names_file).read_bytes().decode("utf-8").splitlines()
            write_outputs(dmg_plan(names, args.arch, args.ver, args.product, args.sha), args.output)
    except SelectError as error:
        print(f"::error::{error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
