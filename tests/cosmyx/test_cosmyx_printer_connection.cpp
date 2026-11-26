// Checks of the Cosmyx physical printer dialog logic (decision 0225): the
// machine address check, the print host URLs written to the preset and read
// back, the unlock rule of the "Machine information" tab and the
// classification of failed requests. Addresses come from the RFC 5737
// documentation ranges.

#include <catch2/catch_test_macros.hpp>

#include <optional>
#include <string>

#include "slic3r/GUI/Cosmyx/logic/CosmyxPrinterConnection.hpp"

using namespace Slic3r::GUI::Cosmyx;

namespace {

HostError host_error(const std::string& input) { return check_host(input).error; }

std::string host_of(const std::string& input)
{
    const HostCheck check = check_host(input);
    REQUIRE(check.ok());
    return check.host;
}

} // namespace

TEST_CASE("An IPv4 address is accepted as typed", "[cosmyx][PrinterConnection]")
{
    CHECK(host_of("192.0.2.10") == "192.0.2.10");
    CHECK(host_of("198.51.100.0") == "198.51.100.0");
    CHECK(host_of("203.0.113.255") == "203.0.113.255");
}

TEST_CASE("Blanks around the address are ignored", "[cosmyx][PrinterConnection]")
{
    CHECK(host_of("  192.0.2.10 ") == "192.0.2.10");
    CHECK(host_of("\t192.0.2.10\n") == "192.0.2.10");
}

TEST_CASE("A port from 1 to 65535 is accepted and normalised", "[cosmyx][PrinterConnection]")
{
    CHECK(host_of("192.0.2.10:80") == "192.0.2.10:80");
    CHECK(host_of("192.0.2.10:1") == "192.0.2.10:1");
    CHECK(host_of("192.0.2.10:65535") == "192.0.2.10:65535");
    CHECK(host_of("192.0.2.10:0080") == "192.0.2.10:80");
    CHECK(host_of("printer.example:8080") == "printer.example:8080");
}

TEST_CASE("A port out of range or not a number is refused", "[cosmyx][PrinterConnection]")
{
    CHECK(host_error("192.0.2.10:0") == HostError::Port);
    CHECK(host_error("192.0.2.10:65536") == HostError::Port);
    CHECK(host_error("192.0.2.10:999999") == HostError::Port);
    CHECK(host_error("192.0.2.10:") == HostError::Port);
    CHECK(host_error("192.0.2.10:http") == HostError::Port);
    CHECK(host_error("192.0.2.10:+80") == HostError::Port);
    CHECK(host_error("192.0.2.10:-1") == HostError::Port);
}

TEST_CASE("An RFC 1123 host name is accepted in lower case", "[cosmyx][PrinterConnection]")
{
    CHECK(host_of("printer.local") == "printer.local");
    CHECK(host_of("Nova-01.Example") == "nova-01.example");
    CHECK(host_of("printer") == "printer");
    CHECK(host_of("3dprinter.example") == "3dprinter.example");
    CHECK(host_of(std::string(63, 'a') + ".example") == std::string(63, 'a') + ".example");
}

TEST_CASE("A host name that breaks RFC 1123 is refused", "[cosmyx][PrinterConnection]")
{
    CHECK(host_error("-printer.local") == HostError::Hostname);
    CHECK(host_error("printer-.local") == HostError::Hostname);
    CHECK(host_error("printer..local") == HostError::Hostname);
    CHECK(host_error("printer.local.") == HostError::Hostname);
    CHECK(host_error("print_er.local") == HostError::Hostname);
    CHECK(host_error("imprimante.\xc3\xa9t\xc3\xa9") == HostError::Hostname);
    CHECK(host_error(std::string(64, 'a') + ".example") == HostError::Hostname);
    CHECK(host_error("a.123") == HostError::Hostname);
}

TEST_CASE("Four numbers that are not an IPv4 address are refused", "[cosmyx][PrinterConnection]")
{
    CHECK(host_error("192.0.2.256") == HostError::Ipv4);
    CHECK(host_error("192.0.2") == HostError::Ipv4);
    CHECK(host_error("192.0.2.10.5") == HostError::Ipv4);
    CHECK(host_error("192.0.2.010") == HostError::Ipv4);
    CHECK(host_error("1234") == HostError::Ipv4);
}

TEST_CASE("An empty address is refused", "[cosmyx][PrinterConnection]")
{
    CHECK(host_error("") == HostError::Empty);
    CHECK(host_error("   ") == HostError::Empty);
}

TEST_CASE("A scheme, a path or user info is refused", "[cosmyx][PrinterConnection]")
{
    CHECK(host_error("http://192.0.2.10") == HostError::Scheme);
    CHECK(host_error("https://printer.local/") == HostError::Scheme);
    CHECK(host_error("192.0.2.10/octoprint") == HostError::Path);
    CHECK(host_error("192.0.2.10/") == HostError::Path);
    CHECK(host_error("192.0.2.10?a=1") == HostError::Path);
    CHECK(host_error("192.0.2.10#top") == HostError::Path);
    CHECK(host_error("192.0.2.10\\x") == HostError::Path);
    CHECK(host_error("user@192.0.2.10") == HostError::UserInfo);
    CHECK(host_error("user:secret@192.0.2.10") == HostError::UserInfo);
}

TEST_CASE("Blanks inside the address are refused", "[cosmyx][PrinterConnection]")
{
    CHECK(host_error("192.0.2. 10") == HostError::Whitespace);
    CHECK(host_error("printer\tlocal") == HostError::Whitespace);
}

TEST_CASE("IPv6 addresses are not supported", "[cosmyx][PrinterConnection]")
{
    CHECK(host_error("2001:db8::1") == HostError::Hostname);
    CHECK(host_error("[2001:db8::1]:80") == HostError::Hostname);
}

TEST_CASE("The API key loses its outer blanks and refuses inner ones", "[cosmyx][PrinterConnection]")
{
    CHECK(check_api_key(" ABCDEF0123456789 ").key == "ABCDEF0123456789");
    CHECK(check_api_key("").ok());
    CHECK(check_api_key("").key.empty());
    CHECK(check_api_key("ABC DEF").error == ApiKeyError::Whitespace);
    CHECK(check_api_key("ABC DEF").key.empty());
}

TEST_CASE("The print host URLs are built from the host", "[cosmyx][PrinterConnection]")
{
    CHECK(octoprint_url("192.0.2.10") == "http://192.0.2.10/octoprint/");
    CHECK(mission_control_url("192.0.2.10:8080") == "http://192.0.2.10:8080/mission-control-viewer/");
    CHECK(cosmos_api_url("printer.local", "api/machine/device") == "http://printer.local/api/machine/device");
}

TEST_CASE("OK writes the four print host values only", "[cosmyx][PrinterConnection]")
{
    const PrintHostValues values = print_host_values({"203.0.113.7", "0123456789ABCDEF"});
    CHECK(values.host_type == "octoprint");
    CHECK(values.print_host == "http://203.0.113.7/octoprint/");
    CHECK(values.print_host_webui == "http://203.0.113.7/mission-control-viewer/");
    CHECK(values.printhost_apikey == "0123456789ABCDEF");
}

TEST_CASE("The host is read back from an OctoPrint URL of this dialog", "[cosmyx][PrinterConnection]")
{
    CHECK(host_from_octoprint_url("http://192.0.2.10/octoprint/") == std::optional<std::string>("192.0.2.10"));
    CHECK(host_from_octoprint_url("http://192.0.2.10/octoprint") == std::optional<std::string>("192.0.2.10"));
    CHECK(host_from_octoprint_url("HTTP://Printer.Local:8080/octoprint/") == std::optional<std::string>("printer.local:8080"));
    // Round trip.
    CHECK(host_from_octoprint_url(octoprint_url("198.51.100.20:81")) == std::optional<std::string>("198.51.100.20:81"));
}

TEST_CASE("Any other print host gives no host", "[cosmyx][PrinterConnection]")
{
    CHECK_FALSE(host_from_octoprint_url("").has_value());
    CHECK_FALSE(host_from_octoprint_url("192.0.2.10").has_value());
    CHECK_FALSE(host_from_octoprint_url("http://192.0.2.10").has_value());
    CHECK_FALSE(host_from_octoprint_url("http://192.0.2.10/").has_value());
    CHECK_FALSE(host_from_octoprint_url("https://192.0.2.10/octoprint/").has_value());
    CHECK_FALSE(host_from_octoprint_url("http://192.0.2.10/octoprint//").has_value());
    CHECK_FALSE(host_from_octoprint_url("http://192.0.2.10/prefix/octoprint/").has_value());
    CHECK_FALSE(host_from_octoprint_url("http://192.0.2.10/octoprint/api").has_value());
    CHECK_FALSE(host_from_octoprint_url("http://user@192.0.2.10/octoprint/").has_value());
    CHECK_FALSE(host_from_octoprint_url("http:///octoprint/").has_value());
    CHECK_FALSE(host_from_octoprint_url("http:// 192.0.2.10/octoprint/").has_value());
    CHECK_FALSE(host_from_octoprint_url("http://192.0.2.10/octoprinter/").has_value());
}

TEST_CASE("A saved connection needs an OctoPrint host written by the dialog", "[cosmyx][PrinterConnection]")
{
    const auto saved = saved_connection("octoprint", "http://192.0.2.10/octoprint/", "KEY");
    REQUIRE(saved.has_value());
    CHECK(saved->host == "192.0.2.10");
    CHECK(saved->api_key == "KEY");
    CHECK_FALSE(saved_connection("prusalink", "http://192.0.2.10/octoprint/", "KEY").has_value());
    CHECK_FALSE(saved_connection("octoprint", "192.0.2.10", "KEY").has_value());
    CHECK_FALSE(saved_connection("octoprint", "", "").has_value());
}

TEST_CASE("Machine information unlocks after a save and a matching successful test", "[cosmyx][PrinterConnection]")
{
    const ConnectionSettings a{"192.0.2.10", "KEY"};
    const ConnectionSettings other_host{"192.0.2.11", "KEY"};
    const ConnectionSettings other_key{"192.0.2.10", "OTHER"};

    CHECK(machine_info_unlocked(a, a));
    // Not saved yet.
    CHECK_FALSE(machine_info_unlocked(std::nullopt, a));
    // Saved but never tested, or the test failed.
    CHECK_FALSE(machine_info_unlocked(a, std::nullopt));
    // The test checked other values than the saved ones.
    CHECK_FALSE(machine_info_unlocked(a, other_host));
    CHECK_FALSE(machine_info_unlocked(a, other_key));
    CHECK_FALSE(machine_info_unlocked(std::nullopt, std::nullopt));
}

TEST_CASE("Failed requests are classified for their message", "[cosmyx][PrinterConnection]")
{
    CHECK(classify_http_failure(401, "") == HttpFailure::Unauthorized);
    CHECK(classify_http_failure(403, "") == HttpFailure::Forbidden);
    CHECK(classify_http_failure(404, "") == HttpFailure::NotFound);
    CHECK(classify_http_failure(500, "") == HttpFailure::HttpError);
    CHECK(classify_http_failure(418, "") == HttpFailure::HttpError);
    CHECK(classify_http_failure(0, "Timeout was reached") == HttpFailure::Timeout);
    CHECK(classify_http_failure(0, "Operation timed out after 10001 milliseconds") == HttpFailure::Timeout);
    CHECK(classify_http_failure(0, "Couldn't connect to server") == HttpFailure::Unreachable);
    CHECK(classify_http_failure(0, "Couldn't resolve host name") == HttpFailure::Unreachable);
    CHECK(classify_http_failure(0, "") == HttpFailure::BadResponse);
    CHECK(classify_http_failure(302, "") == HttpFailure::BadResponse);
}
