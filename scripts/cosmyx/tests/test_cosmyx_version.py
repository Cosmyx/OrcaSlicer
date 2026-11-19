"""Tests of scripts/cosmyx/cosmyx_version.py and of its wiring into the build workflow."""

from __future__ import annotations

import importlib.util
import io
import re
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

COSMYX_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = COSMYX_DIR.parents[1]

_spec = importlib.util.spec_from_file_location("cosmyx_version", COSMYX_DIR / "cosmyx_version.py")
cv = importlib.util.module_from_spec(_spec)
sys.modules["cosmyx_version"] = cv
_spec.loader.exec_module(cv)

HEADER_TEMPLATE = """// header
namespace Slic3r {{ namespace GUI {{ namespace Cosmyx {{
inline constexpr int patch_version = {patch};
}}}}}}
"""


def make_root(base: Path, upstream: str = "2.6.0", patch: str = "8") -> Path:
    (base / "version.inc").write_text(
        f'set(SLIC3R_APP_NAME "OrcaSlicer")\nset(SoftFever_VERSION "{upstream}")\n', encoding="utf-8"
    )
    header = base / cv.VERSION_HEADER
    header.parent.mkdir(parents=True)
    header.write_text(HEADER_TEMPLATE.format(patch=patch), encoding="utf-8")
    return base


def run_main(argv: list[str], env: dict[str, str] | None = None, run=None) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = cv.main(argv, env=env or {}, run=run)
    return code, out.getvalue().strip(), err.getvalue()


class ComposeTests(unittest.TestCase):
    # Same cases as tests/cosmyx/test_cosmyx_version.cpp, so both sides follow one rule.
    def test_release_base(self) -> None:
        self.assertEqual(cv.compose_display_version("2.6.0", 8), "2.6.0-8")
        self.assertEqual(cv.compose_display_version("2.3.1", 12), "2.3.1-12")

    def test_pre_release_suffix_is_kept(self) -> None:
        self.assertEqual(cv.compose_display_version("2.6.0-dev", 8), "2.6.0-dev-8")
        self.assertEqual(cv.compose_display_version("2.3.2-beta2", 9), "2.3.2-beta2-9")


class ReadTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_reads_both_sources(self) -> None:
        root = make_root(self.base, "2.6.0-dev", "11")
        self.assertEqual(cv.display_version(root), "2.6.0-dev-11")

    def test_patch_below_8_is_refused(self) -> None:
        root = make_root(self.base, patch="7")
        with self.assertRaisesRegex(cv.VersionError, "start at 8"):
            cv.patch_version(root)

    def test_missing_patch_line_is_refused(self) -> None:
        root = make_root(self.base)
        (root / cv.VERSION_HEADER).write_text("// nothing here\n", encoding="utf-8")
        with self.assertRaises(cv.VersionError):
            cv.patch_version(root)

    def test_malformed_upstream_version_is_refused(self) -> None:
        for bad in ("", "2.6", "v2.6.0", "2.6.0 dev", "2.6.0-"):
            with self.subTest(bad=bad):
                root = make_root(Path(tempfile.mkdtemp(dir=self.base)), upstream=bad)
                with self.assertRaises(cv.VersionError):
                    cv.upstream_version(root)

    def test_commented_set_line_is_not_read_as_patch(self) -> None:
        root = make_root(self.base)
        header = root / cv.VERSION_HEADER
        header.write_text("// inline constexpr int patch_version = 99;\n" + header.read_text(), encoding="utf-8")
        self.assertEqual(cv.patch_version(root), 8)


class RealRepositoryTests(unittest.TestCase):
    def test_real_files_give_a_valid_display_version(self) -> None:
        version = cv.display_version()
        self.assertRegex(version, r"^\d+\.\d+\.\d+(-[0-9A-Za-z.]+)?-\d+$")
        self.assertTrue(version.startswith(cv.upstream_version() + "-"))
        self.assertGreaterEqual(cv.patch_version(), 8)

    def test_cpp_header_declares_the_patch_once(self) -> None:
        text = (REPO_ROOT / cv.VERSION_HEADER).read_text(encoding="utf-8")
        self.assertEqual(len(cv.PATCH.findall(text)), 1)


class CommitTests(unittest.TestCase):
    def test_head_commit_without_override_uses_git_log(self) -> None:
        calls = []

        def run(args):
            calls.append(args)
            return "abc1234\n"

        self.assertEqual(cv.head_commit(run, {}), "abc1234")
        self.assertEqual(calls, [["git", "log", "-1", "--format=%h"]])

    def test_override_is_shortened_by_git(self) -> None:
        def run(args):
            self.assertEqual(args[:3], ["git", "rev-parse", "--short"])
            return "deadbee\n"

        self.assertEqual(cv.head_commit(run, {"git_commit_hash": "deadbeef" * 5}), "deadbee")

    def test_override_unknown_to_git_is_cut_to_7(self) -> None:
        def run(args):
            raise subprocess.CalledProcessError(128, args)

        self.assertEqual(cv.head_commit(run, {"git_commit_hash": "ABCDEF0123456789"}), "abcdef0")

    def test_build_tag_rejects_non_hash(self) -> None:
        for bad in ("", "abc", "ABC1234", "abc 1234", "g123456"):
            with self.subTest(bad=bad), self.assertRaises(cv.VersionError):
                cv.build_tag("2.6.0-8", bad)


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = make_root(Path(self.tmp.name), "2.6.0-dev", "8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_version(self) -> None:
        self.assertEqual(run_main(["--root", str(self.root), "version"])[:2], (0, "2.6.0-dev-8"))

    def test_build_tag_with_commit(self) -> None:
        code, out, _ = run_main(["--root", str(self.root), "build-tag", "--commit", "aa9dac8"])
        self.assertEqual((code, out), (0, "2.6.0-dev-8_aa9dac8"))

    def test_build_tag_from_git(self) -> None:
        code, out, _ = run_main(["--root", str(self.root), "build-tag"], run=lambda args: "1234abc\n")
        self.assertEqual((code, out), (0, "2.6.0-dev-8_1234abc"))

    def test_github_env_appends_ver(self) -> None:
        env_file = Path(self.tmp.name) / "github_env"
        # Bytes, not write_text: text mode would write CRLF on Windows and the
        # fixture, not the cli, would put the \r in the file.
        env_file.write_bytes(b"ver=V2.6.0-dev\n")
        code, out, _ = run_main(
            ["--root", str(self.root), "github-env", "--commit", "aa9dac8"], env={"GITHUB_ENV": str(env_file)}
        )
        self.assertEqual((code, out), (0, "2.6.0-dev-8_aa9dac8"))
        # The later line wins in GitHub Actions, so the upstream value is overridden.
        self.assertEqual(env_file.read_bytes(), b"ver=V2.6.0-dev\nver=2.6.0-dev-8_aa9dac8\n")

    def test_github_env_is_written_with_lf_on_every_os(self) -> None:
        # Text mode with the default newline writes CRLF on Windows only; GitHub
        # Actions reads $GITHUB_ENV as LF lines, so the cli must ask for LF
        # explicitly. Record the open() call so this holds on every host.
        env_file = Path(self.tmp.name) / "github_env"
        calls = []

        def spy(file, *args, **kwargs):
            calls.append((str(file), args, kwargs))
            return open(file, *args, **kwargs)

        with mock.patch.object(cv, "open", spy, create=True):
            code, _, _ = run_main(
                ["--root", str(self.root), "github-env", "--commit", "aa9dac8"], env={"GITHUB_ENV": str(env_file)}
            )
        self.assertEqual(code, 0)
        modes = [(args, kwargs) for file, args, kwargs in calls if file == str(env_file)]
        self.assertEqual(len(modes), 1)
        args, kwargs = modes[0]
        self.assertNotIn("b", (args[0] if args else kwargs.get("mode", "r")))
        self.assertEqual(kwargs.get("newline", args[3] if len(args) > 3 else None), "\n")

    def test_github_env_without_github_env_fails(self) -> None:
        code, _, err = run_main(["--root", str(self.root), "github-env", "--commit", "aa9dac8"])
        self.assertEqual(code, 1)
        self.assertIn("GITHUB_ENV", err)

    def test_error_is_reported_not_raised(self) -> None:
        (self.root / "version.inc").unlink()
        code, _, err = run_main(["--root", str(self.root), "version"])
        self.assertEqual(code, 1)
        self.assertIn("cosmyx_version:", err)


class WorkflowWiringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = (REPO_ROOT / ".github" / "workflows" / "build_orca.yml").read_text(encoding="utf-8")

    def test_one_step_writes_the_build_tag(self) -> None:
        self.assertEqual(self.text.count("scripts/cosmyx/cosmyx_version.py"), 1)
        self.assertIn('"github-env"', self.text)

    def test_step_runs_after_both_upstream_version_steps(self) -> None:
        hook = self.text.index("scripts/cosmyx/cosmyx_version.py")
        for name in ("Get the version and date on Ubuntu and macOS", "Get the version and date on Windows"):
            self.assertLess(self.text.index(f"- name: {name}"), hook, name)
        # Before the first step that names a file or an artifact after env.ver.
        first_use = re.search(r"env\.ver\s*}}", self.text[self.text.index("#   Mac"):])
        self.assertIsNotNone(first_use)
        self.assertLess(hook, self.text.index("#   Mac"))


if __name__ == "__main__":
    unittest.main()
