# hermes-reply-footer

A Hermes plugin that keeps a standing reply-format rule from fading in long sessions. It adds a short,
user-written reminder to the context of every user turn, and can check long replies against a regular
expression and log hits and misses.

It does nothing until `reminder` is set.

## Settings

Under `plugins.entries.reply-footer.settings` in `config.yaml` (also shown in the Desktop Plugins tab):

| Key | Default | Meaning |
|---|---|---|
| `reminder` | `""` | Text added to every user turn. Empty = the plugin is a no-op. |
| `skip_sources` | `[cron, subagent, batch, webhook]` | Platforms that get neither reminder nor check. `subagent` also matches delegated child sessions. |
| `check_pattern` | `""` | Regex a long reply should match. Empty = no check. |
| `min_chars` | `400` | Replies shorter than this are not checked. |
| `log` | `false` | Append `OK` / `MISS` lines to `<HERMES_HOME>/logs/reply_footer.log` (needs `check_pattern`). |

```yaml
plugins:
  enabled: [reply-footer]
  entries:
    reply-footer:
      settings:
        reminder: "End every long reply with a **Next steps** section."
        check_pattern: '^\*\*Next steps\*\*'
        log: true
```

Log line: `2026-01-01T12:00:00 MISS platform=cli session=<id>`.

## Disclosure

No network calls, no credentials, no subprocesses. The only file it writes is `logs/reply_footer.log` under the
active Hermes home, and only when `log` is true. The reminder is added to the user message each turn (a few
tokens per turn, counted against the context). Both hooks fail open.

## Notes

- Hermes loads plugins when a process starts. A long-running messaging gateway admits finite
  (`hermes chat -Q`) sessions with the plugin set it started with, so a newly installed or enabled plugin only
  reaches those sessions after the gateway restarts.

## Tests

`PYTHONPATH=<hermes-agent checkout> python -m pytest tests`
