// Checks of the plugin package signature verifier (decision 0204) against the
// CosmoCloud test vectors, copied as they are into
// tests/cosmyx/data/plugin-signatures.json: every row gives its expected
// result, every statement rebuilds its signed message, and the Ed25519 library
// passes RFC 8032 section 7.1. Also the pinned key table, the anti-rollback
// order, the entry package name guard and the package record format.

#include <catch2/catch_test_macros.hpp>

#include <cstdint>
#include <ios>
#include <map>
#include <string>
#include <utility>
#include <vector>

#include <boost/filesystem/path.hpp>
#include <boost/nowide/fstream.hpp>
#include <nlohmann/json.hpp>

#include "slic3r/GUI/Cosmyx/logic/PluginSigning.hpp"

namespace CC = Slic3r::GUI::Cosmyx;
using nlohmann::json;

namespace {

json load_vectors()
{
    const boost::filesystem::path path = boost::filesystem::path(TEST_DATA_DIR) / ".." / "cosmyx" / "data" / "plugin-signatures.json";
    boost::nowide::ifstream       file(path.string(), std::ios::binary);
    REQUIRE(file);
    return json::parse(file);
}

std::string unhex(const std::string& hex)
{
    std::string bytes;
    REQUIRE(CC::from_lower_hex(hex, bytes));
    return bytes;
}

// Key name (k1, k2, k3) -> {key_id, raw public key}.
std::map<std::string, std::pair<std::string, std::string>> vector_keys(const json& vectors)
{
    std::map<std::string, std::pair<std::string, std::string>> keys;
    for (const json& key : vectors.at("keys"))
        keys[key.at("name").get<std::string>()] = {key.at("key_id").get<std::string>(), unhex(key.at("public_key").get<std::string>())};
    return keys;
}

} // namespace

TEST_CASE("The vectors file is the format this verifier implements", "[cosmyx]")
{
    const json vectors = load_vectors();
    CHECK(vectors.at("format") == "cosmocloud-plugin-signature-vectors-v1");
    CHECK(vectors.at("domain_hex") == "636f736d6f636c6f75642d706c7567696e2d7061636b6167652d763100");
    CHECK(vectors.at("rows").size() >= 85);
}

TEST_CASE("Ed25519 passes RFC 8032 section 7.1", "[cosmyx]")
{
    const json vectors = load_vectors();
    for (const json& test : vectors.at("rfc8032")) {
        INFO(test.at("name").get<std::string>());
        const std::string key       = unhex(test.at("public_key").get<std::string>());
        const std::string message   = unhex(test.at("message_hex").get<std::string>());
        const std::string signature = unhex(test.at("signature").get<std::string>());
        CHECK(CC::ed25519_verify(key, message, signature));
        std::string flipped = signature;
        flipped[0] = static_cast<char>(flipped[0] ^ 0x01);
        CHECK_FALSE(CC::ed25519_verify(key, message, flipped));
        CHECK_FALSE(CC::ed25519_verify(key, message + "x", signature));
        CHECK_FALSE(CC::ed25519_verify(key.substr(0, 31), message, signature));
        CHECK_FALSE(CC::ed25519_verify(key, message, signature.substr(0, 63)));
    }
}

TEST_CASE("Key ids are recomputed from the public keys", "[cosmyx]")
{
    const json vectors = load_vectors();
    for (const json& key : vectors.at("keys")) {
        INFO(key.at("name").get<std::string>());
        CHECK(CC::key_id_of(unhex(key.at("public_key").get<std::string>())) == key.at("key_id").get<std::string>());
    }

    SECTION("pinned production keys hash to their key id")
    {
        // Each entry of PRODUCTION_KEYS must load; an empty table is the
        // documented state until the production key is known (decision 0204).
        for (const CC::PinnedKey& pin : CC::PRODUCTION_KEYS) {
            INFO(pin.key_id);
            CC::KeyTable table;
            std::string  error;
            CHECK(CC::add_pinned_key(table, pin.key_id, pin.public_key, error));
        }
        CHECK(CC::built_in_keys().size() == CC::PRODUCTION_KEYS.size());
        for (const char* revoked : CC::REVOKED_KEY_IDS)
            CHECK(CC::is_lower_hex(revoked, 64));
    }

    SECTION("a pin whose key id is not the hash of its key is refused")
    {
        const auto   keys = vector_keys(vectors);
        CC::KeyTable table;
        std::string  error;
        CHECK_FALSE(CC::add_pinned_key(table, keys.at("k2").first, CC::to_hex(keys.at("k1").second), error));
        CHECK_FALSE(error.empty());
        CHECK_FALSE(CC::add_pinned_key(table, keys.at("k1").first, "03A107BFF3CE10BE1D70DD18E74BC09967E4D6309BA50D5F1DDC8664125531B8", error));
        CHECK_FALSE(CC::add_pinned_key(table, keys.at("k1").first, "03a1", error));
        CHECK(table.empty());
        CHECK(CC::add_pinned_key(table, keys.at("k1").first, CC::to_hex(keys.at("k1").second), error));
        CHECK(table.size() == 1);
    }
}

TEST_CASE("Every statement rebuilds its signed message and verifies", "[cosmyx]")
{
    const json vectors = load_vectors();
    const auto keys    = vector_keys(vectors);
    for (const json& statement : vectors.at("statements")) {
        INFO(statement.at("name").get<std::string>());
        const auto&       key     = keys.at(statement.at("key").get<std::string>());
        const std::string message = CC::signed_message(statement.at("fields"), key.first);
        CHECK(CC::to_hex(message) == statement.at("message_hex").get<std::string>());
        CHECK(CC::ed25519_verify(key.second, message, unhex(statement.at("signature").get<std::string>())));
    }
}

TEST_CASE("Every vector row gives its expected result", "[cosmyx]")
{
    const json vectors = load_vectors();
    const auto keys    = vector_keys(vectors);
    for (const json& vector : vectors.at("rows")) {
        INFO(vector.at("name").get<std::string>());
        CC::KeyTable pinned;
        for (const json& name : vector.at("pinned")) {
            const auto& key = keys.at(name.get<std::string>());
            pinned[key.first] = key.second;
        }
        CC::KeyIdSet revoked;
        for (const json& name : vector.at("revoked"))
            revoked.insert(keys.at(name.get<std::string>()).first);

        const json&       client = vector.at("client");
        CC::ClientRequest request;
        request.plugin_id = client.at("plugin_id").get<std::string>();
        request.version   = client.at("version").is_null() ? std::string() : client.at("version").get<std::string>();
        request.os        = client.at("os").get<std::string>();
        request.arch      = client.at("arch").get<std::string>();

        std::string key_id;
        const std::string result = CC::verify_package_row(vector.at("row"), unhex(vector.at("body_hex").get<std::string>()), request,
                                                          pinned, revoked, &key_id);
        CHECK(result == vector.at("expect").get<std::string>());
        if (result == CC::SIGN_OK)
            CHECK(pinned.count(key_id) == 1);
        else
            CHECK(key_id.empty());
    }
}

TEST_CASE("The unsigned check keeps every step but the signature ones", "[cosmyx]")
{
    const json vectors = load_vectors();
    for (const json& vector : vectors.at("rows")) {
        const std::string expect = vector.at("expect").get<std::string>();
        INFO(vector.at("name").get<std::string>());
        const json&       client = vector.at("client");
        CC::ClientRequest request{client.at("plugin_id").get<std::string>(),
                                  client.at("version").is_null() ? std::string() : client.at("version").get<std::string>(),
                                  client.at("os").get<std::string>(), client.at("arch").get<std::string>()};
        const std::string result = CC::check_unsigned_package_row(vector.at("row"), unhex(vector.at("body_hex").get<std::string>()),
                                                                  request);
        const bool signature_step = expect == CC::SIGN_MISSING_SIGNATURE || expect == CC::SIGN_UNKNOWN_KEY ||
                                    expect == CC::SIGN_BAD_SIGNATURE;
        // A signature failure is skipped: the body steps then decide. Any
        // other reason is the same, since steps 1-4 and 8-10 run unchanged.
        if (!signature_step)
            CHECK(result == expect);
        else
            CHECK(result != CC::SIGN_MALFORMED_ROW);
    }
}

TEST_CASE("The client slot uses the protocol vocabulary", "[cosmyx]")
{
    std::string os, arch;
    CHECK(CC::client_slot("macos", "arm64", os, arch));
    CHECK(os == "macosx");
    CHECK(CC::client_slot("win", "x86_64", os, arch));
    CHECK(os == "win");
    CHECK(CC::client_slot("linux", "i386", os, arch));
    CHECK_FALSE(CC::client_slot("unknown", "x86_64", os, arch));
    CHECK_FALSE(CC::client_slot("linux", "unknown", os, arch));
    CHECK_FALSE(CC::client_slot("*", "*", os, arch));
}

TEST_CASE("A downgrade compares strict versions numerically", "[cosmyx]")
{
    CHECK(CC::is_downgrade("1.2.0", "1.1.9"));
    CHECK(CC::is_downgrade("1.10.0", "1.9.0"));
    CHECK(CC::is_downgrade("2.0.0", "1.999999.999999"));
    CHECK_FALSE(CC::is_downgrade("1.2.0", "1.2.0"));
    CHECK_FALSE(CC::is_downgrade("1.2.0", "1.2.1"));
    CHECK_FALSE(CC::is_downgrade("", "1.0.0"));        // nothing recorded
    CHECK_FALSE(CC::is_downgrade("1.0", "0.9.0"));     // not strict: the record is not trusted
    CHECK_FALSE(CC::is_downgrade("1.0.0", "01.0.0"));  // not strict: step 1 refuses it
}

TEST_CASE("The entry package name is a plain module name", "[cosmyx]")
{
    for (const char* name : {"hello", "orca_hello", "_private", "Pkg2", "con_tool", "COM10", "LPT"})
        CHECK(CC::is_safe_import_name(name));
    for (const char* name : {"", "../escape", "..", ".", "/abs", "C:\\x", "pkg.sub", "pkg-name", "2pkg", "__init__",
                             "__whl_extracted__", "CON", "con", "Nul", "aux", "PRN", "COM1", "com9", "LPT0", "lpt7",
                             "na\xc3\xafve", "name ", "a/b"})
        CHECK_FALSE(CC::is_safe_import_name(name));
    CHECK_FALSE(CC::is_safe_import_name(std::string(256, 'a')));
    CHECK(CC::is_safe_import_name(std::string(255, 'a')));
    CHECK_FALSE(CC::is_safe_import_name(std::string("pkg\0x", 5)));
}

TEST_CASE("The entry package must sit at the top of the wheel", "[cosmyx]")
{
    const std::vector<std::string> entries = {"hello/__init__.py", "hello/core.py", "single.py",
                                              "hello-1.0.0.dist-info/METADATA", "deep/hidden/__init__.py"};
    CHECK(CC::has_top_level_entry(entries, "hello"));
    CHECK(CC::has_top_level_entry(entries, "single"));
    CHECK_FALSE(CC::has_top_level_entry(entries, "hidden"));
    CHECK_FALSE(CC::has_top_level_entry(entries, "Hello")); // imports are case-sensitive
    CHECK_FALSE(CC::has_top_level_entry(entries, "hell"));
    CHECK_FALSE(CC::has_top_level_entry({"hello/"}, "hello")); // a folder entry alone holds nothing
}

TEST_CASE("The package record round-trips and refuses anything else", "[cosmyx]")
{
    const CC::PackageRecord record{"0b5e2d6c-3f41-4a8e-9c27-5d1e8f3a6b90", "1.0.0",
                                   "7b99f45f2ce88ca84eafc98b615c8b437a5800f8e0eba52b58b31dd50e0610ab", 63,
                                   "56475aa75463474c0285df5dbf2bcab73da651358839e9b77481b2eab107708c"};
    const std::string text = CC::record_to_json(record);
    CHECK(text.back() == '\n');
    const json doc = json::parse(text);
    CHECK(doc.size() == 5);
    CHECK(doc.at("size").is_number_integer());

    CC::PackageRecord read;
    REQUIRE(CC::record_from_json(text, read));
    CHECK(read.plugin_id == record.plugin_id);
    CHECK(read.version == record.version);
    CHECK(read.sha256 == record.sha256);
    CHECK(read.size == record.size);
    CHECK(read.key_id == record.key_id);
    CHECK(read.verified());

    CC::PackageRecord unverified = record;
    unverified.key_id.clear();
    REQUIRE(CC::record_from_json(CC::record_to_json(unverified), read));
    CHECK_FALSE(read.verified());

    CHECK_FALSE(CC::record_from_json("", read));
    CHECK_FALSE(CC::record_from_json("[]", read));
    CHECK_FALSE(CC::record_from_json("{not json", read));
    json bad = doc;
    bad["version"] = "1.0";
    CHECK_FALSE(CC::record_from_json(bad.dump(), read));
    bad = doc;
    bad["size"] = 5.0;
    CHECK_FALSE(CC::record_from_json(bad.dump(), read));
    bad = doc;
    bad["key_id"] = "ABC";
    CHECK_FALSE(CC::record_from_json(bad.dump(), read));
    bad = doc;
    bad.erase("sha256");
    CHECK_FALSE(CC::record_from_json(bad.dump(), read));
}
