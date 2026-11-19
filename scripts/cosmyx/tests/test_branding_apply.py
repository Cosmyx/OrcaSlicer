"""Tests of the branding pipeline: apply, revert, idempotence, the clean
git tree after apply + hide, the report, the stage plugins, the CLI and a
real-tree apply on a scratch copy of this repository's branded files."""

from __future__ import annotations

import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from branding_fixture import (
    RELEASE,
    TreeCase,
    apply_module,
    branding,
    cli,
    copy_real_tree,
    git,
    manifest,
    read,
    render,
    snapshot,
    svg,
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

    def test_sync_refuses_a_branded_tree(self) -> None:
        self.apply()
        lines = []
        self.assertEqual(cli.main(["--root", str(self.root), "sync"], out=lines.append), 2)
        self.assertIn("brand-revert", lines[0])


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
        code = apply_module.apply(self.root, env={}, out=lines.append)
        self.assertEqual(code, 0, "\n".join(lines))
        self.assertFalse([line for line in lines if line.startswith("error")])
        apply_module.revert(self.root)
        self.assertEqual(snapshot(self.root), before)

    def test_a_vendored_logo_applies_and_reverts(self) -> None:
        target = "resources/images/OrcaSlicer.svg"
        write(self.root, f"{branding.OVERLAY_DIR}/{target}", svg("#8000FF", 64))
        manifest.sync(self.root)
        render.write(self.root, manifest.load(self.root))
        before = snapshot(self.root)
        self.assertEqual(apply_module.apply(self.root, env={}, out=lambda _: None), 0)
        self.assertEqual(read(self.root, target), svg("#8000FF", 64).encode())
        apply_module.revert(self.root)
        self.assertEqual(snapshot(self.root), before)


if __name__ == "__main__":
    unittest.main()
