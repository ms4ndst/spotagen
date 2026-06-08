"""Typed helpers over `spotipy` — artist search, top tracks, catalogue search."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import spotipy

from ..settings.schema import Settings
from .auth import get_access_token


@dataclass(frozen=True)
class ArtistInfo:
    id: str
    name: str


class SpotifyClient:
    """Thin wrapper around `spotipy.Spotify` with the calls spotagen needs."""

    def __init__(self, sp: spotipy.Spotify) -> None:
        self._sp = sp
        self._me_id: str | None = None

    @classmethod
    def from_settings(cls, settings: Settings) -> SpotifyClient:
        token = get_access_token(settings)
        sp = spotipy.Spotify(auth=token, requests_timeout=20)
        return cls(sp)

    # ----- user
    def me_id(self) -> str:
        if self._me_id is None:
            me = self._sp.current_user()
            self._me_id = str(me["id"])
        return self._me_id

    # ----- artist / catalogue
    def search_artist(self, name: str) -> ArtistInfo | None:
        result = self._sp.search(q=f'artist:"{name}"', type="artist", limit=1)
        items = result.get("artists", {}).get("items", []) if result else []
        if not items:
            # Try unquoted fallback for free-form names.
            result = self._sp.search(q=name, type="artist", limit=1)
            items = result.get("artists", {}).get("items", []) if result else []
        if not items:
            return None
        return ArtistInfo(id=str(items[0]["id"]), name=str(items[0]["name"]))

    def top_tracks(self, artist_id: str, market: str = "from_token") -> list[dict[str, Any]]:
        try:
            result = self._sp.artist_top_tracks(artist_id, country=market)
        except spotipy.SpotifyException:
            # `from_token` requires user-read-private; fall back to US.
            result = self._sp.artist_top_tracks(artist_id, country="US")
        return list(result.get("tracks", []) if result else [])

    def search_tracks(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        result = self._sp.search(q=query, type="track", limit=limit)
        return list(result.get("tracks", {}).get("items", []) if result else [])

    def followed_artists(self) -> list[ArtistInfo]:
        """Return every artist the authenticated user follows.

        Paginates the /me/following?type=artist cursor-based endpoint
        (50 artists per page). Requires the `user-follow-read` scope.
        """
        artists: list[ArtistInfo] = []
        after: str | None = None
        while True:
            response = self._sp.current_user_followed_artists(limit=50, after=after)
            block = (response or {}).get("artists", {})
            items = block.get("items", []) or []
            for item in items:
                artists.append(
                    ArtistInfo(id=str(item["id"]), name=str(item["name"]))
                )
            cursors = block.get("cursors") or {}
            next_after = cursors.get("after")
            if not next_after or not items:
                break
            after = str(next_after)
        return artists

    # ----- playlist primitives — used by playlist.py
    def create_user_playlist(
        self, user_id: str, name: str, description: str, public: bool
    ) -> dict[str, Any]:
        result = self._sp.user_playlist_create(
            user=user_id, name=name, public=public, description=description
        )
        return dict(result or {})

    def add_playlist_items(self, playlist_id: str, uris: list[str]) -> None:
        self._sp.playlist_add_items(playlist_id, uris)
