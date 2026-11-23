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
# OpenSSL::Crypto for the plugin package signatures (logic/PluginSigning.cpp,
# decision 0204); libslic3r links it privately, so its headers are not inherited.
target_link_libraries(${_TEST_NAME}_tests test_common libslic3r OpenSSL::Crypto Catch2::Catch2WithMain)
# The static OpenSSL of the Windows deps reads the system certificate store
# (Cert* functions), which lives in crypt32; libslic3r_gui gets it through the
# libcurl target in the top-level CMakeLists.txt, the same way.
if (WIN32)
    target_link_libraries(${_TEST_NAME}_tests crypt32)
endif ()
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
