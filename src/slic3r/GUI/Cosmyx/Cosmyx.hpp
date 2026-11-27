#ifndef slic3r_GUI_Cosmyx_hpp_
#define slic3r_GUI_Cosmyx_hpp_

// Entry points of the Cosmyx GUI module. Upstream GUI files include this one
// header, through a single hook line each, and call what the features declare
// here. The declarations stay free of wxWidgets types where they can, so the
// header is cheap to include; logic that needs no wxWidgets at all lives in
// logic/ and is unit tested by cosmyx_tests.

namespace Slic3r {
namespace GUI {
namespace Cosmyx {

} // namespace Cosmyx
} // namespace GUI
} // namespace Slic3r

#endif // slic3r_GUI_Cosmyx_hpp_
