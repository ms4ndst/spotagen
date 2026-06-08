"""Mistral provider — direct REST via httpx (no mistralai SDK dependency).

The Mistral chat-completions endpoint is OpenAI-compatible, so the request and
response shapes mirror the OpenAI provider exactly. Avoiding the `mistralai`
SDK keeps spotagen free of its (very aggressive) opentelemetry pins.
"""
from __future__ import annotations

from typing import Any

import httpx

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

MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"


class MistralProvider(AgentProvider):
    name = "mistral"

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = MISTRAL_API_URL,
    ) -> None:
        if not api_key:
            raise ValueError(
                "Mistral API key not set — run `spotagen setup` or edit config.toml."
            )
        self._api_key = api_key
        self._model = model
        self._url = base_url

    def _chat(self, user: str) -> str:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user},
            ],
            "temperature": 0.7,
        }
        response = httpx.post(
            self._url, headers=headers, json=payload, timeout=180.0
        )
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        choices = data.get("choices") or []
        if not choices:
            return ""
        message = choices[0].get("message") or {}
        content = message.get("content", "")
        return str(content)

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
