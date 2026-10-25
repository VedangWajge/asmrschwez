import os
from contextlib import asynccontextmanager
from datetime import date, time, timedelta

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.elexon import (
    DEFAULT_CUTOFF_HOUR,
    FORECAST_PUB_END,
    FORECAST_PUB_START,
    JAN_END,
    JAN_START,
    fetch_wind_actuals,
    fetch_wind_forecasts,
    match_delivery_data,
    calculate_accuracy_metrics,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Single shared client with a sensible timeout; reused across requests.
    app.state.http = httpx.AsyncClient(timeout=30.0)
    yield
    await app.state.http.aclose()


app = FastAPI(title="Wind Dashboard API", lifespan=lifespan)

_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/actuals")
async def actuals(
    date_from: date = Query(default=JAN_START, description="Start date (YYYY-MM-DD)"),
    date_to: date = Query(default=JAN_END, description="End date (YYYY-MM-DD)"),
):
    """
    Return half-hourly wind actual generation from Elexon FUELHH.

    Defaults to the full January 2026 range. Each record has:
      - start_time: ISO-8601 UTC
      - generation_mw: integer
    """
    if date_from > date_to:
        raise HTTPException(status_code=400, detail="date_from must be <= date_to")
    try:
        records = await fetch_wind_actuals(app.state.http, date_from, date_to)
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Elexon API error: {e.response.status_code}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {"count": len(records), "records": records}


@app.get("/api/forecasts")
async def forecasts(
    publish_date_from: date = Query(default=FORECAST_PUB_START, description="Fetch forecasts published from this date"),
    publish_date_to: date = Query(default=FORECAST_PUB_END, description="Fetch forecasts published up to this date"),
):
    """
    Return all WINDFOR forecast records published within the given date range.

    All forecast runs are preserved so the caller can evaluate forecasts
    available at any decision point in time.
    """
    if publish_date_from > publish_date_to:
        raise HTTPException(status_code=400, detail="publish_date_from must be <= publish_date_to")
    try:
        records = await fetch_wind_forecasts(app.state.http, publish_date_from, publish_date_to)
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Elexon API error: {e.response.status_code}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {"count": len(records), "records": records}


@app.get("/api/day-ahead")
async def day_ahead(
    date_from: date = Query(default=JAN_START, description="Delivery start date (YYYY-MM-DD)"),
    date_to: date = Query(default=JAN_END, description="Delivery end date (YYYY-MM-DD)"),
    cutoff_hour: int = Query(default=DEFAULT_CUTOFF_HOUR, ge=0, le=23, description="Cutoff hour on D-1 in UTC"),
):
    """
    Return delivery periods matched with actual generation and the day-ahead forecast
    available before the D-1 decision cutoff.
    """
    if date_from > date_to:
        raise HTTPException(status_code=400, detail="date_from must be <= date_to")

    cutoff_time = time(cutoff_hour, 0)
    pub_from = date_from - timedelta(days=1)
    try:
        actuals = await fetch_wind_actuals(app.state.http, date_from, date_to)
        forecasts = await fetch_wind_forecasts(app.state.http, pub_from, date_to)
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Elexon API error: {e.response.status_code}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

    records = match_delivery_data(actuals, forecasts, date_from, date_to, cutoff_time)
    metrics = calculate_accuracy_metrics(records)
    return {
        "delivery_from": date_from.isoformat(),
        "delivery_to": date_to.isoformat(),
        "cutoff_hour": cutoff_hour,
        "count": len(records),
        "metrics": metrics,
        "records": records,
    }
