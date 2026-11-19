"""Tests of the branding pipeline: apply, revert, idempotence, the clean
git tree after apply + hide, the report, the stage plugins, the CLI and a
real-tree apply on a scratch copy of this repository's branded files."""

from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock
from pathlib import Path

from branding_fixture import (
    REAL_TREE_ENV,
    RELEASE,
    REPO_ROOT,
    TreeCase,
    apply_module,
    branding,
    cli,
    copy_real_tree,
    git,
    lf_snapshot,
    manifest,
    read,
    render,
    snapshot,
    svg,
    to_crlf,
    to_lf,
    write,
)

COSMYX_DIR = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location("worktree_clean", COSMYX_DIR / "worktree_clean.py")
worktree_clean = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worktree_clean)

COLOURS = {
    "schema": 1,
    "palette": {"brand": "#8000FF"},
    "mappings": [],
    "scopes": ["src/slic3r/*.cpp"],
    "literals": [
        {"file": "src/slic3r/GUI/Widget.cpp", "find": "wxColour(0, 150, 136)", "replace": "wxColour(128, 0, 255)", "count": 1, "reason": "brand"},
        {"file": "src/slic3r/GUI/Widget.cpp", "find": '"#009688"', "replace": '"#8000FF"', "count": 1, "reason": "brand"},
    ],
    "allow_residue": [],
}
NAME_PATCH = {"file": "version.inc", "old": 'SLIC3R_APP_NAME "OrcaSlicer"', "new": 'SLIC3R_APP_NAME "CosmoSlice"', "count": 1, "reason": "name"}


class BrandedTreeCase(TreeCase):
    def setUp(self) -> None:
        super().setUp()
        self.add_overlay("resources/images/apple.svg", svg("#8000FF"))
        self.add_overlay("resources/images/OrcaSlicer_32px.png", b"\x89PNG cosmyx")
        self.add_overlay("resources/images/OrcaSlicer_new.svg", svg("#8000FF", 8))
        write(self.root, "resources/images/zebra.svg", svg("#26a69a", css=True).replace("\n", "\r\n"))
        self.add_overlay("resources/images/zebra.svg", svg("#A472F5", css=True))
        self.write_json(branding.COLOURS_FILE, COLOURS)
        self.write_json(f"{branding.PRODUCT_NAME_DIR}/patches.json", {"schema": 1, "rows": [NAME_PATCH]})
        self.original = snapshot(self.root)


class ApplyRevertTest(BrandedTreeCase):
    def test_apply_writes_every_stage(self) -> None:
        code, lines = self.apply()
        self.assertEqual(code, 0, lines)
        self.assertEqual(read(self.root, "resources/images/apple.svg"), svg("#8000FF").encode())
        self.assertEqual(read(self.root, "resources/images/OrcaSlicer_32px.png"), b"\x89PNG cosmyx")
        self.assertTrue((self.root / "resources/images/OrcaSlicer_new.svg").is_file())
        self.assertIn(b"wxColour(128, 0, 255)", read(self.root, "src/slic3r/GUI/Widget.cpp"))
        self.assertIn(b'"CosmoSlice"', read(self.root, "version.inc"))
        self.assertIn(b'SLIC3R_APP_KEY "OrcaSlicer"', read(self.root, "version.inc"))

    def test_revert_is_exact(self) -> None:
        self.assertEqual(self.apply()[0], 0)
        restored = apply_module.revert(self.root)
        self.assertIn("resources/images/OrcaSlicer_new.svg", restored)
        self.assertEqual(snapshot(self.root), self.original)
        self.assertEqual(apply_module.revert(self.root), [])

    def test_revert_tolerates_the_backup_of_a_restored_file(self) -> None:
        """An older interrupted revert may have deleted a backup before the
        state dropped its file: the next revert takes it as restored."""
        self.assertEqual(self.apply()[0], 0)
        state = apply_module.State(self.root)
        write(self.root, "version.inc", self.original["version.inc"])
        state.backup_path("version.inc").unlink()
        with redirect_stderr(io.StringIO()) as err:
            restored = apply_module.revert(self.root)
        self.assertIn("version.inc", restored)
        self.assertIn("version.inc", err.getvalue())
        self.assertEqual(snapshot(self.root), self.original)
        self.assertFalse(apply_module.State(self.root).active)

    def test_apply_is_idempotent(self) -> None:
        self.apply()
        once = snapshot(self.root)
        self.assertEqual(self.apply()[0], 0)
        self.assertEqual(snapshot(self.root), once)
        apply_module.revert(self.root)
        self.assertEqual(snapshot(self.root), self.original)

    def test_refused_apply_writes_nothing(self) -> None:
        write(self.root, f"{branding.OVERLAY_DIR}/resources/images/apple.svg", svg("#123456"))
        before = snapshot(self.root)
        code, lines = self.apply()
        self.assertEqual(code, 1)
        self.assertEqual(snapshot(self.root), before)
        self.assertFalse(apply_module.State(self.root).active)
        self.assertTrue(any("G1" in line for line in lines))
        self.assertIn("refused", lines[-1])

    def test_release_refuses_unvalidated_rows(self) -> None:
        self.assertEqual(self.apply(env=RELEASE)[0], 1)
        self.assertEqual(snapshot(self.root), self.original)

    def test_post_guard_failure_reverts(self) -> None:
        self.write_json(branding.COLOURS_FILE, dict(COLOURS, literals=COLOURS["literals"][:1]))
        before = snapshot(self.root)
        code, lines = self.apply()
        self.assertEqual(code, 1)
        self.assertTrue(any("G5" in line and "#009688" in line for line in lines), lines)
        self.assertEqual(snapshot(self.root), before)
        report = json.loads(read(self.root, branding.REPORT_FILE))
        self.assertEqual(report["result"], "failed")

    def test_stage_error_reverts(self) -> None:
        class Broken:
            @staticmethod
            def apply(ctx, backup):
                backup("README.md")
                write(ctx.root, "README.md", "half done\n")
                raise branding.BrandingError("boom")

            @staticmethod
            def guards(ctx, phase):
                return []

        code, lines = self.apply(plugins={"product_name": [Broken]})
        self.assertEqual(code, 1)
        self.assertTrue(any("boom" in line for line in lines))
        self.assertEqual(snapshot(self.root), self.original)

    def test_plugins_run_after_the_table_rows(self) -> None:
        seen = []

        class Colours:
            @staticmethod
            def apply(ctx, backup):
                seen.append(read(ctx.root, "src/slic3r/GUI/Widget.cpp"))
                return {"rewritten": 0}

            @staticmethod
            def guards(ctx, phase):
                return []

        self.assertEqual(self.apply(plugins={"colours": [Colours]})[0], 0)
        self.assertIn(b"wxColour(128, 0, 255)", seen[0])
        report = json.loads(read(self.root, branding.REPORT_FILE))
        self.assertEqual(report["stages"]["colours"]["plugin"], {"rewritten": 0})

    def test_report_is_deterministic(self) -> None:
        self.apply()
        first = read(self.root, branding.REPORT_FILE)
        self.apply()
        self.assertEqual(read(self.root, branding.REPORT_FILE), first)
        report = json.loads(first)
        self.assertEqual(report["result"], "applied")
        self.assertEqual(report["counts"]["icons-a-m"], {"missing": 0, "to-validate": 1, "validated": 0})

    def test_ci_annotations_and_step_summary(self) -> None:
        summary = self.root / "summary.md"
        lines = []
        env = {"GITHUB_STEP_SUMMARY": str(summary), "GITHUB_REF": "refs/heads/DEV"}
        self.assertEqual(apply_module.apply(self.root, ci=True, env=env, out=lines.append, plugins={}), 0)
        self.assertTrue(any(line.startswith("::warning::P") for line in lines), lines)
        text = summary.read_text(encoding="utf-8")
        self.assertIn("### Cosmyx branding: applied (development build)", text)
        self.assertIn("| icons-a-m | 0 | 1 | 0 |", text)

    def test_check_uses_post_guards_on_a_branded_tree(self) -> None:
        self.apply()
        self.assertFalse(branding.errors(apply_module.check(self.root, {}, {})))
        write(self.root, "resources/images/apple.svg", svg("#000000"))
        self.assertTrue(any(f.guard == "G1" for f in apply_module.check(self.root, {}, {})))


TOLERANT = {branding.MODE_ENV: "tolerant"}
GONE_LITERAL = {"file": "src/slic3r/GUI/Gone.cpp", "find": '"#009688"', "replace": '"#8000FF"', "count": 1, "reason": "gone file"}
GONE_PATCH = {"file": "version.inc", "old": "SLIC3R_GONE", "new": "COSMYX_GONE", "count": 1, "reason": "gone text"}


class ModeTest(unittest.TestCase):
    """Strict by default; tolerant only off DEV (a build pull request into
    another cosmyx-ci/ base, or an integration/ branch) or when asked."""

    def test_detection(self) -> None:
        cases = [
            ({}, "strict"),
            ({"GITHUB_BASE_REF": "DEV"}, "strict"),
            ({"GITHUB_BASE_REF": "cosmyx-ci/DEV"}, "strict"),
            ({"GITHUB_REF": "refs/heads/DEV"}, "strict"),
            ({"GITHUB_REF": "refs/heads/MIXED"}, "strict"),
            ({"GITHUB_BASE_REF": "cosmyx-ci/v2.5.2"}, "tolerant"),
            ({"GITHUB_REF": "refs/heads/integration/v2.5.2"}, "tolerant"),
            ({"GITHUB_BASE_REF": "cosmyx-ci/v2.5.2", branding.MODE_ENV: "strict"}, "strict"),
            ({branding.MODE_ENV: "tolerant"}, "tolerant"),
            ({branding.MODE_ENV: " "}, "strict"),
            # A release is always complete: never tolerant.
            ({branding.MODE_ENV: "tolerant", "COSMYX_BRAND_REF": "refs/tags/v1"}, "strict"),
            ({"GITHUB_REF": "refs/heads/integration/v2.5.2", "COSMYX_BRAND_REF": "refs/heads/release/2.6"}, "strict"),
        ]
        for env, expected in cases:
            with self.subTest(env=env):
                self.assertEqual(branding.brand_mode(env), expected)

    def test_unknown_mode_is_refused(self) -> None:
        with self.assertRaises(branding.BrandingError):
            branding.brand_mode({branding.MODE_ENV: "lenient"})


class TolerantModeTest(BrandedTreeCase):
    """Off DEV, a table row whose target file or text the tree lacks is
    skipped with a warning; on DEV (strict, the default) it still fails."""

    def gone_rows(self) -> None:
        self.write_json(branding.COLOURS_FILE, dict(COLOURS, literals=[*COLOURS["literals"], GONE_LITERAL]))
        self.write_json(f"{branding.PRODUCT_NAME_DIR}/patches.json", {"schema": 1, "rows": [NAME_PATCH, GONE_PATCH]})

    def test_strict_fails_on_a_missing_file_or_text(self) -> None:
        self.gone_rows()
        before = snapshot(self.root)
        code, lines = self.apply()
        self.assertEqual(code, 1, lines)
        self.assertTrue(any("G5" in line and "Gone.cpp" in line and line.startswith("error") for line in lines), lines)
        self.assertTrue(any("G8" in line and "SLIC3R_GONE" in line and line.startswith("error") for line in lines), lines)
        self.assertEqual(snapshot(self.root), before)

    def test_tolerant_skips_them_with_a_warning(self) -> None:
        self.gone_rows()
        code, lines = self.apply(env=TOLERANT)
        self.assertEqual(code, 0, lines)
        self.assertTrue(any(line.startswith("warning: G5 src/slic3r/GUI/Gone.cpp:") and "skipped" in line for line in lines), lines)
        self.assertTrue(any(line.startswith("warning: G8 version.inc:") and "SLIC3R_GONE" in line for line in lines), lines)
        self.assertFalse([line for line in lines if line.startswith("error")], lines)
        # The rows that match are still applied.
        self.assertIn(b"wxColour(128, 0, 255)", read(self.root, "src/slic3r/GUI/Widget.cpp"))
        self.assertIn(b'"CosmoSlice"', read(self.root, "version.inc"))
        self.assertFalse((self.root / "src/slic3r/GUI/Gone.cpp").exists())
        self.assertIn("tolerant", lines[-1])
        report = json.loads(read(self.root, branding.REPORT_FILE))
        self.assertEqual(report["mode"], "tolerant")
        apply_module.revert(self.root)

    def test_tolerant_still_fails_a_wrong_count(self) -> None:
        wrong = dict(NAME_PATCH, count=2)
        self.write_json(f"{branding.PRODUCT_NAME_DIR}/patches.json", {"schema": 1, "rows": [wrong]})
        code, lines = self.apply(env=TOLERANT)
        self.assertEqual(code, 1, lines)
        self.assertTrue(any(line.startswith("error: G8") and "found 1 time(s), expected 2" in line for line in lines), lines)

    def test_strict_is_unchanged_on_dev(self) -> None:
        code, lines = self.apply(env={"GITHUB_REF": "refs/heads/DEV"})
        self.assertEqual(code, 0, lines)
        self.assertNotIn("tolerant", lines[-1])
        self.assertEqual(json.loads(read(self.root, branding.REPORT_FILE))["mode"], "strict")

    def test_overlay_of_a_gone_upstream_file(self) -> None:
        (self.root / "resources/images/apple.svg").unlink()
        # Strict keeps the drift policy: a warning on development builds,
        # and the overlay file is written.
        code, lines = self.apply()
        self.assertEqual(code, 0, lines)
        self.assertTrue((self.root / "resources/images/apple.svg").is_file())
        apply_module.revert(self.root)
        # Tolerant does not create a file the older tree never had.
        code, lines = self.apply(env=TOLERANT)
        self.assertEqual(code, 0, lines)
        self.assertFalse((self.root / "resources/images/apple.svg").exists())
        self.assertTrue(any("G3" in line and "apple.svg" in line and "skipped" in line for line in lines), lines)
        # An overlay that adds a file upstream never had is still written.
        self.assertTrue((self.root / "resources/images/OrcaSlicer_new.svg").is_file())
        apply_module.revert(self.root)
        self.assertFalse((self.root / "resources/images/apple.svg").exists())


class GitCleanTest(BrandedTreeCase):
    use_git = True

    def setUp(self) -> None:
        super().setUp()
        self.commit("tables")

    def test_tree_is_clean_after_apply_and_hide(self) -> None:
        self.assertEqual(self.apply()[0], 0)
        self.assertNotEqual(git(self.root, "diff", "--quiet", "HEAD").returncode, 0)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(worktree_clean.hide(self.root), 0)
        self.assertEqual(git(self.root, "diff", "--quiet", "HEAD").returncode, 0)

    def test_revert_after_hide_restores_and_unhides(self) -> None:
        self.apply()
        with redirect_stdout(io.StringIO()):
            worktree_clean.hide(self.root)
        apply_module.revert(self.root)
        self.assertEqual(snapshot(self.root), self.original)
        self.assertEqual(worktree_clean.hidden_files(self.root), [])
        self.assertEqual(git(self.root, "status", "--porcelain").stdout, b"")

    def test_failing_git_is_reported_with_its_message(self) -> None:
        # A container workspace git does not trust fails every call with exit
        # 128; the warning carries git's text instead of passing silently.
        failed = subprocess.CompletedProcess([], 128, stdout=b"", stderr=b"fatal: detected dubious ownership")
        err = io.StringIO()
        with mock.patch.object(apply_module.subprocess, "run", return_value=failed), redirect_stderr(err):
            apply_module.clear_skip_worktree(self.root, ["README.md"])
        self.assertIn("git ls-files -v failed", err.getvalue())
        self.assertIn("fatal: detected dubious ownership", err.getvalue())

    def test_sync_refuses_a_branded_tree(self) -> None:
        self.apply()
        lines = []
        self.assertEqual(cli.main(["--root", str(self.root), "sync"], out=lines.append), 2)
        self.assertIn("brand-revert", lines[0])


class OutsideGitTest(BrandedTreeCase):
    def test_clear_skip_worktree_is_silent_outside_git(self) -> None:
        err = io.StringIO()
        with redirect_stderr(err):
            apply_module.clear_skip_worktree(self.root, ["README.md"])
        self.assertEqual(err.getvalue(), "")


class CliTest(TreeCase):
    def run_cli(self, *args):
        lines = []
        return cli.main(["--root", str(self.root), *args], out=lines.append), lines

    def test_commands(self) -> None:
        self.assertEqual(self.run_cli("check")[0], 0)
        self.assertEqual(self.run_cli("render", "--check")[0], 0)
        write(self.root, f"{branding.TABLES_DIR}/web.md", "stale\n")
        self.assertEqual(self.run_cli("render", "--check")[0], 1)
        self.assertEqual(self.run_cli("check")[0], 1)
        self.assertEqual(self.run_cli("render")[0], 0)
        self.assertEqual(self.run_cli("sync")[0], 0)
        self.assertEqual(self.run_cli("refresh", "nothing/*")[0], 2)
        self.assertEqual(self.run_cli("refresh", "web")[0], 0)
        self.assertEqual(self.run_cli("apply")[0], 0)
        self.assertEqual(self.run_cli("revert")[0], 0)

    def test_mode_option_and_command(self) -> None:
        self.write_json(f"{branding.PRODUCT_NAME_DIR}/patches.json", {"schema": 1, "rows": [GONE_PATCH]})
        with mock.patch.dict("os.environ", {branding.MODE_ENV: "", "GITHUB_BASE_REF": "", "GITHUB_REF": ""}):
            self.assertEqual(self.run_cli("apply")[0], 1)
            self.assertEqual(self.run_cli("check")[0], 1)
            self.assertEqual(self.run_cli("check", "--mode", "tolerant")[0], 0)
            code, lines = self.run_cli("apply", "--mode", "tolerant")
            self.assertEqual(code, 0, lines)
            self.assertEqual(self.run_cli("revert")[0], 0)
            self.assertEqual(self.run_cli("mode"), (0, ["strict"]))
        with mock.patch.dict("os.environ", {branding.MODE_ENV: "", "GITHUB_BASE_REF": "cosmyx-ci/v2.5.2"}):
            self.assertEqual(self.run_cli("mode"), (0, ["tolerant"]))

    def test_validate_refuses_from_the_cli_without_the_flag(self) -> None:
        code, lines = self.run_cli("validate", "logos")
        self.assertEqual(code, 1)
        self.assertIn("refused", lines[0])


class RealTreeTest(unittest.TestCase):
    """Apply the committed tables to a scratch copy of the files they name."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        copy_real_tree(self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_committed_tables_apply_and_revert(self) -> None:
        before = snapshot(self.root)
        lines = []
        code = apply_module.apply(self.root, env=REAL_TREE_ENV, out=lines.append)
        self.assertEqual(code, 0, "\n".join(lines))
        self.assertFalse([line for line in lines if line.startswith("error")])
        apply_module.revert(self.root)
        self.assertEqual(snapshot(self.root), before)

    def test_a_vendored_logo_applies_and_reverts(self) -> None:
        target = "resources/images/OrcaSlicer.svg"
        write(self.root, f"{branding.OVERLAY_DIR}/{target}", svg("#8000FF", 64))
        # The committed row may already carry a vendored logo: re-baseline it on the new overlay.
        manifest.refresh(self.root, target)
        render.write(self.root, manifest.load(self.root))
        before = snapshot(self.root)
        self.assertEqual(apply_module.apply(self.root, env=REAL_TREE_ENV, out=lambda _: None), 0)
        self.assertEqual(read(self.root, target), svg("#8000FF", 64).encode())
        apply_module.revert(self.root)
        self.assertEqual(snapshot(self.root), before)


class CrlfRealTreeTest(unittest.TestCase):
    """A Windows checkout (core.autocrlf) of the real tree brands exactly like
    an LF one, keeps CRLF in every file it patches, and reverts byte for byte."""

    # True when this checkout already holds CRLF (Windows, core.autocrlf).
    checkout_crlf = False

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.lf = Path(self._tmp.name) / "lf"
        self.crlf = Path(self._tmp.name) / "crlf"
        copy_real_tree(self.lf)
        copy_real_tree(self.crlf)
        if self.checkout_crlf:
            to_crlf(self.lf)
            to_crlf(self.crlf)
        # Start from true LF copies whatever this checkout holds, so the CRLF
        # copy below really differs from the LF one.
        to_lf(self.lf)
        to_lf(self.crlf)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_crlf_tree_applies_like_lf(self) -> None:
        converted = to_crlf(self.crlf)
        self.assertTrue(converted)
        before = snapshot(self.crlf)
        for root in (self.lf, self.crlf):
            lines = []
            code = apply_module.apply(root, env=REAL_TREE_ENV, out=lines.append)
            self.assertEqual(code, 0, f"{root.name}:\n" + "\n".join(lines))
        lf_after, crlf_after = lf_snapshot(self.lf), lf_snapshot(self.crlf)
        self.assertEqual(sorted(crlf_after), sorted(lf_after))
        differ = [relative for relative in lf_after if crlf_after[relative] != lf_after[relative]]
        self.assertEqual(differ, [], "branded content differs between the LF and CRLF trees")
        after = snapshot(self.crlf)
        patched = [relative for relative in converted if after[relative] != before[relative]]
        if (REPO_ROOT / branding.COLOURS_FILE).is_file() or (REPO_ROOT / branding.PRODUCT_NAME_DIR).is_dir():
            # The text stages exist on this branch: they must have patched files.
            self.assertTrue(patched)
        mixed = [relative for relative in converted if after[relative].count(b"\n") != after[relative].count(b"\r\n")]
        self.assertEqual(mixed, [], "mixed line endings after apply")
        apply_module.revert(self.crlf)
        self.assertEqual(snapshot(self.crlf), before)


class CrlfRealTreeFromCrlfCheckoutTest(CrlfRealTreeTest):
    """The same test run from a checkout that is already CRLF, as on the
    Windows runners: the copies must still start as true LF and true CRLF."""

    checkout_crlf = True


if __name__ == "__main__":
    unittest.main()
