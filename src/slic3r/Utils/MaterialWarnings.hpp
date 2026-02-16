#pragma once

#include <string>
#include <vector>
#include <memory>

// Material Warning System
//
// This system shows warning popups when slicing with specific filament types (e.g., Nylon)
// to remind users of important preparation steps (drying, chamber heating, bed adhesion).
//
// Global Flag: ignore_filament_check
//   - AppConfig key: ignore_filament_check (default [app] section)
//   - Default: false (warnings enabled, checkbox unchecked)
//   - Set to true to bypass all material warnings
//   - Exposed in Preferences > General > "Ignore filament warnings" checkbox

namespace Slic3r {
namespace GUI {

// Condition that must be true for a RecommendedSetting to be applied or verified.
// Both the value expression syntax ("[key] + N") and the config_scope field work here too.
//
// Operators: "==" (default), "!=", ">", "<", ">=", "<="
// Comparison is numeric when both sides parse as numbers, otherwise string.
//
// Example (apply +20°C only when ironing is active):
//   "condition": { "key": "ironing_type", "operator": "!=", "value": "0" }
struct SettingCondition {
    std::string key;
    std::string value;
    std::string op           = "==";    // "==", "!=", ">", "<", ">=", "<="
    std::string config_scope = "print"; // which config to read the key from: "print", "filament", "printer"
};

// Structure to hold recommended settings for future auto-apply functionality
struct RecommendedSetting {
    std::string key;   // Config key (e.g., "nozzle_temperature")
    std::string value; // Value to set — supports expressions like "[nozzle_temperature] + 20"
    std::string label; // User-friendly label (e.g., "Increase nozzle temperature by 20°C")
    bool verify = true; // If true, check this setting before showing popup
    // "print"    -> reads/writes from the print preset config (default)
    // "filament" -> reads/writes from the active filament preset config
    // "printer"  -> reads/writes from the printer preset config (hardware capabilities)
    std::string config_scope = "print";
    // Optional condition — setting is skipped (in both verify and apply) when condition is false
    bool has_condition = false;
    SettingCondition condition;
};

// Configuration for a material warning
struct MaterialWarningConfig {
    std::vector<std::string> material_types; // Materials that trigger this warning (e.g., ["PA", "PA-CF"])
    std::string title;                        // Dialog title
    std::string message;                      // Warning message to display
    std::string icon;                         // Icon type: "warning", "info", "error"
    // Classification used to group warnings in Preferences.
    // Known values: "process", "filament", "nozzle", "general" (default)
    // Each classification has its own ignore checkbox in Preferences > General.
    std::string classification = "general";

    // Future enhancement: Settings to recommend/auto-apply
    std::vector<RecommendedSetting> recommended_settings;

    // Future enhancement: Control display behavior
    bool show_every_time = true;              // If false, can be dismissed persistently
    bool verify_settings = false;             // If true, check if settings already match before showing
    // If true (default): dialog shows Yes / No  — No skips the warning and proceeds to slicing
    // If false:          dialog shows Apply / Cancel — user must either apply settings or cancel slicing
    bool is_skippable    = true;
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
