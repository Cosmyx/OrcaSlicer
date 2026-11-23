"""macos_signing: discovery and signing order, notarisation retries, DMG names,
verification rules and secret redaction with a fake runner; and a real ad-hoc
signing of a compiled app on macOS (cc and codesign), with a byte flip that
verification must catch (decision 0158)."""

from __future__ import annotations

import io
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from macos_signing import Context, Settings, SigningError, cli, discover, dmg, notarize, sign, verify  # noqa: E402

IDENTITY = "Developer ID Application: Example Corp (TEAM123456)"
TEAM = "TEAM123456"
APPLE_ID = "builder@example.invalid"
PASSWORD = "abcd-efgh-ijkl-mnop"
SECRETS = (IDENTITY, TEAM, APPLE_ID, PASSWORD)


def thin_macho(filetype: int = 2) -> bytes:
    return struct.pack("<IiII", 0xFEEDFACF, 0x0100000C, 0, filetype) + bytes(32)


def make_app(root: Path, name: str = "OrcaSlicer", executable: str | None = None) -> Path:
    """A fake universal-build app: main executable, a dylib, a nested framework,
    the relocated Python runtime with its link, an object file and a non-Mach-O.
    The executable is named after the app unless given (CosmoSlice.app keeps
    the OrcaSlicer executable)."""
    executable = executable or name
    app = root / "build" / "universal" / "OrcaSlicer" / f"{name}.app"
    contents = app / "Contents"
    (contents / "MacOS").mkdir(parents=True)
    (contents / "Info.plist").write_bytes(b'<?xml version="1.0"?><plist version="1.0"><dict>'
                                          b'<key>CFBundleName</key><string>' + name.encode() + b'</string>'
                                          b'<key>CFBundleExecutable</key><string>' + executable.encode() + b'</string>'
                                          b'</dict></plist>')
    (contents / "MacOS" / executable).write_bytes(thin_macho())
    (contents / "Frameworks").mkdir()
    (contents / "Frameworks" / "libfoo.dylib").write_bytes(thin_macho(6))
    fw = contents / "Frameworks" / "Bar.framework"
    (fw / "Versions" / "A" / "Resources").mkdir(parents=True)
    (fw / "Versions" / "A" / "Bar").write_bytes(thin_macho(6))
    (fw / "Versions" / "A" / "Resources" / "Info.plist").write_text("<plist/>", encoding="utf-8")
    os.symlink("A", fw / "Versions" / "Current")
    os.symlink("Versions/Current/Bar", fw / "Bar")
    python = contents / "Resources" / "python" / "lib"
    python.mkdir(parents=True)
    (python / "_ssl.cpython-312-darwin.so").write_bytes(thin_macho(8))
    (python / "module.o").write_bytes(thin_macho(1))
    (python / "readme.txt").write_text("not code", encoding="utf-8")
    os.symlink("../Resources/python", contents / "MacOS" / "python")
    return app


def done(args, code=0, out="", err=""):
    return subprocess.CompletedProcess(args, code, out, err)


class FakeRunner:
    """Answers each tool from a handler list; records every call."""

    def __init__(self, handlers=None) -> None:
        self.calls: list[list[str]] = []
        self.inputs: list[tuple[list[str], dict]] = []
        self.handlers = handlers or {}

    def __call__(self, args, **kwargs):
        args = [str(a) for a in args]
        self.calls.append(args)
        if "input" in kwargs:
            self.inputs.append((args, kwargs))
        key = " ".join(args[:3]) if args[0] == "xcrun" else args[0]
        handler = self.handlers.get(key)
        if handler is not None:
            return handler(args)
        if args[0] == "bash":
            Path(args[2].rsplit(" ", 1)[1].strip("'")).write_bytes(b"dmg")
        return done(args)

    def of(self, prefix: str) -> list[list[str]]:
        return [c for c in self.calls if " ".join(c).startswith(prefix)]


def context(runner, adhoc: bool = False, which=lambda _name: None) -> tuple[Context, list[str]]:
    lines: list[str] = []
    settings = Settings("-") if adhoc else Settings(IDENTITY, TEAM, APPLE_ID, PASSWORD, keychain="/tmp/k.keychain-db")
    return Context(settings, run=runner, sleep=lambda _s: None, which=which, out=lines.append), lines


class TempCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)


class DiscoverTests(TempCase):
    def test_finds_apps_and_fails_without_any(self) -> None:
        with self.assertRaises(SigningError):
            discover.find_apps(self.root)
        make_app(self.root)
        make_app(self.root, "OrcaSlicer_profile_validator")
        names = [p.name for p in discover.find_apps(self.root)]
        self.assertEqual(names, ["OrcaSlicer.app", "OrcaSlicer_profile_validator.app"])

    def test_plan_is_inside_out_and_skips_links_and_objects(self) -> None:
        app = make_app(self.root)
        items, objects = discover.plan(app)
        rel = [(i.path.relative_to(app.parent).as_posix(), i.kind) for i in items]
        self.assertEqual(rel[-1], ("OrcaSlicer.app", "bundle"))
        paths = [p for p, _ in rel]
        framework = paths.index("OrcaSlicer.app/Contents/Frameworks/Bar.framework")
        self.assertLess(paths.index("OrcaSlicer.app/Contents/Frameworks/Bar.framework/Versions/A/Bar"), framework)
        self.assertIn("OrcaSlicer.app/Contents/Resources/python/lib/_ssl.cpython-312-darwin.so", paths)
        self.assertNotIn("OrcaSlicer.app/Contents/MacOS/python", " ".join(paths))
        self.assertFalse(any(p.endswith("Bar.framework/Bar") or "/Current" in p for p in paths))
        self.assertFalse(any(p.endswith("readme.txt") for p in paths))
        self.assertEqual([o.name for o in objects], ["module.o"])
        # Every item is signed after everything it contains.
        for index, (path, _kind) in enumerate(rel):
            for later, _ in rel[index + 1:]:
                self.assertFalse(later.startswith(path + "/"), f"{later} after {path}")

    def test_app_without_macho_is_an_error(self) -> None:
        app = self.root / "build" / "universal" / "OrcaSlicer" / "Empty.app" / "Contents"
        app.mkdir(parents=True)
        with self.assertRaises(SigningError):
            discover.plan(app.parent)


class SignTests(TempCase):
    def test_codesign_arguments(self) -> None:
        app = make_app(self.root)
        runner = FakeRunner()
        ctx, _ = context(runner)
        count = sign.sign_app(ctx, app)
        self.assertEqual(count, 4)
        signs = [c for c in runner.calls if c[:2] == ["codesign", "--force"]]
        self.assertTrue(signs)
        for call in signs:
            self.assertNotIn("--deep", call)
            self.assertEqual(call[2:5], ["--options", "runtime", "--timestamp"])
            self.assertIn("--entitlements", call)
            self.assertTrue(call[call.index("--entitlements") + 1].endswith("disable_validation.entitlements"))
            self.assertEqual(call[call.index("--sign") + 1], IDENTITY)
            self.assertEqual(call[call.index("--keychain") + 1], "/tmp/k.keychain-db")
        self.assertEqual(signs[-1][-1], str(app))
        self.assertEqual(runner.calls[-1][:4], ["codesign", "--verify", "--deep", "--strict"])

    def test_adhoc_has_no_timestamp_or_keychain(self) -> None:
        app = make_app(self.root)
        runner = FakeRunner()
        ctx, _ = context(runner, adhoc=True)
        sign.sign_app(ctx, app)
        call = next(c for c in runner.calls if c[:2] == ["codesign", "--force"])
        self.assertIn("--timestamp=none", call)
        self.assertNotIn("--keychain", call)
        self.assertEqual(call[call.index("--sign") + 1], "-")

    def test_codesign_failure_is_redacted(self) -> None:
        app = make_app(self.root)
        runner = FakeRunner({"codesign": lambda a: done(a, 1, "", f"{IDENTITY}: no identity found")})
        ctx, _ = context(runner)
        with self.assertRaises(SigningError) as raised:
            sign.sign_app(ctx, app)
        self.assertNotIn(IDENTITY, str(raised.exception))
        self.assertIn("***", str(raised.exception))

    def test_dmg_signature(self) -> None:
        runner = FakeRunner()
        ctx, _ = context(runner)
        sign.sign_file(ctx, self.root / "x.dmg")
        call = runner.calls[0]
        self.assertNotIn("--options", call)
        self.assertIn("--timestamp", call)


def notary_handlers(wait_answers, submit_answers=None, log=None):
    counter = {"submit": 0, "wait": 0}
    waits = list(wait_answers)
    submits = list(submit_answers or [])

    def submit(args):
        counter["submit"] += 1
        if submits:
            return submits.pop(0)(args)
        return done(args, 0, json.dumps({"id": f"id-{counter['submit']}", "message": "ok"}))

    def wait(args):
        counter["wait"] += 1
        return waits.pop(0)(args) if waits else done(args, 0, json.dumps({"status": "Accepted"}))

    def log_handler(args):
        return done(args, 0, json.dumps(log or {"issues": [{"path": "a/b.dylib", "message": "not signed"}]}))

    return {"xcrun notarytool submit": submit, "xcrun notarytool wait": wait, "xcrun notarytool log": log_handler}, counter


class NotarizeTests(TempCase):
    def test_profile_needs_the_temporary_keychain(self) -> None:
        runner = FakeRunner()
        ctx, _ = context(runner)
        ctx.settings.keychain = ""
        with self.assertRaises(SigningError) as raised:
            notarize.notarize(ctx, [self.root / "a.zip"], None)
        self.assertIn("COSMYX_MAC_KEYCHAIN", str(raised.exception))
        self.assertEqual(runner.calls, [])

    def test_failed_profile_store_is_redacted(self) -> None:
        handlers = {"xcrun notarytool store-credentials": lambda a: done(a, 1, "", f"bad {APPLE_ID} {PASSWORD}")}
        ctx, _ = context(FakeRunner(handlers))
        with self.assertRaises(SigningError) as raised:
            notarize.notarize(ctx, [self.root / "a.zip"], None)
        self.assertNotIn(PASSWORD, str(raised.exception))
        self.assertNotIn(APPLE_ID, str(raised.exception))

    def test_submit_all_then_wait(self) -> None:
        handlers, _ = notary_handlers([])
        runner = FakeRunner(handlers)
        ctx, _ = context(runner)
        result = notarize.notarize(ctx, [self.root / "a.zip", self.root / "b.zip"], None)
        self.assertEqual([s.status for s in result], ["Accepted", "Accepted"])
        kinds = [c[2] for c in runner.calls]
        self.assertEqual(kinds, ["store-credentials", "submit", "submit", "wait", "wait"])
        store = runner.calls[0]
        self.assertEqual(store[3], notarize.PROFILE)
        for flag, value in (("--apple-id", APPLE_ID), ("--team-id", TEAM), ("--keychain", "/tmp/k.keychain-db")):
            self.assertEqual(store[store.index(flag) + 1], value)
        self.assertNotIn("--password", store)
        # The password is the answer to the prompt, on stdin, with no terminal.
        self.assertEqual(len(runner.inputs), 1)
        self.assertEqual(runner.inputs[0][1]["input"], PASSWORD + "\n")
        self.assertTrue(runner.inputs[0][1]["start_new_session"])
        for call in runner.calls[1:]:
            self.assertEqual(call[call.index("--keychain-profile") + 1], notarize.PROFILE)
            self.assertEqual(call[call.index("--keychain") + 1], "/tmp/k.keychain-db")
            self.assertNotIn("--password", call)
        submit = runner.calls[1]
        self.assertIn("--no-wait", submit)
        wait = runner.calls[3]
        self.assertEqual(wait[wait.index("--timeout") + 1], "40m")

    def test_network_errors_are_retried_three_times(self) -> None:
        flaky = lambda a: done(a, 1, "", "Error: The network connection was lost.")  # noqa: E731
        handlers, counter = notary_handlers([flaky, flaky], [flaky, flaky])
        runner = FakeRunner(handlers)
        ctx, _ = context(runner)
        notarize.notarize(ctx, [self.root / "a.zip"], None)
        self.assertEqual((counter["submit"], counter["wait"]), (3, 3))
        handlers, counter = notary_handlers([], [flaky, flaky, flaky])
        ctx, _ = context(FakeRunner(handlers))
        with self.assertRaises(SigningError):
            notarize.notarize(ctx, [self.root / "a.zip"], None)
        self.assertEqual(counter["submit"], 3)

    def test_invalid_is_never_retried_and_its_log_is_kept(self) -> None:
        invalid = lambda a: done(a, 1, json.dumps({"status": "Invalid", "id": "id-1"}))  # noqa: E731
        handlers, counter = notary_handlers([invalid])
        runner = FakeRunner(handlers)
        ctx, lines = context(runner)
        logs = self.root / "logs"
        with self.assertRaises(SigningError):
            notarize.notarize(ctx, [self.root / "a.zip"], logs)
        self.assertEqual(counter["wait"], 1)
        self.assertTrue((logs / "a.zip.notary-log.json").is_file())
        self.assertTrue(any("Invalid" in line for line in ctx.summary))
        self.assertTrue(any("a/b.dylib: not signed" in line for line in ctx.summary))

    def test_staple_retries_five_times(self) -> None:
        calls = []
        runner = FakeRunner({"xcrun stapler staple": lambda a: calls.append(a) or done(a, 1 if len(calls) < 5 else 0,
                                                                                         "", "Error 68")})
        ctx, _ = context(runner)
        notarize.staple(ctx, self.root / "a.app")
        self.assertEqual(len(calls), 5)
        calls.clear()
        runner = FakeRunner({"xcrun stapler staple": lambda a: calls.append(a) or done(a, 65, "", "Error 68")})
        ctx, _ = context(runner)
        with self.assertRaises(SigningError):
            notarize.staple(ctx, self.root / "a.app")
        self.assertEqual(len(calls), 5)

    def test_zip_uses_ditto_keep_parent(self) -> None:
        runner = FakeRunner()
        ctx, _ = context(runner)
        target = notarize.zip_app(ctx, self.root / "OrcaSlicer.app", self.root / "work")
        self.assertEqual(target.name, "OrcaSlicer.zip")
        self.assertEqual(runner.calls[0][:4], ["ditto", "-c", "-k", "--keepParent"])


class DmgTests(TempCase):
    def test_names_and_volume(self) -> None:
        app = make_app(self.root)
        self.assertEqual(dmg.dmg_name(app, "2.4.0-dev_abc"), "OrcaSlicer_Mac_universal_2.4.0-dev_abc.dmg")
        self.assertEqual(dmg.volume_name(app), "OrcaSlicer")
        (app / "Contents" / "Info.plist").write_text("broken", encoding="utf-8")
        self.assertEqual(dmg.volume_name(app), "OrcaSlicer")
        for damaged in ("<?xml version=\"1.0\"?><plist><dict><key>a</key>",
                        "<plist><date>x</date></plist>", "<plist><integer>zz</integer></plist>",
                        "<plist><dict><key>CFBundleName</key><integer>5</integer></dict></plist>"):
            (app / "Contents" / "Info.plist").write_text(damaged, encoding="utf-8")
            self.assertEqual(dmg.volume_name(app), "OrcaSlicer", damaged)

    def test_build_reuses_upstream_helpers(self) -> None:
        app = make_app(self.root, "OrcaSlicer_profile_validator")
        staging = self.root / "build" / "universal" / "OrcaSlicer_profile_validator_dmg"
        staging.mkdir(parents=True)
        (staging / "stale.txt").write_text("old", encoding="utf-8")
        runner = FakeRunner()
        ctx, _ = context(runner)
        output = dmg.build(ctx, app, self.root, "1.0")
        self.assertEqual(output, self.root / "OrcaSlicer_profile_validator_Mac_universal_1.0.dmg")
        self.assertFalse((staging / "stale.txt").exists())
        self.assertEqual(os.readlink(staging / "Applications"), "/Applications")
        command = runner.of("bash")[0][2]
        self.assertIn("retry.sh", command)
        self.assertIn("create_dmg.sh", command)
        self.assertIn("create_dmg OrcaSlicer_profile_validator ", command)


DEVELOPER_ID_DISPLAY = f"""Executable=/x
Identifier=com.example
CodeDirectory v=20500 size=1 flags=0x10000(runtime) hashes=1+7 location=embedded
Authority={IDENTITY}
Authority=Developer ID Certification Authority
Authority=Apple Root CA
Timestamp=19 Nov 2026 at 10:00:00
TeamIdentifier={TEAM}
"""
ADHOC_DISPLAY = """Executable=/x
CodeDirectory v=20400 size=1 flags=0x10002(adhoc,runtime) hashes=1+0 location=embedded
Signature=adhoc
TeamIdentifier=not set
"""


class VerifyRuleTests(unittest.TestCase):
    def test_parse(self) -> None:
        sig = verify.parse_display(DEVELOPER_ID_DISPLAY)
        self.assertEqual(sig.team, TEAM)
        self.assertTrue(sig.runtime and sig.timestamp and not sig.adhoc)
        self.assertTrue(sig.authorities[0].startswith("Developer ID Application:"))
        sig = verify.parse_display(ADHOC_DISPLAY)
        self.assertTrue(sig.adhoc and sig.runtime)
        self.assertEqual(sig.team, "")
        self.assertFalse(verify.parse_display("x: code object is not signed at all").signed)

    def test_rules(self) -> None:
        good = verify.parse_display(DEVELOPER_ID_DISPLAY)
        self.assertEqual(verify.file_problems(good, "", TEAM, False), [])
        self.assertIn("team", " ".join(verify.file_problems(good, "", "OTHER", False)))
        self.assertIn("get-task-allow", " ".join(verify.file_problems(good, "<key>com.apple.security.get-task-allow</key>",
                                                                       TEAM, False)))
        no_runtime = verify.parse_display(DEVELOPER_ID_DISPLAY.replace("0x10000(runtime)", "0x0(none)"))
        self.assertIn("no hardened runtime", verify.file_problems(no_runtime, "", TEAM, False))
        no_stamp = verify.parse_display(DEVELOPER_ID_DISPLAY.replace("Timestamp=", "Signed Time="))
        self.assertIn("no secure timestamp", verify.file_problems(no_stamp, "", TEAM, False))
        adhoc = verify.parse_display(ADHOC_DISPLAY)
        self.assertTrue(verify.file_problems(adhoc, "", TEAM, False))
        self.assertEqual(verify.file_problems(adhoc, "", "", True), [])


class VerifyFlowTests(TempCase):
    def handlers(self, spctl_out="accepted\nsource=Notarized Developer ID\n", display=DEVELOPER_ID_DISPLAY):
        return {
            "codesign": lambda a: done(a, 0, "", display) if a[1] == "-d" else done(a),
            "spctl": lambda a: done(a, 0, "", f"{a[-1]}: {spctl_out}"),
        }

    def test_good_build_passes(self) -> None:
        app = make_app(self.root)
        runner = FakeRunner(self.handlers())
        ctx, _ = context(runner, which=lambda name: f"/usr/bin/{name}")
        verify.verify(ctx, [app], [self.root / "a.dmg"])
        self.assertTrue(runner.of("xcrun stapler validate"))
        self.assertTrue(runner.of("syspolicy_check distribution"))
        self.assertIn("context:primary-signature", " ".join(runner.of("spctl -a -vvv -t open")[0]))

    def test_not_notarised_fails_without_leaking(self) -> None:
        app = make_app(self.root)
        runner = FakeRunner(self.handlers(spctl_out="rejected\nsource=Unnotarized Developer ID\n"))
        ctx, lines = context(runner)
        with self.assertRaises(SigningError):
            verify.verify(ctx, [app], [])
        self.assertTrue(any("spctl -t exec" in line for line in ctx.summary))
        for secret in SECRETS:
            self.assertFalse(any(secret in line for line in lines + ctx.summary), secret)

    def test_adhoc_skips_gatekeeper(self) -> None:
        app = make_app(self.root)
        runner = FakeRunner(self.handlers(display=ADHOC_DISPLAY))
        ctx, _ = context(runner, adhoc=True)
        verify.verify(ctx, [app], [self.root / "a.dmg"])
        self.assertFalse(runner.of("spctl"))
        self.assertFalse(runner.of("xcrun stapler"))


class CliTests(TempCase):
    ENV = {"COSMYX_MAC_SIGN_IDENTITY": IDENTITY, "COSMYX_MAC_TEAM_ID": TEAM, "COSMYX_MAC_APPLE_ID": APPLE_ID,
           "COSMYX_MAC_APP_PASSWORD": PASSWORD, "COSMYX_MAC_KEYCHAIN": "/tmp/k"}

    def test_settings_from_env(self) -> None:
        self.assertEqual(cli.settings_from_env(self.ENV).identity, IDENTITY)
        self.assertTrue(cli.settings_from_env({"COSMYX_MAC_SIGN_IDENTITY": "-"}).adhoc)
        with self.assertRaises(SigningError):
            cli.settings_from_env({})
        with self.assertRaises(SigningError) as raised:
            cli.settings_from_env({"COSMYX_MAC_SIGN_IDENTITY": IDENTITY})
        self.assertIn("COSMYX_MAC_APP_PASSWORD", str(raised.exception))

    def test_full_run_order_and_summary(self) -> None:
        make_app(self.root)
        make_app(self.root, "OrcaSlicer_profile_validator")
        handlers, _ = notary_handlers([])
        handlers.update(VerifyFlowTests.handlers(None))
        runner = FakeRunner(handlers)
        summary = self.root / "summary.md"
        args = cli.parser().parse_args(["run", "--root", str(self.root), "--version", "9.9", "--summary", str(summary),
                                        "--work", str(self.root / "work")])
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(cli.cmd_run(args, env=self.ENV, run=runner), 0)
        order = [c[2] if c[0] == "xcrun" else c[0] for c in runner.calls
                 if c[0] in ("xcrun", "ditto", "bash") and (c[0] != "xcrun" or c[1] != "stapler" or c[2] == "staple")]
        # apps: zip x2, notary profile stored once, submit x2, wait x2, staple x2;
        # dmgs: (ditto + bash) x2, submit x2, wait x2, staple x2 (same profile)
        self.assertEqual(order[:9], ["ditto", "ditto", "store-credentials", "submit", "submit", "wait", "wait",
                                     "staple", "staple"])
        self.assertEqual(order[9:13], ["ditto", "bash", "ditto", "bash"])
        self.assertEqual(order[13:19], ["submit", "submit", "wait", "wait", "staple", "staple"])
        self.assertEqual(len(runner.of("xcrun notarytool store-credentials")), 1)
        submitted = [Path(c[3]).name for c in runner.of("xcrun notarytool submit")]
        self.assertEqual(submitted[2:], ["OrcaSlicer_Mac_universal_9.9.dmg",
                                         "OrcaSlicer_profile_validator_Mac_universal_9.9.dmg"])
        text = summary.read_text(encoding="utf-8")
        self.assertIn("**Result: signed**", text)
        for secret in SECRETS:
            self.assertNotIn(secret, text + out.getvalue())

    def test_failed_run_reports_and_exits_1(self) -> None:
        make_app(self.root)
        invalid = lambda a: done(a, 1, json.dumps({"status": "Invalid"}))  # noqa: E731
        handlers, _ = notary_handlers([invalid])
        runner = FakeRunner(handlers)
        summary = self.root / "summary.md"
        args = cli.parser().parse_args(["run", "--root", str(self.root), "--version", "1", "--summary", str(summary),
                                        "--work", str(self.root / "work"), "--log-dir", str(self.root / "logs")])
        with redirect_stdout(io.StringIO()):
            self.assertEqual(cli.cmd_run(args, env=self.ENV, run=runner), 1)
        self.assertIn("**Result: failed**", summary.read_text(encoding="utf-8"))
        self.assertFalse(runner.of("bash"))


class CosmoSliceAppTests(TempCase):
    """The renamed app (CosmoSlice.app, executable still OrcaSlicer) is signed,
    notarised and shipped under its own name: nothing in the signing code is
    tied to OrcaSlicer.app (package names plan, decision 0154)."""

    def test_discovered_planned_and_named_after_the_app(self) -> None:
        app = make_app(self.root, "CosmoSlice", executable="OrcaSlicer")
        self.assertEqual(discover.find_apps(self.root), [app])
        items, _ = discover.plan(app)
        rel = [i.path.relative_to(app.parent).as_posix() for i in items]
        self.assertEqual(rel[-1], "CosmoSlice.app")
        self.assertIn("CosmoSlice.app/Contents/MacOS/OrcaSlicer", rel)
        self.assertEqual(dmg.dmg_name(app, "2.4.0-dev_abc"), "CosmoSlice_Mac_universal_2.4.0-dev_abc.dmg")
        self.assertEqual(dmg.volume_name(app), "CosmoSlice")

    def test_full_run_ships_the_cosmoslice_dmg(self) -> None:
        make_app(self.root, "CosmoSlice", executable="OrcaSlicer")
        handlers, _ = notary_handlers([])
        handlers.update(VerifyFlowTests.handlers(None))
        runner = FakeRunner(handlers)
        args = cli.parser().parse_args(["run", "--root", str(self.root), "--version", "9.9",
                                        "--work", str(self.root / "work")])
        with redirect_stdout(io.StringIO()):
            self.assertEqual(cli.cmd_run(args, env=CliTests.ENV, run=runner), 0)
        submitted = [Path(c[3]).name for c in runner.of("xcrun notarytool submit")]
        self.assertEqual(submitted, ["CosmoSlice.zip", "CosmoSlice_Mac_universal_9.9.dmg"])
        command = runner.of("bash")[0][2]
        self.assertIn("create_dmg CosmoSlice ", command)
        self.assertTrue((self.root / "CosmoSlice_Mac_universal_9.9.dmg").exists())
        self.assertFalse(list(self.root.glob("OrcaSlicer_*.dmg")))


REAL_TOOLS = sys.platform == "darwin" and all(shutil.which(t) for t in ("cc", "codesign"))


@unittest.skipUnless(REAL_TOOLS, "needs macOS with cc and codesign")
class RealAdhocTests(TempCase):
    """Sign a compiled app ad-hoc with the real codesign, as the CI does with
    the Developer ID identity, then break one byte."""

    def setUp(self) -> None:
        super().setUp()
        self.app = make_app(self.root)
        source = self.root / "main.c"
        source.write_text("int main(void) { return 0; }\n", encoding="utf-8")
        library = self.root / "lib.c"
        library.write_text("int cosmyx_answer(void) { return 42; }\n", encoding="utf-8")
        contents = self.app / "Contents"
        targets = [
            (["-o", contents / "MacOS" / "OrcaSlicer", source]),
            (["-dynamiclib", "-o", contents / "Frameworks" / "libfoo.dylib", library]),
            (["-dynamiclib", "-o", contents / "Frameworks" / "Bar.framework" / "Versions" / "A" / "Bar", library]),
            (["-bundle", "-o", contents / "Resources" / "python" / "lib" / "_ssl.cpython-312-darwin.so", library]),
        ]
        (contents / "Resources" / "python" / "lib" / "module.o").unlink()
        for extra in targets:
            built = subprocess.run(["cc", *[str(a) for a in extra]], capture_output=True, text=True, check=False)
            if built.returncode != 0:
                self.skipTest(f"cc cannot build here: {built.stderr.strip()[:200]}")
        framework_plist = contents / "Frameworks" / "Bar.framework" / "Versions" / "A" / "Resources" / "Info.plist"
        framework_plist.write_text('<?xml version="1.0" encoding="UTF-8"?>\n<plist version="1.0"><dict>'
                                   '<key>CFBundleExecutable</key><string>Bar</string>'
                                   '<key>CFBundleIdentifier</key><string>com.example.bar</string>'
                                   '<key>CFBundlePackageType</key><string>FMWK</string></dict></plist>\n',
                                   encoding="utf-8")
        os.symlink("Versions/Current/Resources", contents / "Frameworks" / "Bar.framework" / "Resources")
        (contents / "Info.plist").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<plist version="1.0"><dict>'
                                             '<key>CFBundleExecutable</key><string>OrcaSlicer</string>'
                                             '<key>CFBundleIdentifier</key><string>com.example.app</string>'
                                             '<key>CFBundleName</key><string>OrcaSlicer</string>'
                                             '<key>CFBundlePackageType</key><string>APPL</string></dict></plist>\n',
                                             encoding="utf-8")
        self.ctx = Context(Settings("-"), sleep=lambda _s: None, out=lambda _line: None)

    def test_adhoc_sign_and_verify(self) -> None:
        sign.sign_app(self.ctx, self.app)
        verify.verify(self.ctx, [self.app], [])
        display = subprocess.run(["codesign", "-d", "--verbose=4", str(self.app / "Contents" / "Frameworks" / "libfoo.dylib")],
                                 capture_output=True, text=True, check=False)
        self.assertTrue(verify.parse_display(display.stderr).runtime)

    def test_byte_flip_is_caught(self) -> None:
        sign.sign_app(self.ctx, self.app)
        target = self.app / "Contents" / "Resources" / "python" / "lib" / "_ssl.cpython-312-darwin.so"
        data = bytearray(target.read_bytes())
        data[len(data) // 2] ^= 0xFF
        target.write_bytes(bytes(data))
        with self.assertRaises(SigningError):
            verify.verify(self.ctx, [self.app], [])

    def test_dryrun_command_leaves_the_source_alone(self) -> None:
        before = (self.app / "Contents" / "MacOS" / "OrcaSlicer").read_bytes()
        args = cli.parser().parse_args(["dryrun", str(self.app)])
        with redirect_stdout(io.StringIO()):
            self.assertEqual(cli.cmd_dryrun(args), 0)
        self.assertEqual((self.app / "Contents" / "MacOS" / "OrcaSlicer").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
