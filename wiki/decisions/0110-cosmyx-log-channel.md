# 0110. Cosmyx log channel and file

## Status

Accepted.

## Context

The CosmoSlice fork logged its own additions ("CosmoLogs") to a file of their
own by editing upstream `utils.cpp` (`set_logging_level()`,
`set_log_path_and_level()`) and `GUI_App.cpp`. Here, upstream logging must not
change and every upstream edit is a possible merge conflict. Only Cosmyx code
uses the new channel; upstream `BOOST_LOG_TRIVIAL` calls stay as they are.

## Decision

- `src/libslic3r/Cosmyx/CosmyxLog.{hpp,cpp}` provides `COSMYX_LOG(level)`, a
  `BOOST_LOG_CHANNEL_SEV` on a `severity_channel_logger_mt` with the channel
  attribute `"Cosmyx"` and the Boost.Log trivial severities.
- The logger and the module state are function-local statics, so nothing is
  built during static initialisation (the crash CosmoSlice hit with a global
  logger).
- A file sink filtered on the channel writes the Cosmyx records to
  `cosmyx_<same time and pid as Orca's debug file>.log.N`, in the folder of
  Orca's current debug log (`data_dir()/log`), with Orca's line layout and
  Orca's rotation size (100 MB, `.N` index from 0, auto flush), like CosmoSlice.
- Orca's file sink gets the filter "not the Cosmyx channel", so each file holds
  one channel, as in CosmoSlice. Upstream records are not affected.
- Cosmyx records keep passing Orca's global severity filter: the log level set
  in the preferences applies to them. CosmoSlice let its channel bypass it, which
  needs an edit of `set_logging_level()`.
- `init_log(folder, name, rotation)`, `shutdown_log()`, `flush_log()`,
  `log_active()` and `log_file_path()` are public, for the tests and for a
  later explicit start if one is ever needed.

## Consequences

- Removing the feature means deleting the two files, the test and the
  `COSMYX_LOG` calls of Cosmyx code.
- `utils.cpp` defines `g_log_sink` without declaring it in a header;
  `CosmyxLog.cpp` declares it `extern`. If upstream makes it `static` or renames
  it, the link fails and the declaration has to follow.
- If upstream ever sets its own filter on its file sink, the Cosmyx filter
  replaces it; `git grep set_filter` after an upstream merge shows it.
