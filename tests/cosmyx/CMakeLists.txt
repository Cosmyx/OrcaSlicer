# Cosmyx unit tests (cosmyx_tests). Built and run by ctest with the upstream
# suites, so the build_all unit test job runs them without any workflow change.
#
# Test files are globbed (test_*.cpp), and so is the wxWidgets-free GUI logic in
# src/slic3r/GUI/Cosmyx/logic/, so a feature adds its tests without editing this
# file. Every test case carries the [cosmyx] tag.
get_filename_component(_TEST_NAME ${CMAKE_CURRENT_LIST_DIR} NAME)

file(GLOB COSMYX_TEST_SOURCES CONFIGURE_DEPENDS
    "${CMAKE_CURRENT_LIST_DIR}/test_*.cpp")
file(GLOB COSMYX_GUI_LOGIC_SOURCES CONFIGURE_DEPENDS
    "${CMAKE_SOURCE_DIR}/src/slic3r/GUI/Cosmyx/logic/*.cpp")

add_executable(${_TEST_NAME}_tests
    ${_TEST_NAME}_tests.cpp
    ${COSMYX_TEST_SOURCES}
    ${COSMYX_GUI_LOGIC_SOURCES}
    ../fff_print/test_helpers.cpp
    )
target_link_libraries(${_TEST_NAME}_tests test_common libslic3r Catch2::Catch2WithMain)
# src/ so tests include "slic3r/GUI/Cosmyx/logic/..." and "libslic3r/Cosmyx/...";
# fff_print/ for the shared print fixtures in test_helpers.hpp.
target_include_directories(${_TEST_NAME}_tests PRIVATE
    ${CMAKE_SOURCE_DIR}/src
    ${CMAKE_CURRENT_LIST_DIR}/../fff_print)
if (SLIC3R_PCH AND NOT SLIC3R_SYNTAXONLY)
    add_precompiled_header(${_TEST_NAME}_tests ${CMAKE_SOURCE_DIR}/src/libslic3r/pchheader.hpp FORCEINCLUDE)
endif ()

set_property(TARGET ${_TEST_NAME}_tests PROPERTY FOLDER "tests")

orcaslicer_copy_test_dlls()

orcaslicer_discover_tests(${_TEST_NAME}_tests)

# The flatpak manifest builds an explicit list of upstream test targets, and
# ctest reports cosmyx_tests_NOT_BUILT for a registered suite left out of it.
# Hanging cosmyx_tests on libslic3r_tests builds it wherever that suite is
# built, without editing the upstream list. Removing it means adding
# cosmyx_tests to the manifest's --target list instead.
if (TARGET libslic3r_tests)
    add_dependencies(libslic3r_tests ${_TEST_NAME}_tests)
endif ()
