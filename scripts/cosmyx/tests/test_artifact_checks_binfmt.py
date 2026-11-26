"""binfmt: PE, Mach-O and ELF recognised by magic, from headers built at runtime."""

from __future__ import annotations

import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from artifact_checks import binfmt  # noqa: E402


def pe(machine: int, pe_offset: int = 0x80) -> bytes:
    data = bytearray(pe_offset + 24)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, pe_offset)
    data[pe_offset:pe_offset + 4] = b"PE\0\0"
    struct.pack_into("<H", data, pe_offset + 4, machine)
    return bytes(data)


def macho(cpu: int, filetype: int = 2, bits64: bool = True) -> bytes:
    magic = 0xFEEDFACF if bits64 else 0xFEEDFACE
    return struct.pack("<IiII", magic, cpu, 0, filetype) + bytes(16)


def fat(*cpus: int) -> bytes:
    count = len(cpus)
    header = struct.pack(">II", 0xCAFEBABE, count)
    slices = b""
    offset = 4096
    body = bytearray()
    for cpu in cpus:
        slices += struct.pack(">iiIII", cpu, 0, offset + len(body), 32, 12)
        body += macho(cpu) + bytes(0)
    data = bytearray(header + slices)
    data += bytes(offset - len(data))
    return bytes(data + body)


def elf(machine: int, big_endian: bool = False, shoff: int = 0x1000, shnum: int = 3) -> bytes:
    endian = ">" if big_endian else "<"
    data = bytearray(64)
    data[:4] = b"\x7fELF"
    data[4] = 2
    data[5] = 2 if big_endian else 1
    struct.pack_into(endian + "H", data, 18, machine)
    struct.pack_into(endian + "Q", data, 0x28, shoff)
    struct.pack_into(endian + "HH", data, 0x3A, 64, shnum)
    return bytes(data)


class DetectTests(unittest.TestCase):
    def test_pe_machines(self) -> None:
        for machine, arch in ((0x8664, "x64"), (0xAA64, "arm64"), (0x014C, "x86")):
            with self.subTest(arch=arch):
                found = binfmt.detect_bytes(pe(machine))
                self.assertEqual((found.kind, found.archs), ("pe", [arch]))

    def test_mz_without_pe_signature_is_not_pe(self) -> None:
        data = bytearray(pe(0x8664))
        data[0x80:0x84] = b"NE\0\0"
        self.assertIsNone(binfmt.detect_bytes(bytes(data)))

    def test_pe_header_past_the_first_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "far.dll"
            path.write_bytes(pe(0xAA64, pe_offset=6000))
            self.assertEqual(binfmt.detect(path).archs, ["arm64"])

    def test_thin_macho(self) -> None:
        self.assertEqual(binfmt.detect_bytes(macho(0x0100000C)).archs, ["arm64"])
        self.assertEqual(binfmt.detect_bytes(macho(0x01000007)).archs, ["x86_64"])
        self.assertTrue(binfmt.detect_bytes(macho(0x0100000C, filetype=1)).is_object)

    def test_fat_macho(self) -> None:
        found = binfmt.detect_bytes(fat(0x0100000C, 0x01000007))
        self.assertEqual((found.kind, found.archs, found.filetype), ("macho", ["arm64", "x86_64"], 2))

    def test_java_class_is_not_macho(self) -> None:
        # Java 8 class file: CAFEBABE, minor 0, major 52 -> "count" 52.
        java = struct.pack(">IHH", 0xCAFEBABE, 0, 52) + bytes(64)
        self.assertIsNone(binfmt.detect_bytes(java))
        # A count just below the limit is still Mach-O.
        self.assertIsNotNone(binfmt.detect_bytes(struct.pack(">II", 0xCAFEBABE, 1) + bytes(64)))

    def test_elf_machines(self) -> None:
        self.assertEqual(binfmt.detect_bytes(elf(0x3E)).archs, ["x86_64"])
        self.assertEqual(binfmt.detect_bytes(elf(0xB7)).archs, ["aarch64"])
        self.assertEqual(binfmt.detect_bytes(elf(0xB7, big_endian=True)).archs, ["aarch64"])

    def test_elf_end(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "runtime"
            path.write_bytes(elf(0x3E, shoff=0x2000, shnum=5))
            self.assertEqual(binfmt.elf_end(path), 0x2000 + 5 * 64)
            (Path(tmp) / "text").write_text("hello", encoding="utf-8")
            self.assertIsNone(binfmt.elf_end(Path(tmp) / "text"))

    def test_other_files(self) -> None:
        for data in (b"", b"MZ", b"hello world" * 10, b"PK\x03\x04" + bytes(60)):
            with self.subTest(data=data[:8]):
                self.assertIsNone(binfmt.detect_bytes(data))


class WalkTests(unittest.TestCase):
    def test_walk_finds_by_magic_and_skips_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "sub dir").mkdir()
            (root / "app.bin").write_bytes(pe(0x8664))
            (root / "sub dir" / "lib.so").write_bytes(elf(0x3E))
            (root / "readme.txt").write_text("no", encoding="utf-8")
            try:
                (root / "link").symlink_to(root / "app.bin")
                (root / "loop").symlink_to(root, target_is_directory=True)
            except (OSError, NotImplementedError):
                pass
            found = [(p.relative_to(root).as_posix(), f.kind) for p, f in binfmt.walk(root)]
            self.assertEqual(found, [("app.bin", "pe"), ("sub dir/lib.so", "elf")])
            self.assertEqual([p.name for p, _ in binfmt.walk(root, "elf")], ["lib.so"])

    @unittest.skipUnless(sys.platform.startswith("linux"), "the running interpreter is an ELF file on Linux only")
    def test_real_interpreter_is_elf(self) -> None:
        found = binfmt.detect(Path(sys.executable).resolve())
        self.assertEqual(found.kind, "elf")


if __name__ == "__main__":
    unittest.main()
