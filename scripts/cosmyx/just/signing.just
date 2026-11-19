# Windows signing recipes (T9). Imported by the root justfile.

# Print the Jsign command and the files Azure signing would sign under PATH (needs pwsh and the COSMYX_SIGN_ENDPOINT, _ACCOUNT, _PROFILE and ORCA_SIGN_JSIGN variables, any values).
sign-dryrun PATH:
    pwsh -NoLogo -NoProfile -Command '$env:COSMYX_SIGN_DRYRUN = 1; & ./scripts/cosmyx/sign_windows_azure.ps1 -Path {{PATH}}'
