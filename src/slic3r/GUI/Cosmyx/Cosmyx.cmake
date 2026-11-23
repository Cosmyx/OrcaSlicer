# Cosmyx GUI module. Included once from src/slic3r/CMakeLists.txt, right after
# add_library(libslic3r_gui ...) and before encoding_check() and the precompiled
# header setup, through a single hook line.
#
# Every source file in this folder and in logic/ is picked up by the glob, so a
# feature adds files here without editing any CMake file. CONFIGURE_DEPENDS
# makes the build re-run the glob when a file is added or removed.
#
# logic/ holds the wxWidgets-free part of the GUI features. The cosmyx_tests
# suite compiles it too, without libslic3r_gui.
file(GLOB COSMYX_GUI_SOURCES CONFIGURE_DEPENDS
    "${CMAKE_CURRENT_LIST_DIR}/*.cpp"
    "${CMAKE_CURRENT_LIST_DIR}/*.hpp"
    "${CMAKE_CURRENT_LIST_DIR}/logic/*.cpp"
    "${CMAKE_CURRENT_LIST_DIR}/logic/*.hpp")

if (APPLE)
    # Objective-C++ sources cannot use the C++ precompiled header.
    file(GLOB COSMYX_GUI_MM_SOURCES CONFIGURE_DEPENDS "${CMAKE_CURRENT_LIST_DIR}/*.mm")
    set_source_files_properties(${COSMYX_GUI_MM_SOURCES} PROPERTIES SKIP_PRECOMPILE_HEADERS ON)
    list(APPEND COSMYX_GUI_SOURCES ${COSMYX_GUI_MM_SOURCES})
endif ()

target_sources(libslic3r_gui PRIVATE ${COSMYX_GUI_SOURCES})
source_group(TREE "${CMAKE_CURRENT_LIST_DIR}" PREFIX "Cosmyx" FILES ${COSMYX_GUI_SOURCES})
