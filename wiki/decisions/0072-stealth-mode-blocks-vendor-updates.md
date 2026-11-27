# 0072. Stealth mode blocks vendor profile updates

## Status

Accepted.

## Context

`PresetUpdater::check_vendor_update()` returns early when stealth mode is on,
so the online vendor profile update check never runs once stealth mode is
forced (decision 0070). Other readers skip the user preset sync, the cloud
login, the privacy version check, HMS and the plugin host cloud features.

## Decision

- This is accepted: Cosmyx ships its printer and filament profiles in the
  bundle and updates them with the application, so it needs none of the
  online updates or cloud services that stealth mode blocks.
- The setup guide's new-vendor install path
  (`PresetUpdater::check_new_vendors()`, called from the guide) is not gated
  by stealth mode upstream and is left as it is.

## Consequences

- Profile fixes reach Cosmyx users through a new Cosmyx build only.
- Removing it: nothing to remove; it follows from decision 0070.
