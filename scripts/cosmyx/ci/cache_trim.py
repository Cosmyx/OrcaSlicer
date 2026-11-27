"""Delete the large GitHub Actions caches that "Build all" saves on the MIXED
branch (decision 0227).

MIXED is DEV merged with upstream, rebuilt by the upstream sync. Its "Build
all" runs save several gigabytes of compiler caches (ccache-*) and
flatpak-builder caches on refs/heads/MIXED. Every run saves new keys, the
repository cache limit is 10 GB and GitHub evicts the least recently used
entries, so MIXED pushed the deps caches of the other branches out before
their builds could restore them. Caches on refs/heads/MIXED are only readable
by MIXED runs, so deleting them costs MIXED a cold compile and nothing else.

What is deleted, only on refs/heads/MIXED: every key starting with one of
TRIM_PREFIXES, and every other entry of TRIM_THRESHOLD_MB or more. The deps
caches are never deleted, whatever their size: "Build OrcaSlicer" restores
them with fail-on-cache-miss, so deleting one between "Build Deps" and the
build would fail the MIXED run. The small toolchain and installer caches stay
too.

Two commands, run by .github/workflows/cosmyx-cache-trim.yml:

- trim: one pass, list the MIXED caches and delete the selected ones.
- watch: a pass every CACHE_TRIM_INTERVAL_SECONDS (default 300) while the
  "Build all" run RUN_ID is going, then a last pass once it completed or the
  deadline (CACHE_TRIM_WATCH_MINUTES, default 330) is reached. It keeps the
  peak usage of a run low, since caches are saved job by job.

Inputs come from the environment: GITHUB_REPOSITORY, GITHUB_TOKEN (or
GH_TOKEN), RUN_ID for watch, CACHE_TRIM_THRESHOLD_MB (default 256).
GITHUB_API_URL overrides the API root.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable, Iterable

# The only ref this tool ever trims. Not configurable on purpose: a typo in a
# variable must never empty the caches of DEV or of a pull request.
TRIM_REF = "refs/heads/MIXED"
TRIM_PREFIXES = ("ccache-", "flatpak-builder-")
# Part of every deps cache key (<os>-cache-orcaslicer_deps-build-<hash>).
KEEP_MARKER = "orcaslicer_deps"
# The deps caches weigh 120-160 MB; the smallest compiler cache is about 390 MB.
DEFAULT_THRESHOLD_MB = 256
DEFAULT_INTERVAL_SECONDS = 300
DEFAULT_WATCH_MINUTES = 330
PER_PAGE = 100

# (method, path) -> decoded JSON body (None for an empty reply).
Api = Callable[[str, str], object]


def select(caches: Iterable[dict], ref: str, threshold_mb: int = DEFAULT_THRESHOLD_MB,
           prefixes: tuple[str, ...] = TRIM_PREFIXES) -> list[dict]:
    """Return the caches to delete: on TRIM_REF only, and only when ref asks
    for it, those whose key has a trimmed prefix or whose size reaches the
    threshold. Deps caches and entries without a key or a ref are never
    selected."""
    if ref != TRIM_REF:
        return []
    threshold = threshold_mb * 1024 * 1024
    chosen = []
    for cache in caches:
        key = cache.get("key")
        if not isinstance(key, str) or not key or cache.get("ref") != TRIM_REF:
            continue
        if KEEP_MARKER in key:
            continue
        size = cache.get("size_in_bytes")
        large = isinstance(size, int) and not isinstance(size, bool) and size >= threshold
        if key.startswith(prefixes) or large:
            chosen.append(cache)
    return chosen


def select_keys(caches: Iterable[dict], ref: str, threshold_mb: int = DEFAULT_THRESHOLD_MB) -> list[str]:
    """The keys of select(), for logs and tests."""
    return [cache["key"] for cache in select(caches, ref, threshold_mb)]


def list_caches(api: Api, repo: str, ref: str) -> list[dict]:
    query = urllib.parse.urlencode({"ref": ref, "per_page": PER_PAGE})
    caches: list[dict] = []
    page = 1
    while True:
        reply = api("GET", f"/repos/{repo}/actions/caches?{query}&page={page}") or {}
        batch = reply.get("actions_caches") or []
        caches.extend(batch)
        if len(batch) < PER_PAGE:
            return caches
        page += 1


def trim(api: Api, repo: str, threshold_mb: int = DEFAULT_THRESHOLD_MB, log: Callable[[str], None] = print) -> int:
    """One pass. Returns the number of bytes freed."""
    freed = 0
    for cache in select(list_caches(api, repo, TRIM_REF), TRIM_REF, threshold_mb):
        size = cache.get("size_in_bytes") or 0
        try:
            api("DELETE", f"/repos/{repo}/actions/caches/{int(cache['id'])}")
        except urllib.error.HTTPError as error:
            # Already gone (another pass or GitHub's eviction got there first).
            if error.code != 404:
                raise
            log(f"gone already: {cache['key']}")
            continue
        freed += size
        log(f"deleted {size // (1024 * 1024)} MB: {cache['key']}")
    log(f"freed {freed // (1024 * 1024)} MB on {TRIM_REF}")
    return freed


def run_completed(api: Api, repo: str, run_id: int) -> bool:
    run = api("GET", f"/repos/{repo}/actions/runs/{run_id}") or {}
    return run.get("status") == "completed"


def watch(api: Api, repo: str, run_id: int, threshold_mb: int = DEFAULT_THRESHOLD_MB,
          interval: int = DEFAULT_INTERVAL_SECONDS, deadline_minutes: int = DEFAULT_WATCH_MINUTES,
          sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic,
          log: Callable[[str], None] = print) -> int:
    """Trim while the run goes, then once more after it completed."""
    end = clock() + deadline_minutes * 60
    freed = 0
    while not run_completed(api, repo, run_id):
        if clock() >= end:
            log(f"run {run_id} still going after {deadline_minutes} minutes; the completed event trims the rest")
            break
        freed += trim(api, repo, threshold_mb, log)
        sleep(interval)
    return freed + trim(api, repo, threshold_mb, log)


def http_api(token: str, root: str) -> Api:
    def call(method: str, path: str) -> object:
        request = urllib.request.Request(
            root.rstrip("/") + path,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "cosmyx-cache-trim",
            },
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read()
        return json.loads(body) if body else None

    return call


def positive_int(env: dict, name: str, default: int) -> int:
    value = env.get(name) or ""
    try:
        number = int(value) if value else default
    except ValueError:
        raise SystemExit(f"{name} must be a whole number, got {value!r}")
    if number <= 0:
        raise SystemExit(f"{name} must be positive, got {number}")
    return number


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in ("trim", "watch"):
        print("usage: cache_trim.py trim|watch", file=sys.stderr)
        return 2
    env = os.environ
    repo = env["GITHUB_REPOSITORY"]
    token = env.get("GITHUB_TOKEN") or env.get("GH_TOKEN", "")
    api = http_api(token, env.get("GITHUB_API_URL", "https://api.github.com"))
    threshold = positive_int(env, "CACHE_TRIM_THRESHOLD_MB", DEFAULT_THRESHOLD_MB)
    if argv[1] == "trim":
        trim(api, repo, threshold)
        return 0
    watch(api, repo, int(env["RUN_ID"]), threshold,
          positive_int(env, "CACHE_TRIM_INTERVAL_SECONDS", DEFAULT_INTERVAL_SECONDS),
          positive_int(env, "CACHE_TRIM_WATCH_MINUTES", DEFAULT_WATCH_MINUTES))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
