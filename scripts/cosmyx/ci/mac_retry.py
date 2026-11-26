"""Rerun the failed jobs of a "Build all" or "Cosmyx dev build" run whose
macOS jobs never got a hosted runner (decision 0217).

Hosted macOS runners are scarce. When GitHub cannot acquire one, it cancels
the job with the annotation "The job was not acquired by Runner of type hosted
even after multiple attempts". Only that cause is retried: a job cancelled by a
user or by a concurrency group carries no such annotation and is left alone.

Two commands, run by .github/workflows/cosmyx-mac-retry.yml:

- decide: reads the finished run, prints why it retries or not, and writes
  rerun=true|false to $GITHUB_OUTPUT.
- rerun: after the workflow has waited, checks the run is still the same
  finished attempt (nobody reran it meanwhile), then asks GitHub to rerun its
  failed and cancelled jobs.

Inputs come from the environment: GITHUB_REPOSITORY, GITHUB_TOKEN (or
GH_TOKEN), RUN_ID, RUN_ATTEMPT, RUN_CONCLUSION, and MAC_RETRY_MAX_ATTEMPTS
(default 5). GITHUB_API_URL overrides the API root.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

RUNNER_NOT_ACQUIRED = "was not acquired by runner of type hosted"
RETRY_CONCLUSIONS = ("failure", "cancelled")
# A job that never got a runner is reported cancelled; failure is accepted too
# because the annotation, not the conclusion, is the proof of the cause.
JOB_CONCLUSIONS = ("cancelled", "failure")
DEFAULT_MAX_ATTEMPTS = 5
PER_PAGE = 100

# (method, path) -> decoded JSON body (None for an empty reply).
Api = Callable[[str, str], object]


@dataclass(frozen=True)
class Decision:
    rerun: bool
    reason: str
    jobs: tuple[str, ...] = ()


def is_macos_job(job: dict) -> bool:
    # Both workflows name every job that runs on macOS with "macos" somewhere:
    # build_macos_arch (<arch>) / ... and macOS arm64 / Unit Tests in both,
    # Build macOS Universal in Build all, macOS DMG <arch> in the dev build.
    return "macos" in str(job.get("name", "")).lower()


def has_runner_annotation(annotations: list) -> bool:
    return any(RUNNER_NOT_ACQUIRED in str(item.get("message", "")).lower() for item in annotations)


def paged(api: Api, path: str, key: str | None) -> list:
    """Fetch every page of a list endpoint. key names the list in the reply
    (the jobs endpoint wraps it), None for a bare list (annotations)."""
    items: list = []
    page = 1
    while True:
        separator = "&" if "?" in path else "?"
        reply = api("GET", f"{path}{separator}per_page={PER_PAGE}&page={page}")
        batch = reply.get(key, []) if key else reply
        items.extend(batch or [])
        if len(batch or []) < PER_PAGE:
            return items
        page += 1


def decide(api: Api, repo: str, run_id: int, attempt: int, conclusion: str, max_attempts: int) -> Decision:
    if conclusion not in RETRY_CONCLUSIONS:
        return Decision(False, f"run concluded {conclusion!r}, nothing to retry")
    if attempt >= max_attempts:
        return Decision(False, f"attempt {attempt} reached the limit of {max_attempts}")
    jobs = paged(api, f"/repos/{repo}/actions/runs/{run_id}/jobs?filter=latest", "jobs")
    candidates = [job for job in jobs if is_macos_job(job) and job.get("conclusion") in JOB_CONCLUSIONS]
    if not candidates:
        return Decision(False, "no cancelled or failed macOS job")
    starved = tuple(
        job["name"]
        for job in candidates
        if has_runner_annotation(paged(api, f"/repos/{repo}/check-runs/{job['id']}/annotations", None))
    )
    if not starved:
        return Decision(False, "macOS jobs stopped for another cause (no runner acquisition annotation)")
    return Decision(True, f"no hosted runner was acquired for: {', '.join(starved)}", starved)


def still_current(api: Api, repo: str, run_id: int, attempt: int) -> tuple[bool, str]:
    """The run must still be the finished attempt the decision was made on."""
    run = api("GET", f"/repos/{repo}/actions/runs/{run_id}")
    if run.get("run_attempt") != attempt:
        return False, f"run is now at attempt {run.get('run_attempt')}, someone reran it"
    if run.get("status") != "completed":
        return False, f"run status is {run.get('status')!r}"
    return True, "run unchanged"


def rerun(api: Api, repo: str, run_id: int, attempt: int) -> tuple[bool, str]:
    current, reason = still_current(api, repo, run_id, attempt)
    if not current:
        return False, reason
    api("POST", f"/repos/{repo}/actions/runs/{run_id}/rerun-failed-jobs")
    return True, "failed jobs rerun requested"


def http_api(token: str, root: str) -> Api:
    def call(method: str, path: str) -> object:
        request = urllib.request.Request(
            root.rstrip("/") + path,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "cosmyx-mac-retry",
            },
            data=b"" if method == "POST" else None,
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read()
        return json.loads(body) if body else None

    return call


def write_output(name: str, value: str) -> None:
    target = os.environ.get("GITHUB_OUTPUT")
    if target:
        with Path(target).open("a", encoding="utf-8") as handle:
            handle.write(f"{name}={value}\n")


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in ("decide", "rerun"):
        print("usage: mac_retry.py decide|rerun", file=sys.stderr)
        return 2
    env = os.environ
    repo = env["GITHUB_REPOSITORY"]
    run_id = int(env["RUN_ID"])
    attempt = int(env["RUN_ATTEMPT"])
    token = env.get("GITHUB_TOKEN") or env.get("GH_TOKEN", "")
    api = http_api(token, env.get("GITHUB_API_URL", "https://api.github.com"))
    if argv[1] == "decide":
        max_attempts = int(env.get("MAC_RETRY_MAX_ATTEMPTS") or DEFAULT_MAX_ATTEMPTS)
        decision = decide(api, repo, run_id, attempt, env.get("RUN_CONCLUSION", ""), max_attempts)
        print(f"{'Rerun' if decision.rerun else 'No rerun'}: {decision.reason}")
        write_output("rerun", "true" if decision.rerun else "false")
        return 0
    done, reason = rerun(api, repo, run_id, attempt)
    print(f"{'Rerun' if done else 'No rerun'}: {reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
