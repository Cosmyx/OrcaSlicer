#include "ConfigDefExtensions.hpp"

#include <algorithm>
#include <cstddef>
#include <iterator>

#include "libslic3r/CommonDefs.hpp"
#include "libslic3r/PrintConfig.hpp"

// Labels stay untranslated in libslic3r; the GUI translates them, as in
// PrintConfig.cpp.
#define L(s) (s)

namespace Slic3r {
namespace Cosmyx {

void extend_cht_nozzle(PrintConfigDef& def)
{
    // Adds the CHT nozzle to the nozzle_type choices. The enum value NozzleType::ntCHT
    // and the key "cht" come from the hooks in CommonDefs.hpp and PrintConfig.{hpp,cpp}.
    //
    // The GUI stores the selected position of a coEnums combo box as the enum
    // value (Choice::get_value), so "cht" must sit at index int(ntCHT), not at
    // the end of the list. See wiki/decisions/0020-cht-enum-position.md.
    if (!def.has("nozzle_type"))
        return;
    ConfigOptionDef* opt = def.get("nozzle_type");

    // Idempotent: the extender may run again on a definition that already has it.
    if (std::find(opt->enum_values.begin(), opt->enum_values.end(), "cht") != opt->enum_values.end())
        return;

    const std::size_t index = std::min(std::size_t(int(NozzleType::ntCHT)), opt->enum_values.size());
    opt->enum_values.insert(std::next(opt->enum_values.begin(), std::ptrdiff_t(index)), "cht");
    if (opt->enum_labels.size() >= index)
        opt->enum_labels.insert(std::next(opt->enum_labels.begin(), std::ptrdiff_t(index)), L("CHT"));
}

} // namespace Cosmyx
} // namespace Slic3r
