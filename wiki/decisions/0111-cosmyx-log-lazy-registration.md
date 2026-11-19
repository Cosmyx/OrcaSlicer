# 0111. Cosmyx log sink registered lazily, with no upstream hook

## Status

Accepted.

## Context

The Cosmyx sink needs Orca's log folder and must be registered after Orca sets
up its own logging in `GUI_App::on_init_inner()`. A call there is one more
upstream hook. Registering a sink too early, or in the CLI, would also change
upstream behaviour: Boost.Log stops using its default console sink as soon as
any sink exists.

## Decision

- No hook. The first `COSMYX_LOG` registers the sink, and only once Orca's file
  sink (`g_log_sink`) exists. The file name is derived from Orca's current file
  (`get_log_file_name()`); if that is not open yet, a `cosmyx_<time>_<pid>.log`
  name in `data_dir()/log` is used.
- Before that (start-up, CLI, old macOS without file logging) nothing is
  registered and Cosmyx records behave like any upstream record.
- Once registered, or once registration failed, a flag makes later calls skip
  the check without taking the mutex.

## Consequences

- Cosmyx records logged before Orca's log file exists are not in the Cosmyx
  file (they go where upstream records go at that time).
- The Cosmyx file appears only once Cosmyx code logs something.
- An explicit start would be a single `Cosmyx::init_log(...)` call after
  `set_log_path_and_level()` in `GUI_App.cpp`.
