#pragma once

#include <string>
#include <vector>
#include <memory>

namespace Slic3r {
namespace GUI {

// Structure to hold recommended settings for future auto-apply functionality
struct RecommendedSetting {
    std::string key;   // Config key (e.g., "chamber_temperature")
    std::string value; // Value to set (e.g., "60")
    std::string label; // User-friendly label (e.g., "Set chamber to 60°C")
};

// Configuration for a material warning
struct MaterialWarningConfig {
    std::vector<std::string> material_types; // Materials that trigger this warning (e.g., ["PA", "PA-CF"])
    std::string title;                        // Dialog title
    std::string message;                      // Warning message to display
    std::string icon;                         // Icon type: "warning", "info", "error"

    // Future enhancement: Settings to recommend/auto-apply
    std::vector<RecommendedSetting> recommended_settings;

    // Future enhancement: Control display behavior
    bool show_every_time = true;              // If false, can be dismissed persistently
    bool verify_settings = false;             // If true, check if settings already match before showing
    std::string documentation_url;            // Optional link to material guide
};

// Singleton manager for material warnings
class MaterialWarningManager {
public:
    // Get singleton instance
    static MaterialWarningManager& get_instance();

    // Load warnings configuration from resources/info/material_warnings.json
    // Returns true on success, false on failure (logs errors)
    bool load_warnings_config();

    // Get all warnings that apply to the given material types
    // Returns vector of matching warnings (may be empty)
    std::vector<MaterialWarningConfig> get_warnings_for_materials(
        const std::vector<std::string>& material_types
    );

    // Check if warnings are loaded successfully
    bool is_loaded() const { return m_loaded; }

    // Get version of loaded config
    std::string get_config_version() const { return m_version; }

    // Future enhancement: Check if a warning has been dismissed by user
    // bool is_warning_dismissed(const std::string& material_type);
    // void set_warning_dismissed(const std::string& material_type, bool dismissed);

    // Future enhancement: Verify if current settings match recommended settings
    // bool verify_settings_match(const MaterialWarningConfig& warning);

private:
    MaterialWarningManager() = default;
    ~MaterialWarningManager() = default;

    // Prevent copying
    MaterialWarningManager(const MaterialWarningManager&) = delete;
    MaterialWarningManager& operator=(const MaterialWarningManager&) = delete;

    std::vector<MaterialWarningConfig> m_warnings;
    bool m_loaded = false;
    std::string m_version;
    std::string m_config_path;
};

} // namespace GUI
} // namespace Slic3r
