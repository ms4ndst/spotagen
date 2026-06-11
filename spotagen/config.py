"""TOML config and artists-list load/save.

Paths are resolved through `platformdirs`:
- Linux:   ~/.config/spotagen/
- macOS:   ~/Library/Application Support/spotagen/
- Windows: %APPDATA%\\spotagen\\
"""
from __future__ import annotations

import sys
from pathlib import Path

import tomli_w
from platformdirs import user_config_path

from .settings.schema import Settings

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib  # noqa: F401 — runtime fallback for Python 3.10

APP_NAME = "spotagen"


def config_dir() -> Path:
    """Return the spotagen config directory, creating it if needed."""
    p = user_config_path(APP_NAME, appauthor=False, roaming=True)
    p.mkdir(parents=True, exist_ok=True)
    return p


def config_path() -> Path:
    return config_dir() / "config.toml"


def artists_path() -> Path:
    return config_dir() / "artists.toml"


def tokens_path() -> Path:
    return config_dir() / "tokens.json"


def history_path() -> Path:
    return config_dir() / "history.toml"


def load_settings() -> Settings:
    """Load and validate the TOML config. Returns defaults if the file is missing.

    Raises:
        ConfigError: if the file exists but is malformed TOML or fails Pydantic
            validation. The exception message names the file and the parse
            location so the user can fix it without reading a stack trace.
    """
    p = config_path()
    if not p.exists():
        return Settings()
    try:
        with p.open("rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(
            f"config.toml is not valid TOML — {exc}\n"
            f"  file: {p}\n"
            "  Fix the line above, or run `spotagen setup` to overwrite it."
        ) from exc
    try:
        return Settings.model_validate(data)
    except Exception as exc:  # noqa: BLE001 — pydantic.ValidationError + others
        raise ConfigError(
            f"config.toml failed validation — {exc}\n"
            f"  file: {p}\n"
            "  Fix the field above, or run `spotagen setup` to overwrite it."
        ) from exc


def save_settings(settings: Settings) -> None:
    """Serialize Settings back to TOML."""
    p = config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    data = settings.model_dump(mode="json")
    with p.open("wb") as f:
        tomli_w.dump(data, f)


def load_artists() -> list[str]:
    p = artists_path()
    if not p.exists():
        return []
    with p.open("rb") as f:
        data = tomllib.load(f)
    raw = data.get("artists", [])
    return [str(a) for a in raw]


def save_artists(artists: list[str]) -> None:
    p = artists_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("wb") as f:
        tomli_w.dump({"artists": artists}, f)


class ConfigError(RuntimeError):
    """Raised when a required config field is missing or invalid."""


def require_field(value: str, key: str) -> str:
    """Raise ConfigError with the user-actionable message for an empty required field."""
    if not value:
        raise ConfigError(
            f"Missing required config key: {key} — run `spotagen setup` to fix."
        )
    return value
