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
import re
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


# Surface ids become file names (decision 0179): the same pattern as is_valid_surface_id() in
# logic/GoldenScript.cpp, which only admits lower-case ASCII names that are portable on every OS
# (no separator, no reserved Windows name, no character Windows forbids). The "surfaces" text event
# is the one fixed name outside it.
SURFACE_ID = re.compile(r"[0-9]{2}-[a-z0-9]+(-[a-z0-9]+)*", re.ASCII)
SURFACES_TEXT = "surfaces"


def _int(value) -> bool:
    # bool is a subclass of int in Python, but true is not a number in the protocol.
    return isinstance(value, int) and not isinstance(value, bool)


def _rect(value) -> bool:
    return isinstance(value, list) and len(value) == 4 and all(_int(v) for v in value)


def check_surface_id(surface_id, text: bool = False) -> str:
    """The id, or GoldenError when it cannot safely name a golden file."""
    if isinstance(surface_id, str) and (SURFACE_ID.fullmatch(surface_id) or (text and surface_id == SURFACES_TEXT)):
        return surface_id
    raise GoldenError(f"invalid surface id {surface_id!r}")


def validate(event) -> dict:
    """The event itself, or GoldenError naming what is wrong with it."""
    if not isinstance(event, dict):
        raise GoldenError(f"event is not a JSON object: {event!r}")
    kind = event.get("event")
    if kind not in KINDS or not _int(event.get("seq")):
        raise GoldenError(f"unknown event: {event!r}")
    missing = [name for name in REQUIRED[kind] if name not in event]
    if missing:
        raise GoldenError(f"{kind} event without {', '.join(missing)}")
    if kind == "hello" and event["protocol"] != PROTOCOL:
        raise GoldenError(f"the driver speaks protocol {event['protocol']}, this harness {PROTOCOL}")
    if kind == "capture":
        check_surface_id(event["id"])
        if event["kind"] not in CAPTURE_KINDS:
            raise GoldenError(f"unknown capture kind {event['kind']!r}")
        if not _rect(event["rect_px"]) or not all(
            isinstance(event[name], list) and all(_rect(m) for m in event[name]) for name in ("masks", "webviews")
        ):
            raise GoldenError(f"capture {event['id']}: bad rectangle")
        if not isinstance(event["scale"], (int, float)) or isinstance(event["scale"], bool):
            raise GoldenError(f"capture {event['id']}: scale is not a number")
    elif kind == "text":
        check_surface_id(event["id"], text=True)
        if not isinstance(event["content"], str):
            raise GoldenError(f"text {event['id']}: content is not a string")
    elif kind == "fail" and not (isinstance(event["id"], str) and isinstance(event["reason"], str)):
        raise GoldenError(f"fail event with a non-string id or reason: {event!r}")
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
    return f"{check_surface_id(surface_id, text=True)}.txt"


def image_file_name(surface_id: str) -> str:
    return f"{check_surface_id(surface_id)}.png"
