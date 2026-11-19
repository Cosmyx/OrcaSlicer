"""Tests of the branding manifest: paths, hex rule, discovery, sync, refresh,
validation, review tables, the user-only validate gate and the ref policy."""

from __future__ import annotations

import json
import struct
import unittest

from branding_fixture import (
    REPO_ROOT,
    TreeCase,
    branding,
    cli,
    manifest,
    png,
    read,
    render,
    svg,
    write,
)


def rows_by_path(root):
    return {row["path"]: (group, row) for group, row in manifest.load(root).rows()}


class PathRuleTest(unittest.TestCase):
    def test_rejects_unsafe_paths(self) -> None:
        for bad in ("", "/etc/passwd", "C:/x.svg", "C:x.svg", "a\\b.svg", "../x.svg", "a/../b.svg", "a//b", "a/./b", "a/"):
            with self.subTest(path=bad):
                with self.assertRaises(branding.BrandingError):
                    branding.check_relative(bad)

    def test_accepts_relative_posix_paths(self) -> None:
        for good in ("x.svg", "resources/images/a b.svg", "resources/web/\u00e9t\u00e9.svg"):
            self.assertEqual(branding.check_relative(good), good)

    def test_cosmyx_paths(self) -> None:
        self.assertTrue(branding.is_cosmyx_path("cosmyx-src/branding/colours.json"))
        self.assertTrue(branding.is_cosmyx_path("src/slic3r/GUI/Cosmyx/ColorMode.cpp"))
        self.assertTrue(branding.is_cosmyx_path("resources/images/menu_add_part_cosmyx.svg"))
        self.assertFalse(branding.is_cosmyx_path("src/slic3r/GUI/Plater.cpp"))


class HexRuleTest(unittest.TestCase):
    def test_forms_and_case(self) -> None:
        text = 'fill="#009688" style="fill:#26a69a" stop-color="#00675B80" x="#0096889"'
        self.assertEqual(branding.find_hexes(text), ["#009688", "#26A69A", "#00675B"])

    def test_skips_references_and_base64(self) -> None:
        text = 'href="#009688" xlink:href="#26A69A" fill="url(#00675B)" mask="url( '#52C7B8')"'
        self.assertEqual(branding.find_hexes(text), [])

    def test_family(self) -> None:
        for teal in ("#009688", "#26A69A", "#00675B", "#52C7B8", "#E5F0EE", "#223C3C"):
            self.assertTrue(branding.in_family(teal), teal)
        for other in ("#00AE42", "#1F8EEA", "#808080", "#8000FF", "#283232", "#000000"):
            self.assertFalse(branding.in_family(other), other)

    def test_text_hash_ignores_crlf(self) -> None:
        self.assertEqual(branding.content_sha256(b"a\r\nb\n", "svg"), branding.content_sha256(b"a\nb\n", "svg"))
        self.assertNotEqual(branding.content_sha256(b"a\r\nb\n", "png"), branding.content_sha256(b"a\nb\n", "png"))


class RefPolicyTest(unittest.TestCase):
    def test_kinds(self) -> None:
        cases = [
            ({}, "development"),
            ({"GITHUB_REF": "refs/heads/DEV"}, "development"),
            ({"GITHUB_REF": "refs/heads/MIXED"}, "development"),
            ({"GITHUB_REF": "refs/heads/release/2.6"}, "release"),
            ({"GITHUB_REF": "refs/tags/v2.6.0-8"}, "release"),
            ({"GITHUB_EVENT_NAME": "pull_request", "GITHUB_REF": "refs/pull/3/merge", "GITHUB_BASE_REF": "release/2.6"}, "development"),
            ({"COSMYX_BRAND_REF": "refs/tags/v1", "GITHUB_REF": "refs/heads/DEV"}, "release"),
        ]
        for env, expected in cases:
            with self.subTest(env=env):
                self.assertEqual(branding.ref_kind(env), expected)


class ImageSizeTest(TreeCase):
    def test_sizes(self) -> None:
        ico = b"\x00\x00\x01\x00" + struct.pack("<H", 2) + bytes([16, 16]) + b"\x00" * 14 + bytes([0, 0]) + b"\x00" * 14
        gif = b"GIF89a" + struct.pack("<HH", 7, 9)
        cases = {
            "a.png": (png(3, 5), "3x5"),
            "a.ico": (ico, "16,256"),
            "a.gif": (gif, "7x9"),
            "a.icns": (b"icns\x00\x00\x00\x08", "multi"),
            "a.svg": ('<svg width="10" height="12.5"></svg>', "10x12.5"),
            "b.svg": (svg("#000", 24), "24x24"),
        }
        for name, (content, expected) in cases.items():
            with self.subTest(name=name):
                self.assertEqual(manifest.image_size(write(self.root, f"sizes/{name}", content)), expected)


class SyncTest(TreeCase):
    def test_discovery_groups_and_missing_status(self) -> None:
        rows = rows_by_path(self.root)
        expected = {
            "resources/images/OrcaSlicer.svg": "logos",
            "resources/images/OrcaSlicer_32px.png": "logos",
            "scripts/msix/assets/StoreLogo.png": "logos",
            "resources/images/apple.svg": "icons-a-m",
            "resources/images/zebra.svg": "icons-n-z",
            "resources/web/img/check_g.svg": "web",
        }
        self.assertEqual({path: group for path, (group, _) in rows.items()}, expected)
        for path, (group, row) in rows.items():
            self.assertEqual(row["status"], "missing")
            self.assertIsNone(row["override_sha256"])
            self.assertEqual(row["upstream_sha256"], branding.file_sha256(self.root / path))
            self.assertEqual(row["kind"], "logo" if group == "logos" else "recolour")
        self.assertEqual(rows["resources/images/OrcaSlicer.svg"][1]["size"], "64x64")
        self.assertEqual(manifest.validate(self.root), [])

    def test_sync_is_deterministic(self) -> None:
        before = {group: read(self.root, f"{branding.MANIFEST_DIR}/{group}.json") for group in branding.GROUPS}
        tables = {group: read(self.root, f"{branding.TABLES_DIR}/{group}.md") for group in branding.GROUPS}
        stats = self.sync()
        self.assertEqual((stats["added"], stats["dropped"], stats["updated"]), (0, 0, 0))
        for group in branding.GROUPS:
            self.assertEqual(read(self.root, f"{branding.MANIFEST_DIR}/{group}.json"), before[group])
            self.assertEqual(read(self.root, f"{branding.TABLES_DIR}/{group}.md"), tables[group])
        self.assertTrue(before["logos"].endswith(b"\n"))
        self.assertNotIn(b"\r", before["logos"])

    def test_usage_is_preserved(self) -> None:
        current = manifest.load(self.root)
        for _, row in current.rows():
            row["usage"] = "kept"
        manifest.save(self.root, current)
        self.sync()
        self.assertTrue(all(row["usage"] == "kept" for _, row in manifest.load(self.root).rows()))

    def test_drops_rows_that_no_longer_need_one(self) -> None:
        (self.root / "resources/images/apple.svg").unlink()
        write(self.root, "resources/images/zebra.svg", svg("#808080"))
        stats = self.sync()
        self.assertEqual(stats["dropped"], 2)
        self.assertNotIn("resources/images/apple.svg", rows_by_path(self.root))

    def test_updates_hash_of_missing_rows(self) -> None:
        write(self.root, "resources/images/apple.svg", svg("#009688", 32))
        self.assertEqual(self.sync()["updated"], 1)
        row = rows_by_path(self.root)["resources/images/apple.svg"][1]
        self.assertEqual(row["upstream_sha256"], branding.file_sha256(self.root / "resources/images/apple.svg"))
        self.assertEqual(row["size"], "32x32")

    def test_records_new_overlay_as_to_validate(self) -> None:
        self.add_overlay("resources/images/apple.svg", svg("#8000FF"))
        row = rows_by_path(self.root)["resources/images/apple.svg"][1]
        self.assertEqual(row["status"], "to-validate")
        self.assertEqual(row["source"], "user")
        self.assertEqual(row["override_sha256"], branding.file_sha256(self.root / branding.OVERLAY_DIR / "resources/images/apple.svg"))

    def test_overlay_without_upstream_gets_a_row(self) -> None:
        self.add_overlay("resources/images/OrcaSlicer_new.svg", svg("#8000FF", 8))
        group, row = rows_by_path(self.root)["resources/images/OrcaSlicer_new.svg"]
        self.assertEqual((group, row["upstream_sha256"], row["size"]), ("logos", None, "8x8"))

    def test_never_rebaselines_an_override(self) -> None:
        self.add_overlay("resources/images/apple.svg", svg("#8000FF"))
        before = rows_by_path(self.root)["resources/images/apple.svg"][1]
        write(self.root, "resources/images/apple.svg", svg("#009688", 48))
        self.sync()
        self.assertEqual(rows_by_path(self.root)["resources/images/apple.svg"][1], before)


class RefreshAndValidateTest(TreeCase):
    def test_refresh_rebaselines_and_asks_review_again(self) -> None:
        self.add_overlay("resources/images/apple.svg", svg("#8000FF"))
        current = manifest.load(self.root)
        for _, row in current.rows():
            if row["path"] == "resources/images/apple.svg":
                row["status"] = "validated"
        manifest.save(self.root, current)
        write(self.root, "resources/images/apple.svg", svg("#009688", 48))
        self.assertEqual(manifest.refresh(self.root, "resources/images/apple*"), ["resources/images/apple.svg"])
        row = rows_by_path(self.root)["resources/images/apple.svg"][1]
        self.assertEqual(row["status"], "to-validate")
        self.assertEqual(row["upstream_sha256"], branding.file_sha256(self.root / "resources/images/apple.svg"))

    def test_refresh_needs_a_match(self) -> None:
        with self.assertRaises(branding.BrandingError):
            manifest.refresh(self.root, "nothing/*")

    def test_mark_validated_only_touches_to_validate_rows(self) -> None:
        self.add_overlay("resources/images/apple.svg", svg("#8000FF"))
        self.assertEqual(manifest.mark_validated(self.root, "icons-a-m"), ["resources/images/apple.svg"])
        self.assertEqual(manifest.mark_validated(self.root, "logos"), [])
        statuses = {path: row["status"] for path, (_, row) in rows_by_path(self.root).items()}
        self.assertEqual(statuses["resources/images/apple.svg"], "validated")
        self.assertEqual(statuses["resources/images/OrcaSlicer.svg"], "missing")

    def test_mark_validated_refuses_a_changed_overlay(self) -> None:
        self.add_overlay("resources/images/apple.svg", svg("#8000FF"))
        write(self.root, f"{branding.OVERLAY_DIR}/resources/images/apple.svg", svg("#123456"))
        with self.assertRaises(branding.BrandingError):
            manifest.mark_validated(self.root, "icons-a-m")


class ValidateGateTest(TreeCase):
    def run_validate(self, flag=True, env=None, tty=True, answer="validate"):
        lines = []
        code = cli.cmd_validate(self.root, "icons-a-m", flag, lines.append, env=env or {}, isatty=lambda: tty, ask=lambda _: answer)
        status = rows_by_path(self.root)["resources/images/apple.svg"][1]["status"]
        return code, status, lines

    def setUp(self) -> None:
        super().setUp()
        self.add_overlay("resources/images/apple.svg", svg("#8000FF"))

    def test_refuses_without_the_flag(self) -> None:
        code, status, lines = self.run_validate(flag=False)
        self.assertEqual((code, status), (1, "to-validate"))
        self.assertIn("agents must never run it", lines[0])

    def test_refuses_in_ci(self) -> None:
        self.assertEqual(self.run_validate(env={"CI": "true"})[:2], (1, "to-validate"))
        self.assertEqual(self.run_validate(env={"GITHUB_ACTIONS": "true"})[:2], (1, "to-validate"))

    def test_refuses_without_a_terminal(self) -> None:
        self.assertEqual(self.run_validate(tty=False)[:2], (1, "to-validate"))

    def test_refuses_without_confirmation(self) -> None:
        self.assertEqual(self.run_validate(answer="y")[:2], (1, "to-validate"))

    def test_validates_with_flag_terminal_and_confirmation(self) -> None:
        self.assertEqual(self.run_validate()[:2], (0, "validated"))
        self.assertEqual(render.stale(self.root, manifest.load(self.root)), [])

    def test_env_variable_replaces_the_flag(self) -> None:
        self.assertEqual(self.run_validate(flag=False, env={"COSMYX_BRAND_VALIDATOR": "me"})[:2], (0, "validated"))


class TableValidationTest(TreeCase):
    def edit(self, group, change) -> None:
        path = self.root / branding.MANIFEST_DIR / f"{group}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        change(data)
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    def assert_problem(self, text: str) -> None:
        problems = manifest.validate(self.root)
        self.assertTrue(any(text in problem for problem in problems), problems)

    def test_unsorted_rows(self) -> None:
        self.edit("logos", lambda data: data["rows"].reverse())
        self.assert_problem("not sorted")

    def test_duplicate_across_groups(self) -> None:
        row = rows_by_path(self.root)["resources/images/apple.svg"][1]
        self.edit("logos", lambda data: data["rows"].append(dict(row, path="resources/images/apple.svg")))
        self.assert_problem("is listed in")

    def test_status_must_match_override(self) -> None:
        self.edit("icons-a-m", lambda data: data["rows"][0].update(status="validated"))
        self.assert_problem("if and only if")

    def test_wrong_group(self) -> None:
        self.edit("icons-n-z", lambda data: data["rows"][0].update(path="resources/images/b.svg"))
        self.assert_problem("belongs to group icons-a-m")

    def test_unsafe_path(self) -> None:
        self.edit("logos", lambda data: data["rows"][0].update(path="../evil.svg"))
        self.assert_problem("'..'")

    def test_field_order_and_enums(self) -> None:
        self.edit("web", lambda data: data["rows"][0].update(kind="banner"))
        self.assert_problem("kind must be")
        self.edit("web", lambda data: data["rows"].__setitem__(0, dict(reversed(list(data["rows"][0].items())))))
        self.assert_problem("fields must be exactly")

    def test_non_canonical_form(self) -> None:
        path = self.root / branding.MANIFEST_DIR / "web.json"
        path.write_bytes(path.read_bytes().replace(b"\n  ", b"\n    "))
        self.assert_problem("canonical")

    def test_crlf_checkout_is_canonical(self) -> None:
        # A Windows checkout (core.autocrlf) turns the committed LF into CRLF.
        for group in branding.GROUPS:
            path = self.root / branding.MANIFEST_DIR / f"{group}.json"
            path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
            table = render.table_path(self.root, group)
            table.write_bytes(table.read_bytes().replace(b"\n", b"\r\n"))
        self.assertEqual(manifest.validate(self.root), [])
        self.assertEqual(render.stale(self.root, manifest.load(self.root)), [])

    def test_missing_group_file(self) -> None:
        (self.root / branding.MANIFEST_DIR / "web.json").unlink()
        self.assert_problem("web.json is missing")


class CommittedTablesTest(unittest.TestCase):
    """The tables committed in this repository."""

    def test_valid_canonical_and_rendered(self) -> None:
        self.assertEqual(manifest.validate(REPO_ROOT), [])
        self.assertEqual(render.stale(REPO_ROOT, manifest.load(REPO_ROOT)), [])

    def test_every_row_points_at_a_real_file(self) -> None:
        for _, row in manifest.load(REPO_ROOT).rows():
            with self.subTest(path=row["path"]):
                self.assertTrue((REPO_ROOT / row["path"]).is_file() or row["upstream_sha256"] is None)


if __name__ == "__main__":
    unittest.main()
