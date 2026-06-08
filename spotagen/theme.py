"""Catppuccin theme constants and `rich.Theme` builder.

All four official Catppuccin flavors (Mocha, Latte, Frappé, Macchiato) are
implemented with the exact hex values from the upstream palette. Routing from
a flavor name string is done through the `FLAVORS` dict — no `if/elif` chains
on flavor names anywhere outside this module.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Final

from rich.console import Console
from rich.panel import Panel
from rich.theme import Theme

# Windows legacy code pages (cp1252, cp437) cannot encode the Unicode glyphs
# used throughout the spotagen UI (♪, ✓, ✗, ⚠, box drawing). Force stdout/stderr
# to UTF-8 at import time so every spotagen entry point — including the
# `python -c "from spotagen.theme import banner; banner()"` smoke test — renders
# correctly without the caller having to set PYTHONIOENCODING.
if sys.platform == "win32":
    for _stream_name in ("stdout", "stderr"):
        _stream = getattr(sys, _stream_name, None)
        if _stream is not None and hasattr(_stream, "reconfigure"):
            try:
                _stream.reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass

# --------------------------------------------------------------------------- #
# Mocha
# --------------------------------------------------------------------------- #
MOCHA_BASE: Final = "#1e1e2e"
MOCHA_MANTLE: Final = "#181825"
MOCHA_CRUST: Final = "#11111b"
MOCHA_SURFACE0: Final = "#313244"
MOCHA_SURFACE1: Final = "#45475a"
MOCHA_SURFACE2: Final = "#585b70"
MOCHA_TEXT: Final = "#cdd6f4"
MOCHA_SUBTEXT1: Final = "#bac2de"
MOCHA_SUBTEXT0: Final = "#a6adc8"
MOCHA_OVERLAY1: Final = "#7f849c"
MOCHA_OVERLAY0: Final = "#6c7086"
MOCHA_MAUVE: Final = "#cba6f7"
MOCHA_BLUE: Final = "#89b4fa"
MOCHA_GREEN: Final = "#a6e3a1"
MOCHA_RED: Final = "#f38ba8"
MOCHA_YELLOW: Final = "#f9e2af"
MOCHA_PEACH: Final = "#fab387"
MOCHA_TEAL: Final = "#94e2d5"
MOCHA_LAVENDER: Final = "#b4befe"
MOCHA_SKY: Final = "#89dceb"

# --------------------------------------------------------------------------- #
# Latte
# --------------------------------------------------------------------------- #
LATTE_BASE: Final = "#eff1f5"
LATTE_MANTLE: Final = "#e6e9ef"
LATTE_CRUST: Final = "#dce0e8"
LATTE_SURFACE0: Final = "#ccd0da"
LATTE_SURFACE1: Final = "#bcc0cc"
LATTE_SURFACE2: Final = "#acb0be"
LATTE_TEXT: Final = "#4c4f69"
LATTE_SUBTEXT1: Final = "#5c5f77"
LATTE_SUBTEXT0: Final = "#6c6f85"
LATTE_OVERLAY1: Final = "#8c8fa1"
LATTE_OVERLAY0: Final = "#9ca0b0"
LATTE_MAUVE: Final = "#8839ef"
LATTE_BLUE: Final = "#1e66f5"
LATTE_GREEN: Final = "#40a02b"
LATTE_RED: Final = "#d20f39"
LATTE_YELLOW: Final = "#df8e1d"
LATTE_PEACH: Final = "#fe640b"
LATTE_TEAL: Final = "#179299"
LATTE_LAVENDER: Final = "#7287fd"
LATTE_SKY: Final = "#04a5e5"

# --------------------------------------------------------------------------- #
# Frappé
# --------------------------------------------------------------------------- #
FRAPPE_BASE: Final = "#303446"
FRAPPE_MANTLE: Final = "#292c3c"
FRAPPE_CRUST: Final = "#232634"
FRAPPE_SURFACE0: Final = "#414559"
FRAPPE_SURFACE1: Final = "#51576d"
FRAPPE_SURFACE2: Final = "#626880"
FRAPPE_TEXT: Final = "#c6d0f5"
FRAPPE_SUBTEXT1: Final = "#b5bfe2"
FRAPPE_SUBTEXT0: Final = "#a5adce"
FRAPPE_OVERLAY1: Final = "#838ba7"
FRAPPE_OVERLAY0: Final = "#737994"
FRAPPE_MAUVE: Final = "#ca9ee6"
FRAPPE_BLUE: Final = "#8caaee"
FRAPPE_GREEN: Final = "#a6d189"
FRAPPE_RED: Final = "#e78284"
FRAPPE_YELLOW: Final = "#e5c890"
FRAPPE_PEACH: Final = "#ef9f76"
FRAPPE_TEAL: Final = "#81c8be"
FRAPPE_LAVENDER: Final = "#babbf1"
FRAPPE_SKY: Final = "#99d1db"

# --------------------------------------------------------------------------- #
# Macchiato
# --------------------------------------------------------------------------- #
MACCHIATO_BASE: Final = "#24273a"
MACCHIATO_MANTLE: Final = "#1e2030"
MACCHIATO_CRUST: Final = "#181926"
MACCHIATO_SURFACE0: Final = "#363a4f"
MACCHIATO_SURFACE1: Final = "#494d64"
MACCHIATO_SURFACE2: Final = "#5b6078"
MACCHIATO_TEXT: Final = "#cad3f5"
MACCHIATO_SUBTEXT1: Final = "#b8c0e0"
MACCHIATO_SUBTEXT0: Final = "#a5adcb"
MACCHIATO_OVERLAY1: Final = "#8087a2"
MACCHIATO_OVERLAY0: Final = "#6e738d"
MACCHIATO_MAUVE: Final = "#c6a0f6"
MACCHIATO_BLUE: Final = "#8aadf4"
MACCHIATO_GREEN: Final = "#a6da95"
MACCHIATO_RED: Final = "#ed8796"
MACCHIATO_YELLOW: Final = "#eed49f"
MACCHIATO_PEACH: Final = "#f5a97f"
MACCHIATO_TEAL: Final = "#8bd5ca"
MACCHIATO_LAVENDER: Final = "#b7bdf8"
MACCHIATO_SKY: Final = "#91d7e3"

# --------------------------------------------------------------------------- #
# Flavor dataclass
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class CatppuccinFlavor:
    """A complete Catppuccin palette."""

    name: str
    base: str
    mantle: str
    crust: str
    surface0: str
    surface1: str
    surface2: str
    text: str
    subtext1: str
    subtext0: str
    overlay1: str
    overlay0: str
    mauve: str
    blue: str
    green: str
    red: str
    yellow: str
    peach: str
    teal: str
    lavender: str
    sky: str


MOCHA: Final[CatppuccinFlavor] = CatppuccinFlavor(
    name="mocha",
    base=MOCHA_BASE, mantle=MOCHA_MANTLE, crust=MOCHA_CRUST,
    surface0=MOCHA_SURFACE0, surface1=MOCHA_SURFACE1, surface2=MOCHA_SURFACE2,
    text=MOCHA_TEXT, subtext1=MOCHA_SUBTEXT1, subtext0=MOCHA_SUBTEXT0,
    overlay1=MOCHA_OVERLAY1, overlay0=MOCHA_OVERLAY0,
    mauve=MOCHA_MAUVE, blue=MOCHA_BLUE, green=MOCHA_GREEN, red=MOCHA_RED,
    yellow=MOCHA_YELLOW, peach=MOCHA_PEACH, teal=MOCHA_TEAL,
    lavender=MOCHA_LAVENDER, sky=MOCHA_SKY,
)

LATTE: Final[CatppuccinFlavor] = CatppuccinFlavor(
    name="latte",
    base=LATTE_BASE, mantle=LATTE_MANTLE, crust=LATTE_CRUST,
    surface0=LATTE_SURFACE0, surface1=LATTE_SURFACE1, surface2=LATTE_SURFACE2,
    text=LATTE_TEXT, subtext1=LATTE_SUBTEXT1, subtext0=LATTE_SUBTEXT0,
    overlay1=LATTE_OVERLAY1, overlay0=LATTE_OVERLAY0,
    mauve=LATTE_MAUVE, blue=LATTE_BLUE, green=LATTE_GREEN, red=LATTE_RED,
    yellow=LATTE_YELLOW, peach=LATTE_PEACH, teal=LATTE_TEAL,
    lavender=LATTE_LAVENDER, sky=LATTE_SKY,
)

FRAPPE: Final[CatppuccinFlavor] = CatppuccinFlavor(
    name="frappe",
    base=FRAPPE_BASE, mantle=FRAPPE_MANTLE, crust=FRAPPE_CRUST,
    surface0=FRAPPE_SURFACE0, surface1=FRAPPE_SURFACE1, surface2=FRAPPE_SURFACE2,
    text=FRAPPE_TEXT, subtext1=FRAPPE_SUBTEXT1, subtext0=FRAPPE_SUBTEXT0,
    overlay1=FRAPPE_OVERLAY1, overlay0=FRAPPE_OVERLAY0,
    mauve=FRAPPE_MAUVE, blue=FRAPPE_BLUE, green=FRAPPE_GREEN, red=FRAPPE_RED,
    yellow=FRAPPE_YELLOW, peach=FRAPPE_PEACH, teal=FRAPPE_TEAL,
    lavender=FRAPPE_LAVENDER, sky=FRAPPE_SKY,
)

MACCHIATO: Final[CatppuccinFlavor] = CatppuccinFlavor(
    name="macchiato",
    base=MACCHIATO_BASE, mantle=MACCHIATO_MANTLE, crust=MACCHIATO_CRUST,
    surface0=MACCHIATO_SURFACE0, surface1=MACCHIATO_SURFACE1, surface2=MACCHIATO_SURFACE2,
    text=MACCHIATO_TEXT, subtext1=MACCHIATO_SUBTEXT1, subtext0=MACCHIATO_SUBTEXT0,
    overlay1=MACCHIATO_OVERLAY1, overlay0=MACCHIATO_OVERLAY0,
    mauve=MACCHIATO_MAUVE, blue=MACCHIATO_BLUE, green=MACCHIATO_GREEN, red=MACCHIATO_RED,
    yellow=MACCHIATO_YELLOW, peach=MACCHIATO_PEACH, teal=MACCHIATO_TEAL,
    lavender=MACCHIATO_LAVENDER, sky=MACCHIATO_SKY,
)

FLAVORS: dict[str, CatppuccinFlavor] = {
    "mocha":     MOCHA,
    "latte":     LATTE,
    "frappe":    FRAPPE,
    "macchiato": MACCHIATO,
}

VALID_ACCENTS: Final[frozenset[str]] = frozenset(
    {"mauve", "blue", "lavender", "peach", "teal", "sky", "green"}
)


def build_rich_theme(flavor: str, accent: str = "mauve") -> Theme:
    """Construct a `rich.Theme` for the named Catppuccin flavor and accent.

    The accent name overrides only the `accent`, `header`, and `highlight`
    semantic roles. All other roles use the flavor's canonical colors.

    Raises:
        ValueError: if `flavor` is not one of `FLAVORS` or `accent` is not a
            recognized accent name.
    """
    if flavor not in FLAVORS:
        raise ValueError(
            f"Unknown Catppuccin flavor {flavor!r} — "
            f"must be one of: {sorted(FLAVORS)}"
        )
    if accent not in VALID_ACCENTS:
        raise ValueError(
            f"Unknown accent {accent!r} — "
            f"must be one of: {sorted(VALID_ACCENTS)}"
        )
    f = FLAVORS[flavor]
    accent_hex = getattr(f, accent)

    styles: dict[str, str] = {
        "header":    f"bold {accent_hex}",
        "subheader": f.lavender,
        "body":      f.text,
        "muted":     f.overlay1,
        "label":     f.subtext1,
        "accent":    f"bold {accent_hex}",
        "success":   f.green,
        "warning":   f.yellow,
        "error":     f.red,
        "info":      f.blue,
        "artist":    f"bold {f.peach}",
        "track":     f.teal,
        "provider":  f.sky,
        "highlight": f"bold underline {accent_hex}",
        "border":    f.surface2,
        "dim":       f.overlay0,
    }
    return Theme(styles)


def banner(console: Console | None = None) -> None:
    """Render the spotagen banner. Uses the supplied themed console, or a
    default Mocha+mauve themed console when none is given.
    """
    if console is None:
        console = Console(theme=build_rich_theme("mocha", "mauve"))
    console.print(
        Panel.fit(
            "[header]♪  spotagen[/header]\n"
            "[muted]AI-powered Spotify playlist generator[/muted]",
            border_style="border",
            padding=(0, 1),
        )
    )
