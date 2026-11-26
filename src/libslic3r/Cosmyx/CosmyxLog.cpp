#include "CosmyxLog.hpp"

#include <atomic>
#include <ctime>
#include <iomanip>
#include <mutex>
#include <sstream>

#include <boost/date_time/posix_time/posix_time_types.hpp>
#include <boost/filesystem/operations.hpp>
#include <boost/log/attributes/current_thread_id.hpp>
#include <boost/log/core.hpp>
#include <boost/log/expressions.hpp>
#include <boost/log/expressions/formatters/date_time.hpp>
#include <boost/log/sinks/sync_frontend.hpp>
#include <boost/log/sinks/text_file_backend.hpp>
#include <boost/log/support/date_time.hpp>
#include <boost/log/utility/setup/common_attributes.hpp>
#include <boost/log/utility/setup/file.hpp>
#include <boost/shared_ptr.hpp>
#include <boost/system/error_code.hpp>

#include "libslic3r/Utils.hpp"

namespace Slic3r {

// Orca's log file sink, defined in utils.cpp and set by set_log_path_and_level().
// Not declared in any header; declared here so the Cosmyx channel can be kept out
// of Orca's file without editing utils.cpp.
extern boost::shared_ptr<boost::log::sinks::synchronous_sink<boost::log::sinks::text_file_backend>> g_log_sink;

namespace Cosmyx {

namespace {

namespace expr  = boost::log::expressions;
namespace kw    = boost::log::keywords;
namespace attrs = boost::log::attributes;
using FileSink  = boost::log::sinks::synchronous_sink<boost::log::sinks::text_file_backend>;

struct LogState
{
    std::mutex mutex;
    // Set once a sink was registered or the lazy registration was turned off, so
    // logger() skips the mutex from then on.
    std::atomic<bool> settled{false};
    boost::shared_ptr<FileSink> sink;
    // Orca's sink that was told to leave out the Cosmyx channel, if any.
    boost::shared_ptr<FileSink> filtered_orca_sink;
};

// Function-local static: never built during static initialisation.
LogState& state()
{
    static LogState s;
    return s;
}

// Matches the Cosmyx records. A record without a "Channel" attribute (every
// BOOST_LOG_TRIVIAL record) does not match.
auto cosmyx_channel_filter() { return expr::attr<std::string>("Channel") == log_channel(); }

// Same line layout as Orca's debug log, so both files read alike.
auto line_format()
{
    return expr::stream << "[" << expr::attr<boost::log::trivial::severity_level>("Severity") << "]\t"
                        << expr::format_date_time<boost::posix_time::ptime>("TimeStamp", "%Y-%m-%d %H:%M:%S.%f")
                        << "[Thread " << expr::attr<attrs::current_thread_id::value_type>("ThreadID") << "]"
                        << ":" << expr::smessage;
}

void remove_sink_locked(LogState& s)
{
    if (s.filtered_orca_sink) {
        s.filtered_orca_sink->reset_filter();
        s.filtered_orca_sink.reset();
    }
    if (s.sink) {
        boost::log::core::get()->remove_sink(s.sink);
        s.sink->flush();
        s.sink.reset();
    }
}

bool init_log_locked(LogState& s, const boost::filesystem::path& folder, const std::string& file_name,
                     std::size_t rotation_size)
{
    remove_sink_locked(s);

    boost::system::error_code ec;
    boost::filesystem::create_directories(folder, ec);
    if (ec || !boost::filesystem::is_directory(folder, ec))
        return false;

    const boost::filesystem::path full_path = (folder / file_name).make_preferred();
    s.sink = boost::log::add_file_log(kw::file_name = full_path.string() + ".%N", kw::rotation_size = rotation_size,
                                      kw::format = line_format(), kw::auto_flush = true);
    s.sink->set_filter(cosmyx_channel_filter());
    // TimeStamp and ThreadID; adding them again is a no-op.
    boost::log::add_common_attributes();

    // Keep the Cosmyx records out of Orca's file, so each file holds one channel.
    if (g_log_sink) {
        g_log_sink->set_filter(!cosmyx_channel_filter());
        s.filtered_orca_sink = g_log_sink;
    }
    s.settled = true;
    return true;
}

// Name used when Orca's log file is not open yet: same pattern as Orca's
// "debug_<time>_<pid>.log" name, built from the current time.
std::string fallback_log_file_name()
{
    const std::time_t t = std::time(nullptr);
    std::tm local{};
#ifdef _WIN32
    localtime_s(&local, &t);
#else
    localtime_r(&t, &local);
#endif
    std::ostringstream name;
    name << std::put_time(&local, "cosmyx_%a_%b_%d_%H_%M_%S_") << get_current_pid() << ".log";
    return name.str();
}

// Registers the Cosmyx sink once Orca's own file sink exists. Without it (CLI,
// start-up before set_log_path_and_level(), old macOS) nothing is registered, so
// upstream's logging behaves exactly as without Cosmyx: adding any sink would
// turn off Boost.Log's default console sink.
void ensure_sink()
{
    LogState& s = state();
    if (s.settled.load(std::memory_order_acquire))
        return;
    std::lock_guard<std::mutex> lock(s.mutex);
    if (s.settled || !g_log_sink)
        return;

    const boost::filesystem::path orca_file = get_log_file_name();
    boost::filesystem::path folder;
    std::string             file_name = paired_log_file_name(orca_file);
    if (file_name.empty()) {
        folder    = boost::filesystem::path(data_dir()) / "log";
        file_name = fallback_log_file_name();
    } else {
        folder = orca_file.parent_path();
    }
    if (!init_log_locked(s, folder, file_name, log_rotation_size))
        s.settled = true; // The folder cannot be used: do not retry on every record.
}

} // namespace

const std::string& log_channel()
{
    static const std::string channel("Cosmyx");
    return channel;
}

LogLogger& logger()
{
    ensure_sink();
    static LogLogger s_logger(kw::channel = log_channel());
    return s_logger;
}

bool init_log(const boost::filesystem::path& folder, const std::string& file_name, std::size_t rotation_size)
{
    LogState& s = state();
    std::lock_guard<std::mutex> lock(s.mutex);
    return init_log_locked(s, folder, file_name, rotation_size);
}

void shutdown_log()
{
    LogState& s = state();
    std::lock_guard<std::mutex> lock(s.mutex);
    remove_sink_locked(s);
    s.settled = true;
}

bool log_active()
{
    LogState& s = state();
    std::lock_guard<std::mutex> lock(s.mutex);
    return bool(s.sink);
}

boost::filesystem::path log_file_path()
{
    LogState& s = state();
    std::lock_guard<std::mutex> lock(s.mutex);
    if (!s.sink)
        return {};
    return s.sink->locked_backend()->get_current_file_name();
}

void flush_log()
{
    LogState& s = state();
    std::lock_guard<std::mutex> lock(s.mutex);
    if (s.sink)
        s.sink->flush();
}

std::string paired_log_file_name(const boost::filesystem::path& orca_log_file)
{
    boost::filesystem::path name = orca_log_file.filename();
    if (name.empty() || name.string() == "." || name.string() == "..")
        return {};
    // Orca's sink writes "<name>.log.<N>": drop the rotation index.
    const std::string index = name.extension().string();
    if (index.size() > 1 && index.find_first_not_of("0123456789", 1) == std::string::npos)
        name = name.stem();
    std::string out = name.string();
    const std::string orca_prefix("debug_");
    if (out.compare(0, orca_prefix.size(), orca_prefix) == 0)
        out.erase(0, orca_prefix.size());
    return "cosmyx_" + out;
}

} // namespace Cosmyx
} // namespace Slic3r
