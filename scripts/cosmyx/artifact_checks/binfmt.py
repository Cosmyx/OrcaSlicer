"""Recognise PE, Mach-O and ELF binaries by their magic bytes, not by name.

Only the headers are read. Java class files share the fat Mach-O magic
(0xCAFEBABE); a real fat header has a small architecture count, so a count of
30 or more is taken as "not Mach-O".
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path

from .records import iter_files

HEADER_BYTES = 4096
MAX_FAT_ARCHS = 30

PE_MACHINES = {0x014C: "x86", 0x8664: "x64", 0xAA64: "arm64", 0x01C4: "arm", 0xA641: "arm64ec"}
MACHO_CPUS = {7: "i386", 0x01000007: "x86_64", 12: "arm", 0x0100000C: "arm64", 0x0200000C: "arm64_32"}
MACHO_OBJECT = 1
ELF_MACHINES = {3: "x86", 0x28: "arm", 0x3E: "x86_64", 0xB7: "aarch64"}


@dataclass
class BinaryFormat:
    kind: str  # pe, macho, elf
    archs: list[str] = field(default_factory=list)
    filetype: int | None = None  # Mach-O file type of the first slice

    @property
    def is_object(self) -> bool:
        return self.kind == "macho" and self.filetype == MACHO_OBJECT


def _pe(data: bytes) -> BinaryFormat | None:
    if len(data) < 0x40 or data[:2] != b"MZ":
        return None
    offset = struct.unpack_from("<I", data, 0x3C)[0]
    if offset + 6 > len(data) or data[offset:offset + 4] != b"PE\0\0":
        return None
    machine = struct.unpack_from("<H", data, offset + 4)[0]
    return BinaryFormat("pe", [PE_MACHINES.get(machine, f"0x{machine:04x}")])


def _macho_thin(data: bytes, offset: int = 0) -> tuple[str, int] | None:
    head = data[offset:offset + 16]
    if len(head) < 16:
        return None
    for endian in ("<", ">"):
        magic = struct.unpack_from(endian + "I", head, 0)[0]
        if magic in (0xFEEDFACE, 0xFEEDFACF):
            cpu, _sub, filetype = struct.unpack_from(endian + "iII", head, 4)
            return MACHO_CPUS.get(cpu & 0xFFFFFFFF, f"0x{cpu & 0xFFFFFFFF:x}"), filetype
    return None


def _macho(data: bytes) -> BinaryFormat | None:
    thin = _macho_thin(data)
    if thin:
        return BinaryFormat("macho", [thin[0]], thin[1])
    if len(data) < 8:
        return None
    magic, count = struct.unpack_from(">II", data, 0)
    if magic not in (0xCAFEBABE, 0xCAFEBABF) or not 0 < count < MAX_FAT_ARCHS:
        return None
    entry = 20 if magic == 0xCAFEBABE else 32
    archs, filetype = [], None
    for index in range(count):
        base = 8 + index * entry
        if base + entry > len(data):
            return None
        cpu = struct.unpack_from(">I", data, base)[0]
        archs.append(MACHO_CPUS.get(cpu, f"0x{cpu:x}"))
        if filetype is None:
            slice_offset = struct.unpack_from(">I" if entry == 20 else ">Q", data, base + 8)[0]
            if slice_offset + 16 <= len(data):
                thin = _macho_thin(data, slice_offset)
                filetype = thin[1] if thin else None
    return BinaryFormat("macho", archs, filetype)


def _elf(data: bytes) -> BinaryFormat | None:
    if len(data) < 20 or data[:4] != b"\x7fELF":
        return None
    endian = "<" if data[5] == 1 else ">"
    machine = struct.unpack_from(endian + "H", data, 18)[0]
    return BinaryFormat("elf", [ELF_MACHINES.get(machine, f"0x{machine:x}")])


def detect_bytes(data: bytes) -> BinaryFormat | None:
    return _pe(data) or _macho(data) or _elf(data)


def detect(path: Path) -> BinaryFormat | None:
    """The format of a file, or None when it is not a PE, Mach-O or ELF binary."""
    with open(path, "rb") as handle:
        head = handle.read(HEADER_BYTES)
    if head[:2] == b"MZ" and len(head) >= 0x40:
        # The PE header may sit past the first block.
        offset = struct.unpack_from("<I", head, 0x3C)[0]
        if offset + 6 > len(head):
            with open(path, "rb") as handle:
                head = handle.read(offset + 8)
    found = detect_bytes(head)
    if found is None and head[:4] in (b"\xca\xfe\xba\xbe", b"\xca\xfe\xba\xbf"):
        # A fat header whose slice headers lie past the first block.
        with open(path, "rb") as handle:
            found = detect_bytes(handle.read(1 << 16))
    return found


def walk(root: Path, kind: str | None = None) -> list[tuple[Path, BinaryFormat]]:
    """Every binary under root (symbolic links skipped), optionally of one kind."""
    found = []
    for path in iter_files(root):
        try:
            fmt = detect(path)
        except OSError:
            continue
        if fmt and (kind is None or fmt.kind == kind):
            found.append((path, fmt))
    return found


def elf_end(path: Path) -> int | None:
    """Where a 64-bit ELF file ends (after its section headers): the offset of
    the squashfs image an AppImage appends to its runtime."""
    with open(path, "rb") as handle:
        head = handle.read(64)
    if len(head) < 64 or head[:4] != b"\x7fELF" or head[4] != 2:
        return None
    endian = "<" if head[5] == 1 else ">"
    shoff = struct.unpack_from(endian + "Q", head, 0x28)[0]
    shentsize, shnum = struct.unpack_from(endian + "HH", head, 0x3A)
    return shoff + shentsize * shnum
