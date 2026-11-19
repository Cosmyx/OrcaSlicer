// libslic3r references nanosvg but does not compile its implementation; each
// test executable that links libslic3r alone provides it once, as the upstream
// suites do.
#define NANOSVG_IMPLEMENTATION
#include "nanosvg/nanosvg.h"
#define NANOSVGRAST_IMPLEMENTATION
#include "nanosvg/nanosvgrast.h"
