"""Link-closure checks of the Cosmyx libslic3r sources.

libslic3r is a static library: a program only pulls the object files it needs.
PrintConfig.cpp calls Cosmyx::extend_print_config_def, so every Cosmyx object
file that defines a PrintConfigDef extension is linked into every program that
uses the configuration, including the small dev-utils tools such as
generate_system_cache. If that object file also calls into the G-code
generator, the linker pulls GCode.o and, through it, the 3MF and SVG code,
which needs the nanosvg implementation that only the GUI and some tools
provide. The link then fails with undefined nsvg* symbols.

So a Cosmyx source that defines a config-def extension must not use the G-code
generator: G-code hooks live in their own source file.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
COSMYX_LIBSLIC3R = REPO_ROOT / "src" / "libslic3r" / "Cosmyx"

# Headers whose use drags the G-code generator (and the 3MF/SVG code) into a link.
GCODE_INCLUDE = re.compile(r'^\s*#\s*include\s*[<"]libslic3r/GCode(\.hpp|Writer\.hpp|/)', re.MULTILINE)
CONFIG_DEF_EXTENSION = re.compile(r"^\s*void\s+\w+\s*\(\s*PrintConfigDef\s*&", re.MULTILINE)


def check_source(text: str) -> bool:
    """Return True when the source keeps config-def code apart from G-code code."""
    return not (CONFIG_DEF_EXTENSION.search(text) and GCODE_INCLUDE.search(text))


class CheckSourceTests(unittest.TestCase):
    def test_mixed_source_is_refused(self) -> None:
        text = '#include "libslic3r/GCode.hpp"\nvoid extend_x(PrintConfigDef& def)\n{\n}\n'
        self.assertFalse(check_source(text))

    def test_writer_include_is_refused(self) -> None:
        text = '#include "libslic3r/GCodeWriter.hpp"\nvoid extend_x(PrintConfigDef& def) {}\n'
        self.assertFalse(check_source(text))

    def test_config_only_source_is_accepted(self) -> None:
        self.assertTrue(check_source('#include "libslic3r/PrintConfig.hpp"\nvoid extend_x(PrintConfigDef& def) {}\n'))

    def test_gcode_only_source_is_accepted(self) -> None:
        self.assertTrue(check_source('#include "libslic3r/GCode.hpp"\nstd::string hook(const GCode& g) { return {}; }\n'))


class CosmyxLibslic3rSourcesTests(unittest.TestCase):
    def test_config_def_extensions_do_not_use_the_gcode_generator(self) -> None:
        sources = sorted(COSMYX_LIBSLIC3R.glob("*.cpp"))
        self.assertTrue(sources, "no Cosmyx libslic3r sources found")
        for source in sources:
            with self.subTest(source=source.name):
                self.assertTrue(
                    check_source(source.read_text(encoding="utf-8")),
                    f"{source.name} defines a PrintConfigDef extension and includes a G-code header; "
                    "move the G-code code to its own source file",
                )


if __name__ == "__main__":
    unittest.main()
