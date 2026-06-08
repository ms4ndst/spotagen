"""Spotify Authorization Code + PKCE flow with local callback server."""
from __future__ import annotations

import base64
import hashlib
import http.server
import json
import secrets
import threading
import time
import urllib.parse
import webbrowser
from typing import ClassVar

from typing import Any

import httpx

from ..config import tokens_path
from ..settings.schema import Settings
from ..theme import MOCHA_BASE, MOCHA_MAUVE, MOCHA_TEXT

TokenDict = dict[str, Any]

SCOPES = (
    "playlist-modify-public playlist-modify-private "
    "user-library-read user-follow-read"
)
REQUIRED_SCOPES = frozenset(SCOPES.split())
AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"  # noqa: S105 — Spotify endpoint, not a secret
CALLBACK_TIMEOUT_SECONDS = 180


class SpotifyAuthError(RuntimeError):
    """Raised when Spotify authentication fails or times out."""


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _gen_verifier() -> str:
    # 64 random bytes -> ~86 base64url chars; Spotify accepts up to 128.
    return _b64url(secrets.token_bytes(64))


def _gen_challenge(verifier: str) -> str:
    return _b64url(hashlib.sha256(verifier.encode("ascii")).digest())


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    code: ClassVar[str | None] = None
    error: ClassVar[str | None] = None
    state: ClassVar[str | None] = None

    def do_GET(self) -> None:  # noqa: N802 — http.server protocol
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/callback":
            self.send_response(404)
            self.end_headers()
            return
        params = urllib.parse.parse_qs(parsed.query)
        type(self).code = params.get("code", [None])[0]
        type(self).error = params.get("error", [None])[0]
        type(self).state = params.get("state", [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        body = (
            "<!doctype html><html><head><meta charset='utf-8'>"
            "<title>spotagen</title></head>"
            "<body style='font-family:system-ui;"
            f"background:{MOCHA_BASE};color:{MOCHA_TEXT};"
            "display:flex;align-items:center;justify-content:center;height:100vh;margin:0'>"
            f"<div><h2 style='color:{MOCHA_MAUVE}'>spotagen</h2>"
            "<p>Authentication complete — you can close this tab.</p></div></body></html>"
        )
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002, ARG002
        # Silence the default stderr access log.
        return


def _save_tokens(tokens: TokenDict) -> None:
    tokens["_saved_at"] = int(time.time())
    p = tokens_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(tokens, indent=2), encoding="utf-8")


def _load_tokens() -> TokenDict | None:
    p = tokens_path()
    if not p.exists():
        return None
    try:
        data: TokenDict = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data


def _exchange_code(
    client_id: str, code: str, verifier: str, redirect_uri: str
) -> TokenDict:
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "code_verifier": verifier,
    }
    response = httpx.post(TOKEN_URL, data=data, timeout=15.0)
    if response.status_code != 200:
        raise SpotifyAuthError(
            f"Token exchange failed: HTTP {response.status_code} — {response.text}"
        )
    body: TokenDict = response.json()
    return body


def _refresh_tokens(client_id: str, refresh_token: str) -> TokenDict:
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
    }
    response = httpx.post(TOKEN_URL, data=data, timeout=15.0)
    if response.status_code != 200:
        raise SpotifyAuthError(
            f"Refresh failed: HTTP {response.status_code} — {response.text}"
        )
    fresh: TokenDict = response.json()
    # Spotify often omits refresh_token from the refresh response — keep the old one.
    fresh.setdefault("refresh_token", refresh_token)
    return fresh


def _run_callback_server(redirect_uri: str) -> None:
    parsed = urllib.parse.urlparse(redirect_uri)
    host = parsed.hostname or "localhost"
    port = parsed.port or 8888
    _CallbackHandler.code = None
    _CallbackHandler.error = None
    _CallbackHandler.state = None
    server = http.server.HTTPServer((host, port), _CallbackHandler)

    def _serve() -> None:
        try:
            server.handle_request()
        finally:
            server.server_close()

    thread = threading.Thread(target=_serve, daemon=True)
    thread.start()
    thread.join(timeout=CALLBACK_TIMEOUT_SECONDS)
    if thread.is_alive():
        # Best-effort: server_close from the main thread unblocks select() on Windows.
        server.server_close()


def get_access_token(settings: Settings, force_reauth: bool = False) -> str:
    """Return a valid Spotify access token, running the PKCE flow if needed.

    Token cache is `~/.config/spotagen/tokens.json` (or platformdirs equivalent).
    """
    cfg = settings.spotify
    if not cfg.client_id:
        raise SpotifyAuthError(
            "Spotify client_id not configured — run `spotagen setup`."
        )

    cached = _load_tokens() if not force_reauth else None
    if cached and "access_token" in cached:
        cached_scopes = set(str(cached.get("scope", "")).split())
        scopes_ok = REQUIRED_SCOPES.issubset(cached_scopes)
        if scopes_ok:
            saved_at = int(cached.get("_saved_at", 0))
            expires_in = int(cached.get("expires_in", 3600))
            if time.time() < saved_at + expires_in - 60:
                return str(cached["access_token"])
            if "refresh_token" in cached:
                try:
                    fresh = _refresh_tokens(cfg.client_id, cached["refresh_token"])
                    _save_tokens(fresh)
                    return str(fresh["access_token"])
                except SpotifyAuthError:
                    pass  # fall through to full flow
        # else: cached token is missing one or more required scopes — re-auth.

    verifier = _gen_verifier()
    challenge = _gen_challenge(verifier)
    state = _b64url(secrets.token_bytes(16))
    query = urllib.parse.urlencode(
        {
            "response_type": "code",
            "client_id": cfg.client_id,
            "redirect_uri": cfg.redirect_uri,
            "scope": SCOPES,
            "state": state,
            "code_challenge_method": "S256",
            "code_challenge": challenge,
        }
    )
    auth_url = f"{AUTH_URL}?{query}"
    webbrowser.open(auth_url)
    _run_callback_server(cfg.redirect_uri)

    if _CallbackHandler.error:
        raise SpotifyAuthError(f"Spotify denied authorization: {_CallbackHandler.error}")
    if not _CallbackHandler.code:
        raise SpotifyAuthError(
            f"Timed out waiting for Spotify callback after {CALLBACK_TIMEOUT_SECONDS}s."
        )
    if _CallbackHandler.state != state:
        raise SpotifyAuthError("Spotify callback state mismatch — possible CSRF.")

    tokens = _exchange_code(
        cfg.client_id, _CallbackHandler.code, verifier, cfg.redirect_uri
    )
    _save_tokens(tokens)
    return str(tokens["access_token"])
