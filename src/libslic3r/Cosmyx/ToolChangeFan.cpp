#include "ToolChangeFan.hpp"

#include <charconv>
#include <system_error>

namespace Slic3r {
namespace Cosmyx {

bool resume_waits_for_tool_change(std::string_view next_line, std::string_view prefix, unsigned int current_tool,
                                  unsigned int tool_count)
{
    if (prefix.empty() || next_line.substr(0, prefix.size()) != prefix)
        return false;
    const std::string_view line = next_line.substr(0, next_line.find('\n'));
    // Same parse as CoolingBuffer::parse_layer_gcode(): only a missing number
    // rejects the line, an out of range one reads as tool 0.
    unsigned int tool = 0;
    const auto   ret  = std::from_chars(line.data() + prefix.size(), line.data() + line.size(), tool);
    if (ret.ec == std::errc::invalid_argument)
        return false;
    return tool < tool_count && tool != current_tool;
}

} // namespace Cosmyx
} // namespace Slic3r
