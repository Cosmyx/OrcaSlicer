#ifndef slic3r_Cosmyx_StealthMode_hpp_
#define slic3r_Cosmyx_StealthMode_hpp_

// Cosmyx stealth mode policy (decision 0200). AppConfig::get_stealth_mode()
// returns stealth_mode() through one hook line; the GUI seeds the default once
// per configuration file with seed_stealth_mode() at start-up.

namespace Slic3r {

class AppConfig;

namespace Cosmyx {

// Stealth mode a configuration starts in, until the user turns it off from
// Preferences or the login dialog.
constexpr bool STEALTH_MODE_DEFAULT = true;

// App key set once the Cosmyx default has been written to "stealth_mode", so
// that from then on the stored value is the user's choice. It is needed
// because AppConfig::set_defaults() stores "stealth_mode" as false, so an
// absent value cannot tell a fresh configuration from a user choice.
constexpr const char* STEALTH_SEEDED_KEY = "cosmyx_stealth_mode_seeded";

// Upstream rule (always on until the setup guide is finished), then the
// stored value once seeded, else STEALTH_MODE_DEFAULT.
bool stealth_mode(const AppConfig& config);

// Writes STEALTH_MODE_DEFAULT to "stealth_mode" and sets STEALTH_SEEDED_KEY,
// once per configuration. Returns true when it wrote anything.
bool seed_stealth_mode(AppConfig& config);

} // namespace Cosmyx
} // namespace Slic3r

#endif // slic3r_Cosmyx_StealthMode_hpp_
