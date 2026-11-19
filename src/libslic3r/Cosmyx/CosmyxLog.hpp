#ifndef slic3r_Cosmyx_CosmyxLog_hpp_
#define slic3r_Cosmyx_CosmyxLog_hpp_

// Cosmyx log channel. Cosmyx code logs with COSMYX_LOG(level) instead of
// BOOST_LOG_TRIVIAL(level); its records carry the Boost.Log channel "Cosmyx" and
// go to their own file, next to Orca's debug log, instead of Orca's file.
//
//     COSMYX_LOG(info) << "[BedTemperatureOff] heater off for extruder " << id;
//
// No upstream hook is needed: the Cosmyx sink is registered lazily, on the first
// COSMYX_LOG once Orca's own log file sink exists (set_log_path_and_level()).
// Until then (CLI, early start-up, old macOS without file logging) Cosmyx records
// follow upstream's default behaviour, like any BOOST_LOG_TRIVIAL record.
//
// Records still pass Orca's global severity filter (set_logging_level()), so the
// log level chosen in the preferences applies to Cosmyx records too.

#include <cstddef>
#include <string>

#include <boost/filesystem/path.hpp>
#include <boost/log/sources/record_ostream.hpp>
#include <boost/log/sources/severity_channel_logger.hpp>
#include <boost/log/trivial.hpp>

namespace Slic3r {
namespace Cosmyx {

using LogLogger = boost::log::sources::severity_channel_logger_mt<boost::log::trivial::severity_level, std::string>;

// Value of the "Channel" attribute of every Cosmyx record.
const std::string& log_channel();

// Size at which the Cosmyx log file rotates to the next index (same as Orca's).
constexpr std::size_t log_rotation_size = 100 * 1024 * 1024;

// The Cosmyx logger. Registers the Cosmyx sink first if it is due (see above).
// A function-local static, so it is never built during static initialisation.
LogLogger& logger();

// Registers the Cosmyx file sink now, writing to `folder`/`file_name`.N (N is
// the rotation index, from 0) and rotating every `rotation_size` bytes. Records
// of the Cosmyx channel go only there; when Orca's log file sink exists, it is
// told to leave them out. Replaces a sink registered before. Returns false, with
// no sink registered, if the folder cannot be created.
bool init_log(const boost::filesystem::path& folder, const std::string& file_name,
              std::size_t rotation_size = log_rotation_size);

// Removes the Cosmyx sink, closes its file and lets Orca's file take Cosmyx
// records again. After this, the lazy registration no longer runs.
void shutdown_log();

// True while the Cosmyx sink is registered.
bool log_active();

// Path of the Cosmyx log file being written, empty if none is open yet.
boost::filesystem::path log_file_path();

// Writes what the Cosmyx sink holds to disk.
void flush_log();

// Name of the Cosmyx log file paired with Orca's log file `orca_log_file`:
// "debug_Thu_Nov_19_10_00_00_123.log.0" gives "cosmyx_Thu_Nov_19_10_00_00_123.log".
// A name without the "debug_" prefix is kept and prefixed with "cosmyx_".
// Empty if `orca_log_file` has no file name.
std::string paired_log_file_name(const boost::filesystem::path& orca_log_file);

} // namespace Cosmyx
} // namespace Slic3r

// Logs a Cosmyx record at the given Boost.Log trivial severity
// (trace, debug, info, warning, error, fatal).
#define COSMYX_LOG(sev) \
    BOOST_LOG_CHANNEL_SEV(::Slic3r::Cosmyx::logger(), ::Slic3r::Cosmyx::log_channel(), ::boost::log::trivial::sev)

#endif // slic3r_Cosmyx_CosmyxLog_hpp_
