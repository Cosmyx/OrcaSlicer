"""Which signing rules apply to a build run (decisions 0098, 0144, 0156).

The build signs when the 0098 predicate holds: Windows, not the upstream
repository, not a pull request, not MIXED, DEV or release/* (or every ref when
the variable COSMYX_SIGN_ALL_REFS is true), and the six Azure secrets are set.
The secrets cannot be read back from the build run, so the check job reads
whether they are set itself (they are repository secrets, the same for both
workflows). The checks mirror the predicate:

- enforce: the build was signed, every rule is a failure when broken;
- not-configured: a ref that would be signed, but the secrets are not all set,
  so the build is unsigned on purpose; reported with a notice (a failure in
  strict mode);
- report: pull requests, MIXED and other refs; signatures are reported only.

macOS follows the same predicate with its own seven Apple secrets (T15,
decision 0151): `mac_mode` gives the mode of the macOS checks.
"""

from __future__ import annotations

from collections.abc import Mapping

UPSTREAM_REPOSITORY = "OrcaSlicer/OrcaSlicer"
ENFORCE, NOT_CONFIGURED, REPORT = "enforce", "not-configured", "report"
NOTICE = "Windows signing not configured (0098): reported, not enforced"
SIGNING_SECRETS = (
    "AZURE_CLIENT_ID", "AZURE_TENANT_ID", "AZURE_SUBSCRIPTION_ID",
    "AZURE_TRUSTED_SIGNING_ENDPOINT", "AZURE_CODE_SIGNING_NAME", "AZURE_CERT_PROFILE_NAME",
)
MAC_NOTICE = "macOS signing not configured (0151): reported, not enforced"
MAC_SIGNING_SECRETS = (
    "BUILD_CERTIFICATE_BASE64", "P12_PASSWORD", "KEYCHAIN_PASSWORD", "MACOS_CERTIFICATE_ID",
    "APPLE_DEV_ACCOUNT", "APP_PWD", "TEAM_ID",
)
SECRET_ENV_PREFIX = "COSMYX_HAS_"


def secrets_from_env(env: Mapping[str, str]) -> dict[str, bool]:
    """Which signing secrets are set, from COSMYX_HAS_<SECRET>=true|false (the
    workflow writes `secrets.X != ''` there, never the secret itself)."""
    return {name: env.get(SECRET_ENV_PREFIX + name, "").strip().lower() == "true"
            for name in SIGNING_SECRETS + MAC_SIGNING_SECRETS}


def missing_secrets(secrets: Mapping[str, bool], names: tuple[str, ...] = SIGNING_SECRETS) -> list[str]:
    return [name for name in names if not secrets.get(name)]


def signed_ref(head_branch: str, variables: Mapping[str, str]) -> bool:
    return (head_branch == "DEV" or head_branch.startswith("release/")
            or variables.get("COSMYX_SIGN_ALL_REFS", "") == "true")


def would_sign(repository: str, event: str, head_branch: str, variables: Mapping[str, str]) -> bool:
    """The 0098 predicate without the secrets."""
    return (repository != UPSTREAM_REPOSITORY and event != "pull_request" and head_branch != "MIXED"
            and signed_ref(head_branch, variables))


def mode(repository: str, event: str, head_branch: str, variables: Mapping[str, str],
         secrets: Mapping[str, bool], names: tuple[str, ...] = SIGNING_SECRETS) -> str:
    if not would_sign(repository, event, head_branch, variables):
        return REPORT
    return NOT_CONFIGURED if missing_secrets(secrets, names) else ENFORCE


def mode_for_run(run: dict, variables: Mapping[str, str], secrets: Mapping[str, bool],
                 names: tuple[str, ...] = SIGNING_SECRETS) -> str:
    return mode(run["repository"]["full_name"], run.get("event", ""), run.get("head_branch") or "", variables, secrets,
                names)


def mac_mode_for_run(run: dict, variables: Mapping[str, str], secrets: Mapping[str, bool]) -> str:
    """The mode of the macOS checks: the same predicate with the Apple secrets."""
    return mode_for_run(run, variables, secrets, MAC_SIGNING_SECRETS)


def exec_ok(run: dict) -> bool:
    """Binaries of a build are run only when they were built from this repository
    (never a fork pull request, decision 0141)."""
    head = (run.get("head_repository") or {}).get("full_name")
    return head is not None and head == run["repository"]["full_name"]
