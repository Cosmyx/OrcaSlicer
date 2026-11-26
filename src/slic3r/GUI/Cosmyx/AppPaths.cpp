#include "AppPaths.hpp"

#include <wx/app.h>
#include <wx/stdpaths.h>
#include <wx/string.h>

namespace Slic3r {
namespace GUI {
namespace Cosmyx {

void use_vendor_data_dir()
{
    if (wxTheApp == nullptr)
        return;
    wxTheApp->SetVendorName(wxString::FromUTF8(Slic3r::Cosmyx::DATA_DIR_VENDOR));
    wxStandardPaths::Get().UseAppInfo(wxStandardPaths::AppInfo_VendorName | wxStandardPaths::AppInfo_AppName);
}

} // namespace Cosmyx
} // namespace GUI
} // namespace Slic3r
