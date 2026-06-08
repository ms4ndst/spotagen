# spotagen

**spotagen** is a cross-platform terminal application that generates
randomised Spotify playlists for your favourite artists, driven by an AI
agent that plays two roles at once:

1. **Curator** — selects and ranks candidate tracks based on taste reasoning.
2. **Orchestrator** — when top-tracks mode is disabled, it drives deeper
   catalogue discovery by generating Spotify search queries on the fly.

Runs on Linux, macOS, and Windows. Python 3.10+, no platform-specific
dependencies, themed with [Catppuccin](https://github.com/catppuccin/catppuccin).

```
┌───────────────────────────────────────┐
│ ♪  spotagen                           │
│ AI-powered Spotify playlist generator │
└───────────────────────────────────────┘
```

---

## Quick start

```bash
# 1. Install
git clone <repo> && cd spotagen
pip install -e .

# 2. Configure (interactive — Spotify creds, AI provider, theme, behaviour)
spotagen setup

# 3. Get artists — either curate manually
spotagen artists add "Radiohead"
spotagen artists add "Portishead"
#    …or import everything you follow on Spotify
spotagen artists sync

# 4. Generate
spotagen generate                       # uses config defaults
spotagen generate --dry-run             # preview without creating a playlist
spotagen generate --exclude-top-tracks  # guaranteed-no-chart-hits playlist
spotagen generate --from-spotify        # this-run-only: include your follows
```

---

## Install

spotagen is not yet on PyPI. Install from a clone:

```bash
git clone <repo>
cd spotagen
python -m venv .venv
# Activate the venv:
#   Windows PowerShell:  .venv\Scripts\Activate.ps1
#   POSIX shells:        source .venv/bin/activate
pip install -e .
spotagen --help
```

### Requirements

- Python **3.10 or newer**
- A [Spotify developer app](https://developer.spotify.com/dashboard) (Client ID only — no client secret needed; PKCE is used)
- An API key for at least one supported AI provider (Anthropic / OpenAI / Mistral), OR a local [Ollama](https://ollama.com/) install

---

## Create a Spotify app

1. Sign in at <https://developer.spotify.com/dashboard> and click **Create app**.
2. Fill in any name + description.
3. **Redirect URI** — set it to:

   ```
   http://127.0.0.1:8888/callback
   ```

   Spotify now rejects `http://localhost:...` for loopback apps — use the
   literal IP `127.0.0.1`. Match the port to whatever you put in
   `redirect_uri` in your spotagen config (`8888` is the default).

4. Under **APIs used**, tick the **Web API** box.
5. Save, then copy the **Client ID** from the app dashboard — you'll paste it
   into `spotagen setup`.

Client secret is **not** required — spotagen uses Authorization Code with
PKCE.

### Spotify scopes used

| Scope                       | Why                                           |
|-----------------------------|-----------------------------------------------|
| `playlist-modify-public`    | Create public playlists on your account       |
| `playlist-modify-private`   | Create private playlists on your account      |
| `user-library-read`         | Reserved for future "saved tracks" features   |
| `user-follow-read`          | Read the artists you follow (`--from-spotify`, `artists sync`) |

If your cached tokens predate a scope addition, spotagen detects the missing
scope on the next Spotify call and re-runs the OAuth flow automatically.

---

## First-time setup

```bash
spotagen setup
```

The interactive wizard collects:

| Section    | What it asks for                                                                          |
|------------|-------------------------------------------------------------------------------------------|
| Spotify    | `client_id`, redirect URI (default `http://localhost:8888/callback` — change to `127.0.0.1`) |
| AI         | provider (`claude` / `mistral` / `openai` / `ollama`) + API key & model                   |
| Theme      | Catppuccin flavor (`mocha` / `latte` / `frappe` / `macchiato`) + accent colour            |
| Behaviour  | auto-include followed artists? · use top tracks? · hard-blacklist top tracks?             |

It then opens your browser for the Spotify OAuth (PKCE) consent screen, runs
a local callback server on the host+port from your `redirect_uri`, exchanges
the code for tokens, and caches them next to the config.

### Where files live

| OS      | Directory                                            |
|---------|------------------------------------------------------|
| Linux   | `~/.config/spotagen/`                                |
| macOS   | `~/Library/Application Support/spotagen/`            |
| Windows | `%APPDATA%\spotagen\`                                |

Files inside:

| File            | Contents                                       |
|-----------------|------------------------------------------------|
| `config.toml`   | Spotify creds, AI provider, theme, behaviour   |
| `artists.toml`  | Your manually-curated artist list              |
| `tokens.json`   | Cached Spotify access + refresh tokens         |
| `history.toml`  | Append-only log of generated playlists         |

---

## Commands

| Command                       | What it does                                                 |
|-------------------------------|--------------------------------------------------------------|
| `spotagen setup`              | Interactive wizard for Spotify, AI, theme, behaviour         |
| `spotagen config`             | Open the config in `$EDITOR` / notepad                       |
| `spotagen config --show`      | Print the current config as a themed table                   |
| `spotagen artists list`       | Print your artist list                                       |
| `spotagen artists add NAME`   | Append an artist (fuzzy-matched against Spotify)             |
| `spotagen artists sync`       | Pull the artists you follow on Spotify and merge into `artists.toml` (use `--replace` to overwrite) |
| `spotagen artists remove`     | Interactive picker to remove an artist                       |
| `spotagen generate`           | Generate a playlist (see flags below)                        |
| `spotagen history`            | Show the last 20 generated playlists with their Spotify URLs |

### `spotagen generate` flags

| Flag                    | Effect                                                     |
|-------------------------|------------------------------------------------------------|
| `--count INT`           | Songs per artist (overrides `playlist.total_songs_per_artist`) |
| `--no-top-tracks`       | Force agent-driven catalogue discovery (deep cuts, B-sides, live, demos) |
| `--exclude-top-tracks`  | Hard-blacklist each artist's chart hits from the candidate pool (implies discovery mode) |
| `--from-spotify`        | Pull the artists you follow on Spotify for this run (merged with `artists.toml`) |
| `--max-artists INT`     | Cap how many artists are used for this run (overrides `playlist.max_artists_per_run`) |
| `--all-artists`         | Disable the artist cap for this run (use every artist — expect long runs and rate-limit warnings) |
| `--provider PROVIDER`   | Override the AI provider for this run                      |
| `--theme FLAVOR`        | Override the UI flavor for this run                        |
| `--dry-run`             | Print the tracklist without creating a playlist            |

### `--no-top-tracks` vs `--exclude-top-tracks`

| Flag                  | Candidate pool comes from | Top-track filtering         |
|-----------------------|---------------------------|-----------------------------|
| _(default)_           | Spotify top-tracks API    | None — they ARE the pool    |
| `--no-top-tracks`     | Agent-generated searches  | Soft — agent is asked to avoid them |
| `--exclude-top-tracks`| Agent-generated searches  | **Hard** — top-track IDs are removed from the pool before the agent sees them |

Use `--exclude-top-tracks` when you want guaranteed-no-chart-hits even if the
agent's curation is sloppy.

---

## Config reference

```toml
[spotify]
client_id     = ""
client_secret = ""                                # optional — PKCE is used
redirect_uri  = "http://127.0.0.1:8888/callback"  # use 127.0.0.1, not localhost

[playlist]
total_songs_per_artist = 5
use_top_tracks         = true   # false = agent-driven catalogue discovery
exclude_top_tracks     = false  # true  = hard-blacklist every artist's chart hits
use_followed_artists   = false  # true  = always merge in your Spotify follows
max_artists_per_run    = 50     # 0     = no cap (warning: large lists hit Spotify rate limits)
randomize_order        = true
playlist_name_prefix   = "Spotagen"

[ui]
flavor = "mocha"      # mocha | macchiato | frappe | latte
accent = "mauve"      # mauve | blue | lavender | peach | teal | sky | green

[ai]
provider = "claude"   # claude | mistral | openai | ollama

[ai.claude]
api_key = ""
model   = "claude-sonnet-4-20250514"

[ai.mistral]
api_key = ""
model   = "mistral-medium"

[ai.openai]
api_key = ""
model   = "gpt-4o"

[ai.ollama]
base_url = "http://localhost:11434"
model    = "llama3"
```

Artists are stored separately at `artists.toml` in the same directory:

```toml
artists = ["Radiohead", "Portishead", "Massive Attack"]
```

---

## Where artists come from

spotagen merges two sources for every `generate` run:

1. **`artists.toml`** — the manually-curated list.
   `spotagen artists add NAME` appends, `artists remove` opens an interactive
   picker.
2. **Your Spotify follows** — pulled on every run when
   `playlist.use_followed_artists = true` or `--from-spotify` is passed.
   Each followed artist comes with its canonical Spotify ID, so no extra
   search-API call is needed to resolve it.

If you'd rather bulk-import follows once into `artists.toml` (so they appear
in `artists list` and you can edit them):

```bash
spotagen artists sync             # merge into existing artists.toml
spotagen artists sync --replace   # overwrite artists.toml entirely
```

Sync needs the `user-follow-read` scope. If your cached tokens predate that
scope, spotagen detects the missing scope on the next Spotify call and
re-runs the OAuth flow automatically.

---

## How a `generate` run works

1. Load `artists.toml`, optionally merge in Spotify follows.
2. Resolve each name to a Spotify artist ID (followed artists skip this step
   — they already have IDs).
3. **Candidate fetch:**
   - If `use_top_tracks = true`: pull each artist's top tracks from Spotify.
   - If `--no-top-tracks` / `use_top_tracks = false` / `--exclude-top-tracks`:
     the AI agent first generates Spotify search queries (BBC sessions, live
     versions, collaborations, demos, remixes), and spotagen runs each query
     against the Spotify search API.
4. **Top-tracks blacklist** (only when `--exclude-top-tracks` /
   `exclude_top_tracks = true`): each artist's top tracks are fetched and
   their IDs hard-removed from the candidate pool before the agent sees them.
5. **Curation pass:** the agent receives the candidate list and selects
   `total_songs_per_artist` tracks per artist, returning only IDs that existed
   in the candidate list (no hallucinated IDs).
6. Spotagen filters out any unknown IDs as a safety net, shows the agent's
   reasoning in a Catppuccin-themed panel, optionally shuffles, and creates a
   private playlist on your account.
7. The new playlist's title, URL, and track count are appended to
   `history.toml`.

---

## Error handling & fallbacks

| Condition                       | Behaviour                                                       |
|---------------------------------|-----------------------------------------------------------------|
| Spotify auth fails              | Themed `✗ Spotify auth failed` + pointer to `spotagen setup`    |
| AI provider API error           | Themed warning, retry **once**, then random fallback            |
| Agent returns invalid JSON      | Themed warning, retry **once**, then random fallback            |
| Agent returns unknown track IDs | Filtered out silently, count printed in summary                 |
| Cached token missing a scope    | Automatic re-auth — browser opens to consent screen             |
| Ollama daemon unreachable       | Themed warning + deterministic random selection                 |
| No artists configured           | Themed error pointing at `artists add` / `artists sync` / `--from-spotify` |
| Spotify search call fails       | That single query is skipped, run continues; count summarised at end |
| Spotify rate-limits artist lookup | That artist is skipped, run continues with the rest             |

### Large artist lists & the per-run cap

spotagen caps each `generate` run at `max_artists_per_run` artists (default
**50**). When your merged list is bigger — common once you import several
hundred Spotify follows — the cap kicks in and samples that many artists at
random for the run. The shuffle means every run feels fresh; no single
artist dominates the rotation.

You'll see a line like:

```
 Sampling   50 artists drawn at random from your 826 total · pass --all-artists to use everything
```

To go bigger:

```bash
spotagen generate --max-artists 200    # this run only
spotagen generate --all-artists        # all of them — expect a long run + rate-limit warnings
```

**Why the cap is there**: with 5 search queries per artist in discovery mode,
826 artists = ~4,000 Spotify search calls. Spotify's API edge will start
dropping connections somewhere around that volume. spotagen now catches
those failures (single failed query → skip, summary at the end) so a
rate-limit no longer aborts the whole run, but the cap is the right
first-line answer.

### Long artist lists & chunking

For runs with more than 8 artists (common once you enable
`use_followed_artists`), spotagen splits the work into chunks of 8 artists
per agent call. You'll see lines like:

```
Curating in 4 chunks of up to 8 artists…
  Chunk 1/4 · 8 artist(s)
  Chunk 2/4 · 8 artist(s)
  …
```

Each chunk is independently retried-then-fallback, so a single chunk hitting
a read timeout or invalid-JSON response only forces a random selection for
*its 8 artists* — the other chunks still get real agent curation. This is
why you might see one `⚠ falling back` line in an otherwise successful run.

Chunk size is set in `curator.py` (`ARTIST_CHUNK_SIZE = 8`) — it's
conservative enough for slow providers like Mistral; if you're on a fast
provider and want fewer chunks, raise it.

### Ollama offline behaviour

If `ai.provider = "ollama"` and the daemon at `base_url` is unreachable,
spotagen prints `⚠ Ollama unreachable — falling back to random selection`
and returns a deterministic random track selection. The same fallback path
is used by the other providers as a last resort after one retry on
API / JSON errors.

---

## Theme

All four official Catppuccin flavors (Mocha, Latte, Frappé, Macchiato) ship
in-box with the exact upstream hex values. The `accent` setting recolours the
`accent`, `header`, and `highlight` semantic roles only; all other roles stay
on the flavor's canonical palette. Flavor and accent can also be overridden
per-run with `--theme`.

Semantic roles available in `rich` markup:

| Role        | Default colour role          | Used for                              |
|-------------|------------------------------|---------------------------------------|
| `header`    | Mauve, bold                  | Main titles                           |
| `subheader` | Lavender                     | Section labels                        |
| `body`      | Text                         | Default body text                     |
| `muted`     | Overlay1                     | Hints, secondary info                 |
| `label`     | Subtext1                     | Field labels in tables                |
| `accent`    | Mauve, bold (configurable)   | Primary action highlight              |
| `success`   | Green                        | `✓` confirmations                     |
| `warning`   | Yellow                       | `⚠` recoverable issues                |
| `error`     | Red                          | `✗` hard failures                     |
| `info`      | Blue                         | URLs, neutral info                    |
| `artist`    | Peach, bold                  | Artist names                          |
| `track`     | Teal                         | Track names                           |
| `provider`  | Sky                          | Provider + model display              |
| `highlight` | Mauve, bold underline (configurable) | Emphasized labels             |
| `border`    | Surface2                     | Rules and panel borders               |
| `dim`       | Overlay0                     | De-emphasized text                    |

---

## Troubleshooting

### Browser opens to consent but never returns

You're hitting the redirect-URI mismatch. Spotify requires:

- the literal IP `127.0.0.1` (not `localhost`) for loopback apps, AND
- an **exact** byte-for-byte match between the redirect URI in your Spotify
  app settings and the `redirect_uri` in `config.toml`.

Set both to `http://127.0.0.1:8888/callback` and try again.

### `Insufficient client scope` from a Spotify call

You have cached tokens from a spotagen version with fewer scopes. spotagen
should detect this and re-auth automatically — if it doesn't, force it:

```bash
rm "$(spotagen config --show | grep -m1 'config.toml' | awk '{print $NF}')/../tokens.json"
spotagen setup
```

Or just delete `tokens.json` from your spotagen config directory and run any
Spotify command — the browser will reopen.

### `pip install` downgrades opentelemetry / breaks other packages

Some AI-vendor SDKs ship with very aggressive opentelemetry version pins.
spotagen's pyproject avoids the worst offender (`mistralai`) by talking to
Mistral via `httpx` directly. If you've previously pip-installed `mistralai`
into the same env and it downgraded your opentelemetry stack, recover with:

```bash
pip uninstall -y mistralai
pip install --upgrade `
  opentelemetry-api `
  opentelemetry-sdk `
  opentelemetry-semantic-conventions `
  opentelemetry-instrumentation `
  opentelemetry-instrumentation-asgi `
  opentelemetry-instrumentation-fastapi `
  opentelemetry-exporter-otlp-proto-grpc
```

The opentelemetry family must all upgrade together — pinning only some of
them strands the rest.

Best practice: install spotagen into its own venv so its deps never collide
with your other tooling.

---

## Development

```bash
git clone <repo>
cd spotagen
python -m venv .venv
# Activate the venv (PowerShell: .venv\Scripts\Activate.ps1, POSIX: source .venv/bin/activate)
pip install -e .
spotagen --help
```

### Smoke tests

The four theme smoke tests required by the spec:

```bash
python -c "from spotagen.theme import banner; banner()"
python -c "from spotagen.theme import FLAVORS; assert set(FLAVORS) == {'mocha','latte','frappe','macchiato'}"
python -c "from spotagen.theme import build_rich_theme; build_rich_theme('frappe','teal')"
python -c "from spotagen.theme import build_rich_theme; build_rich_theme('macchiato','lavender')"
```

### Type checking

```bash
pip install mypy
mypy --strict spotagen
```

`mypy --strict` passes clean on the whole package. The only `# type: ignore`
in the codebase is one `[union-attr]` in `agents/anthropic_provider.py` where
the Anthropic SDK returns a union of content-block types — we runtime-check
`type == "text"` but mypy can't narrow on the `getattr()` result.

---

## License

MIT.
