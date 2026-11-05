# youtube-transcript

A [Hermes Agent](https://github.com/NousResearch/hermes-agent) plugin that turns "summarize this
YouTube link" into a single tool call. Your agent gets the video's title, channel, length and
transcript in about a second, with no shell, no `yt-dlp` and no skill round-trips.

## What it changes

Stock Hermes handles a YouTube link through the bundled `youtube-content` skill. The model loads
the skill, runs `yt-dlp` in the terminal for metadata, then runs a Python helper for the
transcript. Each step is a separate model call. On a gateway with command approvals, each
terminal run can also wait for someone to tap "approve".

With this plugin the model calls `youtube_transcript(url)` once and writes the answer.

Measured on one install with `hermes -z` (Hermes v0.22.7, grok-4.6, a 15-minute video, a fresh
session each run):

| | Stock `youtube-content` | With this plugin |
|---|---|---|
| Model calls per summary | 3 | 2 |
| Tool calls | 3 `skill_view`, 2 `terminal` | 1 `youtube_transcript` (plus your summary skill, in the same call) |
| Time until the answer starts | ~12 s | ~5–6 s |
| Shell commands to approve | 2 | 0 |
| Input tokens on the answer call | ~35K | ~31K |

The answer call itself still takes as long as your model takes to write a summary. The plugin
removes the work before it.

## How it gets there

Two pieces, both registered by the plugin.

**The tool.** `youtube_transcript` reads metadata from YouTube's oEmbed endpoint and the
transcript from `youtube-transcript-api`, which Hermes already ships. Nothing new to install,
nothing runs in a shell, and every request has a 10 s timeout. When a video has no transcript in
the languages you prefer, it falls back to any manual transcript, then any auto-generated one.

**A 600-character prompt section.** Hermes hides plugin tools behind `tool_search`, so a model
normally has to call `tool_describe` before it can use one, and it often reaches for the skill it
already knows. The plugin adds a short note to each new session prompt that routes YouTube links
to the tool and spells out the `tool_call` shape, so the model calls it straight away. The note
also tells the model to keep following any summary skill you have for the format of the answer,
and to load it in the same turn. Your output style stays yours.

## Arguments

| Argument | Default | Meaning |
|---|---|---|
| `url` | required | Any YouTube URL (watch, youtu.be, shorts, embed, live, music) or an 11-character id |
| `languages` | `["en", "es"]` | Preferred transcript languages, in order |
| `timestamps` | `false` | Prefix lines with `[m:ss]`, for chapters and quotes |
| `max_chars` | `60000` | Transcript cap, 2,000 to 200,000. A cut result says where it stopped |

The result is JSON: `video_id`, `url`, `title`, `channel`, `length`, `language`,
`auto_generated`, `chars`, `truncated`, `transcript`, and a `note` when the transcript was cut.
Failures come back as `{"error": "..."}` with a plain reason (subtitles disabled, video
unavailable, age-restricted, request blocked), so the model can tell the user instead of
retrying.

## Limits

- It reads existing subtitles. A video with none, manual or generated, has no transcript here;
  there is no speech-to-text.
- YouTube blocks transcript requests from many cloud and datacenter IPs. On a home machine this
  works; on a VPS you may get "YouTube blocked the transcript request". The plugin does not try
  to get around that.
- The prompt section costs about 150 tokens in every new session, YouTube link or not.

## Install

```bash
hermes plugins install IpastorSan/hermes-youtube --enable
```

Restart the gateway (`hermes gateway restart`, or your service manager) so new sessions pick up
the tool and the prompt section. `--enable` adds the `youtube-transcript` toolset to every
platform in `platform_toolsets`; take it off one with
`hermes tools disable --platform <platform> youtube-transcript`.

To hack on it, clone the repo and link the checkout instead:

```bash
git clone https://github.com/IpastorSan/hermes-youtube
cd hermes-youtube
scripts/install.sh                      # links this checkout into $HERMES_HOME/plugins
hermes plugins enable youtube-transcript
```

## Development

```bash
scripts/check.sh   # ruff, pytest, hermes plugins doctor and validate
```

Needs `uv`, and `hermes` on `PATH` for the last two checks. The tests use fake transcript
listings and never touch the network.

## License

MIT
