#include "MaterialWarnings.hpp"
#include "nlohmann/json.hpp"
#include "libslic3r/Utils.hpp"

#include <fstream>
#include <boost/log/trivial.hpp>
#include <boost/nowide/fstream.hpp>
#include <boost/filesystem.hpp>

using json = nlohmann::json;

namespace Slic3r {
namespace GUI {

MaterialWarningManager& MaterialWarningManager::get_instance()
{
    static MaterialWarningManager instance;
    return instance;
}

bool MaterialWarningManager::load_warnings_config()
{
    // Early return if already loaded successfully
    if (m_loaded) {
        return true;
    }

    try {
        // Construct path to material_warnings.json
        m_config_path = Slic3r::resources_dir() + "/info/material_warnings.json";

        BOOST_LOG_TRIVIAL(info) << "MaterialWarningManager: Loading config from " << m_config_path;

        // Check if file exists
        if (!boost::filesystem::exists(m_config_path)) {
            BOOST_LOG_TRIVIAL(warning) << "MaterialWarningManager: Config file not found at " << m_config_path
                                       << " - material warnings disabled";
            return false;
        }

        // Open and parse JSON file
        boost::nowide::ifstream file(m_config_path);
        if (!file.is_open()) {
            BOOST_LOG_TRIVIAL(error) << "MaterialWarningManager: Failed to open config file: " << m_config_path;
            return false;
        }

        json j;
        file >> j;
        file.close();

        // Parse version
        if (j.contains("version") && j["version"].is_string()) {
            m_version = j["version"].get<std::string>();
            BOOST_LOG_TRIVIAL(info) << "MaterialWarningManager: Config version " << m_version;
        }

        // Parse warnings array
        if (!j.contains("warnings") || !j["warnings"].is_array()) {
            BOOST_LOG_TRIVIAL(error) << "MaterialWarningManager: Invalid config - missing 'warnings' array";
            return false;
        }

        m_warnings.clear();
        for (const auto& warning_json : j["warnings"]) {
            try {
                MaterialWarningConfig config;

                // Parse material_types (required)
                if (!warning_json.contains("material_types") || !warning_json["material_types"].is_array()) {
                    BOOST_LOG_TRIVIAL(warning) << "MaterialWarningManager: Skipping warning - missing material_types";
                    continue;
                }
                for (const auto& mat : warning_json["material_types"]) {
                    if (mat.is_string()) {
                        config.material_types.push_back(mat.get<std::string>());
                    }
                }

                // Parse title (required)
                if (warning_json.contains("title") && warning_json["title"].is_string()) {
                    config.title = warning_json["title"].get<std::string>();
                } else {
                    config.title = "Material Warning";
                }

                // Parse message (required)
                if (!warning_json.contains("message") || !warning_json["message"].is_string()) {
                    BOOST_LOG_TRIVIAL(warning) << "MaterialWarningManager: Skipping warning - missing message";
                    continue;
                }
                config.message = warning_json["message"].get<std::string>();

                // Parse icon (optional, default to "warning")
                if (warning_json.contains("icon") && warning_json["icon"].is_string()) {
                    config.icon = warning_json["icon"].get<std::string>();
                } else {
                    config.icon = "warning";
                }

                // Parse optional fields for future enhancements
                if (warning_json.contains("show_every_time") && warning_json["show_every_time"].is_boolean()) {
                    config.show_every_time = warning_json["show_every_time"].get<bool>();
                }

                if (warning_json.contains("verify_settings") && warning_json["verify_settings"].is_boolean()) {
                    config.verify_settings = warning_json["verify_settings"].get<bool>();
                }

                if (warning_json.contains("documentation_url") && warning_json["documentation_url"].is_string()) {
                    config.documentation_url = warning_json["documentation_url"].get<std::string>();
                }

                // Parse recommended_settings array (for future auto-apply functionality)
                if (warning_json.contains("recommended_settings") && warning_json["recommended_settings"].is_array()) {
                    for (const auto& setting_json : warning_json["recommended_settings"]) {
                        if (setting_json.contains("key") && setting_json.contains("value")) {
                            RecommendedSetting setting;
                            setting.key = setting_json["key"].get<std::string>();
                            setting.value = setting_json["value"].get<std::string>();

                            if (setting_json.contains("label") && setting_json["label"].is_string()) {
                                setting.label = setting_json["label"].get<std::string>();
                            }

                            // Parse verify flag (defaults to true if not specified)
                            if (setting_json.contains("verify") && setting_json["verify"].is_boolean()) {
                                setting.verify = setting_json["verify"].get<bool>();
                            }

                            config.recommended_settings.push_back(setting);
                        }
                    }
                }

                // Add warning to list
                m_warnings.push_back(config);
                BOOST_LOG_TRIVIAL(info) << "MaterialWarningManager: Loaded warning for materials: "
                                       << config.material_types.size() << " types";

            } catch (const std::exception& e) {
                BOOST_LOG_TRIVIAL(warning) << "MaterialWarningManager: Failed to parse warning entry: " << e.what();
                continue;
            }
        }

        m_loaded = true;
        BOOST_LOG_TRIVIAL(info) << "MaterialWarningManager: Successfully loaded " << m_warnings.size() << " warnings";
        return true;

    } catch (const std::exception& e) {
        BOOST_LOG_TRIVIAL(error) << "MaterialWarningManager: Exception loading config: " << e.what();
        m_loaded = false;
        return false;
    }
}

std::vector<MaterialWarningConfig> MaterialWarningManager::get_warnings_for_materials(
    const std::vector<std::string>& material_types)
{
    std::vector<MaterialWarningConfig> matching_warnings;

    // Ensure config is loaded
    if (!m_loaded) {
        if (!load_warnings_config()) {
            // Failed to load config
            return matching_warnings; // Return empty vector
        }
    }

    // Find all warnings that match any of the detected material types
    for (const auto& warning : m_warnings) {
        for (const auto& detected_material : material_types) {
            // Check if this warning applies to the detected material
            for (const auto& warning_material : warning.material_types) {
                if (detected_material == warning_material) {
                    // Found a match - add this warning if not already added
                    bool already_added = false;
                    for (const auto& existing : matching_warnings) {
                        if (&existing == &warning) {
                            already_added = true;
                            break;
                        }
                    }

                    if (!already_added) {
                        matching_warnings.push_back(warning);
                        BOOST_LOG_TRIVIAL(debug) << "MaterialWarningManager: Material " << detected_material
                                                << " matches warning: " << warning.title;
                    }
                    goto next_warning; // Break out of nested loops
                }
            }
        }
        next_warning:;
    }

    if (!matching_warnings.empty()) {
        BOOST_LOG_TRIVIAL(info) << "MaterialWarningManager: Found " << matching_warnings.size()
                               << " warnings for " << material_types.size() << " material types";
    }

    return matching_warnings;
}

// Future enhancement stubs (commented out for now):
/*
bool MaterialWarningManager::is_warning_dismissed(const std::string& material_type)
{
    // TODO: Check AppConfig for dismissed status
    // Example: return wxGetApp().app_config->get("material_warnings", "dismissed_" + material_type) == "1";
    return false;
}

void MaterialWarningManager::set_warning_dismissed(const std::string& material_type, bool dismissed)
{
    // TODO: Store dismissed status in AppConfig
    // Example: wxGetApp().app_config->set("material_warnings", "dismissed_" + material_type, dismissed ? "1" : "0");
}

bool MaterialWarningManager::verify_settings_match(const MaterialWarningConfig& warning)
{
    // TODO: Check if current print settings match recommended settings
    // If all recommended settings are already applied, return true (skip warning)
    // Otherwise return false (show warning)
    return false;
}
*/

} // namespace GUI
} // namespace Slic3r
