"""OpenAI provider."""
from __future__ import annotations

from openai import OpenAI

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


class OpenAIProvider(AgentProvider):
    name = "openai"

    def __init__(self, api_key: str, model: str) -> None:
        if not api_key:
            raise ValueError(
                "OpenAI API key not set — run `spotagen setup` or edit config.toml."
            )
        self._client = OpenAI(api_key=api_key)
        self._model = model

    def _chat(self, user: str) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user},
            ],
        )
        content = response.choices[0].message.content or ""
        return content

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
