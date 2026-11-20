#ifndef slic3r_Cosmyx_ToolChangeFan_hpp_
#define slic3r_Cosmyx_ToolChangeFan_hpp_

// Cooling pass side of the Cosmyx tool change fan order (decision 0040).
// CoolingBuffer.cpp includes this header through a single hook line.

#include <string_view>

namespace Slic3r {
namespace Cosmyx {

// Whether `next_line`, the G-code that follows a ";_FORCE_RESUME_FAN_SPEED"
// tag, starts with a tool change the cooling pass acts on: `prefix` followed by
// a tool number below `tool_count` that differs from `current_tool`. These are
// the conditions CoolingBuffer uses to classify a line as TYPE_SET_TOOL.
//
// The tool change G-code writes the resume tag right before the Tn line. When
// such a Tn follows, the cooling pass holds the resume back and sends the fan
// speed after the Tn, so on printers with one part cooling fan per tool the
// speed lands on the new tool rather than on the tool being parked.
bool resume_waits_for_tool_change(std::string_view next_line, std::string_view prefix, unsigned int current_tool,
                                  unsigned int tool_count);

} // namespace Cosmyx
} // namespace Slic3r

#endif // slic3r_Cosmyx_ToolChangeFan_hpp_
