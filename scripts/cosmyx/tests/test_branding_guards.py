"""Tests of the branding guards: each of G1-G8 fires, and the status policy
depends on the ref (warn on development builds, fail on release builds)."""

from __future__ import annotations

import unittest

from branding_fixture import RELEASE, TreeCase, branding, guards, manifest, svg, write

COLOURS = {
    "schema": 1,
    "palette": {"brand": "#8000FF", "screen": "#A472F5"},
    "mappings": [],
    "family": {"hue": [160, 190], "min_saturation": 0.25, "min_lightness": 0.15},
    "ignore": ["#00AE42", "#1F8EEA"],
    "scopes": ["src/slic3r/*.cpp", "resources/web/*.css", "!src/slic3r/GUI/Cosmyx/*"],
    "literals": [
        {"file": "src/slic3r/GUI/Widget.cpp", "find": "wxColour(0, 150, 136)", "replace": "wxColour(128, 0, 255)", "count": 1, "reason": "brand"},
    ],
    "allow_residue": [],
}


def levels(findings):
    return sorted({finding.level for finding in findings})


class G1G2OverlayTest(TreeCase):
    def test_g1_changed_overlay(self) -> None:
        self.add_overlay("resources/images/apple.svg", svg("#8000FF"))
        self.assertEqual(self.findings(guard="G1"), [])
        write(self.root, f"{branding.OVERLAY_DIR}/resources/images/apple.svg", svg("#123456"))
        self.assertEqual(levels(self.findings(guard="G1")), ["error"])

    def test_g1_overlay_file_removed(self) -> None:
        self.add_overlay("resources/images/apple.svg", svg("#8000FF"))
        (self.root / branding.OVERLAY_DIR / "resources/images/apple.svg").unlink()
        self.assertIn("missing", self.findings(guard="G1")[0].message)

    def test_g1_post_checks_the_applied_file(self) -> None:
        self.add_overlay("resources/images/apple.svg", svg("#8000FF"))
        self.assertEqual(len(self.findings("post", guard="G1")), 1)
        write(self.root, "resources/images/apple.svg", svg("#8000FF"))
        self.assertEqual(self.findings("post", guard="G1"), [])

    def test_g2_orphan_overlay(self) -> None:
        self.add_overlay("resources/images/orphan.svg", svg("#8000FF"), sync=False)
        found = self.findings(guard="G2")
        self.assertEqual([(f.level, f.path) for f in found], [("error", "resources/images/orphan.svg")])

    def test_gitkeep_is_not_an_orphan(self) -> None:
        self.assertEqual(self.findings(guard="G2"), [])


class G3G4DriftTest(TreeCase):
    def test_clean_tree_has_no_drift(self) -> None:
        self.assertEqual(self.findings(guard="G3") + self.findings(guard="G4"), [])

    def test_g3_upstream_changed(self) -> None:
        write(self.root, "resources/images/apple.svg", svg("#009688", 32))
        self.assertEqual(levels(self.findings(guard="G3")), ["warning"])
        self.assertEqual(levels(self.findings(env=RELEASE, guard="G3")), ["error"])

    def test_g3_upstream_gone(self) -> None:
        (self.root / "resources/images/zebra.svg").unlink()
        self.assertIn("gone", self.findings(guard="G3")[0].message)

    def test_g3_upstream_added_a_new_file(self) -> None:
        self.add_overlay("resources/images/OrcaSlicer_new.svg", svg("#8000FF"))
        write(self.root, "resources/images/OrcaSlicer_new.svg", svg("#009688"))
        self.assertIn("now has", self.findings(guard="G3")[0].message)

    def test_g3_is_pre_only(self) -> None:
        write(self.root, "resources/images/apple.svg", svg("#009688", 32))
        self.assertEqual(self.findings("post", guard="G3"), [])

    def test_g4_new_teal_svg(self) -> None:
        write(self.root, "resources/images/nut.svg", svg("#00897B"))
        found = self.findings(guard="G4")
        self.assertEqual([(f.level, f.path) for f in found], [("warning", "resources/images/nut.svg")])
        self.assertEqual(levels(self.findings(env=RELEASE, guard="G4")), ["error"])

    def test_g4_new_logo(self) -> None:
        write(self.root, "resources/web/image/logo3.png", b"\x89PNG")
        self.assertEqual([f.path for f in self.findings(guard="G4")], ["resources/web/image/logo3.png"])


class G5ColoursTest(TreeCase):
    def setUp(self) -> None:
        super().setUp()
        self.colours = dict(COLOURS)

    def ctx_with_colours(self, env=None):
        self.write_json(branding.COLOURS_FILE, self.colours)
        return self.ctx(env)

    def test_inactive_without_colours_table(self) -> None:
        self.assertEqual(self.findings(guard="G5"), [])
        self.assertEqual(self.findings("post", guard="G5"), [])

    def test_literal_count_mismatch(self) -> None:
        self.assertEqual(self.findings(guard="G5", ctx=self.ctx_with_colours()), [])
        self.colours["literals"] = [dict(COLOURS["literals"][0], count=2)]
        found = self.findings(guard="G5", ctx=self.ctx_with_colours())
        self.assertEqual(levels(found), ["error"])
        self.assertIn("found 1 time(s), expected 2", found[0].message)

    def test_malformed_literal_row(self) -> None:
        self.colours["literals"] = [{"file": "src/slic3r/GUI/Widget.cpp", "find": "x"}]
        self.assertEqual(levels(self.findings(guard="G5", ctx=self.ctx_with_colours())), ["error"])

    def test_residue_after_apply(self) -> None:
        found = self.findings("post", guard="G5", ctx=self.ctx_with_colours())
        self.assertEqual(
            sorted((f.path, f.message.split()[1]) for f in found),
            [("resources/web/css/global.css", "#009688"), ("src/slic3r/GUI/Widget.cpp", "#009688")],
        )

    def test_residue_allowlist_needs_the_exact_count(self) -> None:
        self.colours["scopes"] = ["src/slic3r/*.cpp"]
        self.colours["allow_residue"] = [{"file": "src/slic3r/GUI/Widget.cpp", "match": "#009688", "count": 1, "reason": "test"}]
        self.assertEqual(self.findings("post", guard="G5", ctx=self.ctx_with_colours()), [])
        self.colours["allow_residue"] = [{"file": "src/slic3r/GUI/Widget.cpp", "match": "#009688", "count": 2, "reason": "test"}]
        self.assertEqual(len(self.findings("post", guard="G5", ctx=self.ctx_with_colours())), 1)

    def test_scope_exclusion(self) -> None:
        write(self.root, "src/slic3r/GUI/Cosmyx/Own.cpp", 'auto c = "#009688";\n')
        self.colours["scopes"] = ["src/slic3r/*.cpp", "!src/slic3r/GUI/Cosmyx/*", "!src/slic3r/GUI/Widget.cpp"]
        self.assertEqual(self.findings("post", guard="G5", ctx=self.ctx_with_colours()), [])

    def test_plugin_guards_are_called(self) -> None:
        calls = []

        class Plugin:
            @staticmethod
            def guards(ctx, phase):
                calls.append(phase)
                return [branding.Finding("G5", "error", "x", "plugin")]

        self.write_json(branding.COLOURS_FILE, self.colours)
        ctx = self.ctx(plugins={"colours": [Plugin]})
        self.assertIn("plugin", [f.message for f in guards.g5_colours(ctx, "pre")])
        self.assertEqual(calls, ["pre"])


class G6TablesTest(TreeCase):
    def test_clean(self) -> None:
        self.assertEqual(self.findings(guard="G6"), [])

    def test_stale_review_table(self) -> None:
        write(self.root, f"{branding.TABLES_DIR}/web.md", "# edited by hand\n")
        self.assertEqual([f.path for f in self.findings(guard="G6")], [f"{branding.TABLES_DIR}/web.md"])

    def test_invalid_manifest(self) -> None:
        path = self.root / branding.MANIFEST_DIR / "logos.json"
        path.write_bytes(path.read_bytes() + b"\n")
        self.assertTrue(any("canonical" in f.message for f in self.findings(guard="G6")))

    def test_colours_schema(self) -> None:
        self.write_json(branding.COLOURS_FILE, dict(COLOURS, schema=2))
        self.assertTrue(any("schema" in f.message for f in self.findings(guard="G6")))

    def test_unreadable_tables(self) -> None:
        write(self.root, branding.COLOURS_FILE, "{not json")
        write(self.root, f"{branding.PRODUCT_NAME_DIR}/patches.json", "[]")
        paths = sorted(f.path for f in self.findings(guard="G6"))
        self.assertEqual(paths, [branding.COLOURS_FILE, f"{branding.PRODUCT_NAME_DIR}/patches.json"])


    def test_malformed_row_path_refuses_instead_of_raising(self) -> None:
        """A row path the engine cannot use (`..`) makes G1 and G3 unable to
        run: they report an error and apply refuses, with no exception."""
        self.add_overlay("resources/images/apple.svg", svg("#8000FF"))
        loaded = manifest.load(self.root)
        rows = loaded.groups["icons-a-m"]
        next(row for row in rows if row["path"] == "resources/images/apple.svg")["path"] = "../apple.svg"
        manifest.save(self.root, loaded)
        found = self.findings()
        self.assertTrue(any(f.guard == "G1" and f.level == "error" for f in found), found)
        code, lines = self.apply()
        self.assertEqual(code, 1)
        self.assertIn("refused", lines[-1])

    def test_malformed_allow_residue_rows(self) -> None:
        rows = [
            "not an object",
            {"file": "", "match": "#009688", "count": 1, "reason": "t"},
            {"file": "README.md", "match": 7, "count": 1, "reason": "t"},
            {"file": "README.md", "match": "#009688", "count": True, "reason": "t"},
            {"file": "README.md", "match": "#009688", "count": 0, "reason": "t"},
            {"file": "README.md", "match": "#009688", "count": 1, "reason": " "},
        ]
        self.write_json(branding.COLOURS_FILE, dict(COLOURS, allow_residue=rows))
        found = [f for f in self.findings(guard="G6") if "allow_residue" in f.message]
        self.assertEqual(len(found), len(rows), found)
        self.findings("post")


class G7UpstreamStaysOrcaTest(TreeCase):
    use_git = True

    def test_clean(self) -> None:
        self.assertEqual(self.findings(guard="G7"), [])

    def test_product_name_in_upstream_file(self) -> None:
        write(self.root, "README.md", "CosmoSlice\n")
        write(self.root, "wiki/cosmyx/x.md", "CosmoSlice\n")
        self.commit("name")
        self.assertEqual([(f.level, f.path) for f in self.findings(guard="G7")], [("error", "README.md")])

    def test_palette_colour_in_upstream_file(self) -> None:
        self.write_json(branding.COLOURS_FILE, COLOURS)
        write(self.root, "resources/web/css/global.css", ":root { --main-color: #8000ff; }\n")
        self.commit("palette")
        self.assertEqual([f.path for f in self.findings(guard="G7")], ["resources/web/css/global.css"])

    def test_palette_colour_allowlisted_with_its_count(self) -> None:
        permit = {"file": "resources/web/css/global.css", "match": "#8000FF", "count": 1, "reason": "upstream palette"}
        self.write_json(branding.COLOURS_FILE, dict(COLOURS, allow_residue=[permit]))
        write(self.root, "resources/web/css/global.css", ":root { --main-color: #8000FF; }\n")
        self.commit("palette")
        self.assertEqual(self.findings(guard="G7"), [])

    def test_untracked_files_do_not_count(self) -> None:
        write(self.root, "notes.txt", "CosmoSlice\n")
        self.assertEqual(self.findings(guard="G7"), [])


class G7OutsideGitTest(TreeCase):
    def test_skipped_with_a_warning(self) -> None:
        self.assertEqual(levels(self.findings(guard="G7")), ["warning"])

    def test_warning_carries_git_message(self) -> None:
        # git's own text (localized, always led by "fatal") makes a CI skip
        # diagnosable, for example a container workspace git does not trust.
        [finding] = self.findings(guard="G7")
        self.assertRegex(finding.message, r"^skipped: git grep failed: .*fatal")


class G8ProductNameTest(TreeCase):
    PATCH = {"file": "version.inc", "old": 'SLIC3R_APP_NAME "OrcaSlicer"', "new": 'SLIC3R_APP_NAME "CosmoSlice"', "count": 1, "reason": "name"}

    def tables(self, rows) -> None:
        self.write_json(f"{branding.PRODUCT_NAME_DIR}/patches.json", {"schema": 1, "rows": rows})

    def test_inactive_without_tables(self) -> None:
        self.assertEqual(self.findings(guard="G8"), [])

    def test_patch_count(self) -> None:
        self.tables([self.PATCH])
        self.assertEqual(self.findings(guard="G8"), [])
        self.tables([dict(self.PATCH, count=3)])
        self.assertEqual(levels(self.findings(guard="G8")), ["error"])

    def test_app_key_must_not_change(self) -> None:
        self.tables([self.PATCH])
        ctx = self.ctx()
        self.assertEqual(guards.g8_product_name(ctx, "pre"), [])
        write(self.root, "version.inc", 'set(SLIC3R_APP_NAME "CosmoSlice")\nset(SLIC3R_APP_KEY "CosmoSlice")\n')
        self.assertEqual(levels(guards.g8_product_name(ctx, "post")), ["error"])

    def test_app_key_untouched_passes(self) -> None:
        self.tables([self.PATCH])
        ctx = self.ctx()
        guards.g8_product_name(ctx, "pre")
        write(self.root, "version.inc", 'set(SLIC3R_APP_NAME "CosmoSlice")\nset(SLIC3R_APP_KEY "OrcaSlicer")\n')
        self.assertEqual(guards.g8_product_name(ctx, "post"), [])

    def app_key_case(self, rows, after: str) -> list:
        write(self.root, "build.sh.in", "Name=@SLIC3R_APP_KEY@\nIcon=@SLIC3R_APP_KEY@\n")
        self.tables(rows)
        ctx = self.ctx()
        self.assertEqual(guards.g8_product_name(ctx, "pre"), [])
        write(self.root, "build.sh.in", after)
        return levels(guards.g8_product_name(ctx, "post"))

    def test_a_row_may_rewire_a_line_naming_the_app_key(self) -> None:
        row = {"file": "build.sh.in", "old": "Name=@SLIC3R_APP_KEY@\n", "new": "Name=@SLIC3R_APP_NAME@\n", "count": 1, "reason": "name"}
        self.assertEqual(self.app_key_case([row], "Name=@SLIC3R_APP_NAME@\nIcon=@SLIC3R_APP_KEY@\n"), [])

    def test_a_line_no_row_names_must_stay(self) -> None:
        row = {"file": "build.sh.in", "old": "Name=@SLIC3R_APP_KEY@\n", "new": "Name=@SLIC3R_APP_NAME@\n", "count": 1, "reason": "name"}
        self.assertEqual(self.app_key_case([row], "Name=@SLIC3R_APP_NAME@\nIcon=x\n"), ["error"])

    def test_new_lines_naming_the_app_key_are_fine(self) -> None:
        row = {"file": "build.sh.in", "old": "Icon=", "new": "Icon=", "count": 1, "reason": "same"}
        self.assertEqual(self.app_key_case([row], "Name=@SLIC3R_APP_KEY@\nIcon=@SLIC3R_APP_KEY@\nX=SLIC3R_APP_KEY\n"), [])

    APPIMAGE = "src/dev-utils/platform/unix/build_appimage.sh.in"
    APPIMAGE_TEXT = (
        'APP_IMAGE="@SLIC3R_APP_KEY@_Linux_V@SoftFever_VERSION@.AppImage"\n'
        "cat <<EOF > com.orcaslicer.@SLIC3R_APP_KEY@.desktop\n[Desktop Entry]\nName=@SLIC3R_APP_KEY@\nEOF\n"
        "mv @SLIC3R_APP_KEY@-$(uname -m).AppImage ${APP_IMAGE}\n"
    )
    APPIMAGE_ROW = {"file": APPIMAGE, "old": "Name=@SLIC3R_APP_KEY@\n", "new": "Name=@SLIC3R_APP_NAME@\n", "count": 1,
                    "reason": "AppImage desktop entry name"}

    def test_renaming_the_appimage_desktop_name_is_an_error(self) -> None:
        # Integration build 44545583808: appimagetool named the AppImage after
        # the renamed desktop entry, and the script's mv of
        # @SLIC3R_APP_KEY@-<arch>.AppImage found nothing.
        write(self.root, self.APPIMAGE, self.APPIMAGE_TEXT)
        self.tables([self.APPIMAGE_ROW])
        ctx = self.ctx()
        self.assertEqual(guards.g8_product_name(ctx, "pre"), [])
        write(self.root, self.APPIMAGE, self.APPIMAGE_TEXT.replace("Name=@SLIC3R_APP_KEY@", "Name=@SLIC3R_APP_NAME@"))
        [finding] = guards.g8_product_name(ctx, "post")
        self.assertEqual((finding.level, finding.path), ("error", self.APPIMAGE))
        self.assertIn("packaging identifier", finding.message)

    def test_untouched_packaging_pins_pass(self) -> None:
        write(self.root, self.APPIMAGE, self.APPIMAGE_TEXT)
        self.tables([self.PATCH])
        ctx = self.ctx()
        self.assertEqual(guards.g8_product_name(ctx, "pre"), [])
        self.assertEqual(guards.g8_product_name(ctx, "post"), [])

    def test_a_pinned_file_without_its_pin_is_drift(self) -> None:
        write(self.root, self.APPIMAGE, self.APPIMAGE_TEXT.replace("mv @SLIC3R_APP_KEY@-", "mv X-"))
        self.tables([self.PATCH])
        self.assertEqual(levels(guards.g8_product_name(self.ctx(), "pre")), ["warning"])
        self.assertEqual(levels(guards.g8_product_name(self.ctx(RELEASE), "pre")), ["error"])

    def test_crlf_pinned_file_still_matches(self) -> None:
        write(self.root, self.APPIMAGE, self.APPIMAGE_TEXT.replace("\n", "\r\n"))
        self.tables([self.PATCH])
        self.assertEqual(guards.g8_product_name(self.ctx(), "pre"), [])

    def test_the_app_key_definition_never_goes(self) -> None:
        row = {"file": "version.inc", "old": 'set(SLIC3R_APP_KEY "OrcaSlicer")', "new": 'set(SLIC3R_APP_KEY "Other")', "count": 1, "reason": "bad"}
        self.tables([row])
        ctx = self.ctx()
        guards.g8_product_name(ctx, "pre")
        write(self.root, "version.inc", 'set(SLIC3R_APP_NAME "OrcaSlicer")\nset(SLIC3R_APP_KEY "Other")\n')
        self.assertEqual(levels(guards.g8_product_name(ctx, "post")), ["error"])


class StatusPolicyTest(TreeCase):
    def test_missing_warns_on_development(self) -> None:
        found = self.findings(guard="P")
        self.assertEqual(levels(found), ["warning"])
        self.assertEqual(sorted(f.path for f in found), sorted(branding.GROUPS))

    def test_to_validate_warns_on_pull_requests_and_fails_on_release(self) -> None:
        self.add_overlay("resources/images/apple.svg", svg("#8000FF"))
        pr = {"GITHUB_EVENT_NAME": "pull_request", "GITHUB_BASE_REF": "release/2.6", "GITHUB_REF": "refs/pull/1/merge"}
        mixed = {"GITHUB_REF": "refs/heads/MIXED"}
        tag = {"GITHUB_REF": "refs/tags/v2.6.0-8"}
        for env, expected in ((pr, "warning"), (mixed, "warning"), (RELEASE, "error"), (tag, "error")):
            with self.subTest(env=env):
                found = [f for f in self.findings(env=env, guard="P") if "to-validate" in f.message]
                self.assertEqual(levels(found), [expected])

    def test_all_validated_is_silent(self) -> None:
        for _, row in manifest.load(self.root).rows():
            if row["path"] != "resources/images/apple.svg":
                (self.root / row["path"]).unlink()
        self.add_overlay("resources/images/apple.svg", svg("#8000FF"))
        manifest.mark_validated(self.root, "icons-a-m")
        self.assertEqual(self.findings(env=RELEASE, guard="P"), [])

if __name__ == "__main__":
    unittest.main()
