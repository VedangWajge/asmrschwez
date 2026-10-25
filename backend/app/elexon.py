"""
Elexon BMRS data fetching and day-ahead forecast selection.

Endpoints used:
  FUELHH  - half-hourly actual generation by fuel type
  WINDFOR - national wind generation forecasts (multiple runs per day)

Base URL: https://data.elexon.co.uk/bmrs/api/v1
"""

from datetime import date, datetime, time, timedelta, timezone
from typing import Any

import httpx

BASE_URL = "https://data.elexon.co.uk/bmrs/api/v1"

# Target delivery period: January 2026
JAN_START = date(2026, 1, 1)
JAN_END = date(2026, 1, 31)

# Publication window: day-ahead purchasing for Jan 1 delivery happens on Dec 31
FORECAST_PUB_START = date(2025, 12, 31)
FORECAST_PUB_END = date(2026, 1, 31)

# Assumed default day-ahead gate closure (midday D-1 in UTC / UK time)
DEFAULT_CUTOFF_HOUR = 12
DEFAULT_CUTOFF_TIME = time(DEFAULT_CUTOFF_HOUR, 0)


def _parse_utc(value: str) -> datetime:
    """Parse an ISO-8601 UTC timestamp from the API."""
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError(f"Timestamp has no timezone info: {value!r}")
    return dt.astimezone(timezone.utc)


async def _get(client: httpx.AsyncClient, path: str, params: dict[str, Any]) -> list[dict]:
    response = await client.get(path, params=params)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON array from {path}, got {type(data).__name__}")
    return data


async def fetch_wind_actuals(
    client: httpx.AsyncClient,
    date_from: date = JAN_START,
    date_to: date = JAN_END,
) -> list[dict]:
    """
    Fetch half-hourly wind actuals from FUELHH for the given date range.

    The API accepts settlementDateFrom / settlementDateTo and a fuelType filter.
    Returns a list of dicts with keys: start_time, generation_mw.
    """
    raw = await _get(
        client,
        f"{BASE_URL}/datasets/FUELHH/stream",
        {
            "settlementDateFrom": date_from.isoformat(),
            "settlementDateTo": date_to.isoformat(),
            "fuelType": "WIND",
        },
    )

    records = []
    for row in raw:
        fuel = row.get("fuelType", "")
        if fuel.upper() != "WIND":
            continue
        start_raw = row.get("startTime")
        generation = row.get("generation")
        if start_raw is None or generation is None:
            continue
        records.append(
            {
                "start_time": _parse_utc(start_raw).isoformat(),
                "generation_mw": int(generation),
            }
        )

    return sorted(records, key=lambda r: r["start_time"])


async def _fetch_forecasts_for_window(
    client: httpx.AsyncClient,
    publish_from: datetime,
    publish_to: datetime,
) -> list[dict]:
    """Fetch all WINDFOR records published within a datetime window."""
    raw = await _get(
        client,
        f"{BASE_URL}/datasets/WINDFOR/stream",
        {
            "publishDateTimeFrom": publish_from.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "publishDateTimeTo": publish_to.strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    )

    records = []
    for row in raw:
        publish_raw = row.get("publishTime")
        start_raw = row.get("startTime")
        generation = row.get("generation")
        if publish_raw is None or start_raw is None or generation is None:
            continue
        records.append(
            {
                "publish_time": _parse_utc(publish_raw).isoformat(),
                "start_time": _parse_utc(start_raw).isoformat(),
                "generation_mw": int(generation),
            }
        )

    return records


async def fetch_wind_forecasts(
    client: httpx.AsyncClient,
    publish_date_from: date = FORECAST_PUB_START,
    publish_date_to: date = FORECAST_PUB_END,
) -> list[dict]:
    """
    Fetch all WINDFOR records published during the given date range.

    WINDFOR is scoped by publishDateTime. All forecast runs are preserved so
    the caller can evaluate forecasts available at any decision cutoff.
    """
    publish_from = datetime(
        publish_date_from.year, publish_date_from.month, publish_date_from.day, tzinfo=timezone.utc
    )
    publish_to = datetime(
        publish_date_to.year, publish_date_to.month, publish_date_to.day, tzinfo=timezone.utc
    ) + timedelta(days=1)

    records = await _fetch_forecasts_for_window(client, publish_from, publish_to)
    return sorted(records, key=lambda r: (r["publish_time"], r["start_time"]))


def get_day_ahead_cutoff(target_time: datetime, cutoff_time: time = DEFAULT_CUTOFF_TIME) -> datetime:
    """Return the decision cutoff timestamp on D-1 for the target delivery time."""
    delivery_date = target_time.date()
    decision_date = delivery_date - timedelta(days=1)
    return datetime.combine(decision_date, cutoff_time, tzinfo=timezone.utc)


def select_day_ahead_forecasts(
    forecasts: list[dict],
    delivery_date_from: date = JAN_START,
    delivery_date_to: date = JAN_END,
    cutoff_time: time = DEFAULT_CUTOFF_TIME,
) -> dict[str, dict]:
    """
    Select the latest forecast published before the D-1 cutoff for each delivery period.

    Forecasts targeting periods outside [delivery_date_from, delivery_date_to]
    (e.g., February deliveries) or published after the D-1 cutoff are excluded.
    Returns a dict keyed by target start_time ISO string.
    """
    delivery_start = datetime(
        delivery_date_from.year, delivery_date_from.month, delivery_date_from.day, tzinfo=timezone.utc
    )
    delivery_end = datetime(
        delivery_date_to.year, delivery_date_to.month, delivery_date_to.day, tzinfo=timezone.utc
    ) + timedelta(days=1)

    selected: dict[str, dict] = {}
    for row in forecasts:
        target_dt = _parse_utc(row["start_time"])
        if target_dt < delivery_start or target_dt >= delivery_end:
            continue

        pub_dt = _parse_utc(row["publish_time"])
        cutoff_dt = get_day_ahead_cutoff(target_dt, cutoff_time)
        if pub_dt > cutoff_dt:
            continue

        start_key = row["start_time"]
        current = selected.get(start_key)
        if current is None or pub_dt > _parse_utc(current["publish_time"]):
            selected[start_key] = {
                "start_time": start_key,
                "generation_mw": row["generation_mw"],
                "publish_time": row["publish_time"],
                "cutoff_time": cutoff_dt.isoformat(),
            }

    return selected


def match_delivery_data(
    actuals: list[dict],
    forecasts: list[dict],
    delivery_date_from: date = JAN_START,
    delivery_date_to: date = JAN_END,
    cutoff_time: time = DEFAULT_CUTOFF_TIME,
) -> list[dict]:
    """
    Match actual generation and selected day-ahead forecasts by target startTime.

    Missing actuals or forecasts are set to None without fabrication.
    """
    delivery_start = datetime(
        delivery_date_from.year, delivery_date_from.month, delivery_date_from.day, tzinfo=timezone.utc
    )
    delivery_end = datetime(
        delivery_date_to.year, delivery_date_to.month, delivery_date_to.day, tzinfo=timezone.utc
    ) + timedelta(days=1)

    selected_forecasts = select_day_ahead_forecasts(
        forecasts, delivery_date_from, delivery_date_to, cutoff_time
    )

    actuals_map: dict[str, int] = {}
    for row in actuals:
        target_dt = _parse_utc(row["start_time"])
        if delivery_start <= target_dt < delivery_end:
            actuals_map[row["start_time"]] = row["generation_mw"]

    records = []
    current = delivery_start
    while current < delivery_end:
        start_iso = current.isoformat()
        cutoff_iso = get_day_ahead_cutoff(current, cutoff_time).isoformat()
        act_val = actuals_map.get(start_iso)
        fc = selected_forecasts.get(start_iso)
        fc_val = fc["generation_mw"] if fc else None
        err_val = (fc_val - act_val) if (fc_val is not None and act_val is not None) else None

        records.append(
            {
                "start_time": start_iso,
                "actual_mw": act_val,
                "forecast_mw": fc_val,
                "error_mw": err_val,
                "forecast_publish_time": fc["publish_time"] if fc else None,
                "cutoff_time": cutoff_iso,
            }
        )
        current += timedelta(minutes=30)

    return records


def calculate_accuracy_metrics(records: list[dict]) -> dict:
    """
    Calculate forecast accuracy metrics on matched actual/forecast periods.

    Missing values are never treated as zero and are excluded from error calculations.
    Energy (MWh) is computed as generation (MW) * 0.5 hours per 30-minute settlement period.
    """
    matched = [
        (r["actual_mw"], r["forecast_mw"])
        for r in records
        if r.get("actual_mw") is not None and r.get("forecast_mw") is not None
    ]

    actual_values = [r["actual_mw"] for r in records if r.get("actual_mw") is not None]
    forecast_values = [r["forecast_mw"] for r in records if r.get("forecast_mw") is not None]

    actual_energy_mwh = round(sum(v * 0.5 for v in actual_values), 1) if actual_values else None
    forecast_energy_mwh = round(sum(v * 0.5 for v in forecast_values), 1) if forecast_values else None
    actual_avg_mw = round(sum(actual_values) / len(actual_values), 1) if actual_values else None
    forecast_avg_mw = round(sum(forecast_values) / len(forecast_values), 1) if forecast_values else None

    if not matched:
        return {
            "matched_periods": 0,
            "total_periods": len(records),
            "mae_mw": None,
            "rmse_mw": None,
            "bias_mw": None,
            "actual_energy_mwh": actual_energy_mwh,
            "forecast_energy_mwh": forecast_energy_mwh,
            "actual_avg_mw": actual_avg_mw,
            "forecast_avg_mw": forecast_avg_mw,
        }

    n = len(matched)
    errors = [fc - act for act, fc in matched]
    abs_errors = [abs(e) for e in errors]
    sq_errors = [e**2 for e in errors]

    mae = round(sum(abs_errors) / n, 1)
    rmse = round((sum(sq_errors) / n) ** 0.5, 1)
    bias = round(sum(errors) / n, 1)

    return {
        "matched_periods": n,
        "total_periods": len(records),
        "mae_mw": mae,
        "rmse_mw": rmse,
        "bias_mw": bias,
        "actual_energy_mwh": actual_energy_mwh,
        "forecast_energy_mwh": forecast_energy_mwh,
        "actual_avg_mw": actual_avg_mw,
        "forecast_avg_mw": forecast_avg_mw,
    }
