// Holes found by breaking the plugin package signature verifier
// (logic/PluginSigning.cpp, decision 0204). Each test reproduces one hole and
// fails until the verifier is fixed.

#include <catch2/catch_test_macros.hpp>

#include <ios>
#include <map>
#include <string>
#include <utility>

#include <boost/filesystem/path.hpp>
#include <boost/nowide/fstream.hpp>
#include <nlohmann/json.hpp>
#include <openssl/err.h>

#include "slic3r/GUI/Cosmyx/logic/PluginSigning.hpp"

namespace CC = Slic3r::GUI::Cosmyx;
using nlohmann::json;

namespace {

json load_break_vectors()
{
    const boost::filesystem::path path = boost::filesystem::path(TEST_DATA_DIR) / ".." / "cosmyx" / "data" / "plugin-signatures.json";
    boost::nowide::ifstream       file(path.string(), std::ios::binary);
    REQUIRE(file);
    return json::parse(file);
}

std::string break_unhex(const std::string& hex)
{
    std::string bytes;
    REQUIRE(CC::from_lower_hex(hex, bytes));
    return bytes;
}

} // namespace

// OpenSSL pushes an error on the calling thread's error queue when an Ed25519
// verification fails (or a raw key is refused). The verifier ignores it and
// returns, so every refused package leaves a stale entry behind on the plugin
// download thread. OpenSSL requires that queue to be empty before the next
// TLS I/O on the thread (SSL_get_error() misreports otherwise), and later
// ERR_get_error() callers read an error that is not theirs. A refusal must
// leave the queue as it found it.
TEST_CASE("A refused signature leaves the OpenSSL error queue empty", "[cosmyx][break]")
{
    const json vectors = load_break_vectors();

    SECTION("ed25519_verify on a wrong signature")
    {
        const json&       test      = vectors.at("rfc8032").at(0);
        const std::string key       = break_unhex(test.at("public_key").get<std::string>());
        const std::string message   = break_unhex(test.at("message_hex").get<std::string>());
        std::string       signature = break_unhex(test.at("signature").get<std::string>());
        signature[0]                = static_cast<char>(signature[0] ^ 0x01);

        ERR_clear_error();
        CHECK_FALSE(CC::ed25519_verify(key, message, signature));
        CHECK(ERR_peek_error() == 0);
        ERR_clear_error();
    }

    SECTION("verify_package_row on every bad_signature vector row")
    {
        std::map<std::string, std::pair<std::string, std::string>> keys;
        for (const json& key : vectors.at("keys"))
            keys[key.at("name").get<std::string>()] = {key.at("key_id").get<std::string>(), key.at("public_key").get<std::string>()};

        int rows = 0;
        for (const json& test : vectors.at("rows")) {
            if (test.at("expect") != CC::SIGN_BAD_SIGNATURE)
                continue;
            INFO(test.at("name").get<std::string>());
            CC::KeyTable pinned;
            CC::KeyIdSet revoked;
            std::string  error;
            for (const json& name : test.at("pinned"))
                REQUIRE(CC::add_pinned_key(pinned, keys.at(name.get<std::string>()).first, keys.at(name.get<std::string>()).second, error));
            for (const json& name : test.at("revoked"))
                revoked.insert(keys.at(name.get<std::string>()).first);
            const json&       client = test.at("client");
            CC::ClientRequest request{client.at("plugin_id").get<std::string>(),
                                      client.at("version").is_null() ? std::string() : client.at("version").get<std::string>(),
                                      client.at("os").get<std::string>(), client.at("arch").get<std::string>()};

            ERR_clear_error();
            REQUIRE(CC::verify_package_row(test.at("row"), break_unhex(test.at("body_hex").get<std::string>()), request, pinned,
                                           revoked) == CC::SIGN_BAD_SIGNATURE);
            CHECK(ERR_peek_error() == 0);
            ERR_clear_error();
            ++rows;
        }
        CHECK(rows > 0);
    }
}
