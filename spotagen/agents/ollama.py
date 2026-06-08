"""Ollama provider — direct REST via httpx, with graceful offline fallback."""
from __future__ import annotations

import httpx
from rich.console import Console

from .base import (
    SYSTEM_PROMPT,
    AgentParseError,
    AgentProvider,
    CuratedTrack,
    DiscoveryQuery,
    TrackCandidate,
    build_curate_prompt,
    build_discover_prompt,
    parse_curated_rows,
    parse_discovery_rows,
    parse_json_array,
    random_fallback_curate,
    random_fallback_discover,
)


class OllamaProvider(AgentProvider):
    name = "ollama"

    def __init__(
        self,
        base_url: str,
        model: str,
        console: Console | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._console = console
        self.available = self._probe()

    def _probe(self) -> bool:
        try:
            response = httpx.get(f"{self._base_url}/api/tags", timeout=2.0)
            return response.status_code == 200
        except (httpx.HTTPError, OSError):
            return False

    def _warn_offline(self) -> None:
        if self._console is not None:
            self._console.print(
                "[warning]⚠ Ollama unreachable — falling back to random selection[/warning]"
            )

    def _chat(self, user: str) -> str:
        payload = {
            "model": self._model,
            "stream": False,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user},
            ],
        }
        response = httpx.post(
            f"{self._base_url}/api/chat", json=payload, timeout=240.0
        )
        response.raise_for_status()
        data = response.json()
        return str(data.get("message", {}).get("content", ""))

    def curate(
        self,
        candidates: list[TrackCandidate],
        songs_per_artist: int,
        use_top_tracks: bool,
    ) -> list[CuratedTrack]:
        if not self.available:
            self._warn_offline()
            return random_fallback_curate(
                candidates,
                songs_per_artist,
                reason="Ollama offline — random selection",
            )
        prompt = build_curate_prompt(candidates, songs_per_artist, use_top_tracks)
        raw = self._chat(prompt)
        try:
            return parse_curated_rows(parse_json_array(raw))
        except AgentParseError:
            if self._console is not None:
                self._console.print(
                    "[warning]⚠ Ollama returned invalid JSON — random fallback.[/warning]"
                )
            return random_fallback_curate(
                candidates,
                songs_per_artist,
                reason="Ollama parse error — random selection",
            )

    def discover(
        self, artists: list[str], songs_per_artist: int
    ) -> list[DiscoveryQuery]:
        if not self.available:
            self._warn_offline()
            return random_fallback_discover(
                artists,
                songs_per_artist,
                reason="Ollama offline — random selection",
            )
        prompt = build_discover_prompt(artists, songs_per_artist)
        raw = self._chat(prompt)
        try:
            return parse_discovery_rows(parse_json_array(raw))
        except AgentParseError:
            if self._console is not None:
                self._console.print(
                    "[warning]⚠ Ollama returned invalid JSON — random fallback.[/warning]"
                )
            return random_fallback_discover(
                artists,
                songs_per_artist,
                reason="Ollama parse error — random selection",
            )
