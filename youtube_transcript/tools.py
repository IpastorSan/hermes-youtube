"""The ``youtube_transcript`` agent tool.

Handlers follow the Hermes plugin contract: ``handler(args, **kwargs) -> str`` returning JSON,
never raising.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from . import core

logger = logging.getLogger(__name__)

TOOLSET = "youtube-transcript"

# The first sentence is what the deferred tool_search listing shows (80 characters at most), so
# it names the argument.
SCHEMA = {
    "name": "youtube_transcript",
    "description": (
        "youtube_transcript(url): a YouTube video's title, length and transcript. One call "
        "returns channel, language and the full transcript too. Use it for any YouTube link "
        "(summaries, questions, quotes, chapters) instead of terminal, yt-dlp or the "
        "youtube-content script. Pass timestamps=true only when the answer needs times, such "
        "as chapters or quotes."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "YouTube URL (watch, youtu.be, shorts, embed, live) or video id.",
            },
            "languages": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Preferred transcript languages in order. Default [\"en\", \"es\"]; "
                "falls back to any available transcript.",
            },
            "timestamps": {
                "type": "boolean",
                "description": "Prefix each line with [m:ss]. Default false.",
            },
            "max_chars": {
                "type": "integer",
                "description": f"Transcript character cap. Default {core.DEFAULT_MAX_CHARS}.",
            },
        },
        "required": ["url"],
    },
}

# Frozen into every new session prompt. It carries the call shape, so the model can call the
# tool through tool_call without a tool_describe round first, and it routes YouTube links here
# whatever the user's skills say.
PROMPT_SECTION = (
    "For a YouTube link, get the video in one call: youtube_transcript(url) returns title, "
    "channel, length, language and transcript. If it is not in your tool list, call "
    'tool_call({"name": "youtube_transcript", "arguments": {"url": "<link>"}}) directly; it '
    "needs no tool_describe. Optional arguments: languages (default [\"en\", \"es\"]), "
    "timestamps=true for chapters or quotes. Do not use terminal, yt-dlp or the youtube-content "
    "skill to fetch a transcript. This replaces only the fetch: if one of your skills covers "
    "summarizing videos, still follow it for the answer, and load it in the same turn as this "
    "call."
)

_LIBRARY_ERRORS = {
    "TranscriptsDisabled": "Subtitles are disabled for this video, so there is no transcript.",
    "NoTranscriptFound": "This video has no transcript in any language.",
    "VideoUnavailable": "The video is unavailable (private, removed or region-locked).",
    "AgeRestricted": "The video is age-restricted; its transcript cannot be read without login.",
    "RequestBlocked": "YouTube blocked the transcript request from this machine. Try again later.",
    "IpBlocked": "YouTube blocked the transcript request from this machine. Try again later.",
}


def available() -> bool:
    try:
        import youtube_transcript_api  # noqa: F401
    except ImportError:
        return False
    return True


def youtube_transcript(args: dict, **kwargs: Any) -> str:
    try:
        result = core.run(args if isinstance(args, dict) else {})
    except core.InputError as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)
    except Exception as exc:
        name = type(exc).__name__
        message = _LIBRARY_ERRORS.get(name)
        if message is None:
            logger.warning("youtube_transcript failed: %s: %s", name, exc)
            message = f"Could not fetch the transcript ({name})."
        return json.dumps({"error": message}, ensure_ascii=False)
    return json.dumps(result, ensure_ascii=False)
