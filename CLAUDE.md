# youtube-transcript

Hermes plugin: one tool, `youtube_transcript`, and a system prompt section (`PROMPT_SECTION` in
`youtube_transcript/tools.py`) that routes YouTube links to it with the `tool_call` shape. Plugin id, folder name and manifest `name` are
`youtube-transcript`. Measurements and context in Coppermind
`004-projects/hermes-tuning-2026-11.md`.

- `~/.hermes/plugins/youtube-transcript` is a symlink to this checkout (`scripts/install.sh`).
- The gateway is the systemd user unit `hermes-gateway` serving Ignacio's live Telegram bot.
  Restart it only when `active_agents` in `~/.hermes/gateway_state.json` is 0.
- Never edit `~/.hermes/config.yaml` by hand; use `hermes plugins enable|disable`.
- `__init__.py` is imported as `hermes_plugins.youtube_transcript`; feature code is imported
  relatively from the `youtube_transcript` subpackage. No module may be named after a Hermes
  package (`tools`, `agent`, `gateway`, ...) at the top level.
- `pyproject.toml` is tool config only: keep `[project].dependencies` empty.
- Keep `provides_tools` in `plugin.yaml` equal to what `register(ctx)` registers.
- The description's first sentence is the `tool_search` catalog line: 80 characters at most
  (a test pins it). Plugin code and the prompt section load at gateway start, and `hermes -z`
  runs through the gateway, so restart it before measuring a change.
- No shell and no subprocess in the tool; every network call keeps a timeout.
- The skill `~/.hermes/skills/media/video-content-summarization` points at this tool
  (workflow step 2); keep the two in step.

## Checks

`scripts/check.sh` must pass before a commit.
