import json
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from youtube_transcript import core, tools  # noqa: E402

VID = "lRe3iKyAXQA"


@pytest.mark.parametrize(
    "url",
    [
        VID,
        f"https://youtu.be/{VID}?is=FFZissXzslKi5FIl",
        f"https://www.youtube.com/watch?v={VID}&t=42s",
        f"youtube.com/watch?feature=share&v={VID}",
        f"https://m.youtube.com/shorts/{VID}",
        f"https://www.youtube.com/embed/{VID}?start=3",
        f"https://www.youtube.com/live/{VID}",
        f"https://music.youtube.com/watch?v={VID}",
    ],
)
def test_video_id_accepts_every_youtube_form(url):
    assert core.video_id(url) == VID


@pytest.mark.parametrize(
    "url",
    [
        "",
        "https://vimeo.com/123456789",
        f"https://evil.example/watch?v={VID}",
        f"https://youtube.com.evil.example/watch?v={VID}",
        "https://www.youtube.com/watch?v=short",
        "https://www.youtube.com/@channel",
    ],
)
def test_video_id_rejects_other_urls(url):
    with pytest.raises(core.InputError):
        core.video_id(url)


def test_clock():
    assert core.clock(0) == "0:00"
    assert core.clock(931.4) == "15:31"
    assert core.clock(3725) == "1:02:05"


SEGMENTS = [
    {"text": "hello  there", "start": 0.0, "duration": 2.0},
    {"text": "", "start": 2.0, "duration": 1.0},
    {"text": "general\nkenobi", "start": 65.0, "duration": 3.0},
]


def test_render_joins_and_normalizes_whitespace():
    text, cut, reached = core.render(SEGMENTS, timestamps=False, max_chars=1000)
    assert (text, cut, reached) == ("hello there general kenobi", False, 68.0)


def test_render_timestamps():
    text, _, _ = core.render(SEGMENTS, timestamps=True, max_chars=1000)
    assert text == "[0:00] hello there\n[1:05] general kenobi"


def test_render_cuts_on_a_segment_boundary():
    text, cut, reached = core.render(SEGMENTS, timestamps=False, max_chars=15)
    assert (text, cut, reached) == ("hello there", True, 2.0)


class FakeTranscript:
    def __init__(self, language_code, is_generated, segments):
        self.language_code = language_code
        self.is_generated = is_generated
        self._segments = segments

    def fetch(self):
        return [types.SimpleNamespace(**s) for s in self._segments]


class FakeListing:
    def __init__(self, transcripts):
        self._transcripts = transcripts

    def __iter__(self):
        return iter(self._transcripts)

    def find_transcript(self, languages):
        from youtube_transcript_api import NoTranscriptFound

        for lang in languages:
            for t in self._transcripts:
                if t.language_code == lang:
                    return t
        raise NoTranscriptFound(VID, languages, self)


class FakeApi:
    def __init__(self, transcripts=None, error=None):
        self.transcripts = transcripts or []
        self.error = error

    def list(self, vid):
        if self.error:
            raise self.error
        return FakeListing(self.transcripts)


def meta(vid):
    return {"title": "A title", "channel": "A channel"}


def test_run_prefers_english_then_spanish_by_default():
    api = FakeApi([FakeTranscript("es", False, SEGMENTS), FakeTranscript("en", True, SEGMENTS)])
    result = core.run({"url": VID}, api=api, meta=meta)
    assert result["language"] == "en"
    assert result["auto_generated"] is True
    assert result["title"] == "A title"
    assert result["length"] == "1:08"
    assert result["truncated"] is False
    assert "note" not in result


def test_run_uses_spanish_when_there_is_no_english():
    api = FakeApi([FakeTranscript("de", False, SEGMENTS), FakeTranscript("es", True, SEGMENTS)])
    assert core.run({"url": VID}, api=api, meta=meta)["language"] == "es"


def test_run_honours_explicit_languages():
    api = FakeApi([FakeTranscript("en", True, SEGMENTS), FakeTranscript("es", False, SEGMENTS)])
    assert core.run({"url": VID, "languages": ["es"]}, api=api, meta=meta)["language"] == "es"


def test_run_falls_back_to_a_manual_transcript_in_another_language():
    api = FakeApi([FakeTranscript("de", True, SEGMENTS), FakeTranscript("fr", False, SEGMENTS)])
    assert core.run({"url": VID}, api=api, meta=meta)["language"] == "fr"


def test_run_accepts_comma_separated_languages_and_clamps_max_chars():
    api = FakeApi([FakeTranscript("en", True, SEGMENTS)])
    result = core.run({"url": VID, "languages": "de, en", "max_chars": 5}, api=api, meta=meta)
    assert result["language"] == "en"
    assert result["truncated"] is False  # clamped up to MIN_MAX_CHARS


def test_run_notes_a_cut_transcript():
    long = [{"text": "word " * 100, "start": float(i), "duration": 1.0} for i in range(100)]
    api = FakeApi([FakeTranscript("en", True, long)])
    result = core.run({"url": VID, "max_chars": 2000}, api=api, meta=meta)
    assert result["truncated"] is True
    assert result["chars"] <= 2000
    assert "cut at" in result["note"]


def test_tool_returns_json_errors_instead_of_raising(monkeypatch):
    out = json.loads(tools.youtube_transcript({"url": "https://vimeo.com/1"}))
    assert "Not a YouTube URL" in out["error"]

    class TranscriptsDisabled(Exception):
        pass

    def boom(args):
        raise TranscriptsDisabled("x")

    monkeypatch.setattr(core, "run", boom)
    out = json.loads(tools.youtube_transcript({"url": VID}))
    assert out["error"].startswith("Subtitles are disabled")

    def other(args):
        raise RuntimeError("socket")

    monkeypatch.setattr(core, "run", other)
    assert json.loads(tools.youtube_transcript({"url": VID}))["error"].endswith("(RuntimeError).")


def test_register_adds_the_tool_and_the_prompt_section(monkeypatch):
    import importlib.util

    monkeypatch.setitem(sys.modules, "hermes_plugins", types.ModuleType("hermes_plugins"))
    spec = importlib.util.spec_from_file_location(
        "hermes_plugins.youtube_transcript", ROOT / "__init__.py",
        submodule_search_locations=[str(ROOT)],
    )
    plugin = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, plugin)
    spec.loader.exec_module(plugin)

    class Ctx:
        def __init__(self):
            self.tools, self.sections = [], []

        def register_tool(self, **kw):
            self.tools.append(kw["name"])

        def register_system_prompt_section(self, id, content):
            self.sections.append((id, content))

    ctx = Ctx()
    plugin.register(ctx)
    assert ctx.tools == ["youtube_transcript"]
    assert ctx.sections == [("youtube-transcript", tools.PROMPT_SECTION)]
    assert '"name": "youtube_transcript"' in tools.PROMPT_SECTION


def test_manifest_matches_registration():
    import yaml

    manifest = yaml.safe_load((ROOT / "plugin.yaml").read_text())
    assert manifest["provides_tools"] == [tools.SCHEMA["name"]]


def test_catalog_line_fits_the_tool_search_cap():
    first = tools.SCHEMA["description"].split(". ")[0] + "."
    assert first.startswith("youtube_transcript(url)")
    assert len(first) <= 80
