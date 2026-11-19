"""Protocol v1 between the in-app driver and this harness (decision 0164).

The driver appends one JSON object per line to <dir>/events.jsonl:

- hello   {seq, protocol, version, GL_RENDERER, GL_VERSION, display, scale, os}
- capture {seq, id, kind main|dialog|menu|menubar, rect_px [x, y, w, h],
           scale, masks [[x, y, w, h], ...], webviews [...], title, menu}
- text    {seq, id, content}
- fail    {seq, id, reason}
- done    {seq, errors}

After a capture event the driver waits for <dir>/ack-<seq>, which the
harness writes once the screen is captured (and a menu closed), with an atomic
rename so the driver never sees half a file.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from . import GoldenError

PROTOCOL = 1
EVENTS = "events.jsonl"
KINDS = ("hello", "capture", "text", "fail", "done")
CAPTURE_KINDS = ("main", "dialog", "menu", "menubar")
REQUIRED = {
    "hello": ("protocol", "version", "GL_RENDERER", "GL_VERSION", "display", "scale", "os"),
    "capture": ("id", "kind", "rect_px", "scale", "masks", "webviews"),
    "text": ("id", "content"),
    "fail": ("id", "reason"),
    "done": ("errors",),
}


def _rect(value) -> bool:
    return isinstance(value, list) and len(value) == 4 and all(isinstance(v, int) for v in value)


def validate(event: dict) -> dict:
    """The event itself, or GoldenError naming what is wrong with it."""
    kind = event.get("event")
    if kind not in KINDS or not isinstance(event.get("seq"), int):
        raise GoldenError(f"unknown event: {event!r}")
    missing = [name for name in REQUIRED[kind] if name not in event]
    if missing:
        raise GoldenError(f"{kind} event without {', '.join(missing)}")
    if kind == "hello" and event["protocol"] != PROTOCOL:
        raise GoldenError(f"the driver speaks protocol {event['protocol']}, this harness {PROTOCOL}")
    if kind == "capture":
        if event["kind"] not in CAPTURE_KINDS:
            raise GoldenError(f"unknown capture kind {event['kind']!r}")
        if not _rect(event["rect_px"]) or not all(_rect(m) for m in event["masks"] + event["webviews"]):
            raise GoldenError(f"capture {event['id']}: bad rectangle")
    return event


class EventReader:
    """Reads the events the driver appended since the last call. A line the
    driver is still writing (no newline yet) is kept for the next call."""

    def __init__(self, directory: Path):
        self.path = directory / EVENTS
        self.offset = 0
        self.partial = b""
        self.last_seq = 0

    def poll(self) -> list[dict]:
        if not self.path.is_file():
            return []
        with self.path.open("rb") as handle:
            handle.seek(self.offset)
            chunk = handle.read()
        self.offset += len(chunk)
        data = self.partial + chunk
        lines = data.split(b"\n")
        self.partial = lines.pop()
        events = []
        for line in lines:
            if not line.strip():
                continue
            try:
                event = validate(json.loads(line.decode("utf-8")))
            except (ValueError, UnicodeDecodeError) as error:
                raise GoldenError(f"unreadable event line: {error}") from error
            if event["seq"] <= self.last_seq:
                raise GoldenError(f"event seq {event['seq']} after {self.last_seq}")
            self.last_seq = event["seq"]
            events.append(event)
        return events


def ack(directory: Path, seq: int) -> None:
    temp = directory / f".ack-{seq}.tmp"
    temp.write_bytes(b"")
    os.replace(temp, directory / f"ack-{seq}")


def text_file_name(surface_id: str) -> str:
    return f"{surface_id}.txt"


def image_file_name(surface_id: str) -> str:
    return f"{surface_id}.png"
