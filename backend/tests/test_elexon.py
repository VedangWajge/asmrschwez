"""
Tests for the Elexon data module, day-ahead forecast selection, and FastAPI routes.

HTTP calls are mocked using httpx.MockTransport — no external mocking dependencies.
"""

from datetime import date, time

import pytest
from httpx import ASGITransport, AsyncClient, MockTransport, Request, Response

from app.elexon import (
    JAN_START,
    _parse_utc,
    calculate_accuracy_metrics,
    fetch_wind_actuals,
    fetch_wind_forecasts,
    get_day_ahead_cutoff,
    match_delivery_data,
    select_day_ahead_forecasts,
)

FUELHH_BASE = "https://data.elexon.co.uk/bmrs/api/v1/datasets/FUELHH/stream"
WINDFOR_BASE = "https://data.elexon.co.uk/bmrs/api/v1/datasets/WINDFOR/stream"


def mock_client(url_prefix: str, response: Response) -> AsyncClient:
    def handler(request: Request) -> Response:
        if str(request.url).startswith(url_prefix):
            return response
        raise ValueError(f"Unexpected request: {request.url}")

    return AsyncClient(transport=MockTransport(handler))


# ---------------------------------------------------------------------------
# Timestamp parsing
# ---------------------------------------------------------------------------


def test_parse_utc_with_z_suffix():
    dt = _parse_utc("2026-01-15T12:30:00Z")
    assert dt.isoformat() == "2026-01-15T12:30:00+00:00"


def test_parse_utc_with_offset():
    dt = _parse_utc("2026-01-15T12:30:00+00:00")
    assert dt.isoformat() == "2026-01-15T12:30:00+00:00"


def test_parse_utc_rejects_naive():
    with pytest.raises(ValueError):
        _parse_utc("2026-01-15T12:30:00")


# ---------------------------------------------------------------------------
# Wind actuals (FUELHH)
# ---------------------------------------------------------------------------

FUELHH_SAMPLE = [
    {
        "dataset": "FUELHH",
        "publishTime": "2026-01-01T00:30:00Z",
        "startTime": "2026-01-01T00:00:00Z",
        "settlementDate": "2026-01-01",
        "settlementPeriod": 1,
        "fuelType": "WIND",
        "generation": 13756,
    },
    {
        "dataset": "FUELHH",
        "publishTime": "2026-01-01T01:00:00Z",
        "startTime": "2026-01-01T00:30:00Z",
        "settlementDate": "2026-01-01",
        "settlementPeriod": 2,
        "fuelType": "SOLAR",
        "generation": 0,
    },
    {
        "dataset": "FUELHH",
        "publishTime": "2026-01-01T01:00:00Z",
        "startTime": "2026-01-01T00:30:00Z",
        "settlementDate": "2026-01-01",
        "settlementPeriod": 2,
        "fuelType": "WIND",
        "generation": 13873,
    },
]


@pytest.mark.asyncio
async def test_fetch_wind_actuals_filters_to_wind_only():
    client = mock_client(FUELHH_BASE, Response(200, json=FUELHH_SAMPLE))
    async with client:
        records = await fetch_wind_actuals(client)

    assert len(records) == 2
    assert all(r["generation_mw"] > 0 for r in records)


@pytest.mark.asyncio
async def test_fetch_wind_actuals_sorted_by_start_time():
    out_of_order = [FUELHH_SAMPLE[2], FUELHH_SAMPLE[0]]
    client = mock_client(FUELHH_BASE, Response(200, json=out_of_order))
    async with client:
        records = await fetch_wind_actuals(client)

    times = [r["start_time"] for r in records]
    assert times == sorted(times)


@pytest.mark.asyncio
async def test_fetch_wind_actuals_skips_missing_fields():
    bad = [{"dataset": "FUELHH", "fuelType": "WIND"}]
    client = mock_client(FUELHH_BASE, Response(200, json=bad))
    async with client:
        records = await fetch_wind_actuals(client)

    assert records == []


@pytest.mark.asyncio
async def test_fetch_wind_actuals_malformed_response_object():
    client = mock_client(FUELHH_BASE, Response(200, json={"error": "Not a list"}))
    async with client:
        with pytest.raises(ValueError, match="Expected a JSON array"):
            await fetch_wind_actuals(client)


@pytest.mark.asyncio
async def test_fetch_wind_actuals_invalid_json():
    client = mock_client(FUELHH_BASE, Response(200, text="not valid json {"))
    async with client:
        with pytest.raises(Exception):
            await fetch_wind_actuals(client)


@pytest.mark.asyncio
async def test_fetch_wind_actuals_raises_on_upstream_error():
    client = mock_client(FUELHH_BASE, Response(503, text="Service Unavailable"))
    async with client:
        with pytest.raises(Exception):
            await fetch_wind_actuals(client)


# ---------------------------------------------------------------------------
# Wind forecasts (WINDFOR)
# ---------------------------------------------------------------------------

WINDFOR_SAMPLE = [
    {
        "dataset": "WINDFOR",
        "publishTime": "2026-01-01T02:30:00Z",
        "startTime": "2026-01-02T06:00:00Z",
        "generation": 18000,
    },
    {
        "dataset": "WINDFOR",
        "publishTime": "2026-01-01T04:30:00Z",
        "startTime": "2026-01-02T06:00:00Z",
        "generation": 18500,
    },
]


@pytest.mark.asyncio
async def test_fetch_wind_forecasts_preserves_all_publish_times():
    """Both forecast runs for the same target start_time must be preserved."""
    client = mock_client(WINDFOR_BASE, Response(200, json=WINDFOR_SAMPLE))
    async with client:
        records = await fetch_wind_forecasts(client, JAN_START, JAN_START)

    assert len(records) == 2
    publish_times = {r["publish_time"] for r in records}
    assert "2026-01-01T02:30:00+00:00" in publish_times
    assert "2026-01-01T04:30:00+00:00" in publish_times


@pytest.mark.asyncio
async def test_fetch_wind_forecasts_sorted():
    reversed_sample = list(reversed(WINDFOR_SAMPLE))
    client = mock_client(WINDFOR_BASE, Response(200, json=reversed_sample))
    async with client:
        records = await fetch_wind_forecasts(client, JAN_START, JAN_START)

    keys = [(r["publish_time"], r["start_time"]) for r in records]
    assert keys == sorted(keys)


@pytest.mark.asyncio
async def test_fetch_wind_forecasts_skips_missing_fields():
    bad = [{"dataset": "WINDFOR", "publishTime": "2026-01-01T02:30:00Z"}]
    client = mock_client(WINDFOR_BASE, Response(200, json=bad))
    async with client:
        records = await fetch_wind_forecasts(client, JAN_START, JAN_START)

    assert records == []


@pytest.mark.asyncio
async def test_fetch_wind_forecasts_malformed_response_object():
    client = mock_client(WINDFOR_BASE, Response(200, json={"error": "Not a list"}))
    async with client:
        with pytest.raises(ValueError, match="Expected a JSON array"):
            await fetch_wind_forecasts(client, JAN_START, JAN_START)


@pytest.mark.asyncio
async def test_fetch_wind_forecasts_raises_on_upstream_error():
    client = mock_client(WINDFOR_BASE, Response(500, text="Internal Server Error"))
    async with client:
        with pytest.raises(Exception):
            await fetch_wind_forecasts(client, JAN_START, JAN_START)


# ---------------------------------------------------------------------------
# Day-ahead selection and delivery matching
# ---------------------------------------------------------------------------


def test_forecast_published_dec_31_selected_for_jan_1():
    """A forecast published on Dec 31 before the cutoff is selected for Jan 1 delivery."""
    forecasts = [
        {
            "publish_time": "2025-12-31T11:30:00+00:00",
            "start_time": "2026-01-01T00:00:00+00:00",
            "generation_mw": 14000,
        }
    ]
    selected = select_day_ahead_forecasts(
        forecasts,
        delivery_date_from=date(2026, 1, 1),
        delivery_date_to=date(2026, 1, 1),
        cutoff_time=time(12, 0),
    )
    assert "2026-01-01T00:00:00+00:00" in selected
    assert selected["2026-01-01T00:00:00+00:00"]["generation_mw"] == 14000
    assert selected["2026-01-01T00:00:00+00:00"]["publish_time"] == "2025-12-31T11:30:00+00:00"


def test_forecast_published_after_cutoff_not_selected():
    """Forecasts published after the D-1 cutoff cannot be selected for that decision."""
    forecasts = [
        {
            "publish_time": "2025-12-31T11:30:00+00:00",  # before 12:00 cutoff
            "start_time": "2026-01-01T00:00:00+00:00",
            "generation_mw": 14000,
        },
        {
            "publish_time": "2025-12-31T15:30:00+00:00",  # after 12:00 cutoff
            "start_time": "2026-01-01T00:00:00+00:00",
            "generation_mw": 16000,
        },
    ]
    selected = select_day_ahead_forecasts(
        forecasts,
        delivery_date_from=date(2026, 1, 1),
        delivery_date_to=date(2026, 1, 1),
        cutoff_time=time(12, 0),
    )
    # The 11:30 run was before cutoff; the 15:30 run must NOT be chosen even though it is newer
    assert selected["2026-01-01T00:00:00+00:00"]["generation_mw"] == 14000
    assert selected["2026-01-01T00:00:00+00:00"]["publish_time"] == "2025-12-31T11:30:00+00:00"


def test_forecast_only_after_cutoff_yields_no_selection():
    """If all forecasts for a delivery period were published after the cutoff, none is selected."""
    forecasts = [
        {
            "publish_time": "2025-12-31T13:00:00+00:00",
            "start_time": "2026-01-01T00:00:00+00:00",
            "generation_mw": 15000,
        }
    ]
    selected = select_day_ahead_forecasts(
        forecasts,
        delivery_date_from=date(2026, 1, 1),
        delivery_date_to=date(2026, 1, 1),
        cutoff_time=time(12, 0),
    )
    assert "2026-01-01T00:00:00+00:00" not in selected


def test_forecasts_targeting_february_excluded_from_january_delivery():
    """Forecasts published in January that target February delivery must be excluded."""
    forecasts = [
        {
            "publish_time": "2026-01-30T10:00:00+00:00",
            "start_time": "2026-01-31T23:30:00+00:00",  # January delivery
            "generation_mw": 12000,
        },
        {
            "publish_time": "2026-01-31T10:00:00+00:00",
            "start_time": "2026-02-01T00:00:00+00:00",  # February delivery
            "generation_mw": 13000,
        },
    ]
    selected = select_day_ahead_forecasts(
        forecasts,
        delivery_date_from=date(2026, 1, 1),
        delivery_date_to=date(2026, 1, 31),
    )
    assert "2026-01-31T23:30:00+00:00" in selected
    assert "2026-02-01T00:00:00+00:00" not in selected


def test_january_delivery_matched_to_actuals_by_target_time():
    """Matching aligns actuals and forecasts by target startTime, not publishTime."""
    actuals = [
        {"start_time": "2026-01-01T00:00:00+00:00", "generation_mw": 12500},
    ]
    forecasts = [
        {
            "publish_time": "2025-12-31T11:30:00+00:00",
            "start_time": "2026-01-01T00:00:00+00:00",
            "generation_mw": 12000,
        }
    ]
    records = match_delivery_data(
        actuals,
        forecasts,
        delivery_date_from=date(2026, 1, 1),
        delivery_date_to=date(2026, 1, 1),
    )
    target_rec = next(r for r in records if r["start_time"] == "2026-01-01T00:00:00+00:00")
    assert target_rec["actual_mw"] == 12500
    assert target_rec["forecast_mw"] == 12000
    assert target_rec["forecast_publish_time"] == "2025-12-31T11:30:00+00:00"


def test_missing_forecast_and_actual_handled_without_fabricated_values():
    """Missing actuals and missing forecasts remain None without fabricated values."""
    actuals = [
        {"start_time": "2026-01-01T00:00:00+00:00", "generation_mw": 10000},
    ]
    forecasts = [
        {
            "publish_time": "2025-12-31T11:30:00+00:00",
            "start_time": "2026-01-01T00:30:00+00:00",
            "generation_mw": 11000,
        }
    ]
    records = match_delivery_data(
        actuals,
        forecasts,
        delivery_date_from=date(2026, 1, 1),
        delivery_date_to=date(2026, 1, 1),
    )
    rec_00 = next(r for r in records if r["start_time"] == "2026-01-01T00:00:00+00:00")
    assert rec_00["actual_mw"] == 10000
    assert rec_00["forecast_mw"] is None
    assert rec_00["forecast_publish_time"] is None

    rec_30 = next(r for r in records if r["start_time"] == "2026-01-01T00:30:00+00:00")
    assert rec_30["actual_mw"] is None
    assert rec_30["forecast_mw"] == 11000
    assert rec_30["forecast_publish_time"] == "2025-12-31T11:30:00+00:00"

    rec_other = next(r for r in records if r["start_time"] == "2026-01-01T01:00:00+00:00")
    assert rec_other["actual_mw"] is None
    assert rec_other["forecast_mw"] is None


# ---------------------------------------------------------------------------
# FastAPI route tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_route():
    from app.main import app

    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r = await ac.get("/health")

    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_actuals_route_returns_count():
    from app.main import app

    app.state.http = mock_client(FUELHH_BASE, Response(200, json=FUELHH_SAMPLE))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/api/actuals?date_from=2026-01-01&date_to=2026-01-01")
    await app.state.http.aclose()

    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 2
    assert len(body["records"]) == 2


@pytest.mark.asyncio
async def test_actuals_route_bad_date_range():
    from app.main import app

    app.state.http = mock_client("http", Response(200, json=[]))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/api/actuals?date_from=2026-01-31&date_to=2026-01-01")
    await app.state.http.aclose()

    assert r.status_code == 400


@pytest.mark.asyncio
async def test_actuals_route_upstream_error_returns_502():
    from app.main import app

    app.state.http = mock_client(FUELHH_BASE, Response(503, text="down"))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/api/actuals?date_from=2026-01-01&date_to=2026-01-01")
    await app.state.http.aclose()

    assert r.status_code == 502


@pytest.mark.asyncio
async def test_forecasts_route_preserves_history():
    from app.main import app

    app.state.http = mock_client(WINDFOR_BASE, Response(200, json=WINDFOR_SAMPLE))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/api/forecasts?publish_date_from=2026-01-01&publish_date_to=2026-01-01")
    await app.state.http.aclose()

    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 2


@pytest.mark.asyncio
async def test_forecasts_route_bad_date_range():
    from app.main import app

    app.state.http = mock_client("http", Response(200, json=[]))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/api/forecasts?publish_date_from=2026-01-31&publish_date_to=2026-01-01")
    await app.state.http.aclose()

    assert r.status_code == 400


@pytest.mark.asyncio
async def test_forecasts_route_upstream_error_returns_502():
    from app.main import app

    app.state.http = mock_client(WINDFOR_BASE, Response(502, text="bad gateway"))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/api/forecasts?publish_date_from=2026-01-01&publish_date_to=2026-01-01")
    await app.state.http.aclose()

    assert r.status_code == 502


@pytest.mark.asyncio
async def test_day_ahead_route():
    from app.main import app

    def handler(request: Request) -> Response:
        url = str(request.url)
        if "FUELHH" in url:
            return Response(200, json=FUELHH_SAMPLE)
        if "WINDFOR" in url:
            return Response(200, json=WINDFOR_SAMPLE)
        raise ValueError(f"Unexpected request: {url}")

    app.state.http = AsyncClient(transport=MockTransport(handler))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/api/day-ahead?date_from=2026-01-01&date_to=2026-01-01&cutoff_hour=12")
    await app.state.http.aclose()

    assert r.status_code == 200
    data = r.json()
    assert data["delivery_from"] == "2026-01-01"
    assert data["delivery_to"] == "2026-01-01"
    assert data["cutoff_hour"] == 12
    assert data["count"] == 48
    assert "metrics" in data
    assert "records" in data


def test_calculate_accuracy_metrics_basic():
    records = [
        {"actual_mw": 1000, "forecast_mw": 1100},  # error = +100
        {"actual_mw": 2000, "forecast_mw": 1900},  # error = -100
    ]
    m = calculate_accuracy_metrics(records)
    assert m["matched_periods"] == 2
    assert m["total_periods"] == 2
    assert m["mae_mw"] == 100.0
    assert m["rmse_mw"] == 100.0
    assert m["bias_mw"] == 0.0
    assert m["actual_energy_mwh"] == 1500.0  # (1000 + 2000) * 0.5
    assert m["forecast_energy_mwh"] == 1500.0  # (1100 + 1900) * 0.5


def test_calculate_accuracy_metrics_excludes_missing():
    records = [
        {"actual_mw": 1000, "forecast_mw": 1200},  # error = +200
        {"actual_mw": None, "forecast_mw": 1500},  # missing actual
        {"actual_mw": 1800, "forecast_mw": None},  # missing forecast
    ]
    m = calculate_accuracy_metrics(records)
    assert m["matched_periods"] == 1
    assert m["total_periods"] == 3
    assert m["mae_mw"] == 200.0
    assert m["rmse_mw"] == 200.0
    assert m["bias_mw"] == 200.0
    # Energy sums only available readings
    assert m["actual_energy_mwh"] == 1400.0  # (1000 + 1800) * 0.5
    assert m["forecast_energy_mwh"] == 1350.0  # (1200 + 1500) * 0.5


def test_calculate_accuracy_metrics_empty():
    records = [
        {"actual_mw": None, "forecast_mw": None},
    ]
    m = calculate_accuracy_metrics(records)
    assert m["matched_periods"] == 0
    assert m["total_periods"] == 1
    assert m["mae_mw"] is None
    assert m["rmse_mw"] is None
    assert m["bias_mw"] is None

