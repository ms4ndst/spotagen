"""Main orchestration:

    load artists → fetch candidates → agent (curate or discover)
    → validate ids → shuffle → create playlist → record history → print summary

All Spotify and AI calls are wrapped in `rich.Progress` so the terminal never
appears to hang on a synchronous network call.
"""
from __future__ import annotations

import datetime as _dt
import random
import sys
from typing import Optional

import tomli_w
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.rule import Rule

from .agents.base import (
    AgentParseError,
    AgentProvider,
    CuratedTrack,
    DiscoveryQuery,
    TrackCandidate,
    random_fallback_curate,
    random_fallback_discover,
)
from .config import history_path, load_artists, load_settings
from .settings.schema import Flavor, Provider, Settings
from .spotify.client import ArtistInfo, SpotifyClient
from .spotify.playlist import add_tracks, create_playlist
from .theme import banner, build_rich_theme

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib  # noqa: F401 — runtime fallback for Python 3.10


# How many artists to send the AI agent per request. Keeps prompts small
# enough to finish well under provider read timeouts even on slow models
# like Mistral, and turns one big single-point-of-failure call into N
# smaller calls where partial results survive a single chunk failure.
ARTIST_CHUNK_SIZE = 8


# --------------------------------------------------------------------------- #
# Provider factory
# --------------------------------------------------------------------------- #


def _make_provider(settings: Settings, console: Console) -> AgentProvider:
    provider = settings.ai.provider
    if provider == Provider.CLAUDE:
        from .agents.anthropic_provider import AnthropicProvider

        return AnthropicProvider(
            settings.ai.claude.api_key, settings.ai.claude.model
        )
    if provider == Provider.MISTRAL:
        from .agents.mistral import MistralProvider

        return MistralProvider(
            settings.ai.mistral.api_key, settings.ai.mistral.model
        )
    if provider == Provider.OPENAI:
        from .agents.openai_provider import OpenAIProvider

        return OpenAIProvider(
            settings.ai.openai.api_key, settings.ai.openai.model
        )
    if provider == Provider.OLLAMA:
        from .agents.ollama import OllamaProvider

        return OllamaProvider(
            settings.ai.ollama.base_url,
            settings.ai.ollama.model,
            console=console,
        )
    raise ValueError(f"Unsupported provider: {provider}")


def _provider_model(settings: Settings) -> str:
    return {
        Provider.CLAUDE: settings.ai.claude.model,
        Provider.MISTRAL: settings.ai.mistral.model,
        Provider.OPENAI: settings.ai.openai.model,
        Provider.OLLAMA: settings.ai.ollama.model,
    }[settings.ai.provider]


# --------------------------------------------------------------------------- #
# Main entry
# --------------------------------------------------------------------------- #


def run_generate(
    count: Optional[int] = None,
    force_discovery: bool = False,
    exclude_top_tracks: bool = False,
    from_spotify: bool = False,
    max_artists: Optional[int] = None,
    all_artists: bool = False,
    provider_override: Optional[Provider] = None,
    theme_override: Optional[Flavor] = None,
    dry_run: bool = False,
) -> None:
    settings = load_settings()
    if provider_override is not None:
        settings.ai.provider = provider_override
    if theme_override is not None:
        settings.ui.flavor = theme_override

    n = count if count is not None else settings.playlist.total_songs_per_artist
    # `exclude_top_tracks` implies discovery — the candidate pool would otherwise
    # be entirely chart hits and we'd blacklist everything.
    blacklist_top_tracks = exclude_top_tracks or settings.playlist.exclude_top_tracks
    use_top_tracks = (
        not force_discovery
        and not blacklist_top_tracks
        and settings.playlist.use_top_tracks
    )
    pull_followed = from_spotify or settings.playlist.use_followed_artists

    console = Console(theme=build_rich_theme(settings.ui.flavor.value, settings.ui.accent.value))
    banner(console)

    artists = load_artists()
    # When followed-artists mode is on we'll merge in Spotify follows below
    # — so an empty local artists.toml isn't fatal in that case.
    if not artists and not pull_followed:
        console.print(
            "[error]✗ No artists configured.[/error] "
            "Add some with [info]spotagen artists add NAME[/info] "
            "or pass [info]--from-spotify[/info] to use your follows."
        )
        return

    console.print(
        f" [label]Provider[/label]   "
        f"[provider]{settings.ai.provider.value} · {_provider_model(settings)}[/provider]"
    )
    console.print(
        f" [label]Artists[/label]    "
        f"[body]{len(artists)} loaded · {n} tracks each[/body]\n"
    )

    # ----- build agent + Spotify client
    try:
        agent = _make_provider(settings, console)
    except (ValueError, RuntimeError) as exc:
        console.print(f"[error]✗ AI provider unavailable: {exc}[/error]")
        return

    try:
        spotify = SpotifyClient.from_settings(settings)
    except Exception as exc:  # noqa: BLE001
        console.print(
            f"[error]✗ Spotify auth failed[/error] — {exc}\n"
            "[muted]Run `spotagen setup` to reconfigure.[/muted]"
        )
        return

    # ----- pull followed artists from Spotify if requested
    followed: list[ArtistInfo] = []
    if pull_followed:
        try:
            followed = spotify.followed_artists()
        except Exception as exc:  # noqa: BLE001
            console.print(
                f"[warning]⚠ Could not fetch followed artists: {exc}[/warning]\n"
                "[muted]Continuing with artists.toml only.[/muted]"
            )
        else:
            console.print(
                f" [label]Followed[/label]   "
                f"[body]{len(followed)} pulled from Spotify[/body]\n"
            )

    if not artists and not followed:
        console.print(
            "[error]✗ No artists to generate from.[/error] "
            "[muted](artists.toml is empty and you don't follow anyone yet)[/muted]"
        )
        return

    # ----- cap artist count for this run
    # Resolve effective cap: --all-artists overrides, --max-artists overrides config,
    # otherwise use playlist.max_artists_per_run (0 disables the cap).
    if all_artists:
        cap = 0
    elif max_artists is not None:
        cap = max(0, max_artists)
    else:
        cap = max(0, settings.playlist.max_artists_per_run)

    # The cap is applied to BOTH the followed list and the artists.toml names
    # together — we union first, then sample, so the user gets a mix from both
    # sources rather than all-of-one-source-then-truncate.
    if cap and len(followed) + len(artists) > cap:
        all_inputs: list[tuple[str, ArtistInfo | None]] = (
            [(info.name, info) for info in followed]
            + [(name, None) for name in artists if name.lower()
               not in {f.name.lower() for f in followed}]
        )
        sampled = random.sample(all_inputs, cap)
        followed = [info for _, info in sampled if info is not None]
        artists = [name for name, info in sampled if info is None]
        console.print(
            f" [label]Sampling[/label]   "
            f"[body]{cap} artists drawn at random from your "
            f"{len(all_inputs)} total · pass [info]--all-artists[/info] to use everything[/body]\n"
        )

    # ----- resolve artists to canonical IDs
    # Followed artists already carry their Spotify ID — only the artists.toml
    # names need a search-API resolution. Followed entries take precedence
    # when there's a case-insensitive name overlap (their IDs are guaranteed).
    console.print(Rule("Resolving artists", style="border"))
    resolved: list[ArtistInfo] = list(followed)
    followed_lower = {info.name.lower() for info in followed}
    pending = [name for name in artists if name.lower() not in followed_lower]

    if pending:
        failed_lookups = 0
        with _spinner(console, "Looking up artists") as progress:
            task = progress.add_task("", total=len(pending))
            for name in pending:
                try:
                    info = spotify.search_artist(name)
                except Exception:  # noqa: BLE001
                    # Transient Spotify error (rate limit, connection reset) —
                    # skip this artist rather than killing the whole run.
                    failed_lookups += 1
                    progress.advance(task)
                    continue
                if info is None:
                    console.print(
                        f"[warning]⚠ Artist not found on Spotify: {name}[/warning]"
                    )
                else:
                    resolved.append(info)
                progress.advance(task)
        if failed_lookups:
            console.print(
                f"[warning]⚠ {failed_lookups} artist lookup(s) failed "
                "(likely rate-limited) and were skipped.[/warning]"
            )

    if not resolved:
        console.print("[error]✗ No artists could be resolved.[/error]")
        return

    # ----- fetch candidates
    if use_top_tracks:
        candidates = _fetch_top_tracks(spotify, resolved, console)
    else:
        candidates = _fetch_via_discovery(spotify, agent, resolved, n, console)
        if blacklist_top_tracks:
            candidates = _apply_top_tracks_blacklist(spotify, resolved, candidates, console)

    if not candidates:
        console.print("[error]✗ No candidate tracks found.[/error]")
        return

    # ----- curate
    console.print(Rule("Agent: curation pass", style="border"))
    curated = _curate_chunked(agent, candidates, n, use_top_tracks, console)

    # ----- filter unknown IDs (safety net)
    valid_ids = {c.track_id for c in candidates}
    filtered_count = sum(1 for c in curated if c.track_id not in valid_ids)
    curated = [c for c in curated if c.track_id in valid_ids]
    if filtered_count:
        console.print(
            f"[muted]Filtered {filtered_count} unknown track id(s) from agent response.[/muted]"
        )

    # ----- reasoning panel
    reasons = [c.reason for c in curated if c.reason]
    if reasons:
        body = "\n".join(f"[muted]· {r}[/muted]" for r in reasons[:8])
        console.print()
        console.print(Panel(body, title="[subheader]Reasoning[/subheader]", border_style="border"))

    # ----- shuffle
    if settings.playlist.randomize_order:
        random.shuffle(curated)

    # ----- dry run exit
    if dry_run:
        console.print(Rule("Dry run — tracklist", style="border"))
        for cur in curated:
            console.print(
                f"  [artist]{cur.artist}[/artist] — [track]{cur.track_name}[/track]"
            )
        console.print(f"\n[success]✓ {len(curated)} tracks (dry-run, no playlist created)[/success]")
        return

    # ----- create + populate playlist
    now = _dt.datetime.now()
    title = (
        f"{settings.playlist.playlist_name_prefix} · "
        f"{now.strftime('%b %Y')} · {len(curated)} tracks"
    )
    try:
        playlist_id, url = create_playlist(
            spotify, title, description="Generated by spotagen", public=False
        )
        add_tracks(spotify, playlist_id, [c.track_id for c in curated])
    except Exception as exc:  # noqa: BLE001
        console.print(
            f"[error]✗ Playlist creation failed: {exc}[/error]\n"
            "[muted]Check your Spotify scopes and that the account isn't read-only.[/muted]"
        )
        return

    _append_history(title, url, len(curated))

    console.print()
    console.print("[success]✓  Playlist created[/success]")
    console.print(f"    [body]{title}[/body]")
    console.print(f"    [info underline]{url}[/info underline]")


# --------------------------------------------------------------------------- #
# Candidate fetching
# --------------------------------------------------------------------------- #


def _fetch_top_tracks(
    spotify: SpotifyClient,
    resolved: list[ArtistInfo],
    console: Console,
) -> list[TrackCandidate]:
    console.print(Rule("Fetching artist data", style="border"))
    candidates: list[TrackCandidate] = []
    with Progress(
        TextColumn("  [artist]{task.fields[artist]:<24}[/artist]"),
        BarColumn(complete_style="accent", finished_style="success"),
        TextColumn("[muted]{task.fields[label]}[/muted]"),
        console=console,
        transient=False,
    ) as progress:
        tasks = [
            progress.add_task("", total=1, artist=info.name, label="…")
            for info in resolved
        ]
        for info, task in zip(resolved, tasks):
            try:
                tracks = spotify.top_tracks(info.id)
            except Exception:  # noqa: BLE001
                progress.update(task, completed=1, label="[warning]error[/warning]")
                continue
            for track in tracks:
                candidates.append(
                    TrackCandidate(
                        artist=info.name,
                        track_id=str(track["id"]),
                        track_name=str(track["name"]),
                        popularity=int(track.get("popularity", 0)),
                        is_top_track=True,
                    )
                )
            progress.update(
                task,
                completed=1,
                label=f"{len(tracks)} candidates",
            )
    return candidates


def _fetch_via_discovery(
    spotify: SpotifyClient,
    agent: AgentProvider,
    resolved: list[ArtistInfo],
    songs_per_artist: int,
    console: Console,
) -> list[TrackCandidate]:
    console.print(Rule("Agent: discovery pass", style="border"))
    names = [info.name for info in resolved]
    queries = _discover_chunked(agent, names, songs_per_artist, console)

    candidates: list[TrackCandidate] = []
    seen: set[str] = set()
    failed_queries = 0
    with Progress(
        SpinnerColumn(style="accent"),
        TextColumn("[muted]{task.description}[/muted]"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task(
            f"Searching Spotify ({len(queries)} queries)",
            total=None,
        )
        for query in queries:
            try:
                tracks = spotify.search_tracks(query.search_query, limit=10)
            except Exception:  # noqa: BLE001
                # Spotify rate limit, connection reset, transient 5xx — skip
                # this one query rather than aborting the entire discovery
                # phase. We summarise the count at the end.
                failed_queries += 1
                continue
            for track in tracks:
                if track["id"] in seen:
                    continue
                if not any(
                    artist["name"].lower() == query.artist.lower()
                    for artist in track.get("artists", [])
                ):
                    continue
                seen.add(track["id"])
                candidates.append(
                    TrackCandidate(
                        artist=query.artist,
                        track_id=str(track["id"]),
                        track_name=str(track["name"]),
                        popularity=int(track.get("popularity", 0)),
                        is_top_track=False,
                    )
                )
        progress.update(task, completed=1)

    if failed_queries:
        console.print(
            f"[warning]⚠ {failed_queries} of {len(queries)} Spotify searches failed "
            "(likely rate-limited) — those queries' tracks are missing from the pool.[/warning]"
        )

    by_artist: dict[str, int] = {}
    for cand in candidates:
        by_artist[cand.artist] = by_artist.get(cand.artist, 0) + 1
    for info in resolved:
        console.print(
            f"  [artist]{info.name:<24}[/artist] "
            f"[muted]{by_artist.get(info.name, 0)} candidates[/muted]"
        )
    return candidates


# --------------------------------------------------------------------------- #
# Top-tracks blacklist — used when --exclude-top-tracks is set
# --------------------------------------------------------------------------- #


def _apply_top_tracks_blacklist(
    spotify: SpotifyClient,
    resolved: list[ArtistInfo],
    candidates: list[TrackCandidate],
    console: Console,
) -> list[TrackCandidate]:
    """Drop any candidate whose track_id is in the artist's Spotify top tracks."""
    console.print(Rule("Excluding chart-topper tracks", style="border"))
    blacklist: set[str] = set()
    for info in resolved:
        try:
            tracks = spotify.top_tracks(info.id)
        except Exception:  # noqa: BLE001
            continue
        for track in tracks:
            tid = track.get("id")
            if tid:
                blacklist.add(str(tid))
    if not blacklist:
        console.print("[muted]No top tracks returned — nothing to blacklist.[/muted]")
        return candidates
    filtered = [c for c in candidates if c.track_id not in blacklist]
    dropped = len(candidates) - len(filtered)
    console.print(
        f"  [muted]Blacklisted {len(blacklist)} top-track id(s) · "
        f"dropped {dropped} candidate(s)[/muted]"
    )
    return filtered


# --------------------------------------------------------------------------- #
# Chunked wrappers — split the artist list into ARTIST_CHUNK_SIZE batches
# before calling the agent. Each call stays small enough to finish well
# under the provider's read timeout, and one chunk failing falls back to
# a random selection FOR THAT CHUNK ONLY — the rest still go through the
# real agent.
# --------------------------------------------------------------------------- #


def _curate_chunked(
    agent: AgentProvider,
    candidates: list[TrackCandidate],
    n: int,
    use_top_tracks: bool,
    console: Console,
) -> list[CuratedTrack]:
    # Group candidates by artist so each chunk is a self-contained batch.
    by_artist: dict[str, list[TrackCandidate]] = {}
    for cand in candidates:
        by_artist.setdefault(cand.artist, []).append(cand)
    artist_names = list(by_artist.keys())
    chunks = [
        artist_names[i : i + ARTIST_CHUNK_SIZE]
        for i in range(0, len(artist_names), ARTIST_CHUNK_SIZE)
    ]
    if len(chunks) > 1:
        console.print(
            f"[muted]Curating in {len(chunks)} chunks of up to "
            f"{ARTIST_CHUNK_SIZE} artists…[/muted]"
        )
    out: list[CuratedTrack] = []
    for i, chunk_names in enumerate(chunks, 1):
        if len(chunks) > 1:
            console.print(
                f"  [muted]Chunk {i}/{len(chunks)} · {len(chunk_names)} artist(s)[/muted]"
            )
        chunk_candidates = [
            cand for name in chunk_names for cand in by_artist[name]
        ]
        out.extend(
            _curate_with_retry(agent, chunk_candidates, n, use_top_tracks, console)
        )
    return out


def _discover_chunked(
    agent: AgentProvider,
    artists: list[str],
    n: int,
    console: Console,
) -> list[DiscoveryQuery]:
    chunks = [
        artists[i : i + ARTIST_CHUNK_SIZE]
        for i in range(0, len(artists), ARTIST_CHUNK_SIZE)
    ]
    if len(chunks) > 1:
        console.print(
            f"[muted]Discovery in {len(chunks)} chunks of up to "
            f"{ARTIST_CHUNK_SIZE} artists…[/muted]"
        )
    out: list[DiscoveryQuery] = []
    for i, chunk in enumerate(chunks, 1):
        if len(chunks) > 1:
            console.print(
                f"  [muted]Chunk {i}/{len(chunks)} · {len(chunk)} artist(s)[/muted]"
            )
        out.extend(_discover_with_retry(agent, chunk, n, console))
    return out


# --------------------------------------------------------------------------- #
# Retry wrappers — apply the spec's "retry once, then random fallback" rule
# --------------------------------------------------------------------------- #


def _curate_with_retry(
    agent: AgentProvider,
    candidates: list[TrackCandidate],
    n: int,
    use_top_tracks: bool,
    console: Console,
) -> list[CuratedTrack]:
    last_err: Exception | None = None
    for attempt in (1, 2):
        try:
            return agent.curate(candidates, n, use_top_tracks)
        except AgentParseError as exc:
            last_err = exc
            console.print(
                f"[warning]⚠ Agent returned invalid JSON "
                f"(attempt {attempt}/2): {exc}[/warning]"
            )
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            console.print(
                f"[warning]⚠ {agent.name} error (attempt {attempt}/2): {exc}[/warning]"
            )
    console.print(
        f"[warning]Falling back to random selection ({last_err}).[/warning]"
    )
    return random_fallback_curate(candidates, n, reason="Agent failed — random selection")


def _discover_with_retry(
    agent: AgentProvider,
    artists: list[str],
    n: int,
    console: Console,
) -> list[DiscoveryQuery]:
    last_err: Exception | None = None
    for attempt in (1, 2):
        try:
            return agent.discover(artists, n)
        except AgentParseError as exc:
            last_err = exc
            console.print(
                f"[warning]⚠ Discovery returned invalid JSON "
                f"(attempt {attempt}/2): {exc}[/warning]"
            )
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            console.print(
                f"[warning]⚠ {agent.name} discovery error (attempt {attempt}/2): {exc}[/warning]"
            )
    console.print(
        f"[warning]Falling back to random discovery angles ({last_err}).[/warning]"
    )
    return random_fallback_discover(artists, n)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _spinner(console: Console, label: str) -> Progress:
    return Progress(
        SpinnerColumn(style="accent"),
        TextColumn("[muted]{task.description}[/muted]"),
        MofNCompleteColumn(),
        console=console,
        transient=True,
    )


def _append_history(title: str, url: str, count: int) -> None:
    p = history_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, object]] = []
    if p.exists():
        with p.open("rb") as f:
            data = tomllib.load(f)
        raw = data.get("entries", [])
        if isinstance(raw, list):
            entries = [e for e in raw if isinstance(e, dict)]
    entries.append(
        {
            "title": title,
            "url": url,
            "count": count,
            "created_at": _dt.datetime.now().isoformat(timespec="seconds"),
        }
    )
    entries = entries[-100:]
    with p.open("wb") as f:
        tomli_w.dump({"entries": entries}, f)
