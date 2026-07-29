"""Client for the Squiggle API (api.squiggle.com.au) — free, no key required.

Squiggle asks callers to identify themselves with a descriptive User-Agent and
to stay at or under 1 request/second; this client self-throttles to that limit
rather than relying on the caller to space out requests.

Field names below follow Squiggle's documented response shape as of this
writing. This has NOT been exercised against the live API in this repo's CI
sandbox (outbound access to api.squiggle.com.au is blocked by the sandbox's
egress policy) — verify against a live pull before trusting it in production.
"""
from __future__ import annotations

import time

import httpx

from moneyball.config.settings import get_settings

SQUIGGLE_BASE_URL = "https://api.squiggle.com.au/"


class SquiggleClient:
    def __init__(self, user_agent: str | None = None, min_interval_s: float = 1.0, timeout_s: float = 15.0):
        self._user_agent = user_agent or get_settings().squiggle_user_agent
        self._min_interval_s = min_interval_s
        self._last_request_at: float | None = None
        self._client = httpx.Client(base_url=SQUIGGLE_BASE_URL, timeout=timeout_s)

    def _throttle(self) -> None:
        if self._last_request_at is None:
            return
        elapsed = time.monotonic() - self._last_request_at
        remaining = self._min_interval_s - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def _get(self, **params) -> dict:
        self._throttle()
        resp = self._client.get("", params=params, headers={"User-Agent": self._user_agent})
        self._last_request_at = time.monotonic()
        resp.raise_for_status()
        return resp.json()

    def get_teams(self) -> list[dict]:
        return self._get(q="teams").get("teams", [])

    def get_games(self, year: int, round_: int | None = None) -> list[dict]:
        params: dict = {"q": "games", "year": year}
        if round_ is not None:
            params["round"] = round_
        return self._get(**params).get("games", [])

    def get_tips(self, year: int, round_: int | None = None, source: int | None = None) -> list[dict]:
        """Squiggle's own model tips/probabilities — used as a sanity anchor in
        the AFL model (Phase 3), never copied as our own prediction."""
        params: dict = {"q": "tips", "year": year}
        if round_ is not None:
            params["round"] = round_
        if source is not None:
            params["source"] = source
        return self._get(**params).get("tips", [])

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "SquiggleClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
