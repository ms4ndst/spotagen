"""spotagen Typer CLI.

Every command builds its `rich.Console` through `_themed_console()` so output
respects the user's configured Catppuccin flavor and accent. No `print()` calls
are made anywhere â€” all output flows through themed consoles.
"""
from __future__ import annotations

import os
import subprocess
import sys
from typing import Optional

import typer
from rich.console import Console
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.rule import Rule
from rich.table import Table

from .config import (
    artists_path,
    config_path,
    load_artists,
    load_settings,
    save_artists,
    save_settings,
)
from .settings.schema import Accent, Flavor, Provider, Settings
from .theme import VALID_ACCENTS, FLAVORS, banner, build_rich_theme

app = typer.Typer(
    name="spotagen",
    help="AI-powered Spotify playlist generator.",
    no_args_is_help=True,
    add_completion=False,
)

artists_app = typer.Typer(no_args_is_help=True, help="Manage your artist list.")
app.add_typer(artists_app, name="artists")


def _themed_console(settings: Optional[Settings] = None) -> Console:
    s = settings if settings is not None else load_settings()
    return Console(theme=build_rich_theme(s.ui.flavor.value, s.ui.accent.value))


# --------------------------------------------------------------------------- #
# setup
# --------------------------------------------------------------------------- #


def _prompt_provider(console: Console, s: Settings) -> None:
    provider_choice = Prompt.ask(
        "[label]AI provider[/label]",
        choices=[p.value for p in Provider],
        default=s.ai.provider.value,
        console=console,
    )
    s.ai.provider = Provider(provider_choice)

    if s.ai.provider == Provider.CLAUDE:
        s.ai.claude.api_key = Prompt.ask(
            "[label]Anthropic API key[/label]",
            default=s.ai.claude.api_key,
            console=console,
        )
        s.ai.claude.model = Prompt.ask(
            "[label]Model[/label]", default=s.ai.claude.model, console=console
        )
    elif s.ai.provider == Provider.MISTRAL:
        s.ai.mistral.api_key = Prompt.ask(
            "[label]Mistral API key[/label]",
            default=s.ai.mistral.api_key,
            console=console,
        )
        s.ai.mistral.model = Prompt.ask(
            "[label]Model[/label]", default=s.ai.mistral.model, console=console
        )
    elif s.ai.provider == Provider.OPENAI:
        s.ai.openai.api_key = Prompt.ask(
            "[label]OpenAI API key[/label]",
            default=s.ai.openai.api_key,
            console=console,
        )
        s.ai.openai.model = Prompt.ask(
            "[label]Model[/label]", default=s.ai.openai.model, console=console
        )
    elif s.ai.provider == Provider.OLLAMA:
        s.ai.ollama.base_url = Prompt.ask(
            "[label]Ollama base URL[/label]",
            default=s.ai.ollama.base_url,
            console=console,
        )
        s.ai.ollama.model = Prompt.ask(
            "[label]Model[/label]", default=s.ai.ollama.model, console=console
        )


@app.command()
def setup() -> None:
    """Interactive wizard: Spotify creds, AI provider, theme."""
    s = load_settings()
    console = _themed_console(s)
    banner(console)

    console.print(Rule("Spotify", style="border"))
    s.spotify.client_id = Prompt.ask(
        "[label]Spotify client_id[/label]",
        default=s.spotify.client_id,
        console=console,
    )
    s.spotify.client_secret = Prompt.ask(
        "[label]Spotify client_secret[/label] [muted](optional â€” PKCE is used)[/muted]",
        default=s.spotify.client_secret,
        console=console,
    )
    s.spotify.redirect_uri = Prompt.ask(
        "[label]Redirect URI[/label]",
        default=s.spotify.redirect_uri,
        console=console,
    )

    console.print(Rule("AI provider", style="border"))
    _prompt_provider(console, s)

    console.print(Rule("Theme", style="border"))
    flavor_choice = Prompt.ask(
        "[label]Flavor[/label]",
        choices=sorted(FLAVORS.keys()),
        default=s.ui.flavor.value,
        console=console,
    )
    s.ui.flavor = Flavor(flavor_choice)
    accent_choice = Prompt.ask(
        "[label]Accent[/label]",
        choices=sorted(VALID_ACCENTS),
        default=s.ui.accent.value,
        console=console,
    )
    s.ui.accent = Accent(accent_choice)

    console.print(Rule("Behaviour", style="border"))
    s.playlist.use_followed_artists = Confirm.ask(
        "[label]Auto-include the artists you follow on Spotify?[/label]",
        default=s.playlist.use_followed_artists,
        console=console,
    )
    s.playlist.use_top_tracks = Confirm.ask(
        "[label]Use top-tracks API for candidates?[/label] "
        "[muted](no = agent-driven catalogue discovery)[/muted]",
        default=s.playlist.use_top_tracks,
        console=console,
    )
    s.playlist.exclude_top_tracks = Confirm.ask(
        "[label]Hard-blacklist chart-topper tracks from every playlist?[/label]",
        default=s.playlist.exclude_top_tracks,
        console=console,
    )
    s.playlist.max_artists_per_run = IntPrompt.ask(
        "[label]Max artists per generate run[/label] "
        "[muted](0 = no cap; large lists hit Spotify rate limits)[/muted]",
        default=s.playlist.max_artists_per_run,
        console=console,
    )

    save_settings(s)
    new_console = _themed_console(s)
    new_console.print(f"[success]âœ“ Saved to {config_path()}[/success]")

    if Confirm.ask(
        "[label]Run Spotify auth now?[/label]",
        default=True,
        console=new_console,
    ):
        try:
            from .spotify.auth import get_access_token

            get_access_token(s)
            new_console.print("[success]âœ“ Spotify authenticated[/success]")
        except Exception as exc:  # noqa: BLE001
            new_console.print(
                f"[error]âœ— Spotify auth failed: {exc}[/error]\n"
                "[muted]Run `spotagen setup` again or check your client_id.[/muted]"
            )


# --------------------------------------------------------------------------- #
# config
# --------------------------------------------------------------------------- #


def _render_config_table(console: Console, s: Settings) -> None:
    surface0 = FLAVORS[s.ui.flavor.value].surface0
    table = Table(
        show_header=True,
        header_style="subheader",
        border_style="border",
        row_styles=["", f"on {surface0}"],
    )
    table.add_column("Key", style="label")
    table.add_column("Value", style="body")

    table.add_section()
    table.add_row("[subheader]spotify[/subheader]", "")
    table.add_row("  client_id", _mask(s.spotify.client_id))
    table.add_row("  client_secret", _mask(s.spotify.client_secret))
    table.add_row("  redirect_uri", s.spotify.redirect_uri)

    table.add_section()
    table.add_row("[subheader]playlist[/subheader]", "")
    table.add_row("  total_songs_per_artist", str(s.playlist.total_songs_per_artist))
    table.add_row("  use_top_tracks", str(s.playlist.use_top_tracks))
    table.add_row("  exclude_top_tracks", str(s.playlist.exclude_top_tracks))
    table.add_row("  use_followed_artists", str(s.playlist.use_followed_artists))
    table.add_row("  max_artists_per_run", str(s.playlist.max_artists_per_run))
    table.add_row("  randomize_order", str(s.playlist.randomize_order))
    table.add_row("  playlist_name_prefix", s.playlist.playlist_name_prefix)

    table.add_section()
    table.add_row("[subheader]ui[/subheader]", "")
    table.add_row("  flavor", s.ui.flavor.value)
    table.add_row("  accent", s.ui.accent.value)

    table.add_section()
    table.add_row("[subheader]ai[/subheader]", "")
    table.add_row("  provider", f"[provider]{s.ai.provider.value}[/provider]")
    table.add_row("  claude.model", s.ai.claude.model)
    table.add_row("  claude.api_key", _mask(s.ai.claude.api_key))
    table.add_row("  mistral.model", s.ai.mistral.model)
    table.add_row("  mistral.api_key", _mask(s.ai.mistral.api_key))
    table.add_row("  openai.model", s.ai.openai.model)
    table.add_row("  openai.api_key", _mask(s.ai.openai.api_key))
    table.add_row("  ollama.base_url", s.ai.ollama.base_url)
    table.add_row("  ollama.model", s.ai.ollama.model)

    console.print(table)


def _mask(value: str) -> str:
    if not value:
        return "[muted]<unset>[/muted]"
    if len(value) <= 8:
        return "[muted]****[/muted]"
    return f"[muted]{value[:4]}â€¦{value[-4:]}[/muted]"


@app.command()
def config(
    show: bool = typer.Option(
        False, "--show", help="Print current config as a table instead of opening an editor."
    ),
) -> None:
    """Open config in $EDITOR / notepad â€” or with --show, print it as a table."""
    s = load_settings()
    console = _themed_console(s)
    banner(console)

    if show:
        _render_config_table(console, s)
        return

    p = config_path()
    if not p.exists():
        save_settings(s)
    editor = os.environ.get("EDITOR") or (
        "notepad" if sys.platform == "win32" else "vi"
    )
    try:
        subprocess.call([editor, str(p)])
    except FileNotFoundError:
        console.print(
            f"[error]âœ— Editor {editor!r} not found.[/error] "
            f"Edit manually: [info]{p}[/info]"
        )


# --------------------------------------------------------------------------- #
# artists
# --------------------------------------------------------------------------- #


@artists_app.command("list")
def artists_list() -> None:
    """Print the current artist list."""
    s = load_settings()
    console = _themed_console(s)
    banner(console)
    artists = load_artists()
    if not artists:
        console.print(
            "[muted]No artists yet â€” add with `spotagen artists add NAME`.[/muted]"
        )
        return
    table = Table(
        show_header=True, header_style="subheader", border_style="border"
    )
    table.add_column("#", style="dim", justify="right")
    table.add_column("Artist", style="artist")
    for i, a in enumerate(artists, 1):
        table.add_row(str(i), a)
    console.print(table)


@artists_app.command("add")
def artists_add(
    name: str = typer.Argument(..., help="Artist name to add"),
    no_fuzzy: bool = typer.Option(
        False, "--no-fuzzy", help="Skip the Spotify fuzzy-match confirmation."
    ),
) -> None:
    """Append an artist (fuzzy-matched against Spotify when possible)."""
    s = load_settings()
    console = _themed_console(s)
    artists = load_artists()

    canonical = name
    if not no_fuzzy:
        try:
            from .spotify.client import SpotifyClient

            client = SpotifyClient.from_settings(s)
            match = client.search_artist(name)
            if match and match.name.lower() != name.lower():
                if Confirm.ask(
                    f"[label]Did you mean[/label] [artist]{match.name}[/artist]?",
                    default=True,
                    console=console,
                ):
                    canonical = match.name
            elif match:
                canonical = match.name
        except Exception as exc:  # noqa: BLE001
            console.print(
                f"[muted]Skipping Spotify match ({exc}). Adding raw name.[/muted]"
            )

    if canonical in artists:
        console.print(f"[warning]'{canonical}' is already in your list.[/warning]")
        return
    artists.append(canonical)
    save_artists(artists)
    console.print(f"[success]âœ“ Added [artist]{canonical}[/artist][/success]")


@artists_app.command("sync")
def artists_sync(
    replace: bool = typer.Option(
        False,
        "--replace",
        help="Replace artists.toml entirely instead of merging.",
    ),
) -> None:
    """Pull the artists you follow on Spotify and merge them into artists.toml."""
    s = load_settings()
    console = _themed_console(s)
    banner(console)

    try:
        from .spotify.client import SpotifyClient

        client = SpotifyClient.from_settings(s)
        followed = client.followed_artists()
    except Exception as exc:  # noqa: BLE001
        console.print(
            f"[error]âœ— Could not fetch followed artists: {exc}[/error]\n"
            "[muted]If this is a scope error, run `spotagen setup` to re-auth.[/muted]"
        )
        return

    if not followed:
        console.print("[muted]You don't follow any artists on Spotify yet.[/muted]")
        return

    existing = [] if replace else load_artists()
    existing_lower = {a.lower() for a in existing}
    added: list[str] = []
    for info in followed:
        if info.name.lower() not in existing_lower:
            existing.append(info.name)
            existing_lower.add(info.name.lower())
            added.append(info.name)

    save_artists(existing)
    verb = "Replaced" if replace else "Merged"
    console.print(
        f"[success]âœ“ {verb}: {len(followed)} followed artist(s) "
        f"from Spotify Â· {len(added)} new[/success]"
    )
    if added:
        for name in added[:12]:
            console.print(f"    [artist]+ {name}[/artist]")
        if len(added) > 12:
            console.print(f"    [muted]â€¦and {len(added) - 12} more[/muted]")


@artists_app.command("remove")
def artists_remove() -> None:
    """Interactive picker to remove an artist."""
    s = load_settings()
    console = _themed_console(s)
    artists = load_artists()
    if not artists:
        console.print("[muted]No artists to remove.[/muted]")
        return
    table = Table(
        show_header=True, header_style="subheader", border_style="border"
    )
    table.add_column("#", style="dim", justify="right")
    table.add_column("Artist", style="artist")
    for i, a in enumerate(artists, 1):
        table.add_row(str(i), a)
    console.print(table)
    idx = IntPrompt.ask(
        "[label]Number to remove[/label] [muted](0 to cancel)[/muted]",
        default=0,
        console=console,
    )
    if not 1 <= idx <= len(artists):
        console.print("[muted]Cancelled.[/muted]")
        return
    removed = artists.pop(idx - 1)
    save_artists(artists)
    console.print(f"[success]âœ“ Removed [artist]{removed}[/artist][/success]")


# --------------------------------------------------------------------------- #
# generate
# --------------------------------------------------------------------------- #


@app.command()
def generate(
    count: Optional[int] = typer.Option(
        None, "--count", help="Songs per artist (overrides config)."
    ),
    no_top_tracks: bool = typer.Option(
        False, "--no-top-tracks", help="Force agent-driven catalogue discovery."
    ),
    exclude_top_tracks: bool = typer.Option(
        False,
        "--exclude-top-tracks",
        help="Hard-blacklist each artist's top tracks from the candidate pool. "
        "Implies discovery mode.",
    ),
    from_spotify: bool = typer.Option(
        False,
        "--from-spotify",
        help="Pull the artists you follow on Spotify for this run "
        "(merged with artists.toml).",
    ),
    max_artists: Optional[int] = typer.Option(
        None,
        "--max-artists",
        help="Cap how many artists are used for this run (overrides "
        "playlist.max_artists_per_run). Sampled randomly if the merged "
        "list is larger.",
    ),
    all_artists: bool = typer.Option(
        False,
        "--all-artists",
        help="Disable the artist cap for this run (use every artist). "
        "Expect long runs and rate-limit warnings for large lists.",
    ),
    provider: Optional[Provider] = typer.Option(
        None, "--provider", help="Override the AI provider for this run."
    ),
    theme: Optional[Flavor] = typer.Option(
        None, "--theme", help="Override the UI flavor for this run."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Print the tracklist without creating a playlist."
    ),
) -> None:
    """Generate a randomised playlist for your artists."""
    from .curator import run_generate

    run_generate(
        count=count,
        force_discovery=no_top_tracks,
        exclude_top_tracks=exclude_top_tracks,
        from_spotify=from_spotify,
        max_artists=max_artists,
        all_artists=all_artists,
        provider_override=provider,
        theme_override=theme,
        dry_run=dry_run,
    )


# --------------------------------------------------------------------------- #
# history
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# genre
# --------------------------------------------------------------------------- #


@app.command()
def genre(
    artist: str = typer.Argument(..., help="Artist name to get genres from"),
    count: int = typer.Option(
        10, "--count", "-c", help="Number of songs in the playlist."
    ),
    limit_artists: int = typer.Option(
        20, "--limit-artists", help="Maximum number of artists to include from the genre."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Print the tracklist without creating a playlist."
    ),
    theme: Optional[Flavor] = typer.Option(
        None, "--theme", help="Override the UI flavor for this run."
    ),
) -> None:
    """Create a playlist from artists in the same genre as the specified artist."""
    from .curator import run_genre

    run_genre(
        artist=artist,
        count=count,
        limit_artists=limit_artists,
        theme_override=theme,
        dry_run=dry_run,
    )



@app.command()
def history(
    limit: int = typer.Option(20, "--limit", help="How many recent entries to show."),
) -> None:
    """List the most recently generated playlists."""
    s = load_settings()
    console = _themed_console(s)
    banner(console)

    from .config import history_path

    if sys.version_info >= (3, 11):
        import tomllib
    else:  # pragma: no cover
        import tomli as tomllib  # noqa: F401 â€” runtime fallback for Python 3.10

    p = history_path()
    if not p.exists():
        console.print("[muted]No playlists generated yet.[/muted]")
        return
    with p.open("rb") as f:
        data = tomllib.load(f)
    entries = list(data.get("entries", []))[-limit:][::-1]
    if not entries:
        console.print("[muted]No playlists generated yet.[/muted]")
        return

    table = Table(
        show_header=True, header_style="subheader", border_style="border"
    )
    table.add_column("When", style="label")
    table.add_column("Title", style="body")
    table.add_column("Tracks", style="track", justify="right")
    table.add_column("URL", style="info")
    for e in entries:
        table.add_row(
            str(e.get("created_at", "")),
            str(e.get("title", "")),
            str(e.get("count", "")),
            str(e.get("url", "")),
        )
    console.print(table)


if __name__ == "__main__":  # pragma: no cover
    app()
