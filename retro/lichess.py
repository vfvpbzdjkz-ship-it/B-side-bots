"""A tiny, dependency-free Lichess client + persisted GUI settings.

Just enough of the Lichess **Bot API** for the GUI to: verify a token, list
online bots, issue a challenge, and play the resulting game move-by-move.  Uses
only the standard library (``urllib``), so there is nothing extra to install.

The account whose token you use must be a **bot account**
(https://lichess.org/api#tag/Bot) for the bot endpoints to work.

Settings (the API token and your last choices) persist to
``~/.retro_roster.json`` so they survive closing the app.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, Iterator, List, Optional

BASE_URL = "https://lichess.org"
SETTINGS_PATH = os.path.join(os.path.expanduser("~"), ".retro_roster.json")


# --- persisted settings ---------------------------------------------------

DEFAULT_SETTINGS = {
    "token": "",
    "engine": "kneejerk",
    "rated": False,
    "clock_limit_min": 3.0,   # initial time, minutes
    "clock_increment": 2,     # seconds
    "color": "black",
}


def load_settings() -> Dict:
    """Load saved settings, falling back to defaults for anything missing."""
    data = dict(DEFAULT_SETTINGS)
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as fh:
            data.update(json.load(fh))
    except (OSError, ValueError):
        pass
    return data


def save_settings(settings: Dict) -> None:
    """Persist settings to disk (best-effort; failures are swallowed)."""
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as fh:
            json.dump(settings, fh, indent=2)
    except OSError:
        pass


# --- API client -----------------------------------------------------------

class LichessError(Exception):
    """Any problem talking to Lichess (network, auth, or API error)."""


class LichessClient:
    def __init__(self, token: str, base_url: str = BASE_URL) -> None:
        self.token = token.strip()
        self.base_url = base_url.rstrip("/")

    # -- low-level helpers --
    def _request(self, method: str, path: str, data: Optional[Dict] = None,
                 stream: bool = False, timeout: float = 30.0):
        url = self.base_url + path
        body = urllib.parse.urlencode(data).encode() if data else None
        req = urllib.request.Request(url, data=body, method=method)
        req.add_header("Authorization", f"Bearer {self.token}")
        req.add_header("Accept", "application/x-ndjson")
        try:
            response = urllib.request.urlopen(req, timeout=None if stream else timeout)
        except urllib.error.HTTPError as exc:  # noqa: PERF203
            detail = exc.read().decode("utf-8", "replace")
            raise LichessError(f"HTTP {exc.code}: {detail.strip() or exc.reason}") from exc
        except urllib.error.URLError as exc:
            raise LichessError(f"network error: {exc.reason}") from exc
        return response

    def _get_json(self, path: str) -> Dict:
        resp = self._request("GET", path)
        return json.loads(resp.read().decode("utf-8"))

    def _stream_ndjson(self, path: str) -> Iterator[Dict]:
        resp = self._request("GET", path, stream=True)
        for raw in resp:
            line = raw.strip()
            if line:  # blank lines are keep-alives
                yield json.loads(line.decode("utf-8"))

    # -- public API --
    def account(self) -> Dict:
        """Return the authenticated account (raises LichessError if invalid)."""
        return self._get_json("/api/account")

    def upgrade_to_bot(self) -> None:
        """Irreversibly upgrade this account to a BOT account.

        Only works on an account that has **never played a game**, and cannot be
        undone. The token must carry the ``bot:play`` scope.
        """
        self._request("POST", "/api/bot/account/upgrade")

    def online_bots(self, count: int = 50) -> List[Dict]:
        """List online bot accounts you could challenge."""
        bots = []
        for entry in self._stream_ndjson(f"/api/bot/online?nb={count}"):
            bots.append({
                "username": entry.get("username") or entry.get("id", "?"),
                "title": entry.get("title", "BOT"),
            })
        return bots

    def create_challenge(self, username: str, *, rated: bool,
                         clock_limit: int, clock_increment: int,
                         color: str = "black") -> Dict:
        """Challenge ``username`` to a game; returns the challenge object."""
        data = {
            "rated": "true" if rated else "false",
            "clock.limit": int(clock_limit),
            "clock.increment": int(clock_increment),
            "color": color,
            "variant": "standard",
        }
        resp = self._request("POST", f"/api/challenge/{username}", data=data)
        return json.loads(resp.read().decode("utf-8"))

    def stream_events(self) -> Iterator[Dict]:
        """Stream incoming account events (gameStart, challenge, …)."""
        yield from self._stream_ndjson("/api/stream/event")

    def stream_game(self, game_id: str) -> Iterator[Dict]:
        """Stream a single bot game's state (gameFull then gameState updates)."""
        yield from self._stream_ndjson(f"/api/bot/game/stream/{game_id}")

    def make_move(self, game_id: str, uci: str) -> None:
        self._request("POST", f"/api/bot/game/{game_id}/move/{uci}")

    def resign(self, game_id: str) -> None:
        self._request("POST", f"/api/bot/game/{game_id}/resign")
