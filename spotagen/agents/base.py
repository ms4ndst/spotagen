"""Abstract AgentProvider contract + shared prompt building, JSON parsing,
and a deterministic random fallback used when an agent fails irrecoverably.
"""
from __future__ import annotations

import json
import random
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

SYSTEM_PROMPT = """You are a music curation agent with deep knowledge of artist discographies.

Your job has two modes:

MODE 1 — CURATE
Given a list of candidate tracks with metadata, select the best
{songs_per_artist} tracks per artist for a cohesive, randomised playlist.
When use_top_tracks=false, actively avoid obvious chart hits and prefer
B-sides, deep cuts, live versions, and collaborations.
Return ONLY valid Spotify track IDs from the candidates list.
Never invent track IDs.

Respond with a JSON array — no preamble, no markdown fences:
[{"artist":"...","track_id":"...","track_name":"...","reason":"..."}]

MODE 2 — DISCOVER
Given a list of artist names and a songs_per_artist count, generate
Spotify search queries that will surface lesser-known tracks.
Think: "Radiohead BBC session", "Portishead live concert", "Thom Yorke feat".

Respond with a JSON array:
[{"artist":"...","search_query":"...","rationale":"..."}]
"""


# --------------------------------------------------------------------------- #
# Data classes
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class TrackCandidate:
    artist: str
    track_id: str
    track_name: str
    popularity: int
    is_top_track: bool


@dataclass(frozen=True)
class CuratedTrack:
    artist: str
    track_id: str
    track_name: str
    reason: str  # one sentence, shown in Reasoning panel


@dataclass(frozen=True)
class DiscoveryQuery:
    artist: str
    search_query: str
    rationale: str


class AgentParseError(RuntimeError):
    """Raised when an agent's response cannot be parsed as JSON."""


# --------------------------------------------------------------------------- #
# Abstract provider
# --------------------------------------------------------------------------- #


class AgentProvider(ABC):
    name: str = "base"

    @abstractmethod
    def curate(
        self,
        candidates: list[TrackCandidate],
        songs_per_artist: int,
        use_top_tracks: bool,
    ) -> list[CuratedTrack]:
        """Select `songs_per_artist` tracks per artist.

        Must return valid Spotify track_ids drawn from `candidates` — no
        hallucinated IDs. The orchestrator filters unknown IDs as a safety net.
        """

    @abstractmethod
    def discover(
        self,
        artists: list[str],
        songs_per_artist: int,
    ) -> list[DiscoveryQuery]:
        """Generate Spotify search queries that surface deep cuts / B-sides.

        Called BEFORE the catalogue fetch, when top-tracks mode is disabled.
        """


# --------------------------------------------------------------------------- #
# Prompt builders (shared by every provider)
# --------------------------------------------------------------------------- #


def build_curate_prompt(
    candidates: list[TrackCandidate],
    songs_per_artist: int,
    use_top_tracks: bool,
) -> str:
    by_artist: dict[str, list[TrackCandidate]] = {}
    for cand in candidates:
        by_artist.setdefault(cand.artist, []).append(cand)
    lines = [
        "MODE: CURATE",
        f"songs_per_artist: {songs_per_artist}",
        f"use_top_tracks: {str(use_top_tracks).lower()}",
        "",
        "Candidates (id  popularity  name):",
    ]
    for artist, tracks in by_artist.items():
        lines.append(f"  [{artist}]")
        for track in tracks:
            top_flag = " *top*" if track.is_top_track else ""
            lines.append(
                f"    {track.track_id}  pop={track.popularity:3d}{top_flag}  "
                f"{track.track_name!r}"
            )
    lines.append("")
    lines.append(
        f"Select exactly {songs_per_artist} tracks per artist. "
        "Return ONLY a JSON array — no markdown, no commentary."
    )
    return "\n".join(lines)


def build_discover_prompt(artists: list[str], songs_per_artist: int) -> str:
    queries_per_artist = max(3, songs_per_artist)
    return (
        "MODE: DISCOVER\n"
        f"songs_per_artist: {songs_per_artist}\n"
        f"Artists: {', '.join(artists)}\n"
        f"Generate at least {queries_per_artist} search queries per artist that "
        "surface B-sides, live recordings, BBC sessions, collaborations, demos, "
        "remixes, and rarities — NOT the obvious chart singles.\n"
        "Return ONLY a JSON array — no markdown, no commentary."
    )


# --------------------------------------------------------------------------- #
# Response parsing
# --------------------------------------------------------------------------- #

_FENCE_RE = re.compile(r"^```(?:json)?\s*|```\s*$", re.MULTILINE)

# Smart-quote / typographic-quote → straight-quote map. LLMs that quote source
# material (track titles, artist names) sometimes echo curly quotes from
# Wikipedia/Genius/etc., which json.loads refuses.
_SMART_QUOTES = str.maketrans(
    {
        "“": '"',  # left double curly
        "”": '"',  # right double curly
        "‘": "'",  # left single curly
        "’": "'",  # right single curly
        "′": "'",  # prime
        "″": '"',  # double prime
    }
)

# `,\s*]` or `,\s*}` — trailing comma, valid JS but invalid JSON.
_TRAILING_COMMA_RE = re.compile(r",(\s*[\]}])")

# Unquoted property name: `{artist: "X"}` or `,foo: 1}` — common Mistral slip.
_UNQUOTED_KEY_RE = re.compile(r'([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)(\s*:)')


def _repair_json(text: str) -> str:
    """Apply low-risk, idempotent fixes for the most common LLM JSON errors."""
    out = text.translate(_SMART_QUOTES)
    out = _TRAILING_COMMA_RE.sub(r"\1", out)
    out = _UNQUOTED_KEY_RE.sub(r'\1"\2"\3', out)
    return out


def _salvage_objects(text: str) -> list[dict[str, Any]]:
    """Last-resort: walk the text top-level, parse each `{...}` block on its
    own, and skip the ones that still fail. One malformed object no longer
    invalidates the surrounding array.
    """
    items: list[dict[str, Any]] = []
    depth = 0
    start_idx = -1
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start_idx = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start_idx >= 0:
                chunk = text[start_idx : i + 1]
                obj: Any = None
                for candidate in (chunk, _repair_json(chunk)):
                    try:
                        obj = json.loads(candidate)
                        break
                    except json.JSONDecodeError:
                        continue
                if isinstance(obj, dict):
                    items.append(obj)
                start_idx = -1
    return items


def parse_json_array(text: str) -> list[dict[str, Any]]:
    """Extract a JSON array from a model response, tolerating fences, prose,
    and common LLM JSON quirks (smart quotes, trailing commas, unquoted keys).

    Raises:
        AgentParseError: if no valid JSON array can be recovered even after
            repair + per-object salvage.
    """
    stripped = _FENCE_RE.sub("", text.strip()).strip()
    start = stripped.find("[")
    end = stripped.rfind("]")
    if start == -1 or end == -1 or end < start:
        raise AgentParseError(f"No JSON array found in response: {text[:300]!r}")
    raw = stripped[start : end + 1]

    # Path 1: strict parse — works for well-formed responses.
    try:
        data: Any = json.loads(raw)
    except json.JSONDecodeError:
        # Path 2: apply low-risk repairs (smart quotes, trailing commas,
        # unquoted keys) and re-parse.
        try:
            data = json.loads(_repair_json(raw))
        except json.JSONDecodeError as exc:
            # Path 3: salvage individual top-level `{...}` objects so one bad
            # entry doesn't lose the whole chunk's worth of work.
            salvaged = _salvage_objects(raw)
            if salvaged:
                return salvaged
            raise AgentParseError(f"Invalid JSON: {exc}") from exc

    if not isinstance(data, list):
        raise AgentParseError("Expected a JSON array at the top level.")
    return [item for item in data if isinstance(item, dict)]


def parse_curated_rows(rows: list[dict[str, Any]]) -> list[CuratedTrack]:
    out: list[CuratedTrack] = []
    for row in rows:
        try:
            out.append(
                CuratedTrack(
                    artist=str(row["artist"]),
                    track_id=str(row["track_id"]),
                    track_name=str(row.get("track_name", "")),
                    reason=str(row.get("reason", ""))[:240],
                )
            )
        except KeyError as exc:
            raise AgentParseError(f"Missing key in curated row: {exc}") from exc
    return out


def parse_discovery_rows(rows: list[dict[str, Any]]) -> list[DiscoveryQuery]:
    out: list[DiscoveryQuery] = []
    for row in rows:
        try:
            out.append(
                DiscoveryQuery(
                    artist=str(row["artist"]),
                    search_query=str(row["search_query"]),
                    rationale=str(row.get("rationale", ""))[:240],
                )
            )
        except KeyError as exc:
            raise AgentParseError(f"Missing key in discovery row: {exc}") from exc
    return out


# --------------------------------------------------------------------------- #
# Random fallback — used by curator on irrecoverable provider failure,
# and by Ollama when the local daemon is offline.
# --------------------------------------------------------------------------- #


def random_fallback_curate(
    candidates: list[TrackCandidate],
    songs_per_artist: int,
    reason: str = "Random selection (agent unavailable).",
) -> list[CuratedTrack]:
    rng = random.Random()
    by_artist: dict[str, list[TrackCandidate]] = {}
    for cand in candidates:
        by_artist.setdefault(cand.artist, []).append(cand)
    out: list[CuratedTrack] = []
    for artist, tracks in by_artist.items():
        picks = rng.sample(tracks, min(songs_per_artist, len(tracks)))
        for cand in picks:
            out.append(
                CuratedTrack(
                    artist=artist,
                    track_id=cand.track_id,
                    track_name=cand.track_name,
                    reason=reason,
                )
            )
    return out


def random_fallback_discover(
    artists: list[str],
    songs_per_artist: int,
    reason: str = "Random angles (agent unavailable).",
) -> list[DiscoveryQuery]:
    angles = [
        "live",
        "BBC session",
        "B-side",
        "rare",
        "feat",
        "deluxe edition",
        "demo",
        "remix",
        "acoustic",
        "EP",
    ]
    rng = random.Random()
    out: list[DiscoveryQuery] = []
    n = min(max(songs_per_artist, 3), len(angles))
    for artist in artists:
        for angle in rng.sample(angles, n):
            out.append(
                DiscoveryQuery(
                    artist=artist,
                    search_query=f"{artist} {angle}",
                    rationale=reason,
                )
            )
    return out
