"""Anthropic (Claude) provider."""
from __future__ import annotations

import anthropic

from .base import (
    SYSTEM_PROMPT,
    AgentProvider,
    CuratedTrack,
    DiscoveryQuery,
    TrackCandidate,
    build_curate_prompt,
    build_discover_prompt,
    parse_curated_rows,
    parse_discovery_rows,
    parse_json_array,
)


class AnthropicProvider(AgentProvider):
    name = "claude"

    def __init__(self, api_key: str, model: str) -> None:
        if not api_key:
            raise ValueError(
                "Anthropic API key not set — run `spotagen setup` or edit config.toml."
            )
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def _chat(self, user: str) -> str:
        message = self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(
            block.text  # type: ignore[union-attr]
            for block in message.content
            if getattr(block, "type", None) == "text"
        )

    def curate(
        self,
        candidates: list[TrackCandidate],
        songs_per_artist: int,
        use_top_tracks: bool,
    ) -> list[CuratedTrack]:
        prompt = build_curate_prompt(candidates, songs_per_artist, use_top_tracks)
        return parse_curated_rows(parse_json_array(self._chat(prompt)))

    def discover(
        self, artists: list[str], songs_per_artist: int
    ) -> list[DiscoveryQuery]:
        prompt = build_discover_prompt(artists, songs_per_artist)
        return parse_discovery_rows(parse_json_array(self._chat(prompt)))
