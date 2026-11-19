# Cosmyx libslic3r module. Included once from src/libslic3r/CMakeLists.txt, right
# after add_library(libslic3r ...), through a single hook line.
#
# Every source file in this folder is picked up by the glob, so a feature adds
# files here without editing any CMake file. CONFIGURE_DEPENDS makes the build
# re-run the glob when a file is added or removed.
file(GLOB COSMYX_LIBSLIC3R_SOURCES CONFIGURE_DEPENDS
    "${CMAKE_CURRENT_LIST_DIR}/*.cpp"
    "${CMAKE_CURRENT_LIST_DIR}/*.hpp")

target_sources(libslic3r PRIVATE ${COSMYX_LIBSLIC3R_SOURCES})
source_group(TREE "${CMAKE_CURRENT_LIST_DIR}" PREFIX "Cosmyx" FILES ${COSMYX_LIBSLIC3R_SOURCES})
