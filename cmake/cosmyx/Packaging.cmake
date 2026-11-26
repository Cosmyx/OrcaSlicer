# Cosmyx installer identity. Included once from the top-level CMakeLists.txt,
# right before include(CPack), through a single hook line, so it overrides
# upstream's CPack values without editing their lines.
#
# A Cosmyx build installs side by side with upstream OrcaSlicer: its own folder
# (Program Files\Cosmyx\CosmoSlice), its own uninstall registry key and its own
# publisher, so neither installer upgrades or removes the other.
# See wiki/cosmyx/install-and-data-paths.md.

set(CPACK_PACKAGE_VENDOR "Cosmyx")
# Relative to CPACK_NSIS_INSTALL_ROOT (Program Files). The backslash is doubled
# twice, like upstream's CPACK_PACKAGE_ICON: CPack writes the value unescaped
# into CPackConfig.cmake, which CMake parses again.
set(CPACK_PACKAGE_INSTALL_DIRECTORY "Cosmyx\\\\CosmoSlice")
# Names the uninstall key (HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall\<key>)
# that CPack's uninstall-before-install step looks for. Upstream uses "OrcaSlicer".
set(CPACK_PACKAGE_INSTALL_REGISTRY_KEY "Cosmyx CosmoSlice")
# Both names default to the install directory, which now holds a backslash.
# The product-name branding may set the display name earlier; its value is kept.
if (NOT DEFINED CPACK_NSIS_DISPLAY_NAME)
    set(CPACK_NSIS_DISPLAY_NAME "CosmoSlice")
endif ()
if (NOT DEFINED CPACK_NSIS_PACKAGE_NAME)
    set(CPACK_NSIS_PACKAGE_NAME "CosmoSlice")
endif ()

# Before copying its files, the installer removes an earlier Cosmyx build that
# used a legacy uninstall key (remove_legacy_install.nsh). The snippet is
# appended to the pre-install commands, after upstream's signing include when
# that one is set. Like upstream's, it goes through !include with a native path
# whose backslashes are doubled for CPackConfig.cmake.
if (WIN32)
    file(TO_NATIVE_PATH "${CMAKE_CURRENT_LIST_DIR}/remove_legacy_install.nsh" _cosmyx_legacy_nsh)
    string(REPLACE "\\" "\\\\" _cosmyx_legacy_nsh "${_cosmyx_legacy_nsh}")
    set(_cosmyx_legacy_include "!include \\\"${_cosmyx_legacy_nsh}\\\"")
    if (CPACK_NSIS_EXTRA_PREINSTALL_COMMANDS)
        string(APPEND CPACK_NSIS_EXTRA_PREINSTALL_COMMANDS "\n${_cosmyx_legacy_include}")
    else ()
        set(CPACK_NSIS_EXTRA_PREINSTALL_COMMANDS "${_cosmyx_legacy_include}")
    endif ()
endif ()
