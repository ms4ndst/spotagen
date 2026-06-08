"""Pydantic schema for the spotagen configuration files."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Provider(str, Enum):
    CLAUDE = "claude"
    MISTRAL = "mistral"
    OPENAI = "openai"
    OLLAMA = "ollama"


class Flavor(str, Enum):
    MOCHA = "mocha"
    MACCHIATO = "macchiato"
    FRAPPE = "frappe"
    LATTE = "latte"


class Accent(str, Enum):
    MAUVE = "mauve"
    BLUE = "blue"
    LAVENDER = "lavender"
    PEACH = "peach"
    TEAL = "teal"
    SKY = "sky"
    GREEN = "green"


class SpotifySettings(BaseModel):
    client_id: str = ""
    client_secret: str = ""
    # Spotify rejects `localhost` for loopback apps now — use the literal IP.
    redirect_uri: str = "http://127.0.0.1:8888/callback"


class PlaylistSettings(BaseModel):
    total_songs_per_artist: int = 5
    use_top_tracks: bool = True
    randomize_order: bool = True
    playlist_name_prefix: str = "Spotagen"
    use_followed_artists: bool = False
    """When True, every `generate` run pulls the user's Spotify-followed
    artists and merges them with `artists.toml`. Default False for backwards
    compatibility — opt in via `spotagen setup` or `--from-spotify`."""
    exclude_top_tracks: bool = False
    """When True, top tracks are hard-blacklisted from the candidate pool.
    Implies `use_top_tracks = False` for the run (the agent's curated set
    will never contain a chart hit, regardless of how the model behaves)."""
    max_artists_per_run: int = 50
    """Maximum artists to consider for a single `generate` run. When the
    merged artist list is larger, spotagen samples this many *randomly* so
    every run feels fresh. Set to 0 (or pass --all-artists) to disable the cap
    — but be aware that hundreds of artists means thousands of Spotify search
    calls and you WILL hit rate limits."""


class UISettings(BaseModel):
    flavor: Flavor = Flavor.MOCHA
    accent: Accent = Accent.MAUVE


class ClaudeSettings(BaseModel):
    api_key: str = ""
    model: str = "claude-sonnet-4-20250514"


class MistralSettings(BaseModel):
    api_key: str = ""
    model: str = "mistral-medium"


class OpenAISettings(BaseModel):
    api_key: str = ""
    model: str = "gpt-4o"


class OllamaSettings(BaseModel):
    base_url: str = "http://localhost:11434"
    model: str = "llama3"


class AISettings(BaseModel):
    provider: Provider = Provider.CLAUDE
    claude: ClaudeSettings = Field(default_factory=ClaudeSettings)
    mistral: MistralSettings = Field(default_factory=MistralSettings)
    openai: OpenAISettings = Field(default_factory=OpenAISettings)
    ollama: OllamaSettings = Field(default_factory=OllamaSettings)


class Settings(BaseModel):
    spotify: SpotifySettings = Field(default_factory=SpotifySettings)
    playlist: PlaylistSettings = Field(default_factory=PlaylistSettings)
    ui: UISettings = Field(default_factory=UISettings)
    ai: AISettings = Field(default_factory=AISettings)
