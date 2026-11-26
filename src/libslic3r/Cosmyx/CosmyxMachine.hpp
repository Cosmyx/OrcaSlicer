#ifndef slic3r_Cosmyx_CosmyxMachine_hpp_
#define slic3r_Cosmyx_CosmyxMachine_hpp_

// Detection of a "Cosmyx machine": the selected printer preset belongs to the
// Cosmyx vendor bundle (resources/profiles/Cosmyx.json). A user preset counts
// when its inheritance chain reaches a Cosmyx system preset; a custom printer
// with no system parent does not (decision 0222).
//
// GUI features that only make sense on Cosmyx machines read this through
// src/slic3r/GUI/Cosmyx/CosmyxMachineHook.hpp.

namespace Slic3r {
class PresetBundle;
class VendorProfile;
namespace Cosmyx {

// Id of the Cosmyx vendor bundle, compared exactly (case-sensitive).
extern const char* const COSMYX_VENDOR_ID;

// True when vendor is the Cosmyx bundle. A null vendor is not Cosmyx.
bool is_cosmyx_vendor(const VendorProfile* vendor);

// True when the edited printer preset of bundle, or the first preset of its
// inheritance chain that carries a vendor, belongs to the Cosmyx bundle.
bool is_cosmyx_printer(const PresetBundle& bundle);

} // namespace Cosmyx
} // namespace Slic3r

#endif // slic3r_Cosmyx_CosmyxMachine_hpp_
