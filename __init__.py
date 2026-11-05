"""YouTube transcript: one tool call for a video's metadata and transcript.

Hermes imports this file as ``hermes_plugins.youtube_transcript`` and calls ``register(ctx)``
once at startup. Feature code lives in the ``youtube_transcript`` subpackage, imported
relatively so it never clashes with Hermes' own top-level packages.
"""

from __future__ import annotations

from typing import Any


def register(ctx: Any) -> None:
    """Plugin entry point: the youtube_transcript tool and a prompt section that routes to it."""
    # Imported here, not at module level: pytest imports this file as a plain module,
    # where relative imports have no parent package.
    from .youtube_transcript import tools

    ctx.register_tool(
        name=tools.SCHEMA["name"],
        toolset=tools.TOOLSET,
        schema=tools.SCHEMA,
        handler=tools.youtube_transcript,
        check_fn=tools.available,
        description="Fetch a YouTube video's metadata and transcript.",
        emoji="📺",
    )
    ctx.register_system_prompt_section("youtube-transcript", tools.PROMPT_SECTION)
