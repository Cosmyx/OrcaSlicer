"""Breaker test for macos_signing/notarize.py: the app-specific password on
the notarytool command line."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_macos_signing import PASSWORD, FakeRunner, context, notary_handlers  # noqa: E402
from test_macos_signing import notarize  # noqa: E402


class NotaryPasswordTests(unittest.TestCase):
    def test_app_password_never_appears_in_a_child_process_argv(self) -> None:
        """Expected: the Apple app-specific password reaches notarytool without
        being an argument (a keychain profile, or another channel that is not
        argv), as cli.py promises that no secret reaches a process listing.
        Actual: every submit, wait and log call passes `--password <APP_PWD>`,
        readable by any process of the runner (ps, /proc) for the up to 40
        minutes a wait lasts, which matters on the persistent self-hosted
        macOS runners decision 0157 supports."""
        with tempfile.TemporaryDirectory() as tmp:
            handlers, _ = notary_handlers([])
            runner = FakeRunner(handlers)
            ctx, _ = context(runner)
            notarize.notarize(ctx, [Path(tmp) / "a.zip"], None)
            leaking = [call[:3] for call in runner.calls if any(PASSWORD in arg for arg in call)]
            self.assertEqual(leaking, [])


if __name__ == "__main__":
    unittest.main()
