"""protocol v1 and the harness loop, against a fake driver that speaks the
protocol like GoldenDriver.cpp: it appends events, waits for each ack file."""

from __future__ import annotations

import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gui_goldens import GoldenError, protocol  # noqa: E402
from gui_goldens import png  # noqa: E402
from gui_goldens.cli import Pass  # noqa: E402

HELLO = {"event": "hello", "protocol": 1, "version": "2.6.0-dev-8", "GL_RENDERER": "llvmpipe", "GL_VERSION": "4.5",
         "display": "1600x1000", "scale": 1.0, "os": "linux"}


def capture(seq: int, surface: str, kind: str = "main", masks=(), webviews=()) -> dict:
    return {"seq": seq, "event": "capture", "id": surface, "kind": kind, "rect_px": [10, 20, 4, 3], "scale": 1.0,
            "masks": [list(m) for m in masks], "webviews": [list(w) for w in webviews], "title": "", "menu": "File"}


class FakeDriver(threading.Thread):
    """Writes events one by one; after a capture, waits for its ack like the
    in-app driver does, and fails loudly if it never comes."""

    def __init__(self, directory: Path, events: list[dict], partial_writes: bool = True):
        super().__init__(daemon=True)
        self.directory, self.events, self.partial_writes = directory, events, partial_writes
        self.missing_ack: int | None = None

    def run(self) -> None:
        path = self.directory / protocol.EVENTS
        with path.open("ab") as out:
            for event in self.events:
                line = json.dumps(event).encode("utf-8") + b"\n"
                if self.partial_writes:
                    # Half a line first: the reader must keep it for later.
                    out.write(line[:len(line) // 2])
                    out.flush()
                    time.sleep(0.01)
                    out.write(line[len(line) // 2:])
                else:
                    out.write(line)
                out.flush()
                if event["event"] == "capture":
                    deadline = time.monotonic() + 5
                    while not (self.directory / f"ack-{event['seq']}").exists():
                        if time.monotonic() > deadline:
                            self.missing_ack = event["seq"]
                            return
                        time.sleep(0.005)


class FakeCapturer:
    def __init__(self, fail_on: str = ""):
        self.calls: list[str] = []
        self.fail_on = fail_on

    def rect(self, rect_px, scale):
        self.calls.append(f"rect {rect_px}")
        if self.fail_on == "rect":
            raise GoldenError("screen locked")
        return png.Image(rect_px[2], rect_px[3], bytes((1, 2, 3, 255)) * (rect_px[2] * rect_px[3]))

    def popup(self):
        self.calls.append("popup")
        return png.Image(2, 2, bytes((9, 9, 9, 255)) * 4)

    def menubar(self, label):
        self.calls.append(f"menubar {label}")
        return png.Image(2, 2, bytes((8, 8, 8, 255)) * 4)

    def escape(self):
        self.calls.append("escape")

    def park_pointer(self):
        self.calls.append("park")


class ValidateTests(unittest.TestCase):
    def test_events_are_checked(self) -> None:
        self.assertEqual(protocol.validate({"seq": 1, **HELLO})["event"], "hello")
        with self.assertRaises(GoldenError):
            protocol.validate({"seq": 1, **HELLO, "protocol": 2})
        with self.assertRaises(GoldenError):
            protocol.validate({"seq": 1, "event": "capture", "id": "x"})
        with self.assertRaises(GoldenError):
            protocol.validate({**capture(2, "x"), "kind": "window"})
        with self.assertRaises(GoldenError):
            protocol.validate({**capture(2, "x"), "rect_px": [0, 0, 1]})
        with self.assertRaises(GoldenError):
            protocol.validate({"seq": "1", "event": "done", "errors": 0})

    def test_reader_keeps_partial_lines_and_checks_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            reader = protocol.EventReader(directory)
            self.assertEqual(reader.poll(), [])
            path = directory / protocol.EVENTS
            line = json.dumps({"seq": 1, **HELLO})
            path.write_text(line[:10], encoding="utf-8")
            self.assertEqual(reader.poll(), [])
            path.write_text(line + "\n" + json.dumps({"seq": 1, "event": "done", "errors": 0}) + "\n", encoding="utf-8")
            with self.assertRaises(GoldenError):
                reader.poll()

    def test_ack_is_atomic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            protocol.ack(Path(tmp), 4)
            self.assertEqual([p.name for p in Path(tmp).iterdir()], ["ack-4"])


class HarnessTests(unittest.TestCase):
    def run_pass(self, events: list[dict], capturer: FakeCapturer, webview_mask: bool = False):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        directory, images = Path(tmp.name) / "driver", Path(tmp.name) / "images"
        directory.mkdir()
        driver = FakeDriver(directory, events)
        driver.start()
        one = Pass(directory, images, capturer, webview_mask, step_timeout=5)
        one.run()
        driver.join(5)
        self.assertIsNone(driver.missing_ack, "the harness did not acknowledge a capture")
        return one, images

    def test_full_protocol_exchange(self) -> None:
        events = [{"seq": 1, **HELLO},
                  {"seq": 2, "event": "text", "id": "surfaces", "content": "00-start main\n"},
                  capture(3, "00-start", masks=[[0, 0, 1, 1]], webviews=[[1, 1, 1, 1]]),
                  capture(4, "20-menu-file", kind="menu"),
                  capture(5, "20-menu-help", kind="menubar"),
                  {"seq": 6, "event": "text", "id": "20-menu-tree", "content": "File\n  Open\n"},
                  {"seq": 7, "event": "fail", "id": "30-help-about", "reason": "no window opened"},
                  {"seq": 8, "event": "done", "errors": 1}]
        capturer = FakeCapturer()
        one, images = self.run_pass(events, capturer)
        self.assertEqual(one.done["errors"], 1)
        self.assertEqual(one.fails, [{"id": "30-help-about", "reason": "no window opened"}])
        self.assertEqual(sorted(p.name for p in images.iterdir()),
                         ["00-start.png", "20-menu-file.png", "20-menu-help.png", "20-menu-tree.txt", "surfaces.txt"])
        self.assertEqual(capturer.calls, ["park", "rect [10, 20, 4, 3]", "popup", "escape", "menubar File", "escape"])
        start = png.read(images / "00-start.png")
        self.assertEqual(start.pixel(0, 0), (255, 0, 255, 255))  # script mask always painted
        self.assertEqual(start.pixel(1, 1), (1, 2, 3, 255))  # WebView left alone on Linux
        self.assertEqual((images / "20-menu-tree.txt").read_text(encoding="utf-8"), "File\n  Open\n")
        self.assertEqual(one.environment("linux")["GL_RENDERER"], "llvmpipe")
        self.assertNotIn("version", one.environment("linux"))

    def test_webviews_are_masked_where_the_tolerance_says(self) -> None:
        events = [{"seq": 1, **HELLO}, capture(2, "10-tab-home", webviews=[[1, 1, 2, 2]]),
                  {"seq": 3, "event": "done", "errors": 0}]
        _, images = self.run_pass(events, FakeCapturer(), webview_mask=True)
        self.assertEqual(png.read(images / "10-tab-home.png").pixel(2, 2), (255, 0, 255, 255))

    def test_a_failed_capture_is_reported_and_still_acknowledged(self) -> None:
        events = [{"seq": 1, **HELLO}, capture(2, "00-start"), {"seq": 3, "event": "done", "errors": 0}]
        one, _ = self.run_pass(events, FakeCapturer(fail_on="rect"))
        self.assertEqual(one.fails, [{"id": "00-start", "reason": "capture failed: screen locked"}])

    def test_silence_and_exit_stop_the_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            now = [0.0]
            silent = Pass(directory, directory / "i", FakeCapturer(), False, clock=lambda: now[0],
                          sleep=lambda s: now.__setitem__(0, now[0] + 1.0), step_timeout=3, pass_timeout=100)
            silent.run()
            self.assertIn("no event from the driver", silent.fails[0]["reason"])
            gone = Pass(directory, directory / "i", FakeCapturer(), False, alive=lambda: False)
            gone.run()
            self.assertIn("exited", gone.fails[0]["reason"])


if __name__ == "__main__":
    unittest.main()
