"""Fetch a YouTube video's title, channel, length, language and transcript in one call.

No shell and no yt-dlp: metadata comes from YouTube's oEmbed endpoint and the transcript from
``youtube-transcript-api``, which Hermes already ships. Every network call has a timeout.
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

import requests

DEFAULT_LANGUAGES = ("en", "es")
DEFAULT_MAX_CHARS = 60_000
MIN_MAX_CHARS = 2_000
HARD_MAX_CHARS = 200_000
HTTP_TIMEOUT = 10.0
OEMBED_URL = "https://www.youtube.com/oembed"

_ID = r"[A-Za-z0-9_-]{11}"
_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com",
          "youtu.be", "www.youtube-nocookie.com", "youtube-nocookie.com"}
_PATH_ID = re.compile(rf"^/(?:shorts|embed|live|v)/({_ID})(?:[/?#]|$)")


class InputError(ValueError):
    """The caller passed something that is not a YouTube video."""


def video_id(url_or_id: str) -> str:
    """The 11-character id of a YouTube URL (watch, youtu.be, shorts, embed, live) or a bare id."""
    text = (url_or_id or "").strip()
    if re.fullmatch(_ID, text):
        return text
    parsed = urllib.parse.urlparse(text if "://" in text else f"https://{text}")
    host = (parsed.hostname or "").lower()
    if host not in _HOSTS:
        raise InputError(f"Not a YouTube URL: {text[:100]!r}")
    if host == "youtu.be":
        candidate = parsed.path.lstrip("/").split("/")[0]
        if re.fullmatch(_ID, candidate):
            return candidate
    else:
        query_id = urllib.parse.parse_qs(parsed.query).get("v", [""])[0]
        if re.fullmatch(_ID, query_id):
            return query_id
        match = _PATH_ID.match(parsed.path)
        if match:
            return match.group(1)
    raise InputError(f"No video id in {text[:100]!r}")


def clock(seconds: float) -> str:
    total = int(seconds)
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


class _TimeoutSession(requests.Session):
    """A requests session whose calls all default to ``HTTP_TIMEOUT``."""

    def request(self, *args: Any, **kwargs: Any) -> requests.Response:
        kwargs.setdefault("timeout", HTTP_TIMEOUT)
        return super().request(*args, **kwargs)


def oembed(vid: str) -> dict[str, str]:
    """Title and channel from oEmbed; empty strings when YouTube does not answer."""
    query = urllib.parse.urlencode({"url": f"https://www.youtube.com/watch?v={vid}",
                                    "format": "json"})
    try:
        with urllib.request.urlopen(f"{OEMBED_URL}?{query}", timeout=HTTP_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return {"title": "", "channel": ""}
    return {"title": str(data.get("title") or ""), "channel": str(data.get("author_name") or "")}


@dataclass
class Transcript:
    language: str
    generated: bool
    segments: list[dict[str, Any]]


def fetch_transcript(vid: str, languages: list[str], api: Any = None) -> Transcript:
    """The first transcript in ``languages``; failing that, any manual one, then any generated.

    Raises the library's own errors (``TranscriptsDisabled``, ``VideoUnavailable``, ...).
    """
    from youtube_transcript_api import NoTranscriptFound, YouTubeTranscriptApi

    api = api or YouTubeTranscriptApi(http_client=_TimeoutSession())
    listing = api.list(vid)
    try:
        chosen = listing.find_transcript(languages)
    except NoTranscriptFound:
        available = list(listing)
        if not available:
            raise
        chosen = next((t for t in available if not t.is_generated), available[0])
    fetched = chosen.fetch()
    segments = [{"text": s.text, "start": s.start, "duration": s.duration} for s in fetched]
    return Transcript(chosen.language_code, bool(chosen.is_generated), segments)


def render(segments: list[dict[str, Any]], *, timestamps: bool,
           max_chars: int) -> tuple[str, bool, float]:
    """Transcript text, whether it was cut, and the second it reaches (all of it when not cut)."""
    parts: list[str] = []
    used = 0
    reached = 0.0
    for seg in segments:
        text = " ".join(str(seg["text"]).split())
        if not text:
            continue
        piece = f"[{clock(seg['start'])}] {text}" if timestamps else text
        cost = len(piece) + 1
        if used + cost > max_chars:
            return ("\n" if timestamps else " ").join(parts), True, reached
        parts.append(piece)
        used += cost
        reached = float(seg["start"]) + float(seg.get("duration") or 0.0)
    return ("\n" if timestamps else " ").join(parts), False, reached


def run(args: dict[str, Any], *, api: Any = None, meta: Any = None) -> dict[str, Any]:
    """Tool body: validated arguments in, result dict out. Raises ``InputError`` on bad input."""
    vid = video_id(str(args.get("url") or ""))
    raw_langs = args.get("languages")
    if isinstance(raw_langs, str):
        raw_langs = raw_langs.split(",")
    languages = [str(x).strip() for x in (raw_langs or DEFAULT_LANGUAGES) if str(x).strip()]
    try:
        max_chars = int(args.get("max_chars") or DEFAULT_MAX_CHARS)
    except (TypeError, ValueError):
        max_chars = DEFAULT_MAX_CHARS
    max_chars = max(MIN_MAX_CHARS, min(max_chars, HARD_MAX_CHARS))
    timestamps = bool(args.get("timestamps"))

    info = (meta or oembed)(vid)
    transcript = fetch_transcript(vid, languages or list(DEFAULT_LANGUAGES), api=api)
    text, truncated, reached = render(transcript.segments, timestamps=timestamps,
                                      max_chars=max_chars)
    last = transcript.segments[-1] if transcript.segments else None
    length = float(last["start"]) + float(last.get("duration") or 0.0) if last else 0.0
    result: dict[str, Any] = {
        "video_id": vid,
        "url": f"https://www.youtube.com/watch?v={vid}",
        "title": info.get("title", ""),
        "channel": info.get("channel", ""),
        "length": clock(length),
        "language": transcript.language,
        "auto_generated": transcript.generated,
        "chars": len(text),
        "truncated": truncated,
        "transcript": text,
    }
    if truncated:
        result["note"] = (f"Transcript cut at {clock(reached)} of {clock(length)} to stay under "
                          f"{max_chars} characters. Say so if it matters for the answer.")
    return result
