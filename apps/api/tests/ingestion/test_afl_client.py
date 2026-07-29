import respx
from httpx import Response

from moneyball.ingestion.afl.client import SQUIGGLE_BASE_URL, SquiggleClient

TEAMS_PAYLOAD = {"teams": [{"id": 3, "name": "Carlton"}, {"id": 14, "name": "Richmond"}]}
GAMES_PAYLOAD = {
    "games": [
        {
            "id": 12345,
            "year": 2024,
            "round": 1,
            "hteam": "Carlton",
            "ateam": "Richmond",
            "hscore": 100,
            "ascore": 85,
            "venue": "M.C.G.",
            "date": "2024-03-14 19:20:00",
            "tz": "+11:00",
            "complete": 100,
        }
    ]
}
TIPS_PAYLOAD = {"tips": [{"gameid": 12345, "source": 1, "tip": "Carlton", "confidence": 65.2}]}


@respx.mock
def test_get_teams_parses_response():
    respx.get(SQUIGGLE_BASE_URL, params={"q": "teams"}).mock(return_value=Response(200, json=TEAMS_PAYLOAD))
    client = SquiggleClient(user_agent="test-agent", min_interval_s=0.0)
    teams = client.get_teams()
    client.close()
    assert teams == TEAMS_PAYLOAD["teams"]


@respx.mock
def test_get_games_passes_year_and_round():
    route = respx.get(SQUIGGLE_BASE_URL, params={"q": "games", "year": "2024", "round": "1"}).mock(
        return_value=Response(200, json=GAMES_PAYLOAD)
    )
    client = SquiggleClient(user_agent="test-agent", min_interval_s=0.0)
    games = client.get_games(year=2024, round_=1)
    client.close()
    assert route.called
    assert games == GAMES_PAYLOAD["games"]


@respx.mock
def test_get_tips_parses_response():
    respx.get(SQUIGGLE_BASE_URL, params={"q": "tips", "year": "2024"}).mock(return_value=Response(200, json=TIPS_PAYLOAD))
    client = SquiggleClient(user_agent="test-agent", min_interval_s=0.0)
    tips = client.get_tips(year=2024)
    client.close()
    assert tips == TIPS_PAYLOAD["tips"]


@respx.mock
def test_requests_carry_configured_user_agent():
    route = respx.get(SQUIGGLE_BASE_URL, params={"q": "teams"}).mock(return_value=Response(200, json=TEAMS_PAYLOAD))
    client = SquiggleClient(user_agent="moneyball-test (contact: test@example.com)", min_interval_s=0.0)
    client.get_teams()
    client.close()
    sent_request = route.calls.last.request
    assert sent_request.headers["User-Agent"] == "moneyball-test (contact: test@example.com)"


@respx.mock
def test_client_throttles_between_requests(monkeypatch):
    respx.get(SQUIGGLE_BASE_URL, params={"q": "teams"}).mock(return_value=Response(200, json=TEAMS_PAYLOAD))

    sleeps: list[float] = []
    monkeypatch.setattr("moneyball.ingestion.afl.client.time.sleep", lambda s: sleeps.append(s))

    clock = iter([100.0, 100.2, 100.2])  # first call ts, throttle check, post-request ts
    monkeypatch.setattr("moneyball.ingestion.afl.client.time.monotonic", lambda: next(clock))

    client = SquiggleClient(user_agent="test-agent", min_interval_s=1.0)
    client.get_teams()
    client.get_teams()
    client.close()

    assert sleeps, "second request within the throttle window should have slept"
    assert round(sleeps[0], 6) == 0.8
