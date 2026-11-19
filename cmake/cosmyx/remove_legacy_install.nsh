; Cosmyx: remove an earlier Cosmyx build installed under a legacy uninstall key,
; before this installer copies its files. Included through
; CPACK_NSIS_EXTRA_PREINSTALL_COMMANDS (cmake/cosmyx/Packaging.cmake), so it runs
; inside CPack's core installation section.
;
; Identification rule: an install is removed only when BOTH hold:
;   - its uninstall key is one of the legacy Cosmyx keys listed at the bottom;
;   - the Publisher value of that key is exactly "Cosmyx".
; Upstream OrcaSlicer installs under the key "OrcaSlicer" with the publisher
; "SoftFever". That key is never listed, so an upstream install is never touched.
; Cosmyx builds that used the upstream key and publisher cannot be told apart
; from upstream and are left in place.
;
; The current key ("Cosmyx CosmoSlice") is not listed: CPack's own
; uninstall-before-install step (CPACK_NSIS_ENABLE_UNINSTALL_BEFORE_INSTALL)
; already offers to remove it.

!define COSMYX_LEGACY_PUBLISHER "Cosmyx"
!define COSMYX_UNINSTALL_ROOT "Software\Microsoft\Windows\CurrentVersion\Uninstall"

!macro CosmyxRemoveLegacyInstall HIVE KEY ID
  Push $0
  Push $1
  Push $2
  ReadRegStr $0 ${HIVE} "${COSMYX_UNINSTALL_ROOT}\${KEY}" "Publisher"
  StrCmp $0 "${COSMYX_LEGACY_PUBLISHER}" 0 cosmyx_legacy_skip_${ID}
  ReadRegStr $0 ${HIVE} "${COSMYX_UNINSTALL_ROOT}\${KEY}" "UninstallString"
  StrCmp $0 "" cosmyx_legacy_skip_${ID}
  ; CPack writes the path unquoted; drop the quotes if a later build added them.
  StrCpy $1 $0 1
  StrCmp $1 '"' 0 cosmyx_legacy_unquoted_${ID}
  StrCpy $0 $0 "" 1
  StrCpy $0 $0 -1
cosmyx_legacy_unquoted_${ID}:
  IfFileExists "$0" 0 cosmyx_legacy_skip_${ID}
  ; The folder that holds Uninstall.exe, computed as CPack's own step does.
  StrLen $1 "\Uninstall.exe"
  StrCpy $2 $0 -$1
  DetailPrint "Removing the earlier Cosmyx install in $2"
  ClearErrors
  ; _?= runs the uninstaller in place, so ExecWait waits for it to finish; it
  ; then leaves itself behind, and its folder is removed only if empty.
  ExecWait '"$0" /S _?=$2'
  Delete "$0"
  RMDir "$2"
cosmyx_legacy_skip_${ID}:
  Pop $2
  Pop $1
  Pop $0
!macroend

; Cosmyx builds before the CosmoSlice folder used the key "Cosmyx OrcaSlicer"
; with the publisher "Cosmyx" (install folder Program Files\Cosmyx\OrcaSlicer).
!insertmacro CosmyxRemoveLegacyInstall HKLM "Cosmyx OrcaSlicer" 0
!insertmacro CosmyxRemoveLegacyInstall HKCU "Cosmyx OrcaSlicer" 1
